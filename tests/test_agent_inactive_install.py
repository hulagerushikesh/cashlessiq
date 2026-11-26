"""Offline installer refusal, extraction containment and verified input snapshot."""

import io
import json
import tarfile
from pathlib import Path

import pytest

from scripts import install_agent_inactive as installer


@pytest.mark.parametrize("path", ["/run/ciq-agent-receipts", "/run/ciq-agent-supervisor"])
def test_existing_private_state_refused_including_dangling_receipt_path(monkeypatch, path):
    def missing(_):
        raise KeyError

    for owner, name in ((installer.pwd, "getpwnam"), (installer.pwd, "getpwuid"),
                        (installer.grp, "getgrnam"), (installer.grp, "getgrgid")):
        monkeypatch.setattr(owner, name, missing)
    monkeypatch.setattr(Path, "exists", lambda _: False)
    monkeypatch.setattr(Path, "is_symlink", lambda p: str(p) == path)
    with pytest.raises(ValueError, match=installer.ERROR):
        installer.inactive()


@pytest.mark.parametrize("platform,uid", [("darwin", 0), ("linux", 501)])
def test_unsupported_host_refused_before_input_or_subprocess(monkeypatch, platform, uid):
    monkeypatch.setattr(installer.sys, "platform", platform)
    monkeypatch.setattr(installer.os, "geteuid", lambda: uid)
    monkeypatch.setattr(installer.release, "verified_files",
                        lambda *_a: pytest.fail("Inputs read"))
    monkeypatch.setattr(installer, "run", lambda *_a, **_k: pytest.fail("Process started"))
    with pytest.raises(ValueError, match="Inactive agent installation"):
        installer.install(Path("wheels"), Path("python"), "a" * 40, "b" * 64)


def archive_bytes(fault=None):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        root = tarfile.TarInfo("python")
        root.type = tarfile.DIRTYPE
        archive.addfile(root)
        item = tarfile.TarInfo("python/bin/python3.11")
        item.size = 4
        if fault == "traversal":
            item.name = "python/../../owner"
        elif fault == "absolute":
            item.name = "/python/bin/python3.11"
        elif fault == "other-root":
            item.name = "other/bin/python3.11"
        elif fault in ("device", "hardlink", "symlink"):
            item.size = 0
            item.type = {"device": tarfile.CHRTYPE, "hardlink": tarfile.LNKTYPE,
                         "symlink": tarfile.SYMTYPE}[fault]
            item.linkname = "../../../owner"
        archive.addfile(item, io.BytesIO(b"code") if item.isfile() else None)
        if fault == "duplicate":
            archive.addfile(item, io.BytesIO(b"code"))
        if fault is None:
            link = tarfile.TarInfo("python/bin/python")
            link.type, link.linkname = tarfile.SYMTYPE, "python3.11"
            archive.addfile(link)
    return output.getvalue()


def test_extracts_only_under_fresh_root_with_internal_link(tmp_path):
    installer.unpack(archive_bytes(), tmp_path)
    assert (tmp_path / "python/bin/python3.11").read_bytes() == b"code"
    assert (tmp_path / "python/bin/python").resolve() == tmp_path / "python/bin/python3.11"


@pytest.mark.parametrize("fault", [
    "traversal", "absolute", "other-root", "device", "hardlink", "symlink", "duplicate",
])
def test_unsafe_archive_cannot_escape_or_replace_owner_data(tmp_path, fault):
    destination = tmp_path / "install"
    destination.mkdir()
    owner = tmp_path / "owner"
    owner.write_bytes(b"owner")
    with pytest.raises((ValueError, tarfile.TarError)):
        installer.unpack(archive_bytes(fault), destination)
    assert owner.read_bytes() == b"owner"
    assert not (destination / "python/bin/python3.11").exists()


@pytest.mark.parametrize("fail_probe", [False, True])
def test_private_snapshot_is_used_and_completion_requires_installed_probe(
    tmp_path, monkeypatch, fail_probe,
):
    root = tmp_path / "install"
    monkeypatch.setattr(installer, "INSTALL", root)
    monkeypatch.setattr(installer, "guard", lambda: None)
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    (wheels / "requirements.txt").write_bytes(b"untrusted after verification")
    verified = {"runtime.whl": b"reviewed wheel", "requirements.txt": b"reviewed pins",
                "agent-review.tar.gz": b"source excluded from installer snapshot"}
    monkeypatch.setattr(installer.release, "verified_files", lambda *_: dict(verified))
    archive = tmp_path / "archive"
    archive.write_bytes(b"pinned archive")
    monkeypatch.setattr(installer.python_bundle, "verify", lambda *_: archive)
    monkeypatch.setattr(installer.python_bundle, "expected", lambda *_: (
        "archive", {"sha256": installer.release.review.sha256(archive.read_bytes())}, b""))
    monkeypatch.setattr(installer, "unpack", lambda *_: None)
    monkeypatch.setattr(installer, "harden", lambda *_: None)
    monkeypatch.setattr(installer, "inactive", lambda: None)
    seen = []

    def run(_python, *args, **_kwargs):
        snapshot = root / ".bootstrap-wheels"
        assert (snapshot / "runtime.whl").read_bytes() == b"reviewed wheel"
        assert (snapshot / "requirements.txt").read_bytes() == b"reviewed pins"
        assert len(list(snapshot.iterdir())) == 2
        assert not (root / "agent-install.json").exists()
        if "install" in args:
            assert str(snapshot / "requirements.txt") in args
            assert str(wheels / "requirements.txt") not in args
        seen.append(args)

    def probe(_revision):
        assert not (root / ".bootstrap-wheels").exists()
        if fail_probe:
            raise ValueError("Installed probe denied")

    monkeypatch.setattr(installer, "run", run)
    monkeypatch.setattr(installer, "installed", probe)
    if fail_probe:
        with pytest.raises(ValueError, match="probe denied"):
            installer.install(wheels, tmp_path, "a" * 40, "b" * 64)
        assert not (root / "agent-install.json").exists()
    else:
        installer.install(wheels, tmp_path, "a" * 40, "b" * 64)
        receipt = json.loads((root / "agent-install.json").read_bytes())
        assert receipt["activation"] == "disabled" and receipt["revision"] == "a" * 40
    assert len(seen) == 3 and root.is_dir()
    with pytest.raises(FileExistsError):
        installer.install(wheels, tmp_path, "a" * 40, "b" * 64)
