"""Original waiter handoff gate; no process creation, consent or host adapter.

Retain before allocating the immutable native bootstrap. Only grant START after
its original direct-child pidfd was received and checked. A lost start return
never loses that handle. Serialized ownership and externally bounded calls are
required; this object does not replace original application-cgroup cleanup.
"""

import array
import errno
import os
import signal
import socket
import stat
import struct
import sys
from contextlib import suppress
from dataclasses import dataclass

ERROR = "single_call_launch_unavailable"
READY = b"single_call_waiter_ready\n"
START = b"single_call_start\n"


def require(value):
    if not value:
        raise ValueError(ERROR)


@dataclass(frozen=True)
class WaiterStatus:
    running: bool
    exit_code: int | None


class OwnedSingleCallLaunch:
    """Fresh socket pair, one descriptor transfer, one START, original pidfd only.

    prepare -> take_descriptor -> attempt bootstrap creation -> release_descriptor
    (in finally) -> receive until ready -> authorize exactly once. Creation is
    deliberately not implemented here. Even if creation raises, receive may
    recover ownership, but that uncertain attempt must NEVER authorize/relaunch.
    disconnect, original group stop, observe/reap and close remain available
    after a failed/lost START acknowledgment. No PID/name lookup or retry API.
    """

    def __init__(self):
        self._host = self._child = None
        self._sockets = {}
        self._fds = []
        self._fd_identities = {}
        self._pidfd = self._pid_identity = None
        self._used = self._offered = self._released = self._received = False
        self._authorized = self._failed = self._closed = False
        self._signaled = self._reaped = False

    def _verify_socket(self, endpoint):
        fd = endpoint.fileno()
        info = os.fstat(fd)
        require(stat.S_ISSOCK(info.st_mode)
                and (info.st_dev, info.st_ino) == self._sockets[fd]
                and not os.get_inheritable(fd))

    def _verify_pidfd(self):
        require(self._pidfd is not None and self._pid_identity is not None and not self._closed)
        info = os.fstat(self._pidfd)
        require((info.st_dev, info.st_ino) == self._pid_identity
                and not os.get_inheritable(self._pidfd))

    def prepare(self):
        require(not self._used and not self._closed)
        self._used = True
        try:
            require(sys.platform == "linux" and os.getresuid() == (0, 0, 0)
                    and os.getresgid() == (0, 0, 0))
            self._host, self._child = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
            for endpoint in (self._host, self._child):
                info = os.fstat(endpoint.fileno())
                self._sockets[endpoint.fileno()] = (info.st_dev, info.st_ino)
                self._verify_socket(endpoint)
            require(len(set(self._sockets.values())) == 2)
            self._host.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
            self._host.setblocking(False)
        except BaseException as error:
            self._failed = True
            self.close()
            if isinstance(error, Exception):
                raise ValueError(ERROR) from None
            raise

    def take_descriptor(self):
        require(self._used and not self._failed and not self._closed and not self._offered)
        self._offered = True
        try:
            self._verify_socket(self._child)
            return self._child.fileno()
        except BaseException as error:
            self._failed = True
            if isinstance(error, Exception):
                raise ValueError(ERROR) from None
            raise

    def release_descriptor(self):
        require(self._offered and not self._closed)
        if self._released:
            return
        self._released = True  # A lost close ACK must never close a reused fd.
        try:
            self._verify_socket(self._child)
            endpoint, self._child = self._child, None
            endpoint.close()
        except BaseException as error:
            self._failed = True
            if isinstance(error, Exception):
                raise ValueError(ERROR) from None
            raise

    def receive(self):
        require(self._released and not self._failed and not self._closed)
        if self._received:
            self._verify_pidfd()
            return True
        try:
            self._verify_socket(self._host)
            try:
                raw, ancillary, flags, _ = self._host.recvmsg(
                    128, socket.CMSG_SPACE(16) + socket.CMSG_SPACE(12),
                    socket.MSG_DONTWAIT | socket.MSG_CMSG_CLOEXEC,
                )
            except BlockingIOError as error:
                require(error.errno in (errno.EAGAIN, errno.EWOULDBLOCK))
                return False
            # Retain ALL installed rights before any packet validation can fail.
            credentials = []
            rights = 0
            known = True
            for level, kind, data in ancillary:
                if (level, kind) == (socket.SOL_SOCKET, socket.SCM_RIGHTS):
                    values = array.array("i")
                    values.frombytes(data[:len(data) - len(data) % values.itemsize])
                    self._fds.extend(values)
                    for fd in values:
                        info = os.fstat(fd)
                        self._fd_identities[fd] = (info.st_dev, info.st_ino)
                    rights += 1
                    known = known and len(data) == values.itemsize
                elif (level, kind) == (socket.SOL_SOCKET, socket.SCM_CREDENTIALS):
                    credentials.append(data)
                else:
                    known = False
            require(raw == READY and not flags & ~socket.MSG_CMSG_CLOEXEC and known
                    and rights == 1 and len(self._fds) == 1
                    and len(credentials) == 1 and len(credentials[0]) == 12)
            sender, uid, gid = struct.unpack("3i", credentials[0])
            require(sender > 0 and uid == gid == 0)
            fd = self._fds[0]
            require(not os.get_inheritable(fd)
                    and os.readlink(f"/proc/self/fd/{fd}") == "anon_inode:[pidfd]")
            info = os.open(f"/proc/self/fdinfo/{fd}", os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
            try:
                raw_info = os.read(info, 4097)
            finally:
                os.close(info)
            require(len(raw_info) <= 4096)
            rows = [row.split() for row in raw_info.splitlines() if row.startswith(b"Pid:")]
            require(rows == [[b"Pid:", str(sender).encode()]])
            # Kernel waitid rejects non-children. WNOWAIT never steals the status.
            result = os.waitid(os.P_PIDFD, fd, os.WEXITED | os.WNOHANG | os.WNOWAIT)
            require(result is None or result.si_pid == sender)
            identity = os.fstat(fd)
            self._pidfd = fd
            self._pid_identity = (identity.st_dev, identity.st_ino)
            self._received = True
            require(result is None)  # Exited waiter remains owned for cleanup, never START.
            return True
        except BaseException as error:
            self._failed = True
            if isinstance(error, Exception):
                raise ValueError(ERROR) from None
            raise

    def authorize(self):
        require(self._received and not self._authorized and not self._failed and not self._closed)
        self._authorized = True  # Consume before send, including lost ACK.
        try:
            self._verify_socket(self._host)
            self._verify_pidfd()
            require(self.observe() == WaiterStatus(True, None))
            require(self._host.send(START, socket.MSG_DONTWAIT | socket.MSG_NOSIGNAL) == len(START))
        except BaseException as error:
            self._failed = True
            if isinstance(error, Exception):
                raise ValueError(ERROR) from None
            raise

    def observe(self):
        require(not self._reaped)
        self._verify_pidfd()  # Remains available after an uncertain authorize.
        result = os.waitid(os.P_PIDFD, self._pidfd, os.WEXITED | os.WNOHANG | os.WNOWAIT)
        if result is None:
            return WaiterStatus(True, None)
        require(result.si_code in (os.CLD_EXITED, os.CLD_KILLED, os.CLD_DUMPED))
        return WaiterStatus(False, result.si_status if result.si_code == os.CLD_EXITED
                            else 128 + result.si_status)

    def reap(self):
        status = self.observe()
        require(not status.running)
        self._reaped = True  # Never re-wait after an uncertain reaping ACK.
        result = os.waitid(os.P_PIDFD, self._pidfd, os.WEXITED | os.WNOHANG)
        require(result is not None
                and result.si_code in (os.CLD_EXITED, os.CLD_KILLED, os.CLD_DUMPED))
        actual = result.si_status if result.si_code == os.CLD_EXITED else 128 + result.si_status
        require(actual == status.exit_code)
        return status

    def terminate(self):
        # Caller must independently stop the ORIGINAL APPLICATION GROUP first.
        # Killing the root waiter alone cannot retire a role or descendants.
        require(not self._signaled and not self._reaped)
        self._signaled = True
        self._verify_pidfd()
        signal.pidfd_send_signal(self._pidfd, signal.SIGKILL)

    def disconnect(self):
        # EOF is native fail-closed cleanup, but never sufficient host evidence.
        if self._host is not None:
            self._verify_socket(self._host)
            endpoint, self._host = self._host, None
            endpoint.close()

    def close(self):
        # No signal/reap/cleanup claim. Only caller-owned original handles.
        self._closed = True
        for name in ("_child", "_host"):
            endpoint, self.__dict__[name] = getattr(self, name), None
            if endpoint is not None:
                try:
                    self._verify_socket(endpoint)
                    endpoint.close()
                except (OSError, ValueError):
                    endpoint.detach()  # Do not let a stale socket object close a reused fd.
        for fd in self._fds:
            with suppress(OSError):
                info = os.fstat(fd)
                identity = self._fd_identities.get(fd)
                if identity is None or (info.st_dev, info.st_ino) == identity:
                    os.close(fd)
        self._fds.clear()
        self._fd_identities.clear()
