"""Offline gate state/fault controls; real pidfd composition runs in Linux CI."""

import array
import errno
import os
import socket
import stat
import struct
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ciq_api import agent_single_call_launch as m


class Endpoint:
    def __init__(self, fd):
        self.fd = fd
        self.send = Mock(return_value=len(m.START))
        self.recvmsg = Mock()
        self.close = Mock()
        self.detach = Mock()
        self.setblocking = Mock()
        self.setsockopt = Mock()

    def fileno(self):
        return self.fd


@contextmanager
def prepared(monkeypatch):
    # These are model handles, not live processes or platform socket constants.
    for name, value in (("SO_PASSCRED", 16), ("SCM_CREDENTIALS", 2),
                        ("MSG_CMSG_CLOEXEC", 0x40000000), ("MSG_NOSIGNAL", 0x4000)):
        monkeypatch.setattr(m.socket, name, value, raising=False)
    for name, value in (("P_PIDFD", 3), ("WNOWAIT", 0x1000000), ("CLD_EXITED", 1),
                        ("CLD_KILLED", 2), ("CLD_DUMPED", 3)):
        monkeypatch.setattr(m.os, name, value, raising=False)
    monkeypatch.setattr(m.sys, "platform", "linux")
    monkeypatch.setattr(m.os, "getresuid", lambda: (0, 0, 0), raising=False)
    monkeypatch.setattr(m.os, "getresgid", lambda: (0, 0, 0), raising=False)
    host, child = Endpoint(101), Endpoint(102)
    monkeypatch.setattr(m.socket, "socketpair", lambda *_: (host, child))
    monkeypatch.setattr(m.os, "fstat", lambda fd: SimpleNamespace(
        st_mode=stat.S_IFSOCK, st_dev=1, st_ino=fd))
    monkeypatch.setattr(m.os, "get_inheritable", lambda _: False)
    monkeypatch.setattr(m.os, "readlink", lambda _: "anon_inode:[pidfd]")
    monkeypatch.setattr(m.os, "open", lambda *_: 104)
    monkeypatch.setattr(m.os, "read", lambda *_: b"pos:\t0\nPid:\t777\nNSpid:\t777\n")
    closed = Mock()
    monkeypatch.setattr(m.os, "close", closed)
    waited = Mock(return_value=None)
    monkeypatch.setattr(m.os, "waitid", waited, raising=False)
    killed = Mock()
    monkeypatch.setattr(m.signal, "pidfd_send_signal", killed, raising=False)
    packet = [m.READY, [
        (socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array("i", [103]).tobytes()),
        (socket.SOL_SOCKET, socket.SCM_CREDENTIALS, struct.pack("3i", 777, 0, 0)),
    ], socket.MSG_CMSG_CLOEXEC, None]
    host.recvmsg.return_value = packet
    launch = m.OwnedSingleCallLaunch()
    try:
        launch.prepare()
        assert launch.take_descriptor() == 102
        launch.release_descriptor()
        yield SimpleNamespace(launch=launch, host=host, child=child, packet=packet,
                              waited=waited, killed=killed, closed=closed)
    finally:
        launch.close()


def exited(code=0, kind=None):
    return SimpleNamespace(si_code=m.os.CLD_EXITED if kind is None else kind,
                           si_status=code, si_pid=777)


def test_receive_is_nonblocking_and_start_requires_original_live_handle(monkeypatch):
    with prepared(monkeypatch) as f:
        with pytest.raises(ValueError, match=m.ERROR):
            f.launch.authorize()
        f.host.recvmsg.side_effect = BlockingIOError(errno.EAGAIN, "dummy")
        assert f.launch.receive() is False
        f.host.recvmsg.side_effect = None
        assert f.launch.receive() and f.launch.receive()
        assert f.host.recvmsg.call_count == 2
        assert f.waited.call_args.args == (m.os.P_PIDFD, 103,
                                          os.WEXITED | os.WNOHANG | m.os.WNOWAIT)
        f.launch.authorize()
        f.host.send.assert_called_once_with(m.START, socket.MSG_DONTWAIT | socket.MSG_NOSIGNAL)
        with pytest.raises(ValueError, match=m.ERROR):
            f.launch.authorize()
        assert f.launch.observe() == m.WaiterStatus(True, None)
        with pytest.raises(ValueError, match=m.ERROR):
            f.launch.reap()
        assert not f.launch._reaped
        f.waited.return_value = exited()
        assert f.launch.reap() == m.WaiterStatus(False, 0)
        with pytest.raises(ValueError, match=m.ERROR):
            f.launch.reap()
        f.killed.assert_not_called()


@pytest.mark.parametrize("mode", ["packet", "eof", "truncated", "unknown", "rights", "creds",
                                   "uid", "pid", "notpidfd", "foreign", "inherited"])
