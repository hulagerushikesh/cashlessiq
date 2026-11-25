"""Review artifacts contain pinned Git blobs, never local material or authority."""

import gzip
import io
import subprocess
import tarfile

import pytest

from scripts import package_agent_review as package


@pytest.fixture
def repository(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.setattr(package, "ROOT", root)

    def git(*args):
        return subprocess.run(["git", *args], cwd=root, check=True,
                              capture_output=True).stdout.decode().strip()

    git("init", "-q")
    for name in (*package.FIXED, *(prefix + "example.py" for prefix in package.TREES)):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("reviewed bytes\n")
    # Even tracked material outside the exact allowlist stays out.
    for name in ("submission/owner.mp4", "output/password.txt",
                 "apps/api/src/ciq_api/.env", "app/services.py"):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("PRIVATE_SENTINEL")
    git("add", "--all")
    git("-c", "user.name=Test", "-c", "user.email=test@example.invalid",
        "commit", "-qm", "review input")
    return root, git, git("rev-parse", "HEAD")


def test_real_git_roundtrip_excludes_working_tree_and_unapproved_files(repository):
    root, _, revision = repository
    dirty = root / package.FIXED[0]
    dirty.write_text("PRIVATE_SENTINEL")
    (root / "apps/api/src/ciq_api/untracked.py").write_text("PRIVATE_SENTINEL")
    files = package.committed_files(revision)
    assert files[package.FIXED[0]] == b"reviewed bytes\n"
    assert b"PRIVATE_SENTINEL" not in b"".join(files.values())
    first = package.encode(revision, files)
    assert first == package.encode(revision, files)
    path, digest, count = package.create(revision)
    assert package.verify(path, revision) == (digest, count)
    assert count == len(package.FIXED) + len(package.TREES)
    assert dirty.read_text() == "PRIVATE_SENTINEL"
    with pytest.raises(FileExistsError):
        package.create(revision)
    assert path.read_bytes() == first


def test_self_consistent_tampering_and_other_revision_do_not_verify(repository):
    root, git, revision = repository
    files = package.committed_files(revision)
    changed = {**files, package.FIXED[0]: b"rewritten bytes\n"}
    with pytest.raises(ValueError, match=package.ERROR):
        package.verify_data(package.encode(revision, changed), revision, files)
    (root / package.FIXED[0]).write_text("another reviewed revision\n")
    git("add", "--all")
    git("-c", "user.name=Test", "-c", "user.email=test@example.invalid",
        "commit", "-qm", "new revision")
    next_revision = git("rev-parse", "HEAD")
    path, _, _ = package.create(revision)
    with pytest.raises(ValueError, match=package.ERROR):
        package.verify(path, next_revision)


@pytest.mark.parametrize("fault", ["symlink", "executable", "missing", "oversize"])
def test_unsafe_committed_input_refuses_without_output(repository, fault, monkeypatch):
    root, git, _ = repository
    path = root / package.FIXED[0]
    if fault == "symlink":
        path.unlink()
        path.symlink_to("../../output/password.txt")
    elif fault == "executable":
        path.chmod(0o755)
        git("update-index", "--chmod=+x", package.FIXED[0])
    elif fault == "missing":
        path.unlink()
    else:
        monkeypatch.setattr(package, "MAX_FILE", 2)
    git("add", "--all")
    git("-c", "user.name=Test", "-c", "user.email=test@example.invalid",
        "commit", "--allow-empty", "-qm", "fault")
    with pytest.raises(ValueError, match=package.ERROR):
        package.create(git("rev-parse", "HEAD"))
    assert not (root / "output/agent-review").exists()


@pytest.mark.parametrize("revision", ["HEAD", "a" * 39, "A" * 40, "--help", "a" * 40])
def test_revision_must_be_full_existing_commit(repository, revision):
    with pytest.raises(ValueError, match=package.ERROR):
        package.committed_files(revision)


@pytest.mark.parametrize("fault", [
    "extra", "duplicate", "missing", "symlink", "hardlink", "directory", "metadata", "oversize",
])
def test_archive_faults_fail_without_extraction(repository, fault):
    _, _, revision = repository
    files = package.committed_files(revision)
    data = package.encode(revision, files)
    raw = io.BytesIO()
    with tarfile.open(fileobj=io.BytesIO(gzip.decompress(data))) as source, \
            tarfile.open(fileobj=raw, mode="w") as target:
        for index, item in enumerate(source):
            body = source.extractfile(item).read()
            if index == 0:
                if fault == "missing":
                    continue
                if fault in ("symlink", "hardlink", "directory"):
                    item.type = {"symlink": tarfile.SYMTYPE, "hardlink": tarfile.LNKTYPE,
                                 "directory": tarfile.DIRTYPE}[fault]
                    item.linkname, item.size, body = "/outside/owner", 0, b""
                elif fault == "metadata":
                    item.mode = 0o777
                elif fault == "oversize":
                    item.size, body = len(body) + 1, body + b"x"
                if fault == "duplicate":
                    target.addfile(item, io.BytesIO(body))
            target.addfile(item, io.BytesIO(body))
        if fault == "extra":
            target.addfile(tarfile.TarInfo("../owner-password"), io.BytesIO())
    with pytest.raises(ValueError, match=package.ERROR):
        package.verify_data(gzip.compress(raw.getvalue()), revision, files)


def test_compressed_and_expanded_limits(repository, monkeypatch):
    _, _, revision = repository
    files = package.committed_files(revision)
    data = package.encode(revision, files)
    monkeypatch.setattr(package, "MAX_COMPRESSED", len(data) - 1)
    with pytest.raises(ValueError, match=package.ERROR):
        package.verify_data(data, revision, files)
    monkeypatch.setattr(package, "MAX_COMPRESSED", len(data))
    monkeypatch.setattr(package, "MAX_TAR", 1024)
    with pytest.raises(ValueError, match=package.ERROR):
        package.verify_data(data, revision, files)


def test_trailing_archive_cannot_hide_behind_tar_end_markers(repository):
    _, _, revision = repository
    files = package.committed_files(revision)
    raw = package.archive_bytes(revision, files)
    data = gzip.compress(raw + raw)
    with pytest.raises(ValueError, match=package.ERROR):
        package.verify_data(data, revision, files)
