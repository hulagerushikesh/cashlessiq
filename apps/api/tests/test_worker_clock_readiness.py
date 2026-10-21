"""Disposable guard/PKI: bad clock state must deny before socket bind."""

import sqlite3
from dataclasses import replace
from http.server import ThreadingHTTPServer
from unittest.mock import Mock

import pytest
from test_worker_transport import context
from test_worker_transport import pki as pki

from ciq_api.worker_authority import WorkerDenied
from ciq_api.worker_clock import SECOND, ClockHealth, ClockLimits, ClockSample, SqliteClockGuard
from ciq_api.worker_transport import (
    ClockCheckedPrivateSummaryServer,
    ClockCheckedSummaryServer,
    PrivateEndpoint,
)


@pytest.fixture
def ready_setup(tmp_path, pki):
    path = tmp_path / "clock.sqlite"
    initial = ClockSample(1000 * SECOND, 10 * SECOND, "test-boot")
    SqliteClockGuard.initialize_for_offline_test(
        path, authority="validator", generation="test-generation", initial=initial
    )
    sample = Mock(return_value=initial)
    health = Mock(return_value=ClockHealth(True, 1, initial.monotonic_ns))
    guard = SqliteClockGuard(
        path,
        authority="validator",
        generation="test-generation",
        sample=sample,
        health=health,
        limits=ClockLimits(100, SECOND, SECOND, 60 * SECOND),
    )
    callback = Mock(side_effect=AssertionError("No source work during startup"))
    config = dict(
        clock_guard=guard,
        context=context(pki, "validator", server=True),
        peers={pki[1]["reader"][2]: "reader:0:nonclinical"},
        validate=callback,
    )
    return path, initial, sample, health, callback, config


@pytest.mark.parametrize("private", [False, True])
@pytest.mark.parametrize(
    "failure",
    [
        "missing",
        "corrupt",
        "legacy",
        "version",
        "generation",
        "unsafe",
        "health",
        "rollback",
    ],
)
def test_bad_state_never_reaches_socket_bind(ready_setup, monkeypatch, private, failure):
    path, initial, sample, health, callback, config = ready_setup
    if failure == "missing":
        path.unlink()
    elif failure == "corrupt":
        path.write_bytes(b"corrupt test evidence")
    elif failure == "health":
        health.return_value = ClockHealth(False, 1, initial.monotonic_ns)
    elif failure == "rollback":
        sample.return_value = replace(initial, wall_ns=initial.wall_ns - 1)
    else:
        with sqlite3.connect(path) as db:
            db.execute(
                {
                    "legacy": "DROP TABLE clock_state",
                    "version": "UPDATE clock_state SET version=99",
                    "generation": "UPDATE clock_state SET generation='old'",
                    "unsafe": "UPDATE clock_state SET unsafe=1",
                }[failure]
            )
    before = path.read_bytes() if path.exists() else None
    bind = Mock(side_effect=AssertionError("Unsafe state reached socket bind"))
    monkeypatch.setattr(ThreadingHTTPServer, "server_bind", bind)
    server = ClockCheckedSummaryServer
    if private:
        server = ClockCheckedPrivateSummaryServer
        config["endpoint"] = PrivateEndpoint("10.20.30.40", 8443)
    with pytest.raises(WorkerDenied, match=r"^Worker access denied$"):
        server(**config)
    bind.assert_not_called()
    callback.assert_not_called()
    if failure in {"missing", "corrupt", "legacy", "version", "generation", "unsafe"}:
        assert (path.read_bytes() if path.exists() else None) == before
    else:
        with sqlite3.connect(path) as db:
            assert db.execute("SELECT unsafe FROM clock_state").fetchone() == (1,)


def test_healthy_check_precedes_real_loopback_bind_without_source_work(ready_setup, monkeypatch):
    _, _, sample, health, callback, config = ready_setup
    original = ThreadingHTTPServer.server_bind
    events = []
    sample.side_effect = lambda: (events.append("sample"), sample.return_value)[1]
    health.side_effect = lambda: (events.append("health"), health.return_value)[1]

    def bind(server):
        events.append("bind")
        return original(server)

    monkeypatch.setattr(ThreadingHTTPServer, "server_bind", bind)
    listener = ClockCheckedSummaryServer(**config)
    try:
        assert listener.server_address[0] == "127.0.0.1"
        assert listener.server_port > 0
        assert events == ["sample", "health", "bind"]
        callback.assert_not_called()
    finally:
        listener.server_close()


def test_legacy_replay_or_missing_guard_cannot_bypass_clock_gate(ready_setup, monkeypatch):
    *_, config = ready_setup
    bind = Mock()
    monkeypatch.setattr(ThreadingHTTPServer, "server_bind", bind)
    config["clock_guard"] = None
    with pytest.raises(WorkerDenied):
        ClockCheckedSummaryServer(**config)
    bind.assert_not_called()
