"""Offline release provenance, hash anchoring and executable wheel boundaries."""

import base64
import csv
import gzip
import io
import json
import os
import stat
import subprocess
import warnings
from pathlib import Path
from zipfile import ZipFile, ZipInfo

import pytest

from scripts import package_agent_release as release


def wheel_bytes(expected, fault=None):
    prefix, project, code = expected
    contents = {**code, prefix + "METADATA": (
        f"Metadata-Version: 2.4\nName: {project['name']}\nVersion: {project['version']}\n"
        f"Requires-Python: {project['requires-python']}\n\n").encode(),
        prefix + "WHEEL": b"Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n"}
    if fault == "code":
        contents[next(iter(code))] = b"unreviewed code"
    elif fault == "script":
        contents["unexpected.data/scripts/activate"] = b"unreviewed executable"
    elif fault in ("name", "version", "python"):
        values = {"name": (project["name"], "another-package"),
                  "version": (project["version"], "999.0.0"),
                  "python": (project["requires-python"], ">=3.12")}
        before, after = values[fault]
        contents[prefix + "METADATA"] = contents[prefix + "METADATA"].replace(
            before.encode(), after.encode())
    elif fault == "tag":
        contents[prefix + "WHEEL"] = contents[prefix + "WHEEL"].replace(b"py3", b"py2")
    record = io.StringIO()
    writer = csv.writer(record, lineterminator="\n")
    for name, data in contents.items():
        digest = base64.urlsafe_b64encode(bytes.fromhex(release.review.sha256(data)))
        writer.writerow((name, "sha256=" + digest.decode().rstrip("="), len(data)))
    writer.writerow((prefix + "RECORD", "", ""))
    contents[prefix + "RECORD"] = record.getvalue().encode()
    if fault == "record":
        contents[prefix + "RECORD"] = b"../outside,sha256=untrusted,1\n"
    output = io.BytesIO()
    with ZipFile(output, "w") as archive:
        for name, data in contents.items():
            entry = ZipInfo(name)
            entry.create_system = 3
            entry.external_attr = (stat.S_IFREG | 0o644) << 16
            if fault == "symlink" and name == next(iter(code)):
                entry.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(entry, data)
        if fault == "duplicate":
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                archive.writestr(next(iter(code)), b"second executable")
    return output.getvalue()


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    # A real isolated Git source, not a mocked manifest or checkout authority.
    source_revision = release.review.git("rev-parse", "HEAD").decode().strip()
    files = release.review.committed_files(source_revision)
    data = b"locked third-party wheel"
    wheel = {"name": "runtime", "version": "1.0", "size": len(data),
             "hash": "sha256:" + release.review.sha256(data),
             "url": "https://files.pythonhosted.org/packages/runtime-1.0-py3-none-any.whl"}
    files["apps/api/uv.lock"] = ("""
requires-python = "==3.11.*"
[[package]]
name = "cashlessiq-api"
source = {editable = "."}
dependencies = [{name = "cashlessiq-domain"}, {name = "runtime"}]
[[package]]
name = "cashlessiq-domain"
source = {directory = "../../packages/domain"}
[[package]]
name = "runtime"
version = "1.0"
source = {registry = "https://pypi.org/simple"}
""" + f'wheels = [{{url = "{wheel["url"]}", hash = "{wheel["hash"]}", '
          f'size = {wheel["size"]}}}]\n').encode()
    for name, value in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)

    def git(*args):
        return subprocess.run(["git", *args], cwd=root, check=True,
                              capture_output=True).stdout.decode().strip()

    git("init", "-q")
    git("add", "--all")
    git("-c", "user.name=Test", "-c", "user.email=test@example.invalid",
        "commit", "-qm", "reviewed source")
    revision = git("rev-parse", "HEAD")
    monkeypatch.setattr(release.review, "ROOT", root)
    monkeypatch.setattr(release.dependencies, "urlopen",
                        lambda *_a, **_k: pytest.fail("Network contacted"))
    dist, dependencies = tmp_path / "dist", tmp_path / "dependencies"
    dist.mkdir()
    dependencies.mkdir()
    for name, expected in release.first_party(files).items():
        (dist / name).write_bytes(wheel_bytes(expected))
    wheels, metadata = release.dependencies.expected(revision)
    for name, value in {**metadata, next(iter(wheels)): data}.items():
        (dependencies / name).write_bytes(value)
    return root, revision, dist, dependencies


def create(inputs, tmp_path):
    _, revision, dist, dependencies = inputs
    directory = tmp_path / "release"
    digest, count = release.create(directory, revision, dist, dependencies)
    assert count == 3
    return directory, revision, digest


def reanchor(directory, revision):
    # An adversary rewrites its manifest to describe forged but self-consistent
    # files. Even with that digest, Git source/lock/requirements still constrain it.
    files = {path.name: path.read_bytes() for path in directory.iterdir()
             if path.name != release.MANIFEST}
    raw = release.manifest(revision, files)
    (directory / release.MANIFEST).write_bytes(raw)
    return release.review.sha256(raw)


