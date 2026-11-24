"""Private source intake uses disposable files; no real credentials or services."""

import os
from types import SimpleNamespace

import pytest

from scripts import agent_service_source as source
from scripts import test_agent_service_journey as journey


@pytest.fixture
def private(tmp_path, monkeypatch):
    monkeypatch.setattr(source.sys, "platform", "linux")
    monkeypatch.setattr(source.os, "geteuid", lambda: 0)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_REPOSITORY", "hulagerushikesh/cashlessiq")
    monkeypatch.setenv("CIQ_AGENT_SERVICE_JOURNEY_TEST", "1")
    monkeypatch.setattr(source, "directory", lambda: os.open(tmp_path, os.O_RDONLY))
    fstat, stat = os.fstat, os.stat

    def root(item):
        values = {name: getattr(item, name) for name in dir(item) if name.startswith("st_")}
        return SimpleNamespace(**{**values, "st_uid": 0, "st_gid": 0})

    # Only ownership is mapped; file modes, links, size, timestamps and inode are real.
    monkeypatch.setattr(source.os, "fstat", lambda fd: root(fstat(fd)))
    monkeypatch.setattr(source.os, "stat", lambda *a, **kw: root(stat(*a, **kw)))
    path = tmp_path / "claim.json"
    path.write_bytes(b"dummy-private-source")
    path.chmod(0o600)
    return path


@pytest.mark.parametrize("role", source.ROLES)
def test_fixed_role_reads_exact_bounded_bytes_without_output(private, role, capsys):
    path = private.with_name(source.plans.TARGETS[role][1])
    if path != private:
        private.rename(path)
    before = path.stat()
    assert source.acquire(role) == b"dummy-private-source"
    assert path.stat().st_ino == before.st_ino and path.read_bytes() == b"dummy-private-source"
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("kind", ["missing", "symlink", "hardlink", "public", "directory",
                                   "fifo", "empty", "oversize", "owner"])
def test_unsafe_source_denied_without_read_repair_or_removal(private, kind, monkeypatch):
    if kind in ("missing", "symlink", "directory", "fifo"):
        private.unlink()
    if kind == "symlink":
        private.symlink_to(private.with_name("absent"))
    elif kind == "directory":
        private.mkdir()
    elif kind == "fifo":
        os.mkfifo(private, 0o600)
    elif kind == "hardlink":
        os.link(private, private.with_name("alias"))
    elif kind == "public":
        private.chmod(0o644)
    elif kind in ("empty", "oversize"):
        private.write_bytes(b"" if kind == "empty" else b"x" * 8193)
    elif kind == "owner":
        current = source.os.fstat

        def wrong_owner(fd):
            item = current(fd)
            item.st_uid = 53001
            return item

        monkeypatch.setattr(source.os, "fstat", wrong_owner)
    before = private.lstat() if kind != "missing" else None
    monkeypatch.setattr(source.os, "read", lambda *_: pytest.fail("Unsafe source read"))
    with pytest.raises(ValueError, match=source.ERROR):
        source.acquire("claim")
    assert (private.lstat() if kind != "missing" else None) == before


@pytest.mark.parametrize("change", ["replace", "rewrite", "truncate", "chmod", "link"])
def test_source_changed_during_read_never_delivered(private, monkeypatch, change):
    read = os.read
    changed = False

    def mutate(fd, size):
        nonlocal changed
        result = read(fd, size)
        if not changed:
            changed = True
            if change == "replace":
                private.rename(private.with_name("retained"))
                private.write_bytes(b"dummy-private-source")
                private.chmod(0o600)
            elif change in ("rewrite", "truncate"):
                private.write_bytes(b"x" * (20 if change == "rewrite" else 1))
            elif change == "chmod":
                private.chmod(0o644)
            else:
                os.link(private, private.with_name("alias"))
        return result

    monkeypatch.setattr(source.os, "read", mutate)
    with pytest.raises(ValueError, match=source.ERROR):
        source.acquire("claim")
    assert private.exists()


def test_short_reads_complete_and_all_descriptors_close(private, monkeypatch):
    read, close = os.read, os.close
    closed = []
    monkeypatch.setattr(source.os, "read", lambda fd, size: read(fd, min(size, 3)))

    def record(fd):
        closed.append(fd)
        close(fd)

    monkeypatch.setattr(source.os, "close", record)
    assert source.acquire("claim") == b"dummy-private-source"
    assert len(closed) == 2 and len(set(closed)) == 2
    for fd in closed:
        with pytest.raises(OSError):
            os.fstat(fd)


