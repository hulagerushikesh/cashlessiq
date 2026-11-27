"""Prepared manual reviewed provider entry; requires external host supervision.

The private plan contains a full reviewed pin, never a credential. The PAT stays
in the existing provider-only file and is opened only after authenticated v2 IPC.
No installer/service/route selects this entry or grants network/activation policy.
"""

import hashlib
import json
import os
import resource
import signal
import sys
from contextlib import suppress

from ciq_api.agent_claim_runner import _alarm, guard_process
from ciq_api.agent_contracts import canonical_json
from ciq_api.agent_private_file import private_object, require
from ciq_api.agent_provider_identity import PLAN, _guard
from ciq_api.agent_provider_peer import ReviewedProviderPeer
from ciq_api.agent_single_call_journal import ReviewedCallPin

PROCESS_SECONDS = 15
READY = b"single_call_provider_ready\n"
ERROR = b"single_call_provider_unavailable\n"


def serve():
    _guard()
    plan = private_object(PLAN, 4096)
    require(set(plan) == {"protocol", "pin"} and plan["protocol"] == "ciq-private-provider-v2")
    pin = ReviewedCallPin.model_validate_json(canonical_json(plan["pin"]))
    # Canonical equality is checked again by the provider identity before PAT
    # access; normalized, differently encoded private pins cannot silently match.
    require(plan["pin"] == json.loads(pin.canonical()))
    peer = ReviewedProviderPeer(hashlib.sha256(pin.canonical().encode()).hexdigest())
    try:
        peer.bind()
        require(os.write(1, READY) == len(READY))
        peer.serve_once(timeout=12.0)
    finally:
        peer.close()


def main():
    try:
        guard_process()
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        signal.signal(signal.SIGALRM, _alarm)
        signal.signal(signal.SIGTERM, _alarm)
        signal.alarm(PROCESS_SECONDS)
        serve()
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
