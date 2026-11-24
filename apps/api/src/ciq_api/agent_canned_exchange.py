"""Fixed-file synthetic response, never a provider or independent observation.

The child shares custody's trusted UID. Clean environment/FDs and bounded pipes
do not establish hostile-child isolation. No credentials are passed to it.
"""

import base64
import hashlib
import json
import os
import resource
import signal
import sys
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path

from ciq_api.agent_executor import MAX_CANDIDATE, MAX_REQUEST, FakeProcessRequest
from ciq_api.agent_private_file import private_object, require, unique

CANDIDATE = Path("/run/ciq-agent-custody/candidate.json")
ERROR = b"fake_canned_exchange_unavailable\n"


def respond(raw, candidate, *, now):
    require(type(raw) is bytes and 0 < len(raw) <= MAX_REQUEST)
    value = json.loads(raw, object_pairs_hook=unique)
    packet = FakeProcessRequest.model_validate(value)
    require(0 < (packet.deadline - now).total_seconds() <= 120)
    # Binding to one operation is checked here; money, evidence and fresh
    # clinical authorization are independently validated by publication.
    require(type(candidate) is dict and candidate.get("run_id") == str(packet.operation_id))
    encoded = json.dumps(candidate, separators=(",", ":")).encode()
    require(0 < len(encoded) <= MAX_CANDIDATE)
    return json.dumps({
        "protocol": "ciq-fake-process-v1", "request_sha256": hashlib.sha256(raw).hexdigest(),
        "candidate_base64": base64.b64encode(encoded).decode(),
    }, separators=(",", ":")).encode()


def alarm(_signum, _frame):
    raise TimeoutError


def main():
    try:
        require(sys.platform == "linux" and sys.flags.isolated and sys.dont_write_bytecode
                and len(sys.argv) == 1 and os.getuid() > 0)
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        signal.signal(signal.SIGALRM, alarm)
        signal.alarm(12)
        candidate = private_object(CANDIDATE, MAX_CANDIDATE)
        raw = sys.stdin.buffer.read(MAX_REQUEST + 1)
        response = respond(raw, candidate, now=datetime.now(UTC))
        # Unbuffered descriptor output: broken pipes cannot flush private data
        # through a shutdown traceback. The caller independently bounds output.
        require(os.write(1, response) == len(response))
        return 0
    except Exception:
        with suppress(OSError):
            os.write(2, ERROR)
        return 1
    finally:
        if sys.platform == "linux":
            signal.alarm(0)


if __name__ == "__main__":
    sys.exit(main())
