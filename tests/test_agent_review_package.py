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


def test_staged_build_tree_uses_selected_commit_not_dirty_or_newer_source(repository, tmp_path):
    root, git, revision = repository
    (root / "apps/api/src/ciq_api/example.py").write_text("newer committed code")
    git("add", "--all")
    git("-c", "user.name=Test", "-c", "user.email=test@example.invalid",
        "commit", "-qm", "newer source")
    (root / "packages/domain/pyproject.toml").write_text("PRIVATE_SENTINEL")
    (root / "apps/api/src/ciq_api/untracked.py").write_text("PRIVATE_SENTINEL")
    destination = tmp_path / "stage"
    count = package.stage(revision, destination)
    files = package.committed_files(revision)
    actual = {p.relative_to(destination).as_posix(): p.read_bytes()
              for p in destination.rglob("*") if p.is_file()}
    assert actual.pop(package.MANIFEST) == package.manifest(revision, files)
    assert actual == files and count == len(files)
    assert not any(p.is_symlink() for p in destination.rglob("*"))
    assert b"PRIVATE_SENTINEL" not in b"".join(actual.values())
    assert actual["apps/api/src/ciq_api/example.py"] == b"reviewed bytes\n"
    assert (root / "packages/domain/pyproject.toml").read_text() == "PRIVATE_SENTINEL"


@pytest.mark.parametrize("fault", ["directory", "symlink", "dangling"])
def test_staging_refuses_existing_output_without_changing_it(repository, tmp_path, fault):
    _, _, revision = repository
    owner = tmp_path / "owner"
    owner.mkdir()
    (owner / "retained").write_bytes(b"owner bytes")
    destination = tmp_path / "stage"
    if fault == "directory":
        destination.mkdir()
        (destination / "retained").write_bytes(b"existing stage")
    else:
        destination.symlink_to(owner if fault == "symlink" else tmp_path / "absent")
    with pytest.raises(FileExistsError):
        package.stage(revision, destination)
    assert (owner / "retained").read_bytes() == b"owner bytes"
    if fault == "directory":
        assert list(destination.iterdir()) == [destination / "retained"]
        assert (destination / "retained").read_bytes() == b"existing stage"
    else:
        assert destination.is_symlink()


def test_invalid_revision_does_not_create_staging_destination(repository, tmp_path):
    destination = tmp_path / "stage"
    with pytest.raises(ValueError, match=package.ERROR):
        package.stage("HEAD", destination)
    assert not destination.exists()


def test_staging_failure_preserves_partial_output_without_completion(
    repository, tmp_path, monkeypatch,
):
    _, _, revision = repository
    destination = tmp_path / "stage"
    original = type(destination).open

    def fail(path, *args, **kwargs):
        if path == destination / "apps/api/alembic.ini":
            raise OSError("simulated write failure")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(type(destination), "open", fail)
    with pytest.raises(OSError):
        package.stage(revision, destination)
    assert (destination / "LICENSE").read_bytes() == b"reviewed bytes\n"
    assert not (destination / package.MANIFEST).exists()
    with pytest.raises(FileExistsError):
        package.stage(revision, destination)


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


def test_git_replacement_refs_cannot_substitute_pinned_source(repository):
    root, git, revision = repository
    original = package.committed_files(revision)
    (root / package.FIXED[0]).write_text("replacement bytes\n")
    git("add", "--all")
    git("-c", "user.name=Test", "-c", "user.email=test@example.invalid",
        "commit", "-qm", "replacement")
    replacement = git("rev-parse", "HEAD")
    git("replace", revision, replacement)
    assert git("show", revision + ":" + package.FIXED[0]) == "replacement bytes"
    assert package.committed_files(revision) == original


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
