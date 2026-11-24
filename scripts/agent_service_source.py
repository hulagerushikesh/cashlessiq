"""Root-only dummy credential intake for disposable CI; no live source adapter.

Fixed paths only. The supervisor retains source evidence through quiescent
teardown. Root is trusted; metadata checks do not defend against hostile root.
"""

import os
import stat
import sys
from pathlib import Path

from scripts import agent_service_plans as plans

SOURCE = Path("/run/ciq-agent-supervisor")
ROLES = ("claim", "custody", "receipt")
ERROR = "Private source unconfirmed; retain state and do not activate"


def require(value):
    if not value:
        raise ValueError(ERROR)


def guard(role):
    require(sys.platform == "linux" and os.geteuid() == 0
            and os.environ.get("GITHUB_ACTIONS") == "true"
            and os.environ.get("GITHUB_REPOSITORY") == "hulagerushikesh/cashlessiq"
            and os.environ.get("CIQ_AGENT_SERVICE_JOURNEY_TEST") == "1")
    require(type(role) is str and role in ROLES)


def directory():
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    fd = os.open("/", flags)
    try:
        for name in (None, "run", SOURCE.name):
            if name is not None:
                child = os.open(name, flags, dir_fd=fd)
                os.close(fd)
                fd = child
            item = os.fstat(fd)
            require(item.st_uid == item.st_gid == 0 and not item.st_mode & 0o022)
            if name == SOURCE.name:
                require(stat.S_IMODE(item.st_mode) == 0o700)
        return fd
    except BaseException:
        os.close(fd)
        raise


def fingerprint(item):
    return (item.st_dev, item.st_ino, item.st_uid, item.st_gid, item.st_mode,
            item.st_nlink, item.st_size, item.st_mtime_ns, item.st_ctime_ns)


def acquire(role):
    """Read bounded private bytes, close all descriptors, return no activation grant."""
    directory_fd = fd = None
    try:
        guard(role)  # Before any filesystem access; candidate is never a credential role.
        _, name, _, maximum = plans.TARGETS[role]
        directory_fd = directory()
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
                     dir_fd=directory_fd)
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_uid == before.st_gid == 0
                and stat.S_IMODE(before.st_mode) == 0o600 and before.st_nlink == 1
                and 0 < before.st_size <= maximum)
        raw = bytearray()
        while len(raw) <= maximum:
            block = os.read(fd, min(4096, maximum + 1 - len(raw)))
            if not block:
                break
            raw.extend(block)
        require(len(raw) == before.st_size)
        require(fingerprint(before) == fingerprint(os.fstat(fd))
                == fingerprint(os.stat(name, dir_fd=directory_fd, follow_symlinks=False)))
        return bytes(raw)
    except Exception:
        raise ValueError(ERROR) from None
    finally:
        if fd is not None:
            os.close(fd)
        if directory_fd is not None:
            os.close(directory_fd)
