"""Real private host staging only; no PostgreSQL install or container acceptance."""

import os

import pytest

from scripts.composition_database import DatabaseStaging, prepare
from scripts.composition_material import Material, MaterialDenied
from tests.test_composition_database import plan


def stage(tmp_path):
    parent = tmp_path / "owned"
    parent.mkdir(mode=0o700)
    bundle = prepare(plan())
    expected = DatabaseStaging.expected("database", "a" * 64, bundle.server)
    return bundle, expected.provision(parent, bundle.server)


def test_private_database_staging_is_separate_and_cannot_use_application_archive(tmp_path):
    bundle, staged = stage(tmp_path)
    assert staged.verify("database", "a" * 64)
    assert staged.root.stat().st_mode & 0o777 == 0o700
    for name, data in bundle.server.items():
        path = staged.root / name
        assert path.read_bytes() == data
        assert path.stat().st_mode & 0o777 == 0o400
        assert path.stat().st_uid == os.getuid()
    assert not set(bundle.membership) & set(os.listdir(staged.root))
    assert bundle.server["admin-password"].decode() not in repr(staged.expected)
    with pytest.raises(MaterialDenied):
        staged.archive("database", "a" * 64)
    with pytest.raises(MaterialDenied):
        Material.expected("database", "a" * 64, bundle.server)
    with pytest.raises(MaterialDenied):
        DatabaseStaging.expected("membership", "a" * 64, bundle.server)


@pytest.mark.parametrize("fault", ["changed", "symlink", "hardlink", "mode", "extra", "root"])
def test_tampering_denies_without_deleting_or_disclosing_secrets(tmp_path, fault, capsys):
    bundle, staged = stage(tmp_path)
    key = staged.root / "server.key"
    if fault == "changed":
        key.chmod(0o600)
        key.write_bytes(b"x" * len(bundle.server["server.key"]))
        key.chmod(0o400)
    elif fault == "symlink":
        key.unlink()
        key.symlink_to(staged.root / "server.pem")
    elif fault == "hardlink":
        os.link(key, tmp_path / "alias")
    elif fault == "mode":
        key.chmod(0o444)
    elif fault == "extra":
        (staged.root / "db.json").write_bytes(bundle.membership["db.json"])
    else:
        staged.root.rename(tmp_path / "retained")
        staged.root.mkdir(mode=0o700)
    with pytest.raises(MaterialDenied) as error:
        staged.verify("database", "a" * 64)
    assert staged.root.exists()
    assert bundle.server["admin-password"].decode() not in str(error.value)
    assert capsys.readouterr() == ("", "")


def test_reuse_and_changed_input_deny_before_overwriting(tmp_path):
    bundle, staged = stage(tmp_path)
    expected = staged.expected
    with pytest.raises(MaterialDenied):
        expected.provision(staged.root.parent, bundle.server)
    assert staged.verify("database", "a" * 64)
    second = tmp_path / "second"
    second.mkdir(mode=0o700)
    changed = dict(bundle.server, **{"admin-password": b"replacement"})
    with pytest.raises(MaterialDenied):
        expected.provision(second, changed)
    assert list(second.iterdir()) == []
    with pytest.raises(MaterialDenied):
        staged.verify("database", "b" * 64)


def test_insecure_parent_and_symlink_parent_deny_before_staging(tmp_path):
    bundle = prepare(plan())
    expected = DatabaseStaging.expected("database", "a" * 64, bundle.server)
    parent = tmp_path / "public"
    parent.mkdir(mode=0o755)
    with pytest.raises(MaterialDenied):
        expected.provision(parent, bundle.server)
    assert list(parent.iterdir()) == []
    parent.chmod(0o700)
    alias = tmp_path / "alias"
    alias.symlink_to(parent, target_is_directory=True)
    with pytest.raises(MaterialDenied):
        expected.provision(alias, bundle.server)
    assert list(parent.iterdir()) == []


def test_failed_write_retains_private_partial_attempt_and_forbids_retry(tmp_path, monkeypatch):
    bundle = prepare(plan())
    expected = DatabaseStaging.expected("database", "a" * 64, bundle.server)
    parent = tmp_path / "owned"
    parent.mkdir(mode=0o700)
    original = os.write

    def fail_write(fd, data):
        original(fd, data[:3])
        raise OSError("injected write failure")

    with monkeypatch.context() as patch:
        patch.setattr(os, "write", fail_write)
        with pytest.raises(MaterialDenied):
            expected.provision(parent, bundle.server)
    retained = parent / "database"
    assert retained.stat().st_mode & 0o777 == 0o700
    partial = list(retained.iterdir())
    assert len(partial) == 1
    assert partial[0].stat().st_mode & 0o777 == 0o600
    assert partial[0].stat().st_size == 3
    with pytest.raises(MaterialDenied):
        expected.provision(parent, bundle.server)
    assert partial[0].stat().st_size == 3
