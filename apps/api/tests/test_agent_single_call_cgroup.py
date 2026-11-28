"""Offline ownership and uncertainty controls; no real cgroup or host mutation."""

import errno
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ciq_api import agent_single_call_cgroup as m


@pytest.fixture
def kernel(monkeypatch):
    state = SimpleNamespace(events=b"populated 0\nfrozen 0\n", kind=b"domain\n",
                            identity=(1, 20), clock=0.0, written=[], closed=[])
    names = {30: "cgroup.type", 31: "cgroup.events", 32: "cgroup.kill"}
    monkeypatch.setattr(m.sys, "platform", "linux")
    monkeypatch.setattr(m.os, "getresuid", lambda: (0, 0, 0), raising=False)
    monkeypatch.setattr(m, "open_parent", lambda: 10)
    monkeypatch.setattr(m, "kernel_file", lambda fd, **kw: (1, 10) if fd == 10 else (1, 20))
    monkeypatch.setattr(m.os, "mkdir", Mock())
    monkeypatch.setattr(m.os, "open", lambda name, *args, **kw: (
        {value: key for key, value in names.items()}.get(name, 20)))
    monkeypatch.setattr(m.os, "stat", lambda path, **kw: SimpleNamespace(
        st_mode=0o40755, st_dev=1, st_ino=10 if path == m.PARENT else state.identity[1]))
    monkeypatch.setattr(m.os, "read", lambda fd, count: (
        state.kind if names[fd] == "cgroup.type" else state.events))
    monkeypatch.setattr(m.os, "write", lambda fd, raw: state.written.append((fd, raw)) or len(raw))
    monkeypatch.setattr(m.os, "close", state.closed.append)
    monkeypatch.setattr(m, "monotonic", lambda: state.clock)
    monkeypatch.setattr(m, "sleep", lambda seconds: setattr(state, "clock", state.clock + seconds))
    return state


@pytest.mark.parametrize("role", ["receipt", "provider", "custody"])
def test_reserve_original_namespace_and_consume_cleanup_once(kernel, role):
    group = m.OwnedSingleCallCgroup(role)
    assert group.name.startswith("ciq-single-call-") and group.name.endswith("-" + role)
    group.prepare()
    assert group.quiescent()
    assert group.stop() and group.stop()
    assert kernel.written == [(32, b"1\n")]
    with pytest.raises(ValueError, match=m.ERROR):
        group.prepare()
    assert group.quiescent()  # Rejected reuse preserves original cleanup ownership.
    group.close()
    group.close()
    assert kernel.closed.count(10) == kernel.closed.count(20) == 1


@pytest.mark.parametrize("role", ["root", "../custody", "custody.service", None, 53002])
def test_no_external_path_or_identity_selector(role):
    with pytest.raises(ValueError, match=m.ERROR):
        m.OwnedSingleCallCgroup(role)


@pytest.mark.parametrize("fault", ["platform", "uid", "collision", "open", "nonempty"])
def test_failed_preparation_never_adopts_or_kills(kernel, monkeypatch, fault):
    group = m.OwnedSingleCallCgroup("custody")
    if fault == "platform":
        monkeypatch.setattr(m.sys, "platform", "darwin")
    elif fault == "uid":
        monkeypatch.setattr(m.os, "getresuid", lambda: (0, 53002, 0))
    elif fault == "collision":
        monkeypatch.setattr(m.os, "mkdir", Mock(side_effect=FileExistsError))
    elif fault == "open":
        monkeypatch.setattr(m.os, "open", Mock(side_effect=PermissionError))
    else:
        kernel.events = b"populated 1\n"
    with pytest.raises(ValueError, match=m.ERROR):
        group.prepare()
    assert not group.stop() and not group.quiescent() and not kernel.written
    with pytest.raises(ValueError, match=m.ERROR):
        group.prepare()
    group.close()


@pytest.mark.parametrize("raw", [b"", b"populated 0\npopulated 0\n", b"populated\n",
                                  b"frozen 0\n", b"populated 2\n", b"populated 0 extra\n",
                                  b"populated 0\nunknown 0\n", b"x" * 4097])
def test_malformed_population_is_never_empty(kernel, raw):
    group = m.OwnedSingleCallCgroup("receipt")
    group.prepare()
    kernel.events = raw
    assert not group.quiescent() and not group.stop() and not group.stop()
    assert kernel.written == [(32, b"1\n")]


@pytest.mark.parametrize("fault", ["replacement", "missing", "unreadable", "threaded"])
def test_changed_namespace_or_missing_evidence_cannot_be_killed(kernel, monkeypatch, fault):
    group = m.OwnedSingleCallCgroup("provider")
    group.prepare()
    if fault == "replacement":
        kernel.identity = (1, 21)
    elif fault == "missing":
        monkeypatch.setattr(m.os, "stat", Mock(side_effect=FileNotFoundError))
    elif fault == "unreadable":
        monkeypatch.setattr(m.os, "read", Mock(side_effect=PermissionError))
    else:
        kernel.kind = b"threaded\n"
    assert not group.quiescent() and not group.stop() and not kernel.written


