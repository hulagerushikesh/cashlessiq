"""Manually launched bounded fake receipt peer. Never provision, reset or retry."""

import os
import resource
import signal
import sys
from contextlib import suppress
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field

from ciq_api.agent_admission import FakeEpochPin, FakeReceiptJournal
from ciq_api.agent_claim_runner import _alarm, guard_process
from ciq_api.agent_contracts import ImmutableContract
from ciq_api.agent_private_file import private_object, read_private, require
from ciq_api.agent_receipt_peer import FakeReceiptPeer

PLAN = Path("/run/ciq-agent-receipts/peer.json")
SOCKET = Path("/run/ciq-agent-receipts/ipc/peer.sock")
JOURNAL = Path("/var/lib/cashlessiq-agent/receipts/retained")
MAX_PLAN = 2048
MAX_CONNECTIONS = 32
IDLE_SECONDS = 10
PROCESS_SECONDS = 60
READY = b"fake_receipt_ready\n"
ERROR = b"fake_receipt_unavailable\n"


class ReceiptPlan(ImmutableContract):
    protocol: Literal["ciq-fake-receipt-v1"]
    epoch: FakeEpochPin
    custody_uid: Annotated[int, Field(strict=True, ge=1, lt=2**31)]


def read_plan():
    return ReceiptPlan.model_validate(private_object(PLAN, MAX_PLAN))


def serve(plan):
    require(type(plan) is ReceiptPlan and plan.custody_uid != os.getuid())
    # Check the fixed retained file and every ancestor before opening SQLite.
    # Owners remain trusted: this is not protection against same-UID/root races.
    read_private(JOURNAL / "fake-receipts.sqlite3", 256 * 1024)
    journal = FakeReceiptJournal(JOURNAL, plan.epoch)
    # Readiness means existing private custody with this active epoch opened.
    # It is NOT approval of history: each command still checks exact SQL history.
    with journal._connection() as db:
        journal._identity(db)
    peer = FakeReceiptPeer(journal, custody_uid=plan.custody_uid)
    with peer.bind(SOCKET) as listener:
        listener.settimeout(IDLE_SECONDS)
        require(os.write(1, READY) == len(READY))
        for _ in range(MAX_CONNECTIONS):
            peer.serve_once(listener)
    # Leave the owned socket name intact. Only an explicitly quiescent trusted
    # operator may remove it; a fresh process cannot adopt a stale endpoint.


def main():
    try:
        guard_process()
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        signal.signal(signal.SIGALRM, _alarm)
        signal.signal(signal.SIGTERM, _alarm)
        signal.alarm(PROCESS_SECONDS)
        serve(read_plan())
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
