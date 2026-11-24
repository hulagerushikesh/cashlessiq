"""Atomic delivery and fail-closed evidence, using disposable files only."""

import os
import stat

import pytest

from scripts import agent_service_plans as plans
from scripts import test_agent_service_journey as journey


@pytest.fixture
def directory(tmp_path):
    fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        yield fd
    finally:
        os.close(fd)


def allowed(monkeypatch):
    monkeypatch.setattr(plans.sys, "platform", "linux")
    monkeypatch.setattr(plans.os, "geteuid", lambda: 0)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_REPOSITORY", "hulagerushikesh/cashlessiq")
    monkeypatch.setenv("CIQ_AGENT_SERVICE_JOURNEY_TEST", "1")


def test_final_name_appears_only_with_complete_private_synced_bytes(
    tmp_path, directory, monkeypatch,
):
    raw = b"dummy-private-bytes" * 500
    write, link, sync = plans.os.write, plans.os.link, plans.os.fsync
    synced = []

    def short_write(fd, data):
        assert not (tmp_path / "plan.json").exists()
        return write(fd, data[:17])

    def record_sync(fd):
        sync(fd)
        synced.append(fd)

    def complete_link(source, target, **options):
        source_path = tmp_path / source
        item = source_path.stat()
        assert synced and source_path.read_bytes() == raw
        assert stat.S_IMODE(item.st_mode) == 0o600 and item.st_nlink == 1
        assert item.st_uid == os.getuid() and item.st_gid == os.getgid()
        assert options == dict(src_dir_fd=directory, dst_dir_fd=directory,
                               follow_symlinks=False)
        link(source, target, **options)

    monkeypatch.setattr(plans.os, "write", short_write)
    monkeypatch.setattr(plans.os, "fsync", record_sync)
    monkeypatch.setattr(plans.os, "link", complete_link)
    # The primitive is tested with our own UID/GID, without privilege or services.
    monkeypatch.setattr(plans.os, "fchown", lambda fd, uid, gid: None)
    plans.publish(directory, "plan.json", os.getuid(), os.getgid(), raw)
    assert list(tmp_path.iterdir()) == [tmp_path / "plan.json"]
    assert (tmp_path / "plan.json").read_bytes() == raw
    assert (tmp_path / "plan.json").stat().st_nlink == 1
    assert synced[-1] == directory and len(synced) == 2


@pytest.mark.parametrize("kind", ["file", "directory", "symlink", "dangling", "hardlink"])
def test_existing_entry_never_replaced(tmp_path, directory, monkeypatch, kind):
    original = tmp_path / "original"
    original.write_bytes(b"original-private")
    target = tmp_path / "plan.json"
    if kind == "directory":
        target.mkdir()
    elif kind in ("symlink", "dangling"):
        target.symlink_to(original if kind == "symlink" else tmp_path / "absent")
    elif kind == "hardlink":
        os.link(original, target)
    else:
        target.write_bytes(b"existing-private")
    before = target.lstat()
    monkeypatch.setattr(plans.os, "fchown", lambda *_: None)
    with pytest.raises(FileExistsError):
        plans.publish(directory, "plan.json", os.getuid(), os.getgid(), b"replacement")
    assert target.lstat() == before and original.read_bytes() == b"original-private"
    assert len(list(tmp_path.glob(".pending-*"))) == 1  # Retained, not retried.


@pytest.mark.parametrize("failure", ["write", "fchown", "fchmod", "fsync", "link", "unlink"])
def test_failures_retain_evidence_and_do_not_remove_final(
    tmp_path, directory, monkeypatch, failure,
):
    monkeypatch.setattr(plans.os, "fchown", lambda *_: None)

    def deny(*_, **__):
        raise OSError("PRIVATE")

    monkeypatch.setattr(plans.os, failure, deny)
    with pytest.raises(OSError):
        plans.publish(directory, "plan.json", os.getuid(), os.getgid(), b"dummy")
    assert len(list(tmp_path.glob(".pending-*"))) == 1
    assert (tmp_path / "plan.json").exists() is (failure == "unlink")


@pytest.mark.parametrize("fault", ["platform", "uid", "actions", "repo", "optin",
                                   "role", "path", "empty", "large", "type"])
