"""Explicit frozen-time STATE TEST helper; excluded from normal service startup.

Caller owes a bounded process, independently verified image/mounts, an exclusive
disposable named volume, and exact exit inspection. No discovery or recovery.
Unlike material read-back, verification needs RW state for health high-water marks.
"""

import json
import os
import stat
import sys
from pathlib import Path

MAX_FRAME = 4096
FILES = {"used.sqlite": 0o600, "public-guard.json": 0o400}


class StateVolumeDenied(ValueError):
    def __init__(self):
        super().__init__("Disposable state volume denied; retain outcome for review")


def require(value):
    if not value:
        raise StateVolumeDenied()


def pairs(rows):
    result = {}
    for key, value in rows:
        require(key not in result)
        result[key] = value
    return result


def parse(frame, fixture):
    try:
        require(type(frame) is bytes and 0 < len(frame) <= MAX_FRAME)
        value = json.loads(frame, object_pairs_hook=pairs)
        require(type(value) is dict and set(value) == {"version", "role", "generation"})
        require(type(value["version"]) is int and value["version"] == 1)
        role = value["role"]
        require(type(role) is str and role in fixture.SERVICE_BINDINGS)
        require(value["generation"] == fixture.GENERATION)
        return role, value["generation"]
    except Exception:
        raise StateVolumeDenied() from None


def directory(root):
    info = root.lstat()
    require(stat.S_ISDIR(info.st_mode))
    return info


def initialize(root, frame, fixture):
    """Empty volume only. Partial outcomes stay intact; no overwrite or retry."""
    try:
        role, generation = parse(frame, fixture)
        info = directory(root)
        require(info.st_uid == os.geteuid() and not list(root.iterdir()))
        fixture.initialize(role, directory=root, generation=generation)
        require((directory(root).st_dev, directory(root).st_ino) == (info.st_dev, info.st_ino))
        return dict(state="INITIALIZED", role=role, generation=generation)
    except Exception:
        raise StateVolumeDenied() from None


def verify(root, frame, fixture, *, owner):
    """Separate existing-state probe, not an initializer or readiness receipt.

    Uses canonical SQLite/config/authority and signed fictional health validation.
    No initial-byte digest: replay/high-water changes are legitimate retained state.
    Trusted exclusive mount required; not hostile same-UID race containment.
    """
    try:
        role, generation = parse(frame, fixture)
        require(type(owner) is tuple and len(owner) == 2)
        require(all(type(n) is int and 0 <= n < 2**31 for n in owner))
        info = directory(root)
        require((info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) == (*owner, 0o700))
        require({p.name for p in root.iterdir()} == set(FILES))
        for name, mode in FILES.items():
            child = (root / name).lstat()
            require(stat.S_ISREG(child.st_mode) and child.st_nlink == 1)
            require((child.st_uid, child.st_gid, stat.S_IMODE(child.st_mode)) == (*owner, mode))
            require(0 < child.st_size <= 262144)
        guard, evidence = fixture.load(directory=root)
        require(guard._config.authority == fixture.authority_for(role))
        require(guard._config.assertion_generation == generation)
        guard.inspect()
        guard.observe(evidence)
        require((directory(root).st_dev, directory(root).st_ino) == (info.st_dev, info.st_ino))
        return dict(state="VERIFIED", role=role, generation=generation)
    except Exception:
        raise StateVolumeDenied() from None


def main():
    try:
        import guard_mtls_fixture as fixture

        require(len(sys.argv) == 2 and sys.argv[1] in {"initialize", "verify"})
        mode = sys.argv[1]
        expected = 0 if mode == "initialize" else 10001
        require(os.geteuid() == expected and os.getegid() == expected)
        frame = sys.stdin.buffer.read(MAX_FRAME + 1)
        root = Path("/var/lib/ciq-replay")
        result = (
            initialize(root, frame, fixture)
            if mode == "initialize"
            else verify(root, frame, fixture, owner=(10001, 10001))
        )
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except Exception:
        print("Disposable state volume denied", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