@pytest.mark.parametrize("fault", ["write", "short", "lost-ack", "kill-missing"])
def test_failed_kill_is_consumed_without_retry(kernel, monkeypatch, fault):
    group = m.OwnedSingleCallCgroup("custody")
    group.prepare()
    def write(fd, raw):
        kernel.written.append((fd, raw))
        if fault == "short":
            return 1
        raise OSError(errno.EIO, "PRIVATE")
    monkeypatch.setattr(m.os, "write", write)
    if fault == "kill-missing":
        monkeypatch.setattr(m.os, "open", Mock(side_effect=FileNotFoundError))
    assert not group.stop() and not group.stop()
    assert len(kernel.written) == (0 if fault == "kill-missing" else 1)


def test_nonempty_tree_times_out_without_retry(kernel):
    group = m.OwnedSingleCallCgroup("receipt")
    group.prepare()
    kernel.events = b"populated 1\nfrozen 0\n"
    assert not group.stop() and kernel.clock <= 1.02
    kernel.events = b"populated 0\n"
    assert group.quiescent() and not group.stop() and len(kernel.written) == 1


@pytest.mark.parametrize("clock", [float("nan"), float("inf"), -1, True])
def test_bad_clock_fails_cleanup_confirmation(kernel, monkeypatch, clock):
    group = m.OwnedSingleCallCgroup("receipt")
    group.prepare()
    values = iter([0.0, clock])
    monkeypatch.setattr(m, "monotonic", lambda: next(values))
    assert not group.stop() and not group.stop()


def test_empty_after_actual_kill_observation(kernel, monkeypatch):
    group = m.OwnedSingleCallCgroup("custody")
    group.prepare()
    kernel.events = b"populated 1\n"
    def wait(seconds):
        kernel.clock += seconds
        kernel.events = b"populated 0\nfrozen 0\n"
    monkeypatch.setattr(m, "sleep", wait)
    assert group.stop() and kernel.clock == 0.02
    group.close()
    assert not group.quiescent() and not group.stop()


@pytest.mark.parametrize("action", ["stop", "close"])
def test_stopped_or_closed_object_cannot_allocate(kernel, action):
    group = m.OwnedSingleCallCgroup("receipt")
    getattr(group, action)()
    with pytest.raises(ValueError, match=m.ERROR):
        group.prepare()
    m.os.mkdir.assert_not_called()


def test_late_empty_observation_cannot_confirm_cleanup(kernel, monkeypatch):
    group = m.OwnedSingleCallCgroup("receipt")
    group.prepare()
    values = iter([0.0, 0.0, 1.01])
    monkeypatch.setattr(m, "monotonic", lambda: next(values))
    assert not group.stop() and not group.stop()


@pytest.mark.parametrize("mode,uid,magic,result", [
    (0o100644, 0, 0x63677270, 0), (0o100644, 0, 0x01021994, 0),
    (0o100666, 0, 0x63677270, 0), (0o100644, 53002, 0x63677270, 0),
    (0o120777, 0, 0x63677270, 0), (0o100644, 0, 0x63677270, -1),
])
def test_real_kernel_file_guard_abi_and_denials(monkeypatch, mode, uid, magic, result):
    import ctypes
    monkeypatch.setattr(m.os, "fstat", lambda fd: SimpleNamespace(
        st_mode=mode, st_uid=uid, st_dev=1, st_ino=20))
    class Call:
        def __call__(self, fd, buffer):
            assert fd == 7 and len(buffer) == 4096
            ctypes.c_long.from_buffer(buffer).value = magic
            return result
    call = Call()
    monkeypatch.setattr(m.ctypes, "CDLL", lambda *a, **kw: SimpleNamespace(fstatfs=call))
    if mode == 0o100644 and uid == 0 and magic == 0x63677270 and result == 0:
        assert m.kernel_file(7) == (1, 20)
        assert call.argtypes == [ctypes.c_int, ctypes.c_void_p] and call.restype == ctypes.c_int
    else:
        with pytest.raises(ValueError, match=m.ERROR):
            m.kernel_file(7)


@pytest.mark.parametrize("fault", [None, "symlink", "filesystem"])
def test_parent_walk_uses_only_fixed_nofollow_components_and_closes_on_fault(monkeypatch, fault):
    opened, closed = [], []
    def open_directory(path, flags, **kwargs):
        assert flags == m.DIRECTORY and flags & m.os.O_NOFOLLOW
        if fault == "symlink" and path == "cgroup":
            raise OSError(errno.ELOOP, "dummy symlink")
        fd = len(opened) + 10
        assert kwargs == ({} if path == "/" else {"dir_fd": fd - 1})
        opened.append(path)
        return fd
    monkeypatch.setattr(m.os, "open", open_directory)
    monkeypatch.setattr(m.os, "close", closed.append)
    monkeypatch.setattr(m, "kernel_file", Mock(
        return_value=(1, 20), side_effect=ValueError(m.ERROR) if fault == "filesystem" else None))
    if fault:
        with pytest.raises((OSError, ValueError)):
            m.open_parent()
        assert len(closed) == len(opened) and len(set(closed)) == len(closed)
    else:
        assert m.open_parent() == 14
        assert opened == ["/", "sys", "fs", "cgroup", "system.slice"]
        assert closed == [10, 11, 12, 13]
