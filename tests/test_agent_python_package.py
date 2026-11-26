"""Interpreter pin authority, bounded fetch and offline staging boundaries."""

import io
import json
import os

import pytest

from scripts import package_agent_python as bundle


@pytest.fixture
def source(monkeypatch):
    revision = bundle.release.review.git("rev-parse", "HEAD").decode().strip()
    files = bundle.release.review.committed_files(revision)
    data = b"inert test archive; never extracted or executed"
    metadata = json.loads(files[bundle.PIN])
    metadata[bundle.KEY]["sha256"] = bundle.release.review.sha256(data)
    raw = bundle.release.canonical(metadata)
    revisions = []

    def committed(selected):
        revisions.append(selected)
        assert selected == revision
        return {bundle.PIN: raw}

    monkeypatch.setattr(bundle.release.review, "committed_files", committed)
    calls = []

    def fetch(url, timeout):
        assert url == metadata[bundle.KEY]["url"] and timeout == 30
        calls.append(url)
        response = io.BytesIO(data)
        response.geturl = lambda: "https://release-assets.githubusercontent.com/public-asset"
        return response

    monkeypatch.setattr(bundle, "urlopen", fetch)
    return revision, data, raw, calls, revisions


def test_fetch_then_verify_and_stage_without_network_or_execution(source, tmp_path, monkeypatch):
    revision, data, raw, calls, revisions = source
    directory = tmp_path / "bundle"
    archive = bundle.create(directory, revision)
    assert archive.read_bytes() == data and len(calls) == 1
    monkeypatch.setattr(bundle, "urlopen", lambda *_a, **_k: pytest.fail("Network accessed"))
    assert bundle.verify(directory, revision) == archive
    staged = bundle.local_metadata(directory, revision, tmp_path / "local.json")
    expected = json.loads(raw)
    expected[bundle.KEY]["url"] = archive.as_uri()
    assert json.loads(staged.read_bytes()) == expected
    assert (directory / bundle.METADATA).read_bytes() == raw
    assert len(list(directory.iterdir())) == 3 and len(revisions) >= 3
    with pytest.raises(FileExistsError):
        bundle.local_metadata(directory, revision, staged)


@pytest.mark.parametrize("fault", ["directory", "symlink", "dangling"])
def test_existing_destination_refused_before_download(source, tmp_path, fault):
    revision, _, _, calls, _ = source
    directory = tmp_path / "bundle"
    owner = tmp_path / "owner"
    if fault == "directory":
        directory.mkdir()
    else:
        if fault == "symlink":
            owner.mkdir()
            (owner / "private").write_bytes(b"owner")
        directory.symlink_to(owner)
    with pytest.raises(FileExistsError):
        bundle.create(directory, revision)
    assert calls == []
    if fault == "symlink":
        assert (owner / "private").read_bytes() == b"owner"


@pytest.mark.parametrize("fault", ["tamper", "oversize", "redirect", "interrupted"])
def test_failed_fetch_retains_no_completion_or_executable(source, tmp_path, monkeypatch, fault):
    revision = source[0]
    directory = tmp_path / "bundle"
    monkeypatch.setattr(bundle, "MAX_ARCHIVE", 64)

    def fetch(*_args, **_kwargs):
        if fault == "interrupted":
            raise OSError("private upstream diagnostic")
        response = io.BytesIO(b"x" * (1000 if fault == "oversize" else 1))
        response.geturl = lambda: ("http://untrusted.invalid/" if fault == "redirect"
                                  else "https://release-assets.githubusercontent.com/public")
        return response

    monkeypatch.setattr(bundle, "urlopen", fetch)
    with pytest.raises((ValueError, OSError)):
        bundle.create(directory, revision)
    assert list(directory.iterdir()) == []
    with pytest.raises(FileExistsError):
        bundle.create(directory, revision)


@pytest.mark.parametrize("fault", [
    "archive", "metadata", "manifest", "extra", "symlink", "hardlink", "fifo",
])
def test_offline_verification_denies_forgery_and_special_files(source, tmp_path, fault):
    revision = source[0]
    directory = tmp_path / "bundle"
    archive = bundle.create(directory, revision)
    if fault == "archive":
        archive.write_bytes(b"replacement executable")
        # A self-consistent manifest still cannot override the Git-pinned hash.
        (directory / bundle.MANIFEST).write_bytes(bundle.manifest(
            revision, archive.name, archive.read_bytes()))
    elif fault in ("metadata", "manifest"):
        (directory / (bundle.METADATA if fault == "metadata" else bundle.MANIFEST)).write_bytes(
            b"replacement metadata")
    elif fault == "extra":
        (directory / "owner.mp4").write_bytes(b"owner")
    elif fault == "hardlink":
        os.link(archive, tmp_path / "other")
    else:
        archive.unlink()
        if fault == "symlink":
            archive.symlink_to(tmp_path / "owner")
        else:
            os.mkfifo(archive)
    with pytest.raises((ValueError, OSError)):
        bundle.local_metadata(directory, revision, tmp_path / "local.json")
    assert not (tmp_path / "local.json").exists()
