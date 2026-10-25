"""Explicit disposable volume helper. Never discovers, mounts or creates volumes.

Only the separately invoked CLI fixes /material and UID/GID 10001. Library tests
use their unprivileged host identity on disposable directories, not Docker mounts.
Caller must independently reserve/verify the exact image, container and volume,
bound this process, retain unknown outcomes and confirm exit before read-back.
"""

import base64
import io
import json
import os
import stat
import sys
import tarfile
from hashlib import sha256
from pathlib import Path

from .composition_material import (
    MAX_FILE,
    MAX_TOTAL,
    Material,
    MaterialDenied,
    Staged,
    _directory,
    _require,
    _stable,
)

MAX_FRAME = 2 * 1024 * 1024


def request(staged, *, install):
    """Private stdin bytes only; never log/persist this credential-bearing frame."""
    _require(type(staged) is Staged and type(install) is bool)
    spec = staged.expected
    value = dict(
        version=1,
        role=spec.role,
        fingerprint=spec.fingerprint,
        records=[[name, size, digest.hex()] for name, size, digest in spec.records],
    )
    if install:
        value["archive"] = base64.b64encode(staged.archive(spec.role, spec.fingerprint)).decode()
    frame = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    _require(len(frame) <= MAX_FRAME)
    return frame


def _pairs(rows):
    value = {}
    for key, item in rows:
        _require(key not in value)
        value[key] = item
    return value


def parse(frame, *, install, material_type=Material):
    """Reject ambiguous/unbounded metadata before touching a target directory."""
    try:
        _require(type(frame) is bytes and 0 < len(frame) <= MAX_FRAME)
        _require(type(install) is bool)
        raw = json.loads(frame, object_pairs_hook=_pairs)
        _require(
            type(raw) is dict
            and set(raw)
            == ({"version", "role", "fingerprint", "records"} | ({"archive"} if install else set()))
        )
        _require(type(raw["version"]) is int and raw["version"] == 1)
        role, fingerprint, rows = raw["role"], raw["fingerprint"], raw["records"]
        _require(type(role) is str and type(fingerprint) is str)
        _require(len(fingerprint) == 64 and all(c in "0123456789abcdef" for c in fingerprint))
        _require(type(rows) is list and len(rows) == len(material_type.names(role)))
        records = []
        for row in rows:
            _require(type(row) is list and len(row) == 3)
            name, size, digest = row
            _require(type(name) is str and name in material_type.names(role))
            _require(type(size) is int and 0 < size <= MAX_FILE)
            _require(type(digest) is str and len(digest) == 64)
            _require(all(c in "0123456789abcdef" for c in digest))
            records.append((name, size, bytes.fromhex(digest)))
        _require([r[0] for r in records] == sorted(material_type.names(role)))
        _require(sum(r[1] for r in records) <= MAX_TOTAL)
        archive = None
        if install:
            _require(type(raw["archive"]) is str)
            archive = base64.b64decode(raw["archive"], validate=True)
        return material_type(role, fingerprint, tuple(records)), archive
    except Exception:
        raise MaterialDenied() from None


def unpack(spec, payload):
    """Validate the entire flat canonical archive; never use extract/extractall."""
    try:
        _require(type(payload) is bytes and 0 < len(payload) <= MAX_FRAME)
        expected = {name: (size, digest) for name, size, digest in spec.records}
        snapshot = {}
        with tarfile.open(fileobj=io.BytesIO(payload), mode="r:") as archive:
            members = archive.getmembers()
            _require([m.name for m in members] == [".", *sorted(expected)])
            for entry in members:
                _require((entry.uid, entry.gid) == spec.archive_owner)
                _require(not entry.pax_headers and not entry.linkname)
                _require(not entry.uname and not entry.gname and entry.mtime == 0)
                if entry.name == ".":
                    _require(entry.isdir() and entry.mode == 0o500 and entry.size == 0)
                    continue
                size, digest = expected[entry.name]
                _require(entry.isreg() and entry.mode == 0o400 and entry.size == size)
                stream = archive.extractfile(entry)
                data = stream.read(size + 1)
                _require(len(data) == size and sha256(data).digest() == digest)
                snapshot[entry.name] = data
        # Refuse hidden trailing archives, noncanonical headers/padding and aliases.
        _require(payload == spec.pack(snapshot))
        return snapshot
    except Exception:
        raise MaterialDenied() from None


