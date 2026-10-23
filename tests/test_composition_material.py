"""Real disposable files/tar metadata only; no volume mount or Docker acceptance."""

import io
import os
import tarfile
from unittest.mock import Mock

import pytest

from scripts.composition_material import ROLES, Material, MaterialDenied, names


def contents(role):
    return {name: ("disposable-" + name).encode() for name in names(role)}


def stage(tmp_path, role="broker"):
    parent = tmp_path / "owned"
    parent.mkdir(mode=0o700)
    data = contents(role)
    expected = Material.expected(role, "a" * 64, data)
    return expected.provision(parent, data)


@pytest.mark.parametrize("role", ROLES)
def test_exact_files_and_private_archive_ownership(tmp_path, role):
    staged = stage(tmp_path, role)
    assert staged.verify(role, "a" * 64) is True
    assert staged.root.stat().st_mode & 0o777 == 0o700
    with tarfile.open(fileobj=io.BytesIO(staged.archive(role, "a" * 64))) as archive:
        rows = archive.getmembers()
        assert {r.name for r in rows} == {".", *names(role)}
        for row in rows:
            assert (row.uid, row.gid, row.uname, row.gname) == (10001, 10001, "", "")
            assert row.mode == (0o500 if row.isdir() else 0o400)
            assert not row.issym() and not row.islnk() and not row.pax_headers
            if row.isfile():
                assert archive.extractfile(row).read() == contents(role)[row.name]
                assert (staged.root / row.name).stat().st_mode & 0o777 == 0o400
    assert "disposable-" not in repr(staged) + repr(staged.expected)


@pytest.mark.parametrize(
    "fault",
    [
        "extra",
        "missing",
        "symlink",
        "hardlink",
        "fifo",
        "mode",
        "root-mode",
        "root-symlink",
        "replacement",
        "changed",
        "oversize",
        "role",
        "fingerprint",
    ],
)
def test_unknown_or_tampered_material_denies_without_repair(tmp_path, fault, capsys):
    staged = stage(tmp_path)
    path = staged.root / "identity.key"
    role, fingerprint = "broker", "a" * 64
    if fault == "extra":
        (staged.root / "db.json").touch(mode=0o400)
    elif fault == "missing":
        path.unlink()
    elif fault == "symlink":
        path.unlink()
        path.symlink_to(staged.root / "identity.pem")
    elif fault == "hardlink":
        os.link(path, tmp_path / "alias")
    elif fault == "fifo":
        path.unlink()
        os.mkfifo(path, 0o400)
    elif fault == "mode":
        path.chmod(0o444)
    elif fault == "root-mode":
        staged.root.chmod(0o755)
    elif fault in {"root-symlink", "replacement"}:
        moved = staged.root.with_name("moved")
        staged.root.rename(moved)
        if fault == "root-symlink":
            staged.root.symlink_to(moved, target_is_directory=True)
        else:
            staged.root.mkdir(mode=0o700)
    elif fault in {"changed", "oversize"}:
        path.chmod(0o600)
        original = path.read_bytes()
        path.write_bytes(b"x" * (len(original) if fault == "changed" else 262145))
        path.chmod(0o400)
    elif fault == "role":
        role = "membership"
    else:
        fingerprint = "b" * 64
    for operation in (staged.verify, staged.archive):
        with pytest.raises(MaterialDenied, match=r"^Disposable material denied;"):
            operation(role, fingerprint)
    assert capsys.readouterr() == ("", "")


def test_expected_has_no_io_and_provision_never_overwrites(tmp_path, monkeypatch):
    data = contents("broker")
    with monkeypatch.context() as patch:
        spy = Mock(side_effect=AssertionError("Unexpected filesystem I/O"))
        patch.setattr(os, "open", spy)
        expected = Material.expected("broker", "a" * 64, data)
        spy.assert_not_called()
    staged = stage(tmp_path)
    original = (staged.root / "identity.key").read_bytes()
    with pytest.raises(MaterialDenied):
        expected.provision(staged.root.parent, data)
    assert (staged.root / "identity.key").read_bytes() == original


@pytest.mark.parametrize(
    "fault", ["extra", "empty", "str", "large", "total", "missing", "role", "hash"]
)
def test_invalid_expected_bytes_have_no_filesystem_effect(tmp_path, fault):
    data, role, fingerprint = contents("broker"), "broker", "a" * 64
    if fault == "extra":
        data["../escape"] = b"bad"
    elif fault == "missing":
        del data["signer.pem"]
    elif fault == "role":
        role = "controller"
    elif fault == "hash":
        fingerprint = "z" * 64
    elif fault == "total":
        data = {name: b"x" * 262144 for name in data}
    else:
        data["identity.key"] = {"empty": b"", "str": "secret", "large": b"x" * 262145}[fault]
    with pytest.raises(MaterialDenied):
        Material.expected(role, fingerprint, data)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("fault", ["parent-mode", "parent-symlink", "changed-bytes", "write"])
def test_failed_provision_retains_private_partial_state(tmp_path, monkeypatch, fault):
    parent = tmp_path / "owned"
    parent.mkdir(mode=0o700)
    data = contents("broker")
    expected = Material.expected("broker", "a" * 64, data)
    if fault == "parent-mode":
        parent.chmod(0o755)
    elif fault == "parent-symlink":
        alias = tmp_path / "alias"
        alias.symlink_to(parent, target_is_directory=True)
        parent = alias
    elif fault == "changed-bytes":
        data["identity.key"] = b"other secret"
    else:
        monkeypatch.setattr(os, "write", Mock(side_effect=OSError("private failure")))
    with pytest.raises(MaterialDenied):
        expected.provision(parent, data)
    if fault == "write":
        root = parent / "broker"
        assert root.stat().st_mode & 0o777 == 0o700
        assert len(list(root.iterdir())) == 1
        with pytest.raises(MaterialDenied):
            expected.provision(parent, data)
    else:
        assert not (parent / "broker").exists()


def test_same_size_change_during_read_denies_without_retry(tmp_path, monkeypatch):
    staged = stage(tmp_path)
    original_read = os.read
    path = staged.root / "ca.pem"
    changed = False

    def read(fd, count):
        nonlocal changed
        data = original_read(fd, count)
        if not changed:
            changed = True
            # Even if the old bytes were returned, a concurrent metadata/content
            # change cannot become a successful archive snapshot.
            path.chmod(0o600)
            path.write_bytes(b"x" * len(data))
            path.chmod(0o400)
        return data

    monkeypatch.setattr(os, "read", read)
    with pytest.raises(MaterialDenied):
        staged.archive("broker", "a" * 64)
    assert changed
