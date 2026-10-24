"""Host filesystem and simulated daemon checks, not Linux mount or PostgreSQL proof."""

import json
import os

import pytest
from test_composition_helpers import CHANGES, setup

from scripts import composition_database_data as data
from scripts.composition_helpers import HelpersDenied
from scripts.composition_journal import fold


def test_empty_data_claim_and_independent_probe(tmp_path):
    owner = os.getuid(), os.getgid()
    data.prepare(tmp_path, owner=owner)
    data.verify(tmp_path, owner=owner)
    with pytest.raises(data.DataDenied):
        data.prepare(tmp_path, owner=owner)
    (tmp_path / "pgdata" / "PG_VERSION").write_text("16")
    with pytest.raises(data.DataDenied):
        data.verify(tmp_path, owner=owner)
    assert (tmp_path / "pgdata" / "PG_VERSION").read_text() == "16"


@pytest.mark.parametrize("fault", ["root-link", "child-link", "mode", "extra", "owner"])
def test_data_probe_rejects_wrong_filesystem(tmp_path, fault):
    root = tmp_path / "volume"
    root.mkdir()
    owner = os.getuid(), os.getgid()
    data.prepare(root, owner=owner)
    if fault == "root-link":
        link = tmp_path / "alias"
        link.symlink_to(root)
        root = link
    elif fault == "child-link":
        (root / "pgdata").rmdir()
        (root / "pgdata").symlink_to(tmp_path)
    elif fault == "mode":
        (root / "pgdata").chmod(0o755)
    elif fault == "extra":
        (root / "unexpected").touch()
    else:
        owner = (owner[0] + 1, owner[1])
    with pytest.raises((data.DataDenied, OSError)):
        data.verify(root, owner=owner)


@pytest.mark.parametrize(
    "frame",
    [
        b"{}",
        b'{"version":1,"version":1}',
        b"x" * 4097,
        json.dumps(dict(version=True, role="database", fingerprint="a" * 64)).encode(),
        json.dumps(dict(version=1, role="broker", fingerprint="a" * 64)).encode(),
    ],
)
def test_request_rejects_ambiguous_or_wrong_contract(frame):
    with pytest.raises(data.DataDenied):
        data.parse(frame)


def test_data_helper_prepares_then_probes_readonly(tmp_path):
    helper, _engine, journal, resources = setup(tmp_path, database_data=True)
    try:
        assert data.parse(helper.body("prepare")) == helper.material_fingerprint()
        assert helper.run()
        assert helper.volume_name().endswith("-db-data")
        assert helper.create("verify")[helper.create("verify").index("--user") + 1] == "10002:10002"
        assert not helper.writable("verify")
        assert all(row[2] == "STOPPED" for row in fold(journal.events)[1].values())
        with pytest.raises(HelpersDenied):
            helper.run()
    finally:
        journal.close()
        resources.close()


@pytest.mark.parametrize(
    "fault",
    [
        *CHANGES,
        "unknown-create",
        "unknown-start",
        "receipt",
        "nonzero",
        "running",
        "collision",
        "duplicate-json",
    ],
)
def test_data_helper_uncertainty_fences(tmp_path, fault):
    helper, engine, journal, resources = setup(tmp_path, database_data=True, fault=fault)
    try:
        with pytest.raises(HelpersDenied):
            helper.run()
        assert engine.fenced and fold(journal.events)[2]
        assert not any(call[0] in {"rm", "exec", "run", "stop"} for call in engine.calls)
    finally:
        journal.close()
        resources.close()


def test_partial_prepare_is_retained_and_cannot_be_retried(tmp_path, monkeypatch):
    owner = os.getuid(), os.getgid()

    def fail(*args):
        raise OSError("simulated ownership failure")

    monkeypatch.setattr(os, "fchown", fail)
    with pytest.raises(OSError):
        data.prepare(tmp_path, owner=owner)
    assert (tmp_path / "pgdata").is_dir()
    with pytest.raises(data.DataDenied):
        data.prepare(tmp_path, owner=owner)


@pytest.mark.parametrize("mode", ["prepare", "verify"])
def test_cli_identity_fixed_path_and_receipt(monkeypatch, capsys, mode):
    import io
    import sys
    from types import SimpleNamespace

    frame = json.dumps(dict(version=1, role="database", fingerprint="a" * 64)).encode()
    monkeypatch.setattr(sys, "argv", ["helper", mode])
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(frame)))
    identity = 0 if mode == "prepare" else 10002
    monkeypatch.setattr(os, "geteuid", lambda: identity)
    monkeypatch.setattr(os, "getegid", lambda: identity)
    calls = []
    monkeypatch.setattr(data, mode, lambda root: calls.append(root))
    assert data.main() == 0
    assert calls == [data.ROOT]
    assert json.loads(capsys.readouterr().out) == dict(
        state="PREPARED" if mode == "prepare" else "VERIFIED", role="database", fingerprint="a" * 64
    )
    monkeypatch.setattr(os, "geteuid", lambda: 10001)
    monkeypatch.setattr(sys, "stdin", None)
    assert data.main() == 1
    assert len(calls) == 1
    output = capsys.readouterr()
    assert not output.out and "outcome unknown" in output.err
