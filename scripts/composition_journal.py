"""Private disposable resource intentions, not an engine or removal authority.

One exclusive writer records reservations before a trusted caller mutates Docker.
Recovery is inspection-only: a leftover reservation is UNKNOWN, never absent.
No credentials, engine output, automatic retry, adoption or cleanup is accepted.
Same-host storage is not independent operational generation/rollback authority.
"""

import fcntl
import json
import os
import re
import stat
from dataclasses import dataclass

from .composition_material import _directory

LIMIT = 1024 * 1024
MAX_EVENTS = 1024


class JournalDenied(ValueError):
    def __init__(self):
        super().__init__("Disposable journal denied; retained resources require review")


def require(value):
    if not value:
        raise JournalDenied()


def private(info, mode):
    require(info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == mode)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode() + b"\n"


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result)
        result[key] = value
    return result


def valid_hex(value):
    return type(value) is str and re.fullmatch("[a-f0-9]{64}", value) is not None


def fold(events):
    require(type(events) is list and 1 <= len(events) <= MAX_EVENTS)
    first = events[0]
    require(type(first) is dict and set(first) == {"version", "prefix"})
    require(type(first["version"]) is int and first["version"] == 1)
    prefix = first["prefix"]
    require(type(prefix) is str and re.fullmatch("ciq-comp-[a-f0-9]{12}", prefix))
    resources, fenced = {}, False
    for event in events[1:]:
        require(type(event) is dict)
        if event == {"action": "fence"}:
            require(not fenced)
            fenced = True
            continue
        require(set(event) == {"action", "kind", "name", "identity", "fingerprint"})
        action, kind, name = event["action"], event["kind"], event["name"]
        identity, fingerprint = event["identity"], event["fingerprint"]
        require(type(kind) is str and kind in {"container", "network", "volume", "image"})
        require(
            type(name) is str and re.fullmatch(re.escape(prefix) + r"-[a-z][a-z0-9-]{0,63}", name)
        )
        require(valid_hex(fingerprint))
        key = (kind, name)
        previous = resources.get(key)
        if action == "reserve":
            require(not fenced and previous is None and identity is None)
            resources[key] = (fingerprint, None, "UNKNOWN")
        else:
            require(previous is not None and fingerprint == previous[0])
            if kind == "volume":
                require(identity == name)
            elif kind == "image":
                require(type(identity) is str and identity.startswith("sha256:"))
                require(valid_hex(identity[7:]))
            else:
                require(valid_hex(identity))
            if action == "observe":
                require(previous[2] == "UNKNOWN")
                require(
                    not any(
                        k != key and k[0] == kind and v[1] == identity for k, v in resources.items()
                    )
                )
                resources[key] = (fingerprint, identity, "PRESENT")
            elif action in {"stopped", "removed"}:
                require(identity == previous[1])
                require(
                    (action == "stopped" and kind == "container" and previous[2] == "PRESENT")
                    or (
                        action == "removed"
                        and previous[2] == ("STOPPED" if kind == "container" else "PRESENT")
                    )
                )
                resources[key] = (fingerprint, identity, action.upper())
            else:
                raise JournalDenied()
    return prefix, resources, fenced


def read(fd):
    info = os.fstat(fd)
    private(info, 0o600)
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and 0 < info.st_size <= LIMIT)
    data = os.pread(fd, LIMIT + 1, 0)
    require(len(data) == info.st_size and data.endswith(b"\n"))
    events = [json.loads(line, object_pairs_hook=unique) for line in data.splitlines()]
    require(b"".join(map(canonical, events)) == data)
    fold(events)
    after = os.fstat(fd)
    require(
        (info.st_size, info.st_mtime_ns, info.st_ctime_ns)
        == (after.st_size, after.st_mtime_ns, after.st_ctime_ns)
    )
    return events


@dataclass(frozen=True)
class Recovery:
    prefix: str
    resources: tuple
    fenced: bool


def inspect(root):
    """Reopen after writer death; metadata only, never resume or remove resources."""
    directory = fd = None
    try:
        directory = _directory(root)
        private(os.fstat(directory), 0o700)
        require(set(os.listdir(directory)) == {"events.jsonl"})
        fd = os.open("events.jsonl", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        prefix, resources, fenced = fold(read(fd))
        require(root.name == prefix)
        return Recovery(prefix, tuple((k, *v) for k, v in resources.items()), fenced)
    except Exception:
        raise JournalDenied() from None
    finally:
        for opened in (fd, directory):
            if opened is not None:
                os.close(opened)


class Journal:
    """Explicit new journal only. Keep outside actor/service mounts; no reopen writer."""

    def __init__(self, parent, prefix):
        self.fd = self.directory = None
        self.failed = False
        self.events = [{"version": 1, "prefix": prefix}]
        parent_fd = None
        try:
            fold(self.events)  # Validate before mutation.
            parent_fd = _directory(parent)
            private(os.fstat(parent_fd), 0o700)
            os.mkdir(prefix, 0o700, dir_fd=parent_fd)
            self.root = parent / prefix
            self.directory = _directory(self.root)
            private(os.fstat(self.directory), 0o700)
            self.fd = os.open(
                "events.jsonl",
                os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=self.directory,
            )
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._write(canonical(self.events[0]))
            os.fsync(self.directory)
            os.fsync(parent_fd)
        except Exception:
            self.failed = True
            self.close()
            raise JournalDenied() from None
        finally:
            if parent_fd is not None:
                os.close(parent_fd)

    def _write(self, data):
        while data:
            written = os.write(self.fd, data)
            require(written > 0)
            data = data[written:]
        os.fsync(self.fd)

    def record(self, action, *, kind, name, identity=None, fingerprint):
        """Caller must independently verify engine identity/exit/removal observations.

        Reserve must return before any engine mutation. Returned observation is
        not engine attestation; never use this journal alone to authorize removal.
        """
        self._append(
            dict(action=action, kind=kind, name=name, identity=identity, fingerprint=fingerprint)
        )

    def fence(self):
        self._append({"action": "fence"})

    def check(self):
        """Validate the still-open retained writer without adding an event."""
        try:
            require(not self.failed and self.fd is not None)
            require(read(self.fd) == self.events)
            path_fd = _directory(self.root)
            try:
                current, original = os.fstat(path_fd), os.fstat(self.directory)
                require((current.st_dev, current.st_ino) == (original.st_dev, original.st_ino))
                require(set(os.listdir(path_fd)) == {"events.jsonl"})
                linked = os.stat("events.jsonl", dir_fd=path_fd, follow_symlinks=False)
                require(
                    (linked.st_dev, linked.st_ino)
                    == (os.fstat(self.fd).st_dev, os.fstat(self.fd).st_ino)
                )
                private(os.fstat(path_fd), 0o700)
            finally:
                os.close(path_fd)
        except Exception:
            self.failed = True
            raise JournalDenied() from None

    def _append(self, event):
        try:
            self.check()
            proposed = [*self.events, event]
            fold(proposed)
            payload = canonical(event)
            require(os.fstat(self.fd).st_size + len(payload) <= LIMIT)
            self._write(payload)
            self.events = proposed
        except Exception:
            self.failed = True
            raise JournalDenied() from None

    def close(self):
        for name in ("fd", "directory"):
            fd = getattr(self, name)
            if fd is not None:
                os.close(fd)
                setattr(self, name, None)
