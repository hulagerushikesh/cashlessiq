"""Inactive authenticated receipt custody; no provider launch or live permit.

Separate from fake grant/receipt IPC. Only hashes and accounting metadata cross
this boundary, never clinical bodies, credentials, paths or caller clocks.
No route, runner, installer or service selects this module.
"""

import hashlib
import os
import resource
import socket
import stat
import struct
import sys
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from time import monotonic
from typing import Annotated, Literal

from pydantic import Field, model_validator

from ciq_api.agent_contracts import Digest, ImmutableContract, canonical_json
from ciq_api.agent_single_call_journal import (
    ReportedTokenUsage,
    ReviewedCallPin,
    SingleCallJournal,
    SingleCallStatus,
)

ENDPOINT = Path("/run/ciq-agent-single-call/ipc/receipt.sock")
CUSTODY_UID, RECEIPT_UID = 53002, 53003
ERROR = "single_call_peer_unavailable"
MAX_PACKET, IPC_SECONDS = 4096, 2.0
_REQUEST, _RESPONSE = b"CIQ-CALL-RECEIPT-1\n", b"CIQ-CALL-STATUS-1\n"


def _require(value):
    if not value:
        raise ValueError(ERROR)


class _Observation(ImmutableContract):
    response_sha256: Digest
    provider_run_id: Annotated[str, Field(min_length=1, max_length=200)] = Field(repr=False)
    usage: ReportedTokenUsage

    @model_validator(mode="after")
    def printable_id(self):
        _require(all(32 <= ord(char) <= 126 for char in self.provider_run_id))
        return self


class _Request(ImmutableContract):
    version: Literal["single-call-receipt-v1"]
    pin_sha256: Digest
    command: Literal["status", "issue", "observe"]
    observation: _Observation | None

    @model_validator(mode="after")
    def shape(self):
        _require((self.command == "observe") == (self.observation is not None))
        return self


class _Response(ImmutableContract):
    version: Literal["single-call-status-v1"]
    pin_sha256: Digest
    command: Literal["status", "issue", "observe"]
    status: SingleCallStatus


def _parse(raw, model):
    _require(type(raw) is bytes and 0 < len(raw) <= MAX_PACKET)
    value = model.model_validate_json(raw)
    _require(canonical_json(value.model_dump(mode="json")).encode() == raw)
    return value


def _guard(uid):
    _require(sys.platform == "linux" and sys.flags.isolated and sys.dont_write_bytecode)
    _require(os.getresuid() == (uid,) * 3 and os.getresgid() == (uid,) * 3)
    _require(not os.getgroups() and resource.getrlimit(resource.RLIMIT_CORE) == (0, 0))
    _require(not set(os.environ) - {"LANG", "LC_CTYPE"})


def _path(*, connected):
    _require(ENDPOINT.is_absolute() and ".." not in ENDPOINT.parts
             and len(os.fsencode(ENDPOINT)) <= 100)
    for parent in ENDPOINT.parents:
        item = parent.lstat()
        _require(stat.S_ISDIR(item.st_mode) and item.st_uid in (0, RECEIPT_UID)
                 and not item.st_mode & 0o022)
    if connected:
        item = ENDPOINT.lstat()
        _require(stat.S_ISSOCK(item.st_mode) and item.st_uid == RECEIPT_UID
                 and stat.S_IMODE(item.st_mode) == 0o666)
    else:
        _require(not ENDPOINT.exists() and not ENDPOINT.is_symlink())


def _peer(connection, uid):
    _require(sys.platform == "linux" and hasattr(socket, "SO_PEERCRED"))
    pid, actual_uid, actual_gid = struct.unpack(
        "3i", connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12),
    )
    _require(pid > 0 and actual_uid == uid and actual_gid == uid)


def _remaining(end):
    remaining = end - monotonic()
    _require(remaining > 0)
    return remaining


def _read(connection, size, end):
    raw = bytearray()
    while len(raw) < size:
        connection.settimeout(_remaining(end))
        part, ancillary, flags, _ = connection.recvmsg(size - len(raw), 0)
        _require(part and not ancillary and not flags)
        raw.extend(part)
    return bytes(raw)


def _receive(connection, marker, model, end):
    _require(_read(connection, len(marker), end) == marker)
    length = struct.unpack("!I", _read(connection, 4, end))[0]
    _require(0 < length <= MAX_PACKET)
    value = _parse(_read(connection, length, end), model)
    connection.settimeout(_remaining(end))
    part, ancillary, flags, _ = connection.recvmsg(1, 0)
    _require(not part and not ancillary and not flags)
    _remaining(end)
    return value


def _send(connection, marker, value, end):
    raw = canonical_json(value.model_dump(mode="json")).encode()
    _require(0 < len(raw) <= MAX_PACKET)
    connection.settimeout(_remaining(end))
    connection.sendall(marker + struct.pack("!I", len(raw)) + raw)
    connection.shutdown(socket.SHUT_WR)
    _remaining(end)


