"""Check a copied synthetic MVP backup without Docker or database access.

This detects accidental truncation or alteration of a verified pg_dump. The
manifest is stored beside the dump, so this is not an authenticity signature.
"""

import argparse
import hashlib
import json
import re
import stat
from pathlib import Path

MAX_DUMP_BYTES = 100 * 1024**2
MAX_MANIFEST_BYTES = 1024**2
SHA256 = re.compile(r"[a-f0-9]{64}\Z")


def digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        if source.read(5) != b"PGDMP":
            raise ValueError("Expected PostgreSQL custom backup")
        source.seek(0)
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def private_regular_file(path: Path, maximum: int) -> int:
    details = path.lstat()
    if not stat.S_ISREG(details.st_mode) or details.st_mode & 0o077:
        raise ValueError("Backup file must be a private regular file")
    if not 0 < details.st_size <= maximum:
        raise ValueError("Backup file size is outside the accepted bound")
    return details.st_size


def verify_package(directory: Path) -> dict:
    directory = Path(directory)
    details = directory.lstat()
    if not stat.S_ISDIR(details.st_mode) or details.st_mode & 0o077:
        raise ValueError("Backup directory must be private and not a symlink")
    manifest_path = directory / "verified.json"
    dump_path = directory / "current.dump"
    private_regular_file(manifest_path, MAX_MANIFEST_BYTES)
    size = private_regular_file(dump_path, MAX_DUMP_BYTES)
    manifest = json.loads(manifest_path.read_text())
    if not isinstance(manifest, dict) or set(manifest) != {"schema", "tables", "dump"}:
        raise ValueError("Expected a complete backup manifest")
    dump = manifest["dump"]
    tables = manifest["tables"]
    if (
        manifest["schema"] != "0003_mvp"
        or not isinstance(tables, dict)
        or not 10 <= len(tables) <= 100
        or not isinstance(dump, dict)
        or set(dump) != {"file", "bytes", "sha256"}
        or dump["file"] != "current.dump"
        or type(dump["bytes"]) is not int
        or dump["bytes"] != size
        or not isinstance(dump["sha256"], str)
        or not SHA256.fullmatch(dump["sha256"])
    ):
        raise ValueError("Backup manifest metadata is invalid")
    for table, value in tables.items():
        if (
            not isinstance(table, str)
            or not re.fullmatch(r"[a-z_][a-z_0-9]*", table)
            or not isinstance(value, dict)
            or set(value) != {"columns", "rows", "sha256"}
            or not isinstance(value["columns"], list)
            or not value["columns"]
            or type(value["rows"]) is not int
            or not 0 <= value["rows"] <= 100000
            or not isinstance(value["sha256"], str)
            or not SHA256.fullmatch(value["sha256"])
        ):
            raise ValueError("Backup table manifest is invalid")
    if digest_file(dump_path) != dump["sha256"]:
        raise ValueError("Backup bytes do not match the verified manifest")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    try:
        manifest = verify_package(args.directory)
    except (OSError, ValueError, json.JSONDecodeError):
        parser.exit(1, "Backup verification failed; do not use this copy for restore.\n")
    print(f"Backup file and manifest verified: {len(manifest['tables'])} MVP tables.")


if __name__ == "__main__":
    main()
