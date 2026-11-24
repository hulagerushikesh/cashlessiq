"""Receipt process startup and lifetime faults, without a local service."""

from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest

from ciq_api import agent_receipt_runner as runner


@pytest.fixture
def values():
    return {"protocol": "ciq-fake-receipt-v1", "custody_uid": 10002,
            "epoch": {"database_id": str(uuid4()), "epoch_id": str(uuid4())}}


@pytest.mark.parametrize(("key", "value"), [
    ("protocol", "live"), ("custody_uid", 0), ("custody_uid", True),
    ("custody_uid", "10002"), ("custody_uid", 2**31), ("path", "/tmp/socket"),
    ("directory", "/tmp/journal"), ("database_url", "postgresql://owner"),
    ("provision", True), ("reset", True), ("retry", True),
    ("max_connections", 10000), ("timeout", 3600), ("command", "issue"),
])
def test_operator_plan_cannot_select_storage_authority_or_limits(values, key, value):
    with pytest.raises(ValueError):
        runner.ReceiptPlan.model_validate({**values, key: value})


def test_fixed_private_plan(values, monkeypatch):
    def read(path, maximum):
        assert path == runner.PLAN and maximum == 2048
        return values
    monkeypatch.setattr(runner, "private_object", read)
    assert runner.read_plan().custody_uid == 10002


@pytest.mark.parametrize("fault", [None, "file", "epoch", "bind", "output", "accept"])
def test_existing_journal_precedes_readiness_and_listener_always_closes(
    values, monkeypatch, capfd, fault,
):
    calls = []

    def step(name):
        calls.append(name)
        if name == fault:
            raise ValueError("PRIVATE-RECEIPT-DATA")

    def read(path, maximum):
        assert path == runner.JOURNAL / "fake-receipts.sqlite3" and maximum == 256 * 1024
        step("file")

    class Journal:
        def __init__(self, path, pin):
            assert path == runner.JOURNAL and pin == runner.ReceiptPlan.model_validate(values).epoch
            step("journal")

        @contextmanager
        def _connection(self):
            step("open")
            try:
                yield "existing-db"
            finally:
                calls.append("db_closed")

        def _identity(self, db):
            assert db == "existing-db"
            step("epoch")

    class Peer:
        def __init__(self, journal, *, custody_uid):
            assert type(journal) is Journal and custody_uid == 10002
            step("peer")

        @contextmanager
        def bind(self, path):
            assert path == runner.SOCKET
            step("bind")
            try:
                yield SimpleNamespace(settimeout=lambda n: calls.append(("timeout", n)))
            finally:
                calls.append("socket_closed")

        def serve_once(self, listener):
            step("accept")

    monkeypatch.setattr(runner.os, "getuid", lambda: 10003)
    monkeypatch.setattr(runner, "read_private", read)
    monkeypatch.setattr(runner, "FakeReceiptJournal", Journal)
    monkeypatch.setattr(runner, "FakeReceiptPeer", Peer)
    if fault == "output":
        def broken(*_):
            raise BrokenPipeError
        monkeypatch.setattr(runner.os, "write", broken)
    if fault:
        with pytest.raises((ValueError, BrokenPipeError)):
            runner.serve(runner.ReceiptPlan.model_validate(values))
    else:
        assert runner.serve(runner.ReceiptPlan.model_validate(values)) is None
    assert calls[0] == "file"
    if "open" in calls:
        assert "db_closed" in calls
    if "peer" in calls:
        assert calls.index("db_closed") < calls.index("peer")
    if ("timeout", 10) in calls:
        assert calls[-1] == "socket_closed"
    if fault is None:
        assert calls.count("accept") == 32
        assert capfd.readouterr().out == runner.READY.decode()
    elif fault in ("file", "epoch", "bind", "output"):
        assert "accept" not in calls and capfd.readouterr().out == ""


def test_same_uid_denied_before_retained_file_open(values, monkeypatch):
    monkeypatch.setattr(runner.os, "getuid", lambda: 10002)
    monkeypatch.setattr(runner, "read_private", lambda *_: pytest.fail("opened custody"))
    with pytest.raises(ValueError):
        runner.serve(runner.ReceiptPlan.model_validate(values))


@pytest.mark.parametrize("fault", [None, "guard", "plan", "serve"])
def test_lifetime_guard_and_fixed_failure_without_private_output(monkeypatch, capfd, fault):
    alarms, signals, calls = [], [], []

    def step(name):
        def call(*_):
            calls.append(name)
            if fault == name:
                raise ValueError("PRIVATE-RECEIPT-DATA")
        return call

    monkeypatch.setattr(runner.sys, "platform", "linux")
    monkeypatch.setattr(runner, "guard_process", step("guard"))
    monkeypatch.setattr(runner, "read_plan", step("plan"))
    monkeypatch.setattr(runner, "serve", step("serve"))
    monkeypatch.setattr(runner.resource, "setrlimit", lambda *_: calls.append("core_zero"))
    monkeypatch.setattr(runner.signal, "alarm", alarms.append)
    monkeypatch.setattr(runner.signal, "signal",
                        lambda sig, handler: signals.append((sig, handler)))
    assert runner.main() == (1 if fault else 0)
    output = capfd.readouterr()
    assert output.out == "" and output.err == (runner.ERROR.decode() if fault else "")
    if fault != "guard":
        assert calls.index("core_zero") < calls.index("plan")
        assert alarms == [60, 0]
        assert signals == [(runner.signal.SIGALRM, runner._alarm),
                           (runner.signal.SIGTERM, runner._alarm)]
    else:
        assert alarms == [0]
