"""Inactive, single-use custody/provider IPC; not live execution authorization.

Fixed Linux identities and endpoint, one complete pinned request per connection.
No route, runner, installer, fake coordinator or service selects this module.
The trusted future supervisor must gate launch on independently retained live
issue. A peer UID and a private body pin do not establish that durable permission.
"""

import hashlib
import math
import os
import resource
import socket
import stat
import struct
import sys
import threading
import time
from pathlib import Path

from ciq_api.agent_https_process import MAX_PROCESS_SECONDS
from ciq_api.agent_https_transport import MAX_REQUEST_BYTES, MAX_RESPONSE_BYTES
from ciq_api.agent_provider_identity import PROVIDER_UID, PrivateProviderAttempt
from ciq_api.agent_provider_identity import _guard as provider_guard

CUSTODY_UID = 53002
ENDPOINT = Path("/run/ciq-agent-provider/ipc/provider.sock")
ERROR = "agent_provider_peer_unavailable"
_REQUEST = b"CIQ-PROVIDER-REQUEST-1\n"
_RESPONSE = b"CIQ-PROVIDER-RESPONSE-1\n"


def _require(value):
    if not value:
        raise ValueError(ERROR)


def _custody_guard():
    _require(sys.platform == "linux" and sys.flags.isolated and sys.dont_write_bytecode)
    _require(os.getresuid() == (CUSTODY_UID,) * 3)
    _require(os.getresgid() == (CUSTODY_UID,) * 3 and not os.getgroups())
    _require(resource.getrlimit(resource.RLIMIT_CORE) == (0, 0))
    _require(not set(os.environ) - {"LANG", "LC_CTYPE"})


def _path(*, connected):
    # Fixed source constant only. Never follow a symlink or adopt/remove an old
    # endpoint. Host root and all code sharing these UIDs remain trusted.
    _require(ENDPOINT.is_absolute() and ".." not in ENDPOINT.parts
             and len(os.fsencode(ENDPOINT)) <= 100)
    for parent in ENDPOINT.parents:
        item = parent.lstat()
        _require(stat.S_ISDIR(item.st_mode) and item.st_uid in (0, PROVIDER_UID)
                 and not item.st_mode & 0o022)
    if connected:
        item = ENDPOINT.lstat()
        _require(stat.S_ISSOCK(item.st_mode) and item.st_uid == PROVIDER_UID
                 and stat.S_IMODE(item.st_mode) == 0o666)
    else:
        _require(not ENDPOINT.exists() and not ENDPOINT.is_symlink())


def _peer(connection, uid):
    _require(sys.platform == "linux" and hasattr(socket, "SO_PEERCRED"))
    pid, actual_uid, actual_gid = struct.unpack(
        "3i", connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12),
    )
    _require(pid > 0 and actual_uid == uid and actual_gid == uid)


def _end(timeout):
    _require(type(timeout) in (int, float) and math.isfinite(timeout)
             and 0 < timeout <= MAX_PROCESS_SECONDS)
    return time.monotonic() + timeout


def _remaining(end):
    remaining = end - time.monotonic()
    _require(remaining > 0)
    return remaining


def _read(connection, size, end):
    raw = bytearray()
    while len(raw) < size:
        connection.settimeout(_remaining(end))
        # No ancillary buffer: passed descriptors are discarded by the kernel;
        # truncation flags reject the frame before any credential read.
        chunk, ancillary, flags, _ = connection.recvmsg(min(size - len(raw), 8192), 0)
        _require(chunk and not ancillary and not flags)
        raw.extend(chunk)
    return bytes(raw)


def _eof(connection, end):
    connection.settimeout(_remaining(end))
    chunk, ancillary, flags, _ = connection.recvmsg(1, 0)
    _require(not chunk and not ancillary and not flags)


class _Once:
    __slots__ = ("_lock", "_used")

    def __init__(self):
        self._lock, self._used = threading.Lock(), False

    def _consume(self):
        with self._lock:
            _require(not self._used)
            self._used = True


