"""Prepared manual retained-receipt entry. No provision/reset/rebind/retry."""

import os
import resource
import signal
import sys
from contextlib import suppress
from pathlib import Path
from typing import Literal

from pydantic import Field

from ciq_api.agent_claim_runner import _alarm, guard_process
from ciq_api.agent_contracts import ImmutableContract, canonical_json
from ciq_api.agent_private_file import private_object, read_private, require
from ciq_api.agent_single_call_journal import ReviewedCallPin, SingleCallJournal
from ciq_api.agent_single_call_peer import RECEIPT_UID, SingleCallReceiptPeer, _guard

PLAN = Path("/run/ciq-agent-single-call/receipt.json")
JOURNAL = Path("/var/lib/cashlessiq-agent/single-call/retained")
PROCESS_SECONDS = 25
READY = b"single_call_receipt_ready\n"
ERROR = b"single_call_receipt_unavailable\n"


class ReceiptPlan(ImmutableContract):
    protocol: Literal["ciq-single-call-receipt-v1"]
    pin: ReviewedCallPin = Field(repr=False)


def serve(plan):
    _guard(RECEIPT_UID)
    require(type(plan) is ReceiptPlan)
    # Only open an existing retained file after checking every fixed ancestor.
    # Never create/adopt missing history or restart an issued/observed attempt.
    read_private(JOURNAL / "single-call.sqlite3", 256 * 1024)
    journal = SingleCallJournal(JOURNAL, plan.pin)
    require(journal.status().phase == "ready")
    peer = SingleCallReceiptPeer(journal)
    try:
        peer.bind()
        require(os.write(1, READY) == len(READY))
        peer.serve_attempt()
    finally:
        peer.close()


def main():
    try:
        guard_process()
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        signal.signal(signal.SIGALRM, _alarm)
        signal.signal(signal.SIGTERM, _alarm)
        signal.alarm(PROCESS_SECONDS)
        _guard(RECEIPT_UID)
        serve(ReceiptPlan.model_validate_json(canonical_json(private_object(PLAN, 4096))))
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