def test_guard_denies_before_filesystem_access(monkeypatch, fault):
    allowed(monkeypatch)
    if fault == "platform":
        monkeypatch.setattr(plans.sys, "platform", "darwin")
    elif fault == "uid":
        monkeypatch.setattr(plans.os, "geteuid", lambda: 501)
    for name, key in (("actions", "GITHUB_ACTIONS"), ("repo", "GITHUB_REPOSITORY"),
                      ("optin", "CIQ_AGENT_SERVICE_JOURNEY_TEST")):
        if fault == name:
            monkeypatch.setenv(key, "wrong")
    monkeypatch.setattr(plans, "parent", lambda *_: pytest.fail("Host accessed"))
    role = {"role": "other", "path": "../claim"}.get(fault, "claim")
    raw = {"empty": b"", "large": b"x" * 8193, "type": "PRIVATE"}.get(fault, b"{}")
    with pytest.raises(ValueError, match=plans.ERROR):
        plans.stage(role, raw)


def test_delivery_suppresses_private_exception_and_preserves_final_on_late_failure(
    tmp_path, directory, monkeypatch, capsys,
):
    allowed(monkeypatch)
    monkeypatch.setattr(plans, "parent", lambda _: os.dup(directory))

    def uncertain(fd, name, uid, gid, raw):
        assert (name, uid, gid, raw) == ("claim.json", 53001, 53001, b"dummy")
        (tmp_path / name).write_bytes(raw)
        raise OSError("PRIVATE")

    monkeypatch.setattr(plans, "publish", uncertain)
    with pytest.raises(ValueError) as error:
        plans.stage("claim", b"dummy")
    assert str(error.value) == plans.ERROR and error.value.__suppress_context__
    assert (tmp_path / "claim.json").read_bytes() == b"dummy"
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("role", list(plans.TARGETS))
def test_service_delivery_checks_quiescence_before_staging(monkeypatch, role):
    services = journey.Services((key, key + ".service") for key in (
        "claim", "custody", "receipt",
    ))
    seen = []
    monkeypatch.setattr(journey.quiescence, "verify_stopped", lambda unit: seen.append(unit))
    monkeypatch.setattr(journey.plans, "stage", lambda key, raw: seen.append((key, raw)))
    services.deliver(role, {"dummy": True})
    assert seen == [("custody" if role == "candidate" else role) + ".service",
                    (role, b'{"dummy": true}')]


def test_uncertain_service_cannot_receive_plan(monkeypatch):
    services = journey.Services([("claim", "claim.service")])

    def deny(_):
        raise ValueError("Quiescence unconfirmed")

    monkeypatch.setattr(journey.quiescence, "verify_stopped", deny)
    monkeypatch.setattr(journey.plans, "stage", lambda *_: pytest.fail("Plan staged"))
    with pytest.raises(ValueError, match="Quiescence unconfirmed"):
        services.deliver("claim", {})


def test_zero_write_never_publishes(tmp_path, directory, monkeypatch):
    monkeypatch.setattr(plans.os, "write", lambda *_: 0)
    with pytest.raises(ValueError):
        plans.publish(directory, "plan.json", os.getuid(), os.getgid(), b"dummy")
    assert not (tmp_path / "plan.json").exists()


def test_directory_sync_failure_retains_published_file(tmp_path, directory, monkeypatch):
    sync = plans.os.fsync
    monkeypatch.setattr(plans.os, "fchown", lambda *_: None)

    def failed_directory_sync(fd):
        if fd == directory:
            raise OSError("PRIVATE")
        sync(fd)

    monkeypatch.setattr(plans.os, "fsync", failed_directory_sync)
    with pytest.raises(OSError):
        plans.publish(directory, "plan.json", os.getuid(), os.getgid(), b"dummy")
    assert (tmp_path / "plan.json").read_bytes() == b"dummy"
    assert (tmp_path / "plan.json").stat().st_nlink == 1


@pytest.mark.parametrize("role", list(plans.TARGETS))
def test_each_role_has_fixed_target_identity_and_size_bound(monkeypatch, role):
    allowed(monkeypatch)
    monkeypatch.setattr(plans, "parent", lambda *_: pytest.fail("Oversize reached host"))
    maximum = plans.TARGETS[role][3]
    with pytest.raises(ValueError, match=plans.ERROR):
        plans.stage(role, b"x" * (maximum + 1))
