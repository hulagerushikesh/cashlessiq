"""Explicit DB-only disposable volume helper; no PostgreSQL startup or discovery.

The future pinned PostgreSQL image MUST run as 10002:10002. This helper does
not establish that image contract, mount identity or process exit. The owner
must use a bounded actor, independent read-back probe and exact journaled volume.
No normal application entrypoint imports or invokes this module.
"""

import json
import os
import sys
from pathlib import Path

from . import composition_volume as volume
from .composition_material import Material, MaterialDenied, Staged, _archive, _require

OWNER = (10002, 10002)
ROOT = Path("/database-material")


class DatabaseVolume(Material):
    archive_owner = OWNER

    @staticmethod
    def names(role):
        if role != "database":
            raise MaterialDenied()
        return frozenset(
            {"server.pem", "server.key", "admin-password", "bootstrap.sql", "pg_hba.conf"}
        )

    @staticmethod
    def pack(snapshot):
        return _archive(snapshot, owner=OWNER)


def request(staged, *, install):
    """Explicit conversion from checked host staging to DB-only private stdin."""
    # Local import keeps cryptography and credential generation out of helper image.
    from .composition_database import DatabaseStaging

    _require(type(staged) is Staged and type(staged.expected) is DatabaseStaging)
    expected = staged.expected
    snapshot = staged._snapshot(expected.role, expected.fingerprint)
    converted = DatabaseVolume.expected(expected.role, expected.fingerprint, snapshot)
    bound = Staged(converted, staged.root, staged.device, staged.inode)
    return volume.request(bound, install=install)


def main():
    try:
        _require(len(sys.argv) == 2 and sys.argv[1] in {"install", "verify"})
        installing = sys.argv[1] == "install"
        required = (0, 0) if installing else OWNER
        _require((os.geteuid(), os.getegid()) == required)
        spec, payload = volume.parse(
            sys.stdin.buffer.read(volume.MAX_FRAME + 1),
            install=installing,
            material_type=DatabaseVolume,
        )
        if installing:
            volume.install(ROOT, spec, payload, owner=OWNER)
        else:
            volume.verify(ROOT, spec, owner=OWNER)
        print(
            json.dumps(
                dict(
                    state="INSTALLED" if installing else "VERIFIED",
                    role=spec.role,
                    fingerprint=spec.fingerprint,
                )
            )
        )
        return 0
    except Exception:
        print("Disposable database material denied; outcome unknown", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
