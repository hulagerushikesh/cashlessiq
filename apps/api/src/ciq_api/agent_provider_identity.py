"""Inactive provider-UID entry, with no service, IPC endpoint or execution grant.

The future provider service must supply the outer sandbox and authenticate a
durably issued original request. Private files alone are NOT such authorization.
No fake coordinator, application route or installed unit imports this module.
"""

import hashlib
import json
import math
import os
import resource
import sys
import threading
import time
from pathlib import Path

from ciq_api.agent_https_process import MAX_PROCESS_SECONDS, BoundedHTTPSProcess
from ciq_api.agent_https_transport import MAX_REQUEST_BYTES, SinglePostHTTPS
from ciq_api.agent_private_file import private_object, read_private

PROVIDER_UID = 53004
PROVIDER_GID = 53004
PLAN = Path("/run/ciq-agent-provider/plan.json")
IDENTITY = Path("/run/ciq-agent-provider/identity.pat")
PYTHON = "/opt/cashlessiq-agent/venv/bin/python"
ERROR = "agent_provider_identity_unavailable"


def _require(value):
    if not value:
        raise ValueError(ERROR)


def _guard():
    _require(sys.platform == "linux" and sys.flags.isolated and sys.dont_write_bytecode)
    _require(os.getresuid() == (PROVIDER_UID,) * 3)
    _require(os.getresgid() == (PROVIDER_GID,) * 3 and not os.getgroups())
    _require(resource.getrlimit(resource.RLIMIT_CORE) == (0, 0))
    _require(not set(os.environ) - {"LANG", "LC_CTYPE"})


class PrivateProviderAttempt:
    """Read the token only inside the distinct, unprivileged provider identity.

    Callers pass request bytes and a decreasing remaining budget, never identity,
    path, interpreter, hostname or a token. Fixed private plan pins the exact body
    and host. One local attempt is not durable replay protection; authenticated
    IPC, live issue, accounting and provider result association remain external.
    """

    __slots__ = ("_lock", "_used")

    def __init__(self):
        self._lock = threading.Lock()
        self._used = False

    def exchange(self, body: bytes, *, timeout: float) -> bytes:
        return self._exchange(body, timeout=timeout, reviewed=False, pin_sha256=None)

    def exchange_reviewed(self, body: bytes, *, timeout: float, pin_sha256: str) -> bytes:
        """Separate v2 plan: match the full reviewed pin before opening the PAT.

        A pin hash is not approval or proof that the PAT has a particular role.
        Trusted provisioning must review the actual token/identity association.
        The original v1 path cannot read a v2 plan, or vice versa.
        """
        return self._exchange(body, timeout=timeout, reviewed=True, pin_sha256=pin_sha256)

    def _exchange(self, body, *, timeout, reviewed, pin_sha256):
        try:
            with self._lock:
                _require(not self._used)
                self._used = True
            started = time.monotonic()
            # Deny identity/environment/budget/input faults before opening any
            # file. Never switch users, retain root, discover credentials or
            # accept selectors from clinical/browser/IPC payloads.
            _guard()
            _require(type(timeout) in (int, float) and math.isfinite(timeout)
                     and 0 < timeout <= MAX_PROCESS_SECONDS)
            end = started + timeout
            _require(type(body) is bytes and 0 < len(body) <= MAX_REQUEST_BYTES)
            if reviewed:
                _require(type(pin_sha256) is str and len(pin_sha256) == 64
                         and all(char in "0123456789abcdef" for char in pin_sha256))
            plan = private_object(PLAN, 4096 if reviewed else 1024)
            keys = {"protocol", "hostname", "request_sha256"}
            _require(set(plan) == ({"protocol", "pin"} if reviewed else keys))
            _require(plan["protocol"] == (
                "ciq-private-provider-v2" if reviewed else "ciq-private-provider-v1"
            ))
            if reviewed:
                # Derive the host/body from the exact committed pin, not from
                # separately editable plan fields next to an asserted digest.
                # Custody validates the full ReviewedCallPin before issuing it.
                pinned = plan["pin"]
                _require(type(pinned) is dict)
                canonical = json.dumps(pinned, sort_keys=True, separators=(",", ":"),
                                       allow_nan=False).encode("utf-8")
                _require(hashlib.sha256(canonical).hexdigest() == pin_sha256)
                plan = {"hostname": pinned["hostname"],
                        "request_sha256": pinned["request_sha256"]}
            digest = hashlib.sha256(body).hexdigest()
            _require(digest == plan["request_sha256"])
            # Validate all nonsecret configuration before reading the identity.
            # This probe creates no connection and is never used for exchange.
            SinglePostHTTPS(hostname=plan["hostname"], token="probe", request_sha256=digest)
            _require(time.monotonic() < end)
            token = read_private(IDENTITY, 8192).decode("ascii")
            # No whitespace normalization, environment/admin CLI fallback or
            # token return. Both parent/child here share ONLY the provider UID.
            transport = BoundedHTTPSProcess(
                python=PYTHON, hostname=plan["hostname"], token=token,
                request_sha256=digest, body=body,
            )
            token = None
            remaining = end - time.monotonic()
            _require(remaining > 0)
            return transport.exchange(timeout=remaining)
        except Exception:
            raise ValueError(ERROR) from None
