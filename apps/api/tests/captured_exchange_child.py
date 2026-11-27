"""Explicit test helper only; never packaged as a runtime entrypoint."""

import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from ciq_api.agent_captured_exchange import MAX_FIXTURE_BYTES, respond_captured_fake
from ciq_api.agent_executor import MAX_REQUEST

try:
    assert not {"DATABASE_URL", "SNOWFLAKE_TOKEN", "PYTHONPATH"} & os.environ.keys()
    with Path(sys.argv[1]).open("rb") as stream:
        fixture = stream.read(MAX_FIXTURE_BYTES + 1)
    raw = sys.stdin.buffer.read(MAX_REQUEST + 1)
    sys.stdout.buffer.write(respond_captured_fake(raw, fixture, now=datetime.now(UTC)))
    sys.stdout.buffer.flush()
except Exception:
    # No traceback/clinical diagnostics across process boundaries.
    sys.exit(1)
