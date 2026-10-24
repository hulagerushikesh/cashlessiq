"""Filesystem/closed process contracts only, no real PostgreSQL acceptance."""

import json
import os
import subprocess
from types import SimpleNamespace

import pytest

from scripts import composition_database_cluster as cluster
from scripts import composition_database_data as data
from scripts import composition_volume as volume
from scripts.composition_material import MaterialDenied
from tests.test_composition_database_volume import parsed


def setup(tmp_path):
    _, _, spec, archive = parsed(tmp_path)
    material, root = tmp_path / "material", tmp_path / "data"
    material.mkdir(mode=0o700)
    root.mkdir(mode=0o700)
    owner = os.getuid(), os.getgid()
    volume.install(material, spec, archive, owner=owner)
    data.prepare(root, owner=owner)
    return root, material, spec, owner


def simulated_init(root):
    pgdata = root / "pgdata"
    (pgdata / "global").mkdir(mode=0o700)
    for path, body in (
        (pgdata / "PG_VERSION", b"16\n"),
        (pgdata / "global" / "pg_control", b"x" * 8192),
    ):
        path.write_bytes(body)
        path.chmod(0o600)


def test_initialize_once_and_separate_probe(tmp_path):
    root, material, spec, owner = setup(tmp_path)
    calls = []

    def runner(argv):
        calls.append(argv)
        assert json.loads((root / cluster.MARKER).read_bytes())["state"] == "ATTEMPTED"
        simulated_init(root)

    cluster.initialize(root, material, spec, owner=owner, runner=runner)
    assert calls == [cluster.command(root, material)]
    assert "--no-clean" in calls[0] and "--auth-host=reject" in calls[0]
    assert "--auth-local=reject" in calls[0] and "--data-checksums" in calls[0]
    cluster.verify(root, material, spec, owner=owner)
    with pytest.raises(data.DataDenied):
        cluster.initialize(root, material, spec, owner=owner, runner=runner)
    assert len(calls) == 1


@pytest.mark.parametrize("fault", ["error", "partial", "empty-success"])
def test_failed_initialization_is_retained_never_adopted(tmp_path, fault):
    root, material, spec, owner = setup(tmp_path)

    def runner(argv):
        if fault == "partial":
            (root / "pgdata" / "partial").write_text("retained")
        if fault != "empty-success":
            raise data.DataDenied()

    with pytest.raises((data.DataDenied, OSError)):
        cluster.initialize(root, material, spec, owner=owner, runner=runner)
    assert json.loads((root / cluster.MARKER).read_bytes())["state"] == "ATTEMPTED"
    with pytest.raises(data.DataDenied):
        cluster.initialize(root, material, spec, owner=owner, runner=runner)
    if fault == "partial":
        assert (root / "pgdata" / "partial").read_text() == "retained"


@pytest.mark.parametrize(
    "fault", ["version", "control", "pid", "marker", "binding", "symlink", "material"]
)
def test_probe_denies_incomplete_changed_or_running_cluster(tmp_path, fault):
    from dataclasses import replace

    root, material, spec, owner = setup(tmp_path)
    cluster.initialize(root, material, spec, owner=owner, runner=lambda _: simulated_init(root))
    if fault == "version":
        (root / "pgdata" / "PG_VERSION").write_bytes(b"15\n")
    elif fault == "control":
        (root / "pgdata" / "global" / "pg_control").write_bytes(b"short")
    elif fault == "pid":
        (root / "pgdata" / "postmaster.pid").touch()
    elif fault == "marker":
        (root / cluster.MARKER).write_bytes(cluster.record(spec, "ATTEMPTED"))
    elif fault == "binding":
        spec = replace(spec, fingerprint="f" * 64)
    elif fault == "symlink":
        (root / "pgdata" / "PG_VERSION").unlink()
        (root / "pgdata" / "PG_VERSION").symlink_to(material / "admin-password")
    else:
        (material / "admin-password").chmod(0o600)
    with pytest.raises((data.DataDenied, MaterialDenied, OSError)):
        cluster.verify(root, material, spec, owner=owner)


def test_invalid_material_prevents_attempt_and_subprocess(tmp_path):
    root, material, spec, owner = setup(tmp_path)
    (material / "server.key").chmod(0o600)
    with pytest.raises(MaterialDenied):
        cluster.initialize(root, material, spec, owner=owner, runner=lambda _: pytest.fail("spawn"))
    assert set(os.listdir(root)) == {"pgdata"}


@pytest.mark.parametrize("failure", [None, "exit", "timeout"])
def test_process_redaction_deadline_and_group_containment(monkeypatch, failure):
    calls, kills = [], []

    class Process:
        pid = 12345

        def wait(self, timeout):
            calls.append(timeout)
            if failure == "timeout" and timeout == 30:
                raise subprocess.TimeoutExpired("hidden", timeout)
            return 1 if failure == "exit" else 0

    def popen(argv, **kwargs):
        assert argv == (cluster.INITDB,)
        assert kwargs == dict(
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=cluster.ENV,
            close_fds=True,
            start_new_session=True,
        )
        return Process()

    monkeypatch.setattr(subprocess, "Popen", popen)
    monkeypatch.setattr(os, "killpg", lambda *args: kills.append(args))
    if failure:
        with pytest.raises(data.DataDenied):
            cluster.execute((cluster.INITDB,))
    else:
        cluster.execute((cluster.INITDB,))
    assert calls == ([30, 2] if failure == "timeout" else [30])
    assert bool(kills) is (failure == "timeout")


def test_cli_requires_nonroot_before_reading(monkeypatch, capsys):
    import sys

    monkeypatch.setattr(sys, "argv", ["cluster", "initialize"])
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=None))
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    assert cluster.main() == 1
    output = capsys.readouterr()
    assert not output.out and "outcome unknown" in output.err
