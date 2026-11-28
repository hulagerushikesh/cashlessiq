"""Prepared owned cgroup cleanup, without process launch or activation authority.

A trusted host must reserve before allocation, prevent subsequent migrations or
starts, reap its children and retain uncertain state. This is not PreparedHost.
"""

import ctypes
import math
import os
import stat
import sys
from contextlib import suppress
from time import monotonic, sleep
from uuid import uuid4

PARENT = "/sys/fs/cgroup/system.slice"
ERROR = "single_call_cgroup_unavailable"
DIRECTORY = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
READ = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC


def resource_limits(role):
    """Fixed review policy, never a caller-supplied capacity or retry selector."""
    require(type(role) is str and role in {"receipt", "provider", "custody"})
    memory = 128 if role == "receipt" else 256
    return (("memory.max", f"{memory * 1024 * 1024}\n".encode()),
            ("memory.swap.max", b"0\n"), ("memory.oom.group", b"1\n"),
            ("pids.max", b"32\n"), ("cpu.max", b"50000 100000\n"))


def require(value):
    if not value:
        raise ValueError(ERROR)


def kernel_file(fd, *, directory=False):
    info = os.fstat(fd)
    require((stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))
            and info.st_uid == 0 and not info.st_mode & 0o022)
    # f_type is the first native long in Linux struct statfs. A generously sized
    # buffer avoids depending on the remaining architecture-specific layout.
    buffer = ctypes.create_string_buffer(4096)
    call = ctypes.CDLL(None, use_errno=True).fstatfs
    call.argtypes, call.restype = [ctypes.c_int, ctypes.c_void_p], ctypes.c_int
    require(call(fd, buffer) == 0 and ctypes.c_long.from_buffer(buffer).value == 0x63677270)
    return info.st_dev, info.st_ino


def open_parent():
    # Do not follow symlinks in any component, including the cgroup mount.
    fd = os.open("/", DIRECTORY)
    try:
        for part in ("sys", "fs", "cgroup", "system.slice"):
            following = os.open(part, DIRECTORY, dir_fd=fd)
            os.close(fd)
            fd = following
        kernel_file(fd, directory=True)
        return fd
    except BaseException:
        os.close(fd)
        raise


class OwnedSingleCallCgroup:
    """One fresh kernel namespace; never adopt, remove, reset or retry a kill.

    Construct and retain this object BEFORE prepare()/any process allocation.
    A failed preparation remains terminal. No PID, external path, timeout or
    group identity is accepted. The host must not start/migrate after stop().
    All methods require serialized calls under that host's exclusive lease.
    """

    def __init__(self, role):
        require(type(role) is str and role in {"receipt", "provider", "custody"})
        self._limits = resource_limits(role)
        self._name = "ciq-single-call-" + uuid4().hex + "-" + role
        self._parent = self._group = None
        self._identity = self._parent_identity = None
        self._used = self._ready = self._stopping = self._clean = False
        self._created = False

    @property
    def name(self):
        return self._name

    def _read(self, name):
        fd = os.open(name, READ, dir_fd=self._group)
        try:
            kernel_file(fd)
            raw = os.read(fd, 4097)
            require(len(raw) <= 4096)
            return raw
        finally:
            os.close(fd)

    def _verify(self):
        require(self._ready and self._parent is not None and self._group is not None)
        require(kernel_file(self._parent, directory=True) == self._parent_identity)
        current = os.stat(PARENT, follow_symlinks=False)
        require(stat.S_ISDIR(current.st_mode)
                and (current.st_dev, current.st_ino) == self._parent_identity)
        require(kernel_file(self._group, directory=True) == self._identity)
        current = os.stat(self.name, dir_fd=self._parent, follow_symlinks=False)
        require(stat.S_ISDIR(current.st_mode)
                and (current.st_dev, current.st_ino) == self._identity)
        require(self._read("cgroup.type") == b"domain\n")

    def _empty(self):
        self._verify()
        records = [line.split() for line in self._read("cgroup.events").splitlines()]
        require(records and all(len(record) == 2 for record in records))
        values = dict(records)
        require(len(values) == len(records) and set(values) <= {b"populated", b"frozen"}
                and b"populated" in values and all(v in (b"0", b"1") for v in values.values()))
        self._verify()
        return values[b"populated"] == b"0"

    def prepare(self):
        # Rejected reuse must not discard original live cleanup ownership.
        require(not self._used and not self._stopping)
        self._used = True
        try:
            require(sys.platform == "linux" and os.getresuid() == (0, 0, 0))
            self._parent = open_parent()
            self._parent_identity = kernel_file(self._parent, directory=True)
            # mkdir is exclusive. An existing name is never adopted or killed.
            # A later failure retains the name for trusted operator review.
            os.mkdir(self.name, mode=0o755, dir_fd=self._parent)
            self._created = True
            self._group = os.open(self.name, DIRECTORY, dir_fd=self._parent)
            self._identity = kernel_file(self._group, directory=True)
            self._ready = True
            require(self._empty())
            # Set every limit on the original EMPTY group, before any launch.
            # Missing controllers/short writes/readback faults are terminal.
            # Never enable controllers on a shared ancestor from this helper.
            for name, raw in self._limits:
                self._verify()
                fd = os.open(name, os.O_WRONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                             dir_fd=self._group)
                try:
                    kernel_file(fd)
                    require(os.write(fd, raw) == len(raw))
                finally:
                    os.close(fd)
                self._verify()
                require(self._read(name) == raw and self._empty())
            require(self.resource_limited())
        except BaseException as error:
            self._ready = False
            if not isinstance(error, Exception):
                raise
            raise ValueError(ERROR) from None

    def resource_limited(self):
        """Fresh exact policy readback; never repair changed limits or grant launch."""
        try:
            self._verify()
            require(all(self._read(name) == raw for name, raw in self._limits))
            self._verify()
            return True
        except Exception:
            return False

    def quiescent(self):
        try:
            return self._empty() and self._empty()
        except Exception:
            return False

    def stop(self):
        if self._stopping:
            return self._clean and self.quiescent()
        self._stopping = True  # Consume before a write, including uncertain ACK.
        try:
            self._verify()
            origin = monotonic()
            require(type(origin) in (float, int) and math.isfinite(origin))
            fd = os.open("cgroup.kill", os.O_WRONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                         dir_fd=self._group)
            try:
                kernel_file(fd)
                self._verify()
                require(os.write(fd, b"1\n") == 2)
            finally:
                os.close(fd)
            # Kernel SIGKILL covers descendants and concurrent forks. Empty
            # population still must be observed; a successful write is not ACK.
            # A fixed iteration ceiling also bounds a stalled injected clock.
            previous = origin
            for _ in range(51):
                now = monotonic()
                require(type(now) in (float, int) and math.isfinite(now)
                        and previous <= now and 0 <= now - origin <= 1.0)
                previous = now
                if self.quiescent():
                    final = monotonic()
                    require(type(final) in (float, int) and math.isfinite(final)
                            and now <= final and final - origin <= 1.0)
                    self._clean = True
                    return True
                sleep(0.02)
        except Exception:
            pass
        return False

    def close(self):
        # Closing handles is not process cleanup. Never remove retained names,
        # private inputs or evidence, even after confirmed empty population.
        self._used = True
        self._ready = False
        for attribute in ("_group", "_parent"):
            fd = getattr(self, attribute)
            setattr(self, attribute, None)
            if fd is not None:
                with suppress(OSError):
                    os.close(fd)
