"""Explicit disposable material staging only; no Docker, generation or activation.

Trusted test provisioning supplies bytes. This does not validate their clinical,
PKI or database semantics, or provide encrypted/operational credential custody.
No manifest containing secret digests is written or printed. No existing bundle
is adopted, repaired or deleted. Archives are private caller-owned secret bytes.
"""

import io
import os
import stat
import tarfile
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path

BASE = frozenset({"config.json", "ca.pem", "identity.pem", "identity.key"})
ROLES = (
    "membership",
    "validator-0",
    "validator-1",
    "reader-0-nonclinical",
    "reader-0-clinical",
    "reader-1-nonclinical",
    "reader-1-clinical",
    "broker",
)
MAX_FILE = 262144
MAX_TOTAL = 1048576


class MaterialDenied(ValueError):
    def __init__(self):
        super().__init__("Disposable material denied; retained state requires review")


def names(role):
    if role not in ROLES:
        raise MaterialDenied()
    extra = (
        {"signer.pem", "local-auth.json"}
        if role == "broker"
        else {"db.json", "db-ca.pem"}
        if role == "membership"
        else {"verify.pem", "source.json"}
        if role.startswith("validator-")
        else {"verify.pem"}
    )
    return BASE | extra


def _require(condition):
    if not condition:
        raise MaterialDenied()


def _directory(path):
    """Walk absolute components without following symlinks, including parents."""
    _require(isinstance(path, Path))
    _require(path.is_absolute() and ".." not in path.parts)
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def _private(info, mode):
    return info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == mode


def _stable(info):
    # Reading may legitimately change atime. Content/security metadata may not.
    return tuple(
        getattr(info, name)
        for name in (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_uid",
            "st_gid",
            "st_nlink",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
    )


@dataclass(frozen=True, repr=False)
class Material:
    """No-I/O expected inventory; keeps hashes, not source bytes. No load/adopt API."""

    role: str
    fingerprint: str
    records: tuple = field(repr=False)

    @classmethod
    def expected(cls, role, fingerprint, contents):
        try:
            _require(type(fingerprint) is str and len(fingerprint) == 64)
            _require(all(c in "0123456789abcdef" for c in fingerprint))
            _require(type(contents) is dict and set(contents) == names(role))
            _require(all(type(b) is bytes and 0 < len(b) <= MAX_FILE for b in contents.values()))
            _require(sum(map(len, contents.values())) <= MAX_TOTAL)
            return cls(
                role,
                fingerprint,
                tuple(
                    (name, len(contents[name]), sha256(contents[name]).digest())
                    for name in sorted(contents)
                ),
            )
        except Exception:
            raise MaterialDenied() from None

    def provision(self, parent, contents):
        """Create one new role directory in a private, invocation-owned parent.

        Failed/partial writes remain private and are never retried or erased here.
        fd-relative O_EXCL/O_NOFOLLOW creation and fsync precede the receipt.
        """
        parent_fd = root_fd = None
        try:
            _require(self == Material.expected(self.role, self.fingerprint, contents))
            parent_fd = _directory(parent)
            _require(_private(os.fstat(parent_fd), 0o700))
            os.mkdir(self.role, mode=0o700, dir_fd=parent_fd)
            root_fd = os.open(
                self.role, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd
            )
            os.fchmod(root_fd, 0o700)
            info = os.fstat(root_fd)
            for name, _, _ in self.records:
                fd = os.open(
                    name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=root_fd,
                )
                try:
                    view = memoryview(contents[name])
                    while view:
                        written = os.write(fd, view)
                        _require(written > 0)
                        view = view[written:]
                    os.fchmod(fd, 0o400)
                    os.fsync(fd)
                finally:
                    os.close(fd)
            os.fsync(root_fd)
            os.fsync(parent_fd)
            return Staged(self, parent / self.role, info.st_dev, info.st_ino)
        except Exception:
            raise MaterialDenied() from None
        finally:
            for fd in (root_fd, parent_fd):
                if fd is not None:
                    os.close(fd)


@dataclass(frozen=True, repr=False)
class Staged:
    expected: Material
    root: Path
    device: int
    inode: int

    def _snapshot(self, role, fingerprint):
        root_fd = current_fd = None
        try:
            _require((role, fingerprint) == (self.expected.role, self.expected.fingerprint))
            root_fd = _directory(self.root)
            info = os.fstat(root_fd)
            _require(_private(info, 0o700))
            _require((info.st_dev, info.st_ino) == (self.device, self.inode))
            _require(set(os.listdir(root_fd)) == names(role))
            result = {}
            for name, size, digest in self.expected.records:
                fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=root_fd)
                try:
                    before = os.fstat(fd)
                    _require(stat.S_ISREG(before.st_mode) and _private(before, 0o400))
                    _require(before.st_nlink == 1 and before.st_size == size)
                    data = bytearray()
                    while len(data) <= size:
                        chunk = os.read(fd, min(65536, size + 1 - len(data)))
                        if not chunk:
                            break
                        data.extend(chunk)
                    after = os.fstat(fd)
                    _require(_stable(before) == _stable(after) and len(data) == size)
                    _require(sha256(data).digest() == digest)
                    result[name] = bytes(data)
                finally:
                    os.close(fd)
            _require(set(os.listdir(root_fd)) == names(role))
            current_fd = _directory(self.root)
            current = os.fstat(current_fd)
            _require(_private(current, 0o700))
            _require((current.st_dev, current.st_ino) == (self.device, self.inode))
            return result
        except Exception:
            raise MaterialDenied() from None
        finally:
            for fd in (current_fd, root_fd):
                if fd is not None:
                    os.close(fd)

    def verify(self, role, fingerprint):
        """Read-only local snapshot check; not mounted-volume or PKI attestation."""
        self._snapshot(role, fingerprint)
        return True

    def archive(self, role, fingerprint):
        """Verified bytes -> exact UID 10001 tar, never reread during packing.

        Caller must pass privately to a bounded installer and verify the actual
        volume afterward. No extraction, Docker execution or disk output here.
        """
        snapshot = self._snapshot(role, fingerprint)
        output = io.BytesIO()
        with tarfile.open(fileobj=output, mode="w", format=tarfile.USTAR_FORMAT) as archive:
            root = tarfile.TarInfo(".")
            root.type, root.mode, root.uid, root.gid = tarfile.DIRTYPE, 0o500, 10001, 10001
            archive.addfile(root)
            for name, data in sorted(snapshot.items()):
                entry = tarfile.TarInfo(name)
                entry.size, entry.mode, entry.uid, entry.gid = len(data), 0o400, 10001, 10001
                archive.addfile(entry, io.BytesIO(data))
        return output.getvalue()
