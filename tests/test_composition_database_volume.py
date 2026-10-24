"""Host filesystem and CLI contracts, not mounted Linux ownership acceptance."""

import io
import json
import os
import sys
import tarfile
from types import SimpleNamespace

import pytest

from scripts import composition_database_volume as db
from scripts import composition_volume as volume
from scripts.composition_material import MaterialDenied
from tests.test_composition_database_staging import stage
from tests.test_composition_volume import edited_archive


def parsed(tmp_path):
    _, staged = stage(tmp_path)
    frame = db.request(staged, install=True)
    spec, archive = volume.parse(frame, install=True, material_type=db.DatabaseVolume)
    return staged, frame, spec, archive


def test_db_archive_roundtrip_is_explicit_and_application_parser_rejects_it(tmp_path):
    staged, frame, spec, archive = parsed(tmp_path)
    with pytest.raises(MaterialDenied):
        volume.parse(frame, install=True)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        assert all((r.uid, r.gid) == db.OWNER for r in tar.getmembers())
    destination = tmp_path / "volume"
    destination.mkdir(mode=0o700)
    owner = os.getuid(), os.getgid()
    try:
        volume.install(destination, spec, archive, owner=owner)
        verify, absent = volume.parse(
            db.request(staged, install=False), install=False, material_type=db.DatabaseVolume
        )
        assert absent is None
        assert volume.verify(destination, verify, owner=owner)
        with pytest.raises(MaterialDenied):
            volume.install(destination, spec, archive, owner=owner)
        key = destination / "server.key"
        key.chmod(0o600)
        key.write_bytes(b"changed")
        key.chmod(0o400)
        with pytest.raises(MaterialDenied):
            volume.verify(destination, verify, owner=owner)
    finally:
        destination.chmod(0o700)


@pytest.mark.parametrize("fault", ["owner", "path", "link", "trailing", "bytes"])
def test_invalid_database_archive_denies_before_mutation(tmp_path, fault):
    _, _, spec, archive = parsed(tmp_path)
    if fault == "owner":
        archive = edited_archive(archive, lambda e: setattr(e, "uid", 10001))
    elif fault == "path":
        archive = edited_archive(archive, lambda e: setattr(e, "name", "../escape"))
    elif fault == "link":
        archive = edited_archive(archive, lambda e: setattr(e, "linkname", "elsewhere"))
    elif fault == "trailing":
        archive += b"hidden"
    else:
        archive = archive.replace(b"BEGIN;", b"WRONG;", 1)
    destination = tmp_path / "volume"
    destination.mkdir(mode=0o700)
    with pytest.raises(MaterialDenied):
        volume.install(destination, spec, archive, owner=(os.getuid(), os.getgid()))
    assert list(destination.iterdir()) == []


@pytest.mark.parametrize("mode", ["install", "verify"])
def test_cli_uses_fixed_directory_owner_and_redacted_receipt(tmp_path, monkeypatch, capsys, mode):
    staged, _, _, _ = parsed(tmp_path)
    frame = db.request(staged, install=mode == "install")
    monkeypatch.setattr(sys, "argv", ["db-helper", mode])
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(frame)))
    uid, gid = (0, 0) if mode == "install" else db.OWNER
    monkeypatch.setattr(os, "geteuid", lambda: uid)
    monkeypatch.setattr(os, "getegid", lambda: gid)
    calls = []
    monkeypatch.setattr(volume, mode, lambda *args, **kwargs: calls.append((args, kwargs)))
    assert db.main() == 0
    args, kwargs = calls[0]
    assert args[0] == db.ROOT
    assert type(args[1]) is db.DatabaseVolume
    assert kwargs == {"owner": db.OWNER}
    output = capsys.readouterr()
    assert json.loads(output.out) == dict(
        state="INSTALLED" if mode == "install" else "VERIFIED",
        role="database",
        fingerprint="a" * 64,
    )
    assert output.err == ""


def test_wrong_cli_identity_denies_before_reading_stdin(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["db-helper", "verify"])
    monkeypatch.setattr(os, "geteuid", lambda: 10001)
    monkeypatch.setattr(os, "getegid", lambda: 10001)
    monkeypatch.setattr(sys, "stdin", None)
    assert db.main() == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err == "Disposable database material denied; outcome unknown\n"
