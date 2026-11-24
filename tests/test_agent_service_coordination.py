"""Real advisory locks on disposable files, without service or host mutations."""

import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

from scripts import agent_service_coordination as coordination
from scripts import test_agent_service_journey as journey


@pytest.fixture
def allowed(tmp_path, monkeypatch):
    monkeypatch.setattr(coordination.sys, "platform", "linux")
    monkeypatch.setattr(coordination.os, "geteuid", lambda: 0)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_REPOSITORY", "hulagerushikesh/cashlessiq")
    monkeypatch.setenv("CIQ_AGENT_SERVICE_JOURNEY_TEST", "1")
    monkeypatch.setattr(coordination, "directory", lambda: os.open(tmp_path, os.O_RDONLY))
    # Map only our ordinary test-file ownership to the fixed root metadata;
    # descriptors, flock, inode/link identity and permission checks stay real.
    fstat, stat = os.fstat, os.stat

    def root(item):
        values = list(item)
        values[4:6] = [0, 0]
        return os.stat_result(values)

    monkeypatch.setattr(coordination.os, "fstat", lambda fd: root(fstat(fd)))
    monkeypatch.setattr(coordination.os, "stat", lambda *a, **kw: root(stat(*a, **kw)))
    return tmp_path / coordination.NAME


def test_competitor_denied_and_same_inode_reused_only_after_lease_closes(allowed):
    with coordination.exclusive() as first:
        first.check()
        inode = allowed.stat().st_ino
        with pytest.raises(ValueError, match=coordination.ERROR), coordination.exclusive():
            pytest.fail("Contending supervisor entered")
        first.check()
    assert allowed.stat().st_ino == inode and allowed.read_bytes() == b""
    with pytest.raises(ValueError, match=coordination.ERROR):
        first.check()
    with coordination.exclusive() as second:
        second.check()
        assert allowed.stat().st_ino == inode
        assert not os.get_inheritable(second.fd)


def test_exception_releases_lock_but_preserves_lock_file(allowed):
    with pytest.raises(RuntimeError, match="sentinel"), coordination.exclusive():
        raise RuntimeError("sentinel")
    with coordination.exclusive() as lease:
        lease.check()
    assert allowed.exists()


def test_separate_process_cannot_enter_until_supervisor_releases(allowed):
    code = """
import fcntl, os, sys
fd = os.open(sys.argv[1], os.O_RDONLY)
try:
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    sys.exit(23)
finally:
    os.close(fd)
"""

    def contender():
        result = subprocess.run([sys.executable, "-I", "-B", "-c", code, str(allowed)],
                                capture_output=True, timeout=5)
        assert result.stdout == result.stderr == b""
        return result.returncode

    with coordination.exclusive() as lease:
        assert contender() == 23
        lease.check()
    assert contender() == 0


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "public", "contents", "directory"])
def test_existing_unsafe_lock_is_not_repaired_or_removed(allowed, kind):
    original = allowed.parent / "original"
    original.write_bytes(b"PRIVATE")
    if kind == "symlink":
        allowed.symlink_to(original)
    elif kind == "hardlink":
        os.link(original, allowed)
    elif kind == "directory":
        allowed.mkdir()
    else:
        allowed.write_bytes(b"PRIVATE" if kind == "contents" else b"")
        allowed.chmod(0o600 if kind == "contents" else 0o644)
    before = allowed.lstat()
    with pytest.raises(ValueError, match=coordination.ERROR) as error, coordination.exclusive():
        pytest.fail("Unsafe lock accepted")
    assert allowed.lstat() == before and original.read_bytes() == b"PRIVATE"
    assert "PRIVATE" not in str(error.value)


@pytest.mark.parametrize("fault", ["replacement", "links", "permissions", "contents", "pid"])
def test_active_lease_denies_identity_or_metadata_change(allowed, fault, monkeypatch):
    with coordination.exclusive() as lease:
        if fault == "replacement":
            allowed.rename(allowed.parent / "retained")
            allowed.touch(mode=0o600)
        elif fault == "links":
            os.link(allowed, allowed.parent / "alias")
        elif fault == "permissions":
            allowed.chmod(0o644)
        elif fault == "contents":
            allowed.write_bytes(b"PRIVATE")
        else:
            monkeypatch.setattr(coordination.os, "getpid", lambda: lease.pid + 1)
        with pytest.raises(ValueError, match=coordination.ERROR):
            lease.check()