class ProviderPeerClient(_Once):
    """Custody receives raw response only, never a token or transport object.

    Every attempt, including invalid input/lost acknowledgment, consumes this
    object. Reconstruction is NOT replay protection or permission to reissue.
    """

    __slots__ = ()

    def exchange(self, body: bytes, *, timeout: float) -> bytes:
        try:
            self._consume()
            end = _end(timeout)
            _custody_guard()
            _require(type(body) is bytes and 0 < len(body) <= MAX_REQUEST_BYTES)
            digest = hashlib.sha256(body).digest()
            _path(connected=True)
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
                connection.settimeout(_remaining(end))
                connection.connect(str(ENDPOINT))
                _peer(connection, PROVIDER_UID)  # Before sending any request bytes.
                connection.settimeout(_remaining(end))
                connection.sendall(_REQUEST + struct.pack("!I", len(body)) + digest + body)
                connection.shutdown(socket.SHUT_WR)
                _require(_read(connection, len(_RESPONSE), end) == _RESPONSE)
                _require(_read(connection, 32, end) == digest)
                length = struct.unpack("!I", _read(connection, 4, end))[0]
                _require(0 < length <= MAX_RESPONSE_BYTES)
                response = _read(connection, length, end)
                _eof(connection, end)
                _remaining(end)
                return response
        except Exception:
            raise ValueError(ERROR) from None


class ProviderPeer(_Once):
    """One manually owned listener and attempt; no loop, activation or retry.

    Authentication precedes reads; complete framing/digest/EOF precedes opening
    the private plan/PAT. No paths, hostnames, grants or timeouts arrive over IPC.
    The server's original budget includes waiting, framing and provider work.
    """

    __slots__ = ("_listener",)

    def __init__(self):
        super().__init__()
        self._listener = None

    def bind(self):
        listener = None
        try:
            # Binding twice, even after failure, cannot replace an owned socket.
            self._consume()
            provider_guard()
            _path(connected=False)
            listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            listener.bind(str(ENDPOINT))
            # Custody has no provider group. DAC permits connecting; kernel
            # credentials remain mandatory before either side transfers data.
            ENDPOINT.chmod(0o666)
            listener.listen(1)
            self._listener = listener
        except Exception:
            if listener is not None:
                listener.close()
            raise ValueError(ERROR) from None

    def serve_once(self, *, timeout: float):
        listener = None
        try:
            with self._lock:
                listener, self._listener = self._listener, None
            _require(listener is not None)
            end = _end(timeout)
            provider_guard()
            listener.settimeout(_remaining(end))
            connection, _ = listener.accept()
            with connection:
                _peer(connection, CUSTODY_UID)  # Before framing or private files.
                _require(_read(connection, len(_REQUEST), end) == _REQUEST)
                length = struct.unpack("!I", _read(connection, 4, end))[0]
                _require(0 < length <= MAX_REQUEST_BYTES)
                digest = _read(connection, 32, end)
                body = _read(connection, length, end)
                _require(hashlib.sha256(body).digest() == digest)
                _eof(connection, end)  # No concatenation/extensions before I/O.
                response = PrivateProviderAttempt().exchange(body, timeout=_remaining(end))
                _require(type(response) is bytes and 0 < len(response) <= MAX_RESPONSE_BYTES)
                connection.settimeout(_remaining(end))
                connection.sendall(_RESPONSE + digest + struct.pack("!I", len(response)) + response)
                connection.shutdown(socket.SHUT_WR)
                _remaining(end)
        except Exception:
            raise ValueError(ERROR) from None
        finally:
            if listener is not None:
                listener.close()
            # Do not unlink a path in runtime code. The trusted supervisor owns
            # fresh creation, lifetime and teardown, including failed binds.

    def close(self):
        """Release an unused listener without removing/adopting its pathname."""
        with self._lock:
            listener, self._listener = self._listener, None
        if listener is not None:
            listener.close()
