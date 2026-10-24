"""Offline bootstrap contracts; subprocess fixtures never start PostgreSQL."""

import json
import signal
import socket
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import composition_database_bootstrap as bootstrap
from scripts import composition_database_cluster as cluster
from scripts.composition_database_data import DataDenied
from tests.test_composition_database_cluster import setup, simulated_init


def initialized(tmp_path):
    root, material, spec, owner = setup(tmp_path)
    cluster.initialize(root, material, spec, owner=owner, runner=lambda args: simulated_init(root))
    return root, material, spec, owner


def test_bootstrap_is_exclusive_and_bound(tmp_path):
    root, material, spec, owner = initialized(tmp_path)
    calls = []

    def runner(r, m, body):
        calls.append(body)
        assert r == root and m == material
        assert json.loads((r / "pgdata" / bootstrap.MARKER).read_bytes())["state"] == "ATTEMPTED"

    bootstrap.bootstrap(root, material, spec, owner=owner, runner=runner)
    assert calls == [(material / "bootstrap.sql").read_bytes()]
    bootstrap.verify(root, material, spec, owner=owner)
    with pytest.raises(FileExistsError):
        bootstrap.bootstrap(root, material, spec, owner=owner, runner=runner)
    assert len(calls) == 1


@pytest.mark.parametrize("fault", ["sql", "pid", "material"])
def test_failure_retained_and_not_verified(tmp_path, fault):
    root, material, spec, owner = initialized(tmp_path)

    def runner(*args):
        if fault == "sql":
            raise DataDenied()
        if fault == "pid":
            (root / "pgdata" / "postmaster.pid").write_text("fake")
        else:
            (material / "bootstrap.sql").chmod(0o600)

    with pytest.raises(ValueError):
        bootstrap.bootstrap(root, material, spec, owner=owner, runner=runner)
    assert json.loads((root / "pgdata" / bootstrap.MARKER).read_bytes())["state"] == "ATTEMPTED"
    with pytest.raises(ValueError):
        bootstrap.verify(root, material, spec, owner=owner)


def test_client_failure_no_retry_and_private_stdin(monkeypatch, tmp_path):
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(returncode=3)

    monkeypatch.setattr(bootstrap.subprocess, "run", run)
    with pytest.raises(DataDenied):
        bootstrap.sql(tmp_path, "synthetic", b"private SQL")
    assert len(calls) == 1
    argv, options = calls[0]
    assert "--set=ON_ERROR_STOP=1" in argv and "--no-psqlrc" in argv
    assert options["input"] == b"private SQL"
    assert all("private SQL" not in arg for arg in argv)
    assert options["stderr"] is subprocess.DEVNULL
    assert options["env"] == {**bootstrap.ENV, "PGCONNECT_TIMEOUT": "3"}


