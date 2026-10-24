"""Mocked package/account preflight only; real image acceptance is separate."""

import stat
import subprocess
from types import SimpleNamespace

import pytest

from scripts import composition_database_runtime as runtime
from scripts.composition_database_data import DataDenied


@pytest.fixture
def installed(monkeypatch):
    monkeypatch.setattr(runtime.os, "geteuid", lambda: 10002)
    monkeypatch.setattr(runtime.os, "getegid", lambda: 10002)
    monkeypatch.setattr(runtime.pwd, "getpwuid", lambda uid: SimpleNamespace(
        pw_name="ciqdb", pw_gid=10002))
    monkeypatch.setattr(runtime.Path, "lstat", lambda path: SimpleNamespace(
        st_mode=stat.S_IFREG | 0o755, st_uid=0))
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(returncode=0, stdout=(
            f"{runtime.Path(argv[0]).name} (PostgreSQL) 16.13 (Debian package)\n"
        ).encode())

    monkeypatch.setattr(runtime.subprocess, "run", run)
    return calls


def test_closed_runtime_commands(installed):
    runtime.check()
    assert [call[0] for call in installed] == [
        [str(runtime.BIN / name), "--version"] for name in ("initdb", "postgres", "psql")]
    for _, options in installed:
        assert options["env"] == runtime.ENV
        assert options["timeout"] == 5 and options["close_fds"]
        assert options["stdin"] is subprocess.DEVNULL
        assert options["stderr"] is subprocess.DEVNULL


@pytest.mark.parametrize("fault", ["uid", "gid", "account", "owner", "writable", "symlink"])
def test_identity_denied_before_execution(installed, monkeypatch, fault):
    if fault in {"uid", "gid"}:
        monkeypatch.setattr(runtime.os, "gete" + fault, lambda: 0)
    elif fault == "account":
        monkeypatch.setattr(runtime.pwd, "getpwuid", lambda uid: SimpleNamespace(
            pw_name="postgres", pw_gid=10002))
    else:
        monkeypatch.setattr(runtime.Path, "lstat", lambda path: SimpleNamespace(
            st_uid=10002 if fault == "owner" else 0,
            st_mode=(stat.S_IFLNK if fault == "symlink" else stat.S_IFREG)
            | (0o777 if fault == "writable" else 0o755)))
    with pytest.raises(DataDenied):
        runtime.check()
    assert not installed


@pytest.mark.parametrize("output,code", [
    (b"initdb (PostgreSQL) 15.13\n", 0),
    (b"initdb (PostgreSQL) 16.13\nextra\n", 0),
    (b"initdb (PostgreSQL) 16.13\n", 1),
    (b"", 0),
])
def test_wrong_version_or_exit_denied(installed, monkeypatch, output, code):
    monkeypatch.setattr(runtime.subprocess, "run", lambda *a, **kw: SimpleNamespace(
        returncode=code, stdout=output))
    with pytest.raises(DataDenied):
        runtime.check()


def test_timeout_redacted(installed, monkeypatch, capsys):
    def timeout(*a, **kw):
        raise subprocess.TimeoutExpired("private diagnostic", 5)
    monkeypatch.setattr(runtime.subprocess, "run", timeout)
    monkeypatch.setattr(runtime.sys, "argv", ["runtime"])
    assert runtime.main() == 1
    assert capsys.readouterr().err == "Disposable PostgreSQL runtime denied\n"


def test_cluster_cli_checks_runtime_before_reading_request(monkeypatch, capsys):
    from scripts import composition_database_cluster as cluster

    monkeypatch.setattr(cluster.os, "geteuid", lambda: 10002)
    monkeypatch.setattr(cluster.os, "getegid", lambda: 10002)
    monkeypatch.setattr(cluster.sys, "argv", ["cluster", "initialize"])

    def denied():
        raise DataDenied()

    monkeypatch.setattr(cluster, "check_runtime", denied)
    # pytest's captured stdin raises if anything attempts to read it.
    assert cluster.main() == 1
    assert capsys.readouterr().err == "Disposable cluster denied; outcome unknown\n"