def test_roundtrip_is_offline_complete_and_excludes_dirty_checkout(inputs, tmp_path):
    root, revision, _, _ = inputs
    (root / "apps/api/src/ciq_api/__init__.py").write_bytes(b"PRIVATE_SENTINEL")
    (root / "owner.mp4").write_bytes(b"PRIVATE_SENTINEL")
    directory, _, digest = create(inputs, tmp_path)
    assert release.verify(directory, revision, digest) == 3
    receipt = json.loads((directory / release.MANIFEST).read_bytes())
    assert receipt["activation"] == "disabled" and receipt["revision"] == revision
    assert len(receipt["files"]) == 5 and len(list(directory.iterdir())) == 6
    pins = (directory / "requirements.txt").read_text().splitlines()
    assert len(pins) == 3 and all(" --hash=sha256:" in line for line in pins)
    assert not any("PRIVATE_SENTINEL" in p.read_bytes().decode(errors="ignore")
                   for p in directory.iterdir())
    assert (root / "owner.mp4").read_bytes() == b"PRIVATE_SENTINEL"


@pytest.mark.parametrize("fault", [
    "code", "script", "duplicate", "symlink", "name", "version", "python", "tag", "record",
])
def test_unsafe_built_wheel_refused_before_output_creation(inputs, tmp_path, fault):
    _, revision, dist, dependencies = inputs
    packages = release.first_party(release.review.committed_files(revision))
    name, expected = next(iter(packages.items()))
    (dist / name).write_bytes(wheel_bytes(expected, fault))
    directory = tmp_path / "release"
    with pytest.raises(ValueError):
        release.create(directory, revision, dist, dependencies)
    assert not directory.exists()


@pytest.mark.parametrize("fault", ["source", "dependency", "requirements", "code"])
def test_self_consistent_forgery_cannot_override_git_authority(inputs, tmp_path, fault):
    directory, revision, _ = create(inputs, tmp_path)
    if fault == "source":
        (directory / release.SOURCE).write_bytes(gzip.compress(b"different source", mtime=0))
    elif fault == "dependency":
        (directory / "runtime-1.0-py3-none-any.whl").write_bytes(b"unreviewed dependency")
    elif fault == "requirements":
        (directory / "requirements.txt").write_bytes(b"provider==999\n")
    else:
        name, expected = next(iter(release.first_party(
            release.review.committed_files(revision)).items()))
        (directory / name).write_bytes(wheel_bytes(expected, "code"))
    digest = reanchor(directory, revision)
    with pytest.raises(ValueError):
        release.verify(directory, revision, digest)


def test_incoming_manifest_is_not_its_own_trust_anchor(inputs, tmp_path):
    directory, revision, digest = create(inputs, tmp_path)
    name = next(directory.glob("cashlessiq_api*.whl"))
    data = name.read_bytes()
    name.write_bytes(data + b"different release container")
    reanchor(directory, revision)
    with pytest.raises(ValueError):
        release.verify(directory, revision, digest)


@pytest.mark.parametrize("fault", ["missing", "extra", "symlink", "hardlink", "fifo"])
def test_inventory_and_nonregular_artifacts_deny_without_following(inputs, tmp_path, fault):
    directory, revision, digest = create(inputs, tmp_path)
    target = directory / "runtime-1.0-py3-none-any.whl"
    if fault == "missing":
        target.unlink()
    elif fault == "extra":
        (directory / "owner.mp4").write_bytes(b"PRIVATE_SENTINEL")
    else:
        retained = tmp_path / "retained"
        target.rename(retained)
        if fault == "symlink":
            target.symlink_to(retained)
        elif fault == "hardlink":
            os.link(retained, target)
        else:
            os.mkfifo(target)
    with pytest.raises((ValueError, OSError)):
        release.verify(directory, revision, digest)
    if fault in ("symlink", "hardlink", "fifo"):
        assert retained.read_bytes() == b"locked third-party wheel"


@pytest.mark.parametrize("fault", ["directory", "symlink", "dangling"])
def test_existing_output_is_preserved(inputs, tmp_path, fault):
    _, revision, dist, dependencies = inputs
    destination = tmp_path / "release"
    retained = tmp_path / "retained"
    retained.mkdir()
    (retained / "owner").write_bytes(b"PRIVATE_SENTINEL")
    if fault == "directory":
        destination.mkdir()
        (destination / "owner").write_bytes(b"PRIVATE_SENTINEL")
    else:
        destination.symlink_to(retained if fault == "symlink" else tmp_path / "absent")
    with pytest.raises(FileExistsError):
        release.create(destination, revision, dist, dependencies)
    assert (retained / "owner").read_bytes() == b"PRIVATE_SENTINEL"
    assert destination.is_symlink() if fault != "directory" else (
        destination / "owner").read_bytes() == b"PRIVATE_SENTINEL"


def test_interrupted_output_has_no_completion_receipt_or_reuse(inputs, tmp_path, monkeypatch):
    _, revision, dist, dependencies = inputs
    directory = tmp_path / "release"
    original = Path.open

    def fail(path, mode="r", *args, **kwargs):
        if path == directory / "requirements.txt" and mode == "xb":
            raise OSError("interrupted public write")
        return original(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fail)
    with pytest.raises(OSError):
        release.create(directory, revision, dist, dependencies)
    assert directory.exists() and list(directory.iterdir())
    assert not (directory / release.MANIFEST).exists()
    with pytest.raises(FileExistsError):
        release.create(directory, revision, dist, dependencies)


def test_unexpected_build_output_is_not_packaged(inputs, tmp_path):
    _, revision, dist, dependencies = inputs
    (dist / "owner.mp4").write_bytes(b"PRIVATE_SENTINEL")
    with pytest.raises(ValueError):
        release.create(tmp_path / "release", revision, dist, dependencies)
    assert not (tmp_path / "release").exists()
