"""Inactive Linux fake receipt IPC. Trusted construction only; no service startup.

One request per connection, both OS identities pinned before payload transfer.
The journal owner is separate from the custody coordinator. No clinical input,
credential, file selector, provision/reset/close command or I/O permit crosses
this boundary. Same-host administrator/UID ownership remains trusted.
"""

import os
import socket
import stat
import struct
import sys
from pathlib import Path
from threading import Lock
from time import monotonic
from typing import Annotated, Literal

from pydantic import Field, model_validator

from ciq_api.agent_admission import (
    ERROR,
    MAX_RECEIPTS,
    FakeCheckpoint,
    FakeEpochPin,
    FakeReceiptJournal,
)
from ciq_api.agent_contracts import AgentContractError, ImmutableContract, canonical_json

MAX_PACKET = 32_768
IPC_SECONDS = 2.0
_OK = b"OK\n"
_NO = b"NO\n"


def _closed():
    raise AgentContractError(ERROR) from None


class _Request(ImmutableContract):
    version: Literal["fake-receipt-peer-v1"]
    epoch: FakeEpochPin
    command: Literal["check", "check_issued", "prepare", "issue"]
    expected: Annotated[tuple[FakeCheckpoint, ...], Field(max_length=MAX_RECEIPTS)]
    selected: FakeCheckpoint | None

    @model_validator(mode="after")
    def exact_shape(self):
        if self.command == "check":
            valid = self.selected is None
        elif self.command == "check_issued":
            valid = self.selected is not None and self.selected in self.expected
        else:
            valid = self.selected is not None and not self.expected
        if not valid or any(
            len({getattr(c, key) for c in self.expected}) != len(self.expected)
            for key in ("operation_id", "submission_id")
        ) or len({(c.tenant_id, c.request_id) for c in self.expected}) != len(self.expected):
            raise ValueError("invalid_peer_request")
        return self


def _parse(raw):
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_PACKET:
        _closed()
    request = _Request.model_validate_json(raw)
    # One representation: rejects duplicate keys, coercions, omitted fields,
    # whitespace tricks and alternate UUID/epoch spellings before any mutation.
    if canonical_json(request.model_dump(mode="json")).encode() != raw:
        _closed()
    return request


def _identity(uid):
    if (
        sys.platform != "linux" or not hasattr(socket, "SO_PEERCRED")
        or type(uid) is not int or not 1 <= uid < 2**31
    ):
        _closed()


def _peer(connection, uid):
    # Read from the connected kernel socket, never a claimed payload identity.
    pid, actual, _gid = struct.unpack(
        "3i", connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12),
    )
    if pid <= 0 or actual != uid:
        _closed()


def _self(uid):
    if os.getresuid() != (uid, uid, uid):
        _closed()  # No effective/saved privileged identity retained by this peer.


def _path(path, server_uid, *, connected):
    path = Path(path)
    if (
        not path.is_absolute() or ".." in path.parts
        or len(os.fsencode(path)) > 100
    ):
        _closed()
    # Every parent must be owned by root or this trusted journal UID, with no
    # group/other write. No abstract socket, symlink or public /tmp ancestor.
    for parent in path.parents:
        details = parent.lstat()
        if (
            not stat.S_ISDIR(details.st_mode) or details.st_uid not in (0, server_uid)
            or details.st_mode & 0o022
        ):
            _closed()
    if connected:
        details = path.lstat()
        if not stat.S_ISSOCK(details.st_mode) or details.st_uid != server_uid:
            _closed()
    elif path.exists() or path.is_symlink():
        _closed()  # Never unlink/adopt a previous listener.
    return path


def _timeout(connection, end):
    remaining = end - monotonic()
    if remaining <= 0:
        _closed()
    connection.settimeout(remaining)


def _read(connection, size, end):
    parts = bytearray()
    while len(parts) < size:
        _timeout(connection, end)
        # No ancillary buffer: the kernel discards/closes passed SCM_RIGHTS;
        # MSG_CTRUNC is rejected. Never install a peer's file descriptor.
        data, ancillary, flags, _address = connection.recvmsg(size - len(parts), 0)
        if not data or ancillary or flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC):
            _closed()
        parts.extend(data)
    return bytes(parts)


def _eof(connection, end):
    _timeout(connection, end)
    data, ancillary, flags, _address = connection.recvmsg(1, 0)
    if data or ancillary or flags:
        _closed()