def _owner(owner):
    _require(type(owner) is tuple and len(owner) == 2)
    _require(all(type(n) is int and 0 <= n < 2**31 for n in owner))


def _metadata(info, owner, mode):
    return (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) == (*owner, mode)


def install(root, spec, payload, *, owner):
    """One explicit attempt; fail/retain partial state, never overwrite or retry.

    CLI installer requires root with CHOWN only, an empty independently verified
    named volume and no networks/other mounts. Chown files then root LAST; a new
    UID-10001 read-only probe, not installer success, must verify actual read-back.
    """
    fd = None
    try:
        _owner(owner)
        snapshot = unpack(spec, payload)  # All input validated BEFORE filesystem mutation.
        fd = _directory(root)
        initial = os.fstat(fd)
        _require(initial.st_uid == os.geteuid() and not os.listdir(fd))
        os.fchmod(fd, 0o700)
        for name, data in sorted(snapshot.items()):
            child = os.open(
                name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=fd,
            )
            try:
                pending = memoryview(data)
                while pending:
                    written = os.write(child, pending)
                    _require(written > 0)
                    pending = pending[written:]
                os.fchmod(child, 0o400)
                os.fchown(child, *owner)
                os.fsync(child)
                info = os.fstat(child)
                _require(_metadata(info, owner, 0o400) and info.st_nlink == 1)
                _require(info.st_size == len(data))
            finally:
                os.close(child)
        _require(set(os.listdir(fd)) == spec.names(spec.role))
        os.fchmod(fd, 0o500)  # Before chown: no FOWNER/DAC override needed afterward.
        os.fchown(fd, *owner)
        os.fsync(fd)
        _require(_metadata(os.fstat(fd), owner, 0o500))
    except Exception:
        raise MaterialDenied() from None
    finally:
        if fd is not None:
            os.close(fd)


def verify(root, spec, *, owner):
    """Read-only regular-file/hash/mode/owner check; no repair or content output."""
    fd = current = None
    try:
        _owner(owner)
        fd = _directory(root)
        initial = os.fstat(fd)
        _require(_metadata(initial, owner, 0o500))
        _require(set(os.listdir(fd)) == spec.names(spec.role))
        for name, size, digest in spec.records:
            child = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
            try:
                before = os.fstat(child)
                _require(stat.S_ISREG(before.st_mode) and _metadata(before, owner, 0o400))
                _require(before.st_nlink == 1 and before.st_size == size)
                result = bytearray()
                while len(result) <= size:
                    chunk = os.read(child, min(65536, size + 1 - len(result)))
                    if not chunk:
                        break
                    result.extend(chunk)
                _require(_stable(before) == _stable(os.fstat(child)))
                _require(len(result) == size and sha256(result).digest() == digest)
            finally:
                os.close(child)
        _require(set(os.listdir(fd)) == spec.names(spec.role))
        current = _directory(root)
        after = os.fstat(current)
        _require(_metadata(after, owner, 0o500))
        _require((initial.st_dev, initial.st_ino) == (after.st_dev, after.st_ino))
        return True
    except Exception:
        raise MaterialDenied() from None
    finally:
        for item in (current, fd):
            if item is not None:
                os.close(item)


def main():
    try:
        _require(len(sys.argv) == 2 and sys.argv[1] in {"install", "verify"})
        installing = sys.argv[1] == "install"
        _require(os.geteuid() == (0 if installing else 10001))
        spec, archive = parse(sys.stdin.buffer.read(MAX_FRAME + 1), install=installing)
        if installing:
            install(Path("/material"), spec, archive, owner=(10001, 10001))
        else:
            verify(Path("/material"), spec, owner=(10001, 10001))
        print(
            json.dumps(
                {
                    "state": "INSTALLED" if installing else "VERIFIED",
                    "role": spec.role,
                    "fingerprint": spec.fingerprint,
                }
            )
        )
        return 0
    except Exception:
        print("Disposable material operation denied; outcome unknown", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