class SingleCallReceiptClient:
    """Fixed endpoint and reviewed pin, no retry after any uncertain exchange.

    A reconstructed client may inspect status, but an issued journal denies a
    second issue. No status response recreates original dispatch permission.
    """

    def __init__(self, pin: ReviewedCallPin):
        try:
            _require(type(pin) is ReviewedCallPin)
            self._pin = ReviewedCallPin.model_validate(
                pin.model_dump(mode="python", warnings=False),
            )
            self._digest = hashlib.sha256(self._pin.canonical().encode()).hexdigest()
            self._lock, self._failed = Lock(), False
        except Exception:
            raise ValueError(ERROR) from None

    def status(self):
        return self._call("status")

    def issue(self):
        # Intentionally no return ticket/status for a mutating command.
        self._call("issue")

    def observe(self, response_sha256: str, *, provider_run_id: str, usage: ReportedTokenUsage):
        self._call("observe", {"response_sha256": response_sha256,
                               "provider_run_id": provider_run_id, "usage": usage})

    def _call(self, command, observation=None):
        with self._lock:
            try:
                _require(not self._failed)
                end = monotonic() + IPC_SECONDS
                _guard(CUSTODY_UID)
                if observation is not None:
                    _require(type(observation["usage"]) is ReportedTokenUsage)
                    observation = observation | {"usage": ReportedTokenUsage.model_validate(
                        observation["usage"].model_dump(mode="python", warnings=False),
                    )}
                request = _Request(version="single-call-receipt-v1", pin_sha256=self._digest,
                                   command=command, observation=observation)
                # Revalidate even instances built with unsafe model_copy().
                request = _parse(canonical_json(request.model_dump(mode="json")).encode(), _Request)
                _path(connected=True)
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
                    connection.settimeout(_remaining(end))
                    connection.connect(str(ENDPOINT))
                    _peer(connection, RECEIPT_UID)  # Before sending any pins.
                    _send(connection, _REQUEST, request, end)
                    response = _receive(connection, _RESPONSE, _Response, end)
                _require(response.pin_sha256 == self._digest and response.command == command)
                status = response.status
                ready, observed = status.phase == "ready", status.phase == "observed"
                _require(status.reserved_units == (self._pin.reserved_units if ready else 0)
                         and status.uncertain_units == (0 if ready else self._pin.reserved_units))
                _require((status.issued_at is None) == ready)
                if not ready:
                    _require(self._pin.starts_at <= status.issued_at <= self._pin.ends_at)
                _require(all((value is not None) == observed for value in (
                    status.response_sha256, status.provider_run_id, status.reported_usage,
                )))
                if command == "issue":
                    _require(status.phase == "issued")
                elif command == "observe":
                    observation = request.observation
                    _require(observed and status.response_sha256 == observation.response_sha256
                             and status.provider_run_id == request.observation.provider_run_id
                             and status.reported_usage == request.observation.usage)
                if observed:
                    _Observation(
                        response_sha256=status.response_sha256,
                        provider_run_id=status.provider_run_id, usage=status.reported_usage,
                    )
                _remaining(end)
                return status
            except Exception:
                self._failed = True
                raise ValueError(ERROR) from None


class SingleCallReceiptPeer:
    """One manually owned listener and request. No loop or automatic activation.

    Issue uses the receipt process's wall clock, never the client's. The future
    supervisor must still fence clock rollback, approval revocation and the
    overall clinical deadline. Commit/ack ambiguity never authorizes retry.
    """

    def __init__(self, journal: SingleCallJournal):
        try:
            _require(type(journal) is SingleCallJournal)
            self._journal = journal
            self._lock, self._used, self._listener = Lock(), False, None
        except Exception:
            raise ValueError(ERROR) from None

    def bind(self):
        listener = None
        try:
            with self._lock:
                _require(not self._used)
                self._used = True
            _guard(RECEIPT_UID)
            _path(connected=False)
            listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            listener.bind(str(ENDPOINT))
            ENDPOINT.chmod(0o666)
            listener.listen(1)
            self._listener = listener
        except Exception:
            if listener is not None:
                listener.close()
            raise ValueError(ERROR) from None

    def serve_once(self):
        listener = None
        try:
            with self._lock:
                listener, self._listener = self._listener, None
            _require(listener is not None)
            end = monotonic() + IPC_SECONDS
            _guard(RECEIPT_UID)
            listener.settimeout(_remaining(end))
            connection, _ = listener.accept()
            with connection:
                _peer(connection, CUSTODY_UID)  # Before reading/mutating retention.
                request = _receive(connection, _REQUEST, _Request, end)
                _require(request.pin_sha256 == self._journal.pin_sha256)
                if request.command == "issue":
                    self._journal.issue(now=datetime.now(UTC))
                elif request.command == "observe":
                    observation = request.observation
                    self._journal.observe_digest(observation.response_sha256,
                                                 provider_run_id=observation.provider_run_id,
                                                 usage=observation.usage)
                status = self._journal.status()  # Recheck retained pin, including status requests.
                _send(connection, _RESPONSE, _Response(
                    version="single-call-status-v1", pin_sha256=request.pin_sha256,
                    command=request.command, status=status,
                ), end)
        except Exception:
            raise ValueError(ERROR) from None
        finally:
            if listener is not None:
                listener.close()

    def close(self):
        """Supervisor releases an unused listener; never removes its pathname."""
        with self._lock:
            listener, self._listener = self._listener, None
        if listener is not None:
            listener.close()