class FakeReceiptPeerClient:
    """Fixed local endpoint/epoch/UIDs; no retry, fallback or public result.

    Only the exact trusted custody UID can use this object. Any denial, malformed
    reply, timeout or lost reply permanently closes this instance. A replacement
    instance can check retained status; it cannot reconstruct coordinator memory.
    A successful issue acknowledgment is not transport execution authority.
    """

    def __init__(self, path: Path, pin: FakeEpochPin, *, server_uid: int, custody_uid: int):
        try:
            for uid in (server_uid, custody_uid):
                _identity(uid)
            if server_uid == custody_uid or os.getuid() != custody_uid:
                _closed()
            _self(custody_uid)
            self._path = _path(path, server_uid, connected=True)
            self.pin = FakeEpochPin.model_validate_json(pin.model_dump_json())
            self._server_uid, self._custody_uid = server_uid, custody_uid
            self._failed = False
            self._lock = Lock()
        except (OSError, ValueError, TypeError, AttributeError):
            _closed()

    def check(self, expected: tuple[FakeCheckpoint, ...]):
        self._call("check", expected, None)

    def check_issued(self, expected: tuple[FakeCheckpoint, ...], selected: FakeCheckpoint):
        self._call("check_issued", expected, selected)

    def prepare(self, selected: FakeCheckpoint):
        self._call("prepare", (), selected)

    def issue(self, selected: FakeCheckpoint):
        self._call("issue", (), selected)

    def _call(self, command, expected, selected):
        with self._lock:
            if self._failed:
                _closed()
            try:
                raw = canonical_json({
                    "version": "fake-receipt-peer-v1", "epoch": self.pin.model_dump(mode="json"),
                    "command": command, "expected": [c.model_dump(mode="json") for c in expected],
                    "selected": selected.model_dump(mode="json") if selected else None,
                }).encode()
                _parse(raw)
                if os.getuid() != self._custody_uid:
                    _closed()
                _self(self._custody_uid)
                _path(self._path, self._server_uid, connected=True)
                end = monotonic() + IPC_SECONDS
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
                    _timeout(connection, end)
                    connection.connect(str(self._path))
                    _peer(connection, self._server_uid)  # BEFORE sending any pin/history.
                    _timeout(connection, end)
                    connection.sendall(struct.pack("!I", len(raw)) + raw)
                    connection.shutdown(socket.SHUT_WR)
                    if _read(connection, len(_OK), end) != _OK:
                        _closed()
                    _eof(connection, end)
            except (OSError, ValueError, TypeError, AttributeError, RecursionError):
                self._failed = True
                _closed()


class FakeReceiptPeer:
    """Trusted journal UID, sequential bounded requests, no automatic provisioning.

    The supervisor owns process lifetime and the path. bind() never removes a
    stale socket. It supplies the listener to serve_once(); no loop/thread/CLI,
    API route, compose service or startup hook is registered here. Runtime UID
    reuse, hostile code with that UID, root and host loss remain outside proof.
    """

    def __init__(self, journal: FakeReceiptJournal, *, custody_uid: int):
        try:
            _identity(custody_uid)
            _identity(os.getuid())
            if type(journal) is not FakeReceiptJournal or custody_uid == os.getuid():
                _closed()
            _self(os.getuid())
            self._journal, self._custody_uid = journal, custody_uid
            self._uid = os.getuid()
        except (OSError, ValueError, TypeError):
            _closed()

    def bind(self, path: Path):
        connection = None
        try:
            if os.getuid() != self._uid:
                _closed()
            _self(self._uid)
            path = _path(path, self._uid, connected=False)
            connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            connection.bind(str(path))
            # OS authentication remains mandatory even if a clinical/transport
            # UID can connect. The parent cannot be replaced by either caller.
            path.chmod(0o666)
            connection.listen(4)
            return connection
        except (OSError, ValueError, TypeError):
            if connection is not None:
                connection.close()
            _closed()

    def serve_once(self, listener):
        connection, _address = listener.accept()
        with connection:
            end = monotonic() + IPC_SECONDS
            try:
                if os.getuid() != self._uid:
                    _closed()
                _self(self._uid)
                _peer(connection, self._custody_uid)  # BEFORE reading/framing/SQLite.
                length = struct.unpack("!I", _read(connection, 4, end))[0]
                if not 0 < length <= MAX_PACKET:
                    _closed()
                raw = _read(connection, length, end)
                _eof(connection, end)  # Reject concatenated frames BEFORE mutation.
                request = _parse(raw)
                if request.epoch != self._journal.pin:
                    _closed()
                _timeout(connection, end)  # No mutation after expired framing budget.
                if request.command == "check":
                    self._journal.check(request.expected)
                elif request.command == "check_issued":
                    self._journal.check_issued(request.expected, request.selected)
                else:
                    getattr(self._journal, request.command)(request.selected)
                # SQLite commit has already completed. Lost acknowledgement must
                # preserve the committed marker; no rollback/reset/retry here.
                _timeout(connection, end)
                connection.sendall(_OK)
            except (OSError, ValueError, TypeError, AttributeError, RecursionError):
                try:
                    _timeout(connection, end)
                    connection.sendall(_NO)
                except (OSError, ValueError):
                    pass
