"""Recovery refuses accidental service restarts and incomplete restores."""

import hashlib
import json
import shutil

import pytest

from scripts import check_mvp_recovery as recovery
from scripts.verify_mvp_backup import verify_package


def test_restart_is_disallowed_outside_disposable_preview_ci(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    with pytest.raises(ValueError, match="disposable GitHub CI"):
        recovery.require_restart_permission("preview")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    with pytest.raises(ValueError, match="disposable GitHub CI"):
        recovery.require_restart_permission("product")
    monkeypatch.delenv("GITHUB_ACTIONS")
    with pytest.raises(ValueError, match="disposable GitHub CI"):
        recovery.fresh_volume_preview(None, {})


def test_fresh_volume_uses_separate_port_and_project():
    assert recovery.fresh_compose_prefix()[2:4] == ["-p", "cashlessiq-recovery-ci"]
    assert recovery.fresh_preview_env()["CIQ_PREVIEW_PORT"] == "3081"
    assert recovery.fresh_preview_env()["CIQ_WEB_ORIGIN"] == "http://127.0.0.1:3081"


def test_restore_rejects_missing_or_changed_table_rows():
    verified = {"review_audit": {"rows": 4, "sha256": "a" * 64}}
    recovery.verify_manifest(verified, verified)
    with pytest.raises(RuntimeError, match="do not match"):
        recovery.verify_manifest(verified, {})
    with pytest.raises(RuntimeError, match="do not match"):
        recovery.verify_manifest(verified, {"review_audit": {"rows": 3, "sha256": "a" * 64}})


def _sample_package(tmp_path):
    directory = tmp_path / "backup"
    directory.mkdir(mode=0o700, parents=True)
    dump = directory / "current.dump"
    contents = b"PGDMP" + b"synthetic fixture" * 20
    dump.write_bytes(contents)
    dump.chmod(0o600)
    manifest = {
        "schema": "0003_mvp",
        "tables": {
            f"table_{index}": {
                "columns": [["id", "integer", True]],
                "rows": index,
                "sha256": "a" * 64,
            }
            for index in range(10)
        },
        "dump": {
            "file": "current.dump",
            "bytes": len(contents),
            "sha256": hashlib.sha256(contents).hexdigest(),
        },
    }
    descriptor = directory / "verified.json"
    descriptor.write_text(json.dumps(manifest))
    descriptor.chmod(0o600)
    return directory, manifest


def test_copied_backup_verifies_without_database_or_docker(tmp_path):
    source, manifest = _sample_package(tmp_path)
    copied = tmp_path / "copied"
    shutil.copytree(source, copied)
    copied.chmod(0o700)
    assert verify_package(copied) == manifest


def test_copied_backup_rejects_damage_and_missing_hash(tmp_path):
    source, _ = _sample_package(tmp_path)
    dump = source / "current.dump"
    changed = bytearray(dump.read_bytes())
    changed[-1] ^= 1
    dump.write_bytes(changed)
    with pytest.raises(ValueError, match="do not match"):
        verify_package(source)
    source, manifest = _sample_package(tmp_path / "second")
    del manifest["dump"]
    (source / "verified.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="complete"):
        verify_package(source)


def test_copied_backup_refuses_public_or_linked_files(tmp_path):
    source, _ = _sample_package(tmp_path)
    (source / "current.dump").chmod(0o644)
    with pytest.raises(ValueError, match="private"):
        verify_package(source)
    (source / "current.dump").chmod(0o600)
    (source / "verified.json").unlink()
    (source / "verified.json").symlink_to(source / "current.dump")
    with pytest.raises(ValueError, match="private regular"):
        verify_package(source)
