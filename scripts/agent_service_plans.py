"""Atomic dummy-plan delivery for opted-in disposable CI, never a live installer.

Trusted callers exclude activation and pin installed units/accounts separately.
No replacement, secret source, rotation, retirement or activation API is provided.
"""

import os
import secrets
import stat
import sys

ERROR = "Private plan delivery unconfirmed; retain state and do not activate"
TARGETS = {
    "claim": ("ciq-agent-claim", "claim.json", 53001, 8192),
    "custody": ("ciq-agent-custody", "custody.json", 53002, 8192),
    "receipt": ("ciq-agent-receipts", "peer.json", 53003, 2048),
    "candidate": ("ciq-agent-custody", "candidate.json", 53002, 128000),
}


def require(value):
    if not value:
        raise ValueError(ERROR)


def parent(role):
    """Walk fixed root-owned directories without following any symlink."""
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    fd = os.open("/", flags)
    try:
        for name in (None, "run", TARGETS[role][0]):
            if name is not None:
                child = os.open(name, flags, dir_fd=fd)
                os.close(fd)
                fd = child
            item = os.fstat(fd)
            require(stat.S_ISDIR(item.st_mode) and item.st_uid == 0
                    and not item.st_mode & 0o022)
        return fd
    except BaseException:
        os.close(fd)
        raise


def publish(directory, name, uid, gid, raw):
    """Internal descriptor primitive; failures retain owned staging/final evidence."""
    temporary = ".pending-" + secrets.token_hex(16)
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
                 | os.O_CLOEXEC, 0o600, dir_fd=directory)
    try:
        remaining = memoryview(raw)
        while remaining:
            count = os.write(fd, remaining)
            require(count > 0)
            remaining = remaining[count:]
        os.fchown(fd, uid, gid)
        os.fchmod(fd, 0o600)
        os.fsync(fd)
        item = os.fstat(fd)
        require(stat.S_ISREG(item.st_mode) and item.st_uid == uid and item.st_gid == gid
                and stat.S_IMODE(item.st_mode) == 0o600 and item.st_nlink == 1
                and item.st_size == len(raw))
        # linkat refuses EVERY existing final entry (including dangling symlinks).
        # Final name first appears only after bytes, ownership and file sync pass.
        os.link(temporary, name, src_dir_fd=directory, dst_dir_fd=directory,
                follow_symlinks=False)
        os.unlink(temporary, dir_fd=directory)
        os.fsync(directory)
        final = os.stat(name, dir_fd=directory, follow_symlinks=False)
        require((final.st_dev, final.st_ino) == (item.st_dev, item.st_ino)
                and final.st_nlink == 1)
    finally:
        os.close(fd)


def stage(role, raw):
    """Deliver complete in-memory dummy bytes; return no credential or permission."""
    try:
        require(sys.platform == "linux" and os.geteuid() == 0
                and os.environ.get("GITHUB_ACTIONS") == "true"
                and os.environ.get("GITHUB_REPOSITORY") == "hulagerushikesh/cashlessiq"
                and os.environ.get("CIQ_AGENT_SERVICE_JOURNEY_TEST") == "1")
        require(type(role) is str and role in TARGETS)
        _directory, name, uid, maximum = TARGETS[role]
        require(type(raw) is bytes and 0 < len(raw) <= maximum)
        directory = parent(role)
        try:
            publish(directory, name, uid, uid, raw)
        finally:
            os.close(directory)
    except Exception:
        # Includes failures after publication: never delete/retry/activate here.
        raise ValueError(ERROR) from None
