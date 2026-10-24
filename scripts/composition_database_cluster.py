"""Explicit disposable initdb only; never bootstrap, start or certify readiness.

A trusted owner must inspect two exact mounts and the pinned image, bound the
whole helper, and independently probe the stopped cluster. Exclusive mounts
are required; this is not hostile same-UID filesystem race containment.
"""

import json
import os
import signal
import stat
import subprocess
import sys
from contextlib import suppress
from pathlib import Path

from scripts import composition_database_data as data
from scripts import composition_volume as volume
from scripts.composition_database_volume import DatabaseVolume

MATERIAL = Path("/database-material")
DATA = Path("/database-data")
INITDB = "/usr/lib/postgresql/16/bin/initdb"
MARKER = "initialization.json"
ENV = {"PATH": "/usr/lib/postgresql/16/bin:/usr/bin:/bin", "LC_ALL": "C"}


def command(root, material):
    return (
        INITDB,
        "--pgdata=" + str(root / "pgdata"),
        "--username=postgres",
        "--pwfile=" + str(material / "admin-password"),
        "--auth-local=reject",
        "--auth-host=reject",
        "--encoding=UTF8",
        "--locale=C",
        "--data-checksums",
        "--no-instructions",
        "--no-clean",
    )


def execute(argv):
    """Closed initdb process, no credential-bearing diagnostics or inherited env.

    The outer owner still owes a wall-clock watchdog and daemon containment.
    SIGKILL targets the owned process group before reaping on deadline expiry.
    """
    child = subprocess.Popen(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=ENV,
        close_fds=True,
        start_new_session=True,
    )
    try:
        code = child.wait(timeout=30)
    except BaseException:
        with suppress(ProcessLookupError):
            os.killpg(child.pid, signal.SIGKILL)
        with suppress(subprocess.TimeoutExpired):
            child.wait(timeout=2)
        raise data.DataDenied() from None
    data.require(code == 0)


def record(spec, state):
    return json.dumps(
        dict(version=1, fingerprint=spec.fingerprint, state=state),
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def read_file(root, name, limit, owner, mode):
    fd = os.open(root / name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        data.require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1)
        data.require((info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) == (*owner, mode))
        data.require(0 < info.st_size <= limit)
        result = os.read(fd, limit + 1)
        data.require(len(result) == info.st_size)
        return result
    finally:
        os.close(fd)


def structure(root, *, owner):
    """Small stopped-cluster sanity check, not PostgreSQL catalog/grant proof."""
    for directory in (root, root / "pgdata", root / "pgdata" / "global"):
        info = directory.lstat()
        data.require(stat.S_ISDIR(info.st_mode))
        data.require((info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) == (*owner, 0o700))
    data.require(read_file(root / "pgdata", "PG_VERSION", 16, owner, 0o600) == b"16\n")
    data.require(
        len(read_file(root / "pgdata" / "global", "pg_control", 8192, owner, 0o600)) == 8192
    )
    data.require(not os.path.lexists(root / "pgdata" / "postmaster.pid"))
    data.require(set(os.listdir(root)) == {"pgdata", MARKER})


def initialize(root, material, spec, *, owner=data.OWNER, runner=execute):
    data.require(type(spec) is DatabaseVolume)
    volume.verify(material, spec, owner=owner)
    data.verify(root, owner=owner)
    # An interrupted write or initdb is permanently distinguishable from fresh
    # prepared data. Never remove this marker, even when initdb returns nonzero.
    fd = os.open(root / MARKER, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(fd, 0o600)
        attempted = record(spec, "ATTEMPTED")
        data.require(os.write(fd, attempted) == len(attempted))
        os.fsync(fd)
        directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        runner(command(root, material))
        structure(root, owner=owner)
        volume.verify(material, spec, owner=owner)
        completed = record(spec, "INITIALIZED")
        os.lseek(fd, 0, os.SEEK_SET)
        data.require(os.write(fd, completed) == len(completed))
        os.ftruncate(fd, len(completed))
        os.fsync(fd)
    finally:
        os.close(fd)


def verify(root, material, spec, *, owner=data.OWNER):
    data.require(type(spec) is DatabaseVolume)
    volume.verify(material, spec, owner=owner)
    structure(root, owner=owner)
    data.require(read_file(root, MARKER, 4096, owner, 0o600) == record(spec, "INITIALIZED"))


def main():
    try:
        data.require(len(sys.argv) == 2 and sys.argv[1] in {"initialize", "verify"})
        data.require((os.geteuid(), os.getegid()) == data.OWNER)
        spec, _ = volume.parse(
            sys.stdin.buffer.read(volume.MAX_FRAME + 1), install=False, material_type=DatabaseVolume
        )
        (initialize if sys.argv[1] == "initialize" else verify)(DATA, MATERIAL, spec)
        print(
            json.dumps(
                dict(
                    state="INITIALIZED" if sys.argv[1] == "initialize" else "VERIFIED",
                    role="database",
                    fingerprint=spec.fingerprint,
                )
            )
        )
        return 0
    except Exception:
        print("Disposable cluster denied; outcome unknown", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
