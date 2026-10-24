"""Closed PostgreSQL runtime identity check; no data access or readiness claim."""

import os
import pwd
import re
import stat
import subprocess
import sys
from pathlib import Path

from scripts.composition_database_data import OWNER, require

BIN = Path("/usr/lib/postgresql/16/bin")
ENV = {"PATH": str(BIN) + ":/usr/bin:/bin", "LC_ALL": "C"}


def check():
    require((os.geteuid(), os.getegid()) == OWNER)
    account = pwd.getpwuid(OWNER[0])
    require(account.pw_name == "ciqdb" and account.pw_gid == OWNER[1])
    # Check only package-owned fixed paths. No caller executable or inherited env.
    for name in ("initdb", "postgres", "psql"):
        path = BIN / name
        info = path.lstat()
        require(stat.S_ISREG(info.st_mode) and info.st_uid == 0)
        require(not info.st_mode & 0o022 and bool(info.st_mode & 0o111))
        result = subprocess.run(
            [str(path), "--version"], stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=ENV,
            close_fds=True, timeout=5, check=False,
        )
        require(result.returncode == 0)
        require(re.fullmatch(
            name.encode() + rb" \(PostgreSQL\) 16\.[0-9]+(?: \([^\r\n]+\))?\n",
            result.stdout,
        ) is not None)


def main():
    try:
        require(len(sys.argv) == 1)
        check()
        print("Disposable PostgreSQL 16 runtime verified; readiness not established")
        return 0
    except Exception:
        print("Disposable PostgreSQL runtime denied", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
