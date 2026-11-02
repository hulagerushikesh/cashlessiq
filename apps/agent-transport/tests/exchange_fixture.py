"""Local synthetic test helper only; excluded from the transport image."""

import runpy
import sys
from datetime import UTC, datetime
from pathlib import Path

runtime = runpy.run_path(sys.argv[1])
raw = sys.stdin.buffer.read(runtime["MAX_REQUEST"] + 1)
fixture = Path(sys.argv[2]).read_bytes()
sys.stdout.buffer.write(runtime["respond"](raw, fixture, now=datetime.now(UTC)))