@pytest.mark.parametrize("fault", ["platform", "uid", "actions", "repo", "optin",
                                   "candidate", "path", "type"])
def test_guard_refuses_before_host_access(private, monkeypatch, fault):
    if fault == "platform":
        monkeypatch.setattr(source.sys, "platform", "darwin")
    elif fault == "uid":
        monkeypatch.setattr(source.os, "geteuid", lambda: 501)
    for label, key in (("actions", "GITHUB_ACTIONS"), ("repo", "GITHUB_REPOSITORY"),
                        ("optin", "CIQ_AGENT_SERVICE_JOURNEY_TEST")):
        if fault == label:
            monkeypatch.setenv(key, "wrong")
    monkeypatch.setattr(source, "directory", lambda: pytest.fail("Host accessed"))
    role = {"candidate": "candidate", "path": "../claim", "type": None}.get(fault, "claim")
    with pytest.raises(ValueError, match=source.ERROR):
        source.acquire(role)


@pytest.mark.parametrize("error", [OSError, KeyboardInterrupt])
def test_read_failure_closes_descriptors_without_output(private, monkeypatch, capsys, error):
    closed, close = [], os.close

    def deny(*_):
        raise error("PRIVATE")

    def record(fd):
        closed.append(fd)
        close(fd)

    monkeypatch.setattr(source.os, "read", deny)
    monkeypatch.setattr(source.os, "close", record)
    with pytest.raises(KeyboardInterrupt if error is KeyboardInterrupt else ValueError) as caught:
        source.acquire("claim")
    if error is OSError:
        assert str(caught.value) == source.ERROR and caught.value.__suppress_context__
    assert len(closed) == 2 and private.exists() and capsys.readouterr() == ("", "")


def test_source_failure_permanently_blocks_later_delivery_and_start(monkeypatch):
    service = journey.Services([("claim", "claim.service")], SimpleNamespace(check=lambda: None))
    monkeypatch.setattr(journey.quiescence, "verify_stopped", lambda _: None)

    def deny(_):
        raise ValueError(source.ERROR)

    monkeypatch.setattr(source, "acquire", deny)
    monkeypatch.setattr(journey.plans, "stage", lambda *_: pytest.fail("Source failure delivered"))
    with pytest.raises(ValueError, match=source.ERROR):
        service.deliver_private("claim")
    with pytest.raises(RuntimeError, match="activation blocked"):
        service.deliver_private("claim")
    with pytest.raises(RuntimeError, match="activation blocked"):
        service.start("claim")


def test_direct_credential_delivery_cannot_bypass_source(monkeypatch):
    service = journey.Services([("claim", "claim.service")], SimpleNamespace(check=lambda: None))
    monkeypatch.setattr(journey.plans, "stage", lambda *_: pytest.fail("Credential bypass"))
    with pytest.raises(ValueError, match=source.ERROR):
        service.deliver("claim", {"password": "dummy"})


@pytest.mark.parametrize("fault", ["lease", "quiescence"])
def test_evidence_rechecked_after_acquisition_before_publication(monkeypatch, fault):
    acquired = False

    def check(which):
        if acquired and which == fault:
            raise ValueError("Evidence changed")

    service = journey.Services([("claim", "claim.service")],
                               SimpleNamespace(check=lambda: check("lease")))
    monkeypatch.setattr(journey.quiescence, "verify_stopped", lambda _: check("quiescence"))

    def acquire(_):
        nonlocal acquired
        acquired = True
        return b"dummy"

    monkeypatch.setattr(source, "acquire", acquire)
    monkeypatch.setattr(journey.plans, "stage", lambda *_: pytest.fail("Stale evidence published"))
    with pytest.raises(ValueError, match="Evidence changed"):
        service.deliver_private("claim")
    assert service.blocked and not service.delivered


def test_journey_refuses_existing_source_before_mutation(tmp_path, monkeypatch):
    monkeypatch.setenv("CIQ_AGENT_SERVICE_JOURNEY_TEST", "1")
    monkeypatch.setenv("CIQ_AGENT_CONTROLLER_TEST", "1")
    monkeypatch.setenv("TEST_DATABASE_URL", journey.EXPECTED)
    monkeypatch.setattr(journey.packages, "guard", lambda: None)
    path = tmp_path / "source"
    path.symlink_to(tmp_path / "absent")
    monkeypatch.setattr(source, "SOURCE", path)
    with pytest.raises(SystemExit, match="existing supervisor credential source"):
        journey.guard()
    assert path.is_symlink()
