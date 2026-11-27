"""Inactive POSIX single-exchange supervisor; no admission or credential isolation.

Trusted construction supplies an installed interpreter and reviewed configuration.
Secrets travel in a private pipe, never argv/environment/files. The child still
shares the caller's UID: do not use this as a live credential-delivery mechanism.
No route, service, worker or fake custody adapter selects this module.
"""

import base64
import hashlib
import json
import math
import os
import selectors
import signal
import subprocess
import threading
import time

from ciq_api.agent_https_transport import (
    MAX_REQUEST_BYTES,
    MAX_RESPONSE_BYTES,
    MAX_SOCKET_SECONDS,
    SinglePostHTTPS,
)

ERROR = "agent_https_process_unavailable"
MAX_PROCESS_SECONDS = 12
MAX_CONTROL_BYTES = 352_000
_ENV = {"LANG": "C.UTF-8"}


def _require(value):
    if not value:
        raise ValueError(ERROR)


class BoundedHTTPSProcess:
    """One original child attempt, including invalid/failed/concurrent calls.

    Installed code, interpreter and caller are trusted. Clean environment, closed
    FDs and a process group are not a filesystem/network/hostile-child sandbox.
    No cross-UID launch, durable issue, refund, retry or publication is provided.
    """

    __slots__ = ("_control", "_lock", "_python", "_used")

    def __init__(self, *, python: str, hostname: str, token: str,
                 request_sha256: str, body: bytes):
        try:
            _require(type(python) is str and os.path.isabs(python) and "\0" not in python)
            _require(type(body) is bytes and 0 < len(body) <= MAX_REQUEST_BYTES)
            _require(hashlib.sha256(body).hexdigest() == request_sha256)
            # Reuse the network primitive's strict configuration validation,
            # without calling exchange or performing any network/credential IO.
            SinglePostHTTPS(hostname=hostname, token=token, request_sha256=request_sha256)
            self._control = json.dumps({
                "hostname": hostname, "token": token, "request_sha256": request_sha256,
                "body": base64.b64encode(body).decode("ascii"),
            }, separators=(",", ":")).encode("ascii")
            _require(len(self._control) <= MAX_CONTROL_BYTES)
            self._python = python
            self._used = False
            self._lock = threading.Lock()
        except Exception:
            raise ValueError(ERROR) from None

    def exchange(self, *, timeout: float) -> bytes:
        """Supervise pipes and process exit against one decreasing local deadline.

        Timeout does not cancel remote work. Retain uncertain allowance externally.
        Popen creation and an unkillable kernel task need an outer service/cgroup
        bound; no claim of an absolute host-level wall-clock guarantee is made.
        """
        child = None
        try:
            with self._lock:
                _require(not self._used)
                self._used = True
                control, self._control = self._control, None
            _require(type(timeout) in (int, float) and math.isfinite(timeout)
                     and 0 < timeout <= MAX_PROCESS_SECONDS)
            end = time.monotonic() + timeout
            child = subprocess.Popen(
                (self._python, "-I", "-B", "-m", "ciq_api.agent_https_worker"),
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                cwd="/", env=_ENV.copy(), close_fds=True, start_new_session=True,
            )
            output = bytearray()
            sent = 0
            with selectors.DefaultSelector() as selector:
                for pipe, event, label in (
                    (child.stdin, selectors.EVENT_WRITE, "input"),
                    (child.stdout, selectors.EVENT_READ, "output"),
                    (child.stderr, selectors.EVENT_READ, "error"),
                ):
                    os.set_blocking(pipe.fileno(), False)
                    selector.register(pipe, event, label)
                while selector.get_map():
                    remaining = end - time.monotonic()
                    _require(remaining > 0)
                    for key, _ in selector.select(remaining):
                        pipe = key.fileobj
                        if key.data == "input":
                            sent += os.write(pipe.fileno(), control[sent:sent + 16_384])
                            if sent == len(control):
                                selector.unregister(pipe)
                                pipe.close()
                                control = None
                        else:
                            chunk = os.read(pipe.fileno(), 16_384)
                            if not chunk:
                                selector.unregister(pipe)
                                pipe.close()
                            else:
                                _require(key.data == "output")
                                _require(len(output) + len(chunk) <= MAX_RESPONSE_BYTES)
                                output.extend(chunk)
            remaining = end - time.monotonic()
            _require(remaining > 0 and child.wait(timeout=remaining) == 0)
            _require(time.monotonic() < end and 0 < len(output) <= MAX_RESPONSE_BYTES)
            return bytes(output)
        except Exception:
            raise ValueError(ERROR) from None
        finally:
            if child is not None:
                # Cleanup is bounded separately. Escaped sessions and unkillable
                # kernel tasks require the future outer cgroup/service policy.
                cleanup_failed = False
                try:
                    try:
                        os.killpg(child.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    except OSError:
                        cleanup_failed = True
                    try:
                        child.wait(timeout=1)
                    except (OSError, subprocess.TimeoutExpired):
                        cleanup_failed = True
                finally:
                    for pipe in (child.stdin, child.stdout, child.stderr):
                        if not pipe.closed:
                            pipe.close()
                if cleanup_failed:
                    raise ValueError(ERROR) from None


def decode_control(raw: bytes):
    """Strict private-pipe framing only; never an execution authorization."""
    try:
        _require(type(raw) is bytes and 0 < len(raw) <= MAX_CONTROL_BYTES)

        def unique(pairs):
            value = {}
            for key, item in pairs:
                _require(key not in value)
                value[key] = item
            return value

        value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique)
        _require(type(value) is dict
                 and set(value) == {"hostname", "token", "request_sha256", "body"})
        _require(type(value["body"]) is str)
        body = base64.b64decode(value["body"], validate=True)
        _require(0 < len(body) <= MAX_REQUEST_BYTES)
        _require(hashlib.sha256(body).hexdigest() == value["request_sha256"])
        transport = SinglePostHTTPS(
            hostname=value["hostname"], token=value["token"],
            request_sha256=value["request_sha256"],
        )
        return transport, body
    except Exception:
        raise ValueError(ERROR) from None


def run_worker(raw: bytes) -> bytes:
    """Single POST; only the externally supervised worker may call this helper."""
    transport, body = decode_control(raw)
    return transport.exchange(body, timeout=MAX_SOCKET_SECONDS)