def test_malformed_or_unowned_handoff_never_authorizes_and_closes_rights(monkeypatch, mode):
    with prepared(monkeypatch) as f:
        if mode == "packet":
            f.packet[0] = b"PRIVATE dummy unexpected content"
        elif mode == "eof":
            f.packet[0] = b""
        elif mode == "truncated":
            f.packet[2] |= socket.MSG_CTRUNC
        elif mode == "unknown":
            f.packet[1].append((socket.SOL_SOCKET, 999, b""))
        elif mode == "rights":
            f.packet[1][0] = (socket.SOL_SOCKET, socket.SCM_RIGHTS,
                               array.array("i", [103, 105]).tobytes())
        elif mode == "creds":
            f.packet[1].pop()
        elif mode == "uid":
            f.packet[1][1] = (socket.SOL_SOCKET, socket.SCM_CREDENTIALS,
                               struct.pack("3i", 777, 53002, 0))
        elif mode == "pid":
            monkeypatch.setattr(m.os, "read", lambda *_: b"Pid:\t778\n")
        elif mode == "notpidfd":
            monkeypatch.setattr(m.os, "readlink", lambda _: "pipe:[777]")
        elif mode == "foreign":
            f.waited.side_effect = ChildProcessError("PRIVATE dummy")
        elif mode == "inherited":
            monkeypatch.setattr(m.os, "get_inheritable", lambda fd: fd == 103)
        with pytest.raises(ValueError, match="^" + m.ERROR + "$"):
            f.launch.receive()
        with pytest.raises(ValueError, match=m.ERROR):
            f.launch.authorize()
        f.host.send.assert_not_called()
        f.launch.close()
        f.closed.assert_any_call(103)
        if mode == "rights":
            f.closed.assert_any_call(105)


@pytest.mark.parametrize("mode", ["short", "lost", "cancel"])
def test_uncertain_start_is_consumed_but_original_cleanup_remains_available(monkeypatch, mode):
    with prepared(monkeypatch) as f:
        assert f.launch.receive()
        if mode == "short":
            f.host.send.return_value = 1
        else:
            f.host.send.side_effect = (
                OSError("PRIVATE dummy") if mode == "lost" else KeyboardInterrupt())
        with pytest.raises(KeyboardInterrupt if mode == "cancel" else ValueError):
            f.launch.authorize()
        with pytest.raises(ValueError, match=m.ERROR):
            f.launch.authorize()
        assert f.host.send.call_count == 1
        f.launch.disconnect()
        f.launch.disconnect()
        assert f.launch.observe().running
        f.launch.terminate()
        f.killed.assert_called_once_with(103, m.signal.SIGKILL)
        with pytest.raises(ValueError, match=m.ERROR):
            f.launch.terminate()
        f.waited.return_value = exited(9, m.os.CLD_KILLED)
        assert f.launch.reap() == m.WaiterStatus(False, 137)


def test_expired_waiter_remains_owned_and_reapable_but_cannot_start(monkeypatch):
    with prepared(monkeypatch) as f:
        f.waited.return_value = exited(125)
        with pytest.raises(ValueError, match=m.ERROR):
            f.launch.receive()
        with pytest.raises(ValueError, match=m.ERROR):
            f.launch.authorize()
        assert f.launch.reap() == m.WaiterStatus(False, 125)


def test_lost_reap_ack_is_terminal_and_never_waits_again(monkeypatch):
    with prepared(monkeypatch) as f:
        assert f.launch.receive()
        f.waited.side_effect = [exited(0), OSError("PRIVATE dummy")]
        with pytest.raises(OSError):
            f.launch.reap()
        count = f.waited.call_count
        with pytest.raises(ValueError, match=m.ERROR):
            f.launch.reap()
        assert f.waited.call_count == count


def test_descriptor_handoff_and_preparation_are_consumed_once(monkeypatch):
    with prepared(monkeypatch) as f:
        with pytest.raises(ValueError, match=m.ERROR):
            f.launch.take_descriptor()
        with pytest.raises(ValueError, match=m.ERROR):
            f.launch.prepare()
        f.launch.release_descriptor()
        assert f.child.close.call_count == 1


def test_replaced_waiter_handle_is_never_signaled_or_reaped(monkeypatch):
    with prepared(monkeypatch) as f:
        assert f.launch.receive()
        monkeypatch.setattr(m.os, "fstat", lambda fd: SimpleNamespace(
            st_dev=1, st_ino=999 if fd == 103 else fd, st_mode=stat.S_IFSOCK))
        with pytest.raises(ValueError, match=m.ERROR):
            f.launch.terminate()
        with pytest.raises(ValueError, match=m.ERROR):
            f.launch.reap()
        f.killed.assert_not_called()


def test_root_linux_guard_rejects_before_socket_allocation(monkeypatch):
    monkeypatch.setattr(m.sys, "platform", "darwin")
    factory = Mock()
    monkeypatch.setattr(m.socket, "socketpair", factory)
    launch = m.OwnedSingleCallLaunch()
    with pytest.raises(ValueError, match=m.ERROR):
        launch.prepare()
    factory.assert_not_called()
