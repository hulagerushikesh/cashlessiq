"""Cooperative lifecycle exclusion for the disposable service journey only.

The persistent lock has no private contents and is never unlinked. It cannot
exclude an uncooperative root process, authorize activation or pin account/code
identity. Keep the lease through delivery, explicit starts and quiescent teardown.
"""

import fcntl
import os
import stat
import sys
from contextlib import contextmanager

ERROR = "Service coordination unconfirmed; retain state and do not activate"
NAME = "ciq-agent-service-journey.lock"


def require(value):
    if not value:
        raise ValueError(ERROR)


def directory():
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    fd = os.open("/", flags)
    try:
        for name in (None, "run"):
            if name:
                child = os.open(name, flags, dir_fd=fd)
                os.close(fd)
                fd = child
            item = os.fstat(fd)
            require(item.st_uid == 0 and not item.st_mode & 0o022)
        return fd
    except BaseException:
        os.close(fd)
        raise


class Lease:
    def __init__(self, parent, fd):
        self.parent, self.fd, self.pid = parent, fd, os.getpid()

    def check(self):
        try:
            require(self.fd is not None and self.pid == os.getpid())
            item = os.fstat(self.fd)
            current = os.stat(NAME, dir_fd=self.parent, follow_symlinks=False)
            require(stat.S_ISREG(item.st_mode) and item.st_uid == 0 and item.st_gid == 0
                    and stat.S_IMODE(item.st_mode) == 0o600 and item.st_nlink == 1
                    and item.st_size == 0
                    and (item.st_dev, item.st_ino) == (current.st_dev, current.st_ino))
        except Exception:
            raise ValueError(ERROR) from None


@contextmanager
def exclusive():
    parent = fd = lease = None
    try:
        require(sys.platform == "linux" and os.geteuid() == 0
                and os.environ.get("GITHUB_ACTIONS") == "true"
                and os.environ.get("GITHUB_REPOSITORY") == "hulagerushikesh/cashlessiq"
                and os.environ.get("CIQ_AGENT_SERVICE_JOURNEY_TEST") == "1")
        parent = directory()
        fd = os.open(NAME, os.O_RDONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC
                     | os.O_NONBLOCK, 0o600, dir_fd=parent)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lease = Lease(parent, fd)
        lease.check()
    except BaseException as error:
        if fd is not None:
            os.close(fd)
        if parent is not None:
            os.close(parent)
        if isinstance(error, Exception):
            raise ValueError(ERROR) from None
        raise
    try:
        yield lease
    finally:
        lease.fd = None
        os.close(fd)
        os.close(parent)