@pytest.mark.parametrize("fault", ["platform", "uid", "actions", "repo", "optin"])
def test_entry_denies_before_filesystem_access(monkeypatch, fault):
    monkeypatch.setattr(coordination.sys, "platform", "darwin" if fault == "platform" else "linux")
    monkeypatch.setattr(coordination.os, "geteuid", lambda: 501 if fault == "uid" else 0)
    for key, value, label in (("GITHUB_ACTIONS", "true", "actions"),
                              ("GITHUB_REPOSITORY", "hulagerushikesh/cashlessiq", "repo"),
                              ("CIQ_AGENT_SERVICE_JOURNEY_TEST", "1", "optin")):
        monkeypatch.setenv(key, "wrong" if fault == label else value)
    monkeypatch.setattr(coordination, "directory", lambda: pytest.fail("Host accessed"))
    with pytest.raises(ValueError, match=coordination.ERROR), coordination.exclusive():
        pytest.fail("Unauthorized supervisor entered")


@pytest.mark.parametrize("failure", ["lease", "quiescence", "publication", "interrupt"])
def test_uncertain_delivery_permanently_blocks_all_activation(monkeypatch, failure):
    def deny(*_):
        if failure == "interrupt":
            raise KeyboardInterrupt
        raise ValueError("PRIVATE")

    lease = SimpleNamespace(check=deny if failure == "lease" else lambda: None)
    services = journey.Services([("claim", "claim.service")], lease)
    monkeypatch.setattr(journey.quiescence, "verify_stopped",
                        deny if failure == "quiescence" else lambda _: None)
    monkeypatch.setattr(journey.plans, "stage",
                        deny if failure in ("publication", "interrupt") else lambda *_: None)
    monkeypatch.setattr(journey.source, "acquire", lambda _: b"{}")
    monkeypatch.setattr(journey.policy, "run", lambda *_: pytest.fail("Service activated"))
    with pytest.raises(KeyboardInterrupt if failure == "interrupt" else ValueError):
        services.deliver_private("claim")
    lease.check = lambda: None
    monkeypatch.setattr(journey.quiescence, "verify_stopped", lambda _: None)
    monkeypatch.setattr(journey.plans, "stage", lambda *_: pytest.fail("Delivery retried"))
    with pytest.raises(RuntimeError, match="activation blocked"):
        services.deliver_private("claim")
    with pytest.raises(RuntimeError, match="activation blocked"):
        services.start("claim")


@pytest.mark.parametrize("delivered", [set(), {"custody"}, {"candidate"}])
def test_custody_needs_both_confirmed_plans_before_any_service_access(monkeypatch, delivered):
    services = journey.Services([("custody", "custody.service")],
                                SimpleNamespace(check=lambda: None))
    services.delivered.update(delivered)
    monkeypatch.setattr(journey.quiescence, "verify_stopped",
                        lambda _: pytest.fail("Incomplete delivery reached service"))
    with pytest.raises(RuntimeError, match="confirmed plan delivery"):
        services.start("custody")


@pytest.mark.parametrize("error", [RuntimeError, KeyboardInterrupt])
def test_uncertain_start_blocks_later_starts_but_still_allows_stop(monkeypatch, error):
    services = journey.Services([("claim", "claim.service")],
                                SimpleNamespace(check=lambda: None))
    services.delivered.add("claim")
    monkeypatch.setattr(journey.quiescence, "verify_stopped", lambda _: None)
    monkeypatch.setattr(journey.policy, "empty", lambda _: True)
    monkeypatch.setattr(journey.policy, "value", lambda *_: "inactive")

    def uncertain(*_):
        raise error("Start result unknown")

    monkeypatch.setattr(journey.policy, "run", uncertain)
    with pytest.raises(error, match="Start result unknown"):
        services.start("claim")
    calls = []
    monkeypatch.setattr(journey.policy, "run", lambda *args: calls.append(args))
    with pytest.raises(RuntimeError, match="activation blocked"):
        services.start("claim")
    services.stop()
    assert calls == [("systemctl", "stop", "claim.service")]