@pytest.mark.parametrize("fault", [None, "sql", "catalog", "startup", "shutdown"])
def test_owned_server_lifecycle(tmp_path, monkeypatch, fault):
    directory = tempfile.TemporaryDirectory(dir="/tmp", prefix="ciq-bs-")
    endpoint = Path(directory.name) / "socket"
    listener = socket.socket(socket.AF_UNIX)
    events = []

    class Child:
        pid = 424242
        returncode = None

        def poll(self):
            return self.returncode

        def send_signal(self, sig):
            events.append(("signal", sig))

        def wait(self, timeout):
            if fault == "shutdown" and timeout == 5:
                raise subprocess.TimeoutExpired("postgres", timeout)
            self.returncode = 0
            return 0

    child = Child()

    def popen(argv, **kwargs):
        assert "listen_addresses=" in argv and "ssl=off" in argv
        assert kwargs["start_new_session"] and kwargs["env"] == bootstrap.ENV
        if fault == "startup":
            child.returncode = 1
        else:
            listener.bind(str(endpoint / ".s.PGSQL.5432"))
        return child

    def sql(path, database, body):
        events.append(("sql", database, body))
        if fault == "sql" or (fault == "catalog" and body == bootstrap.CATALOG_SQL):
            raise DataDenied()

    monkeypatch.setattr(bootstrap.subprocess, "Popen", popen)
    monkeypatch.setattr(bootstrap, "sql", sql)
    monkeypatch.setattr(bootstrap, "wait_ready", lambda *args: None)
    monkeypatch.setattr(bootstrap.os, "killpg", lambda pid, sig: events.append(("kill", pid, sig)))
    try:
        if fault:
            with pytest.raises((DataDenied, subprocess.TimeoutExpired)):
                bootstrap.execute(tmp_path, tmp_path, b"secret body", socket=endpoint)
        else:
            bootstrap.execute(tmp_path, tmp_path, b"secret body", socket=endpoint)
            assert [e[1] for e in events if e[0] == "sql"] == ["postgres", "synthetic", "synthetic"]
            assert [e[2] for e in events if e[0] == "sql"][-1] == bootstrap.CATALOG_SQL
            assert ("signal", signal.SIGINT) in events
        if fault == "sql":
            assert len([e for e in events if e[0] == "sql"]) == 1
            assert ("signal", signal.SIGINT) in events
        if fault == "catalog":
            assert len([e for e in events if e[0] == "sql"]) == 3
            assert ("signal", signal.SIGINT) in events
        if fault == "shutdown":
            assert ("kill", child.pid, signal.SIGKILL) in events
        assert endpoint.is_dir()  # No automatic removal on success or failure.
    finally:
        listener.close()
        directory.cleanup()


@pytest.mark.parametrize("codes,denied", [([2, 0], False), ([3], True), ([1], True)])
def test_only_connection_probe_retries(monkeypatch, tmp_path, codes, denied):
    outputs = iter(codes)
    bodies = []

    def run(*args, **kwargs):
        bodies.append(kwargs["input"])
        return SimpleNamespace(returncode=next(outputs))

    monkeypatch.setattr(bootstrap.subprocess, "run", run)
    monkeypatch.setattr(bootstrap.time, "monotonic", lambda: 0)
    monkeypatch.setattr(bootstrap.time, "sleep", lambda seconds: None)
    child = SimpleNamespace(poll=lambda: None)
    if denied:
        with pytest.raises(DataDenied):
            bootstrap.wait_ready(child, tmp_path, 5)
    else:
        bootstrap.wait_ready(child, tmp_path, 5)
    assert bodies == [b"SELECT 1;\n"] * len(codes)


def test_connection_probe_deadline_prevents_execution(monkeypatch, tmp_path):
    monkeypatch.setattr(bootstrap.time, "monotonic", lambda: 6)
    with pytest.raises(DataDenied):
        bootstrap.wait_ready(SimpleNamespace(poll=lambda: None), tmp_path, 5)


@pytest.mark.parametrize("fault", ["contents", "mode", "symlink"])
def test_completion_marker_cannot_be_replaced_or_weakened(tmp_path, fault):
    root, material, spec, owner = initialized(tmp_path)
    bootstrap.bootstrap(root, material, spec, owner=owner, runner=lambda *args: None)
    marker = root / "pgdata" / bootstrap.MARKER
    if fault == "contents":
        marker.write_bytes(b"{}")
    elif fault == "mode":
        marker.chmod(0o644)
    else:
        other = root / "pgdata" / "copied-marker"
        marker.rename(other)
        marker.symlink_to(other)
    with pytest.raises((DataDenied, OSError)):
        bootstrap.verify(root, material, spec, owner=owner)


def test_existing_socket_directory_prevents_process_launch(tmp_path):
    with pytest.raises(FileExistsError):
        bootstrap.execute(tmp_path, tmp_path, b"never executed", socket=tmp_path)


def test_cli_runtime_denial_before_stdin(monkeypatch, capsys):
    monkeypatch.setattr(bootstrap.sys, "argv", ["bootstrap", "bootstrap"])

    def denied():
        raise DataDenied()

    monkeypatch.setattr(bootstrap, "check_runtime", denied)
    assert bootstrap.main() == 1
    assert capsys.readouterr().err == "Disposable bootstrap denied; outcome unknown\n"
