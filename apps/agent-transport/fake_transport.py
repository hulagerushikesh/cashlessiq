"""Stdlib-only, one-shot FAKE fixture transport. No live provider capability.

The fixed file contains a synthetic canned response bound to one exact request.
It is not a credential store or independent source observation. No input field
can select a file, credential, command, endpoint, tenant grant or retry mode.
"""

import base64
import hashlib
import json
import signal
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

MAX_REQUEST = 1_200_000
MAX_FIXTURE = 180_000
MAX_CANDIDATE = 128_000
PROTOCOL = "ciq-fake-process-v1"
FIXTURE = Path("/run/ciq-fake/response.json")


def unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError
        value[key] = item
    return value


def respond(raw, fixture_raw, *, now):
    if not 0 < len(raw) <= MAX_REQUEST or not 0 < len(fixture_raw) <= MAX_FIXTURE:
        raise ValueError
    request = json.loads(raw, object_pairs_hook=unique)
    fixture = json.loads(fixture_raw, object_pairs_hook=unique)
    if set(request) != {
        "protocol", "operation_id", "attempt_id", "submission_id", "tenant_id",
        "config_digest", "source_digest", "deadline", "snapshot",
    } or request["protocol"] != PROTOCOL:
        raise ValueError
    for key in ("operation_id", "attempt_id", "submission_id", "tenant_id"):
        if str(UUID(request[key])) != request[key]:
            raise ValueError
    for key in ("config_digest", "source_digest"):
        value = request[key]
        if (
            type(value) is not str or len(value) != 64
            or any(c not in "0123456789abcdef" for c in value)
        ):
            raise ValueError
    deadline = datetime.fromisoformat(request["deadline"].replace("Z", "+00:00"))
    if deadline.tzinfo is None or not 0 < (deadline - now).total_seconds() <= 120:
        raise ValueError
    snapshot = request["snapshot"]
    if (
        type(snapshot) is not dict
        or snapshot.get("binding", {}).get("tenant_id") != request["tenant_id"]
        or set(fixture) != {"request_sha256", "candidate_base64"}
        or fixture["request_sha256"] != hashlib.sha256(raw).hexdigest()
    ):
        raise ValueError
    candidate = base64.b64decode(fixture["candidate_base64"], validate=True)
    if not 0 < len(candidate) <= MAX_CANDIDATE:
        raise ValueError
    return json.dumps({"protocol": PROTOCOL, **fixture}, separators=(",", ":")).encode()


def alarm(_signal, _frame):
    raise TimeoutError


def main():
    # Includes blocked stdin/file reads; container/parent cleanup remains required.
    signal.signal(signal.SIGALRM, alarm)
    signal.alarm(15)
    try:
        if len(sys.argv) != 1 or FIXTURE.is_symlink() or not FIXTURE.is_file():
            raise ValueError
        raw = sys.stdin.buffer.read(MAX_REQUEST + 1)
        with FIXTURE.open("rb") as stream:
            fixture_raw = stream.read(MAX_FIXTURE + 1)
        sys.stdout.buffer.write(respond(raw, fixture_raw, now=datetime.now(UTC)))
        sys.stdout.buffer.flush()
    except Exception:
        # Clinical payload, path and exception details must never reach stderr.
        sys.stderr.write("fake_transport_unavailable\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
