"""Prepare an empty disposable PGDATA, never initdb/startup/readiness.

Exclusive trusted named mount required. Partial outcomes remain for review;
no adoption, cleanup or retry. Separate probe runs before PostgreSQL writes.
"""

import json
import os
import re
import stat
import sys
from pathlib import Path

OWNER = (10002, 10002)
ROOT = Path("/database-data")
MAX_FRAME = 4096


class DataDenied(ValueError):
    def __init__(self):
        super().__init__("Disposable database data denied; retain outcome for review")


def require(value):
    if not value:
        raise DataDenied()


def pairs(rows):
    result = {}
    for key, value in rows:
        require(key not in result)
        result[key] = value
    return result


def parse(frame):
    try:
        require(type(frame) is bytes and 0 < len(frame) <= MAX_FRAME)
        value = json.loads(frame, object_pairs_hook=pairs)
        require(type(value) is dict and set(value) == {"version", "role", "fingerprint"})
        require(type(value["version"]) is int and value["version"] == 1)
        require(value["role"] == "database")
        require(type(value["fingerprint"]) is str)
        require(re.fullmatch("[0-9a-f]{64}", value["fingerprint"]) is not None)
        return value["fingerprint"]
    except Exception:
        raise DataDenied() from None


def prepare(root, *, owner=OWNER):
    """Claim once by exclusive child creation; never accept an existing pgdata."""
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        require(not os.listdir(fd))
        require(os.fstat(fd).st_uid == os.geteuid())
        os.mkdir("pgdata", mode=0o700, dir_fd=fd)
        child = os.open("pgdata", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
        try:
            os.fchmod(child, 0o700)
            os.fchown(child, *owner)
            os.fsync(child)
        finally:
            os.close(child)
        os.fchmod(fd, 0o700)
        os.fchown(fd, *owner)
        os.fsync(fd)
    finally:
        os.close(fd)


def verify(root, *, owner=OWNER):
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        require(os.listdir(fd) == ["pgdata"])
        child = os.open("pgdata", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
        try:
            for descriptor in (fd, child):
                info = os.fstat(descriptor)
                require((info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) == (*owner, 0o700))
            require(not os.listdir(child))
        finally:
            os.close(child)
    finally:
        os.close(fd)


def main():
    try:
        require(len(sys.argv) == 2 and sys.argv[1] in {"prepare", "verify"})
        mode = sys.argv[1]
        require((os.geteuid(), os.getegid()) == ((0, 0) if mode == "prepare" else OWNER))
        fingerprint = parse(sys.stdin.buffer.read(MAX_FRAME + 1))
        (prepare if mode == "prepare" else verify)(ROOT)
        print(
            json.dumps(
                dict(
                    state="PREPARED" if mode == "prepare" else "VERIFIED",
                    role="database",
                    fingerprint=fingerprint,
                )
            )
        )
        return 0
    except Exception:
        print("Disposable database data denied; outcome unknown", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
