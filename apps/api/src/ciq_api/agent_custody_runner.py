"""One manually launched fake custody attempt. No worker, recovery or live I/O."""

import os
import resource
import signal
import sys
from contextlib import suppress
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr
from sqlalchemy import URL, create_engine, event
from sqlalchemy.pool import NullPool

from ciq_api.agent_admission import FakeEpochPin
from ciq_api.agent_claim_runner import Identifier, Oid, _alarm, _identity, guard_process
from ciq_api.agent_contracts import ImmutableContract
from ciq_api.agent_custody_submission import FakeCustodySubmission
from ciq_api.agent_executor import BoundedFakeProcess
from ciq_api.agent_ledger import ClaimReceipt
from ciq_api.agent_private_file import private_object, require
from ciq_api.agent_receipt_peer import FakeReceiptPeerClient

PLAN = Path("/run/ciq-agent-custody/custody.json")
SOCKET = Path("/run/ciq-agent-receipts/ipc/peer.sock")
MAX_PLAN = 8192
PROCESS_SECONDS = 35
ERROR = "fake_custody_unavailable\n"
SUCCESS = b"fake_custody_published\n"


class CustodyClaim(ClaimReceipt):
    state: Literal["reserved"]
    version: Annotated[int, Field(strict=True, ge=1, lt=2_147_483_647)]


class CustodyPlan(ImmutableContract):
    protocol: Literal["ciq-fake-custody-v1"]
    database: Identifier
    database_oid: Oid
    login: Identifier
    login_oid: Oid
    password: SecretStr = Field(repr=False, min_length=1, max_length=1024)
    receipts_schema: Annotated[str, Field(
        strict=True, pattern=r"^ciq_agent_receipts(?:_[a-f0-9]{24})?$",
    )]
    request_id: Annotated[str, Field(strict=True, min_length=1, max_length=120)]
    claim: CustodyClaim
    epoch: FakeEpochPin
    receipt_uid: Annotated[int, Field(strict=True, ge=1, lt=2**31)]


def read_plan():
    return CustodyPlan.model_validate(private_object(PLAN, MAX_PLAN))


def run_once(plan):
    require(type(plan) is CustodyPlan and plan.receipt_uid != os.getuid())
    # Kernel UID authentication and private retained history; never direct SQLite
    # or owner-ledger fallback. The independent SQL assignment remains required.
    client = FakeReceiptPeerClient(SOCKET, plan.epoch, server_uid=plan.receipt_uid,
                                   custody_uid=os.getuid())
    engine = create_engine(URL.create(
        "postgresql+psycopg", username=plan.login, password=plan.password.get_secret_value(),
        host="127.0.0.1", port=5432, database=plan.database,
    ), poolclass=NullPool, connect_args={
        "connect_timeout": 3, "sslmode": "disable", "gssencmode": "disable",
        "options": "-cstatement_timeout=5000 -clock_timeout=2000 "
                   "-cidle_in_transaction_session_timeout=8000",
    })
    try:
        event.listen(engine, "connect", lambda raw, _: _identity(raw, plan))
        transport = BoundedFakeProcess((
            sys.executable, "-I", "-B", "-m", "ciq_api.agent_canned_exchange",
        ))
        # Convert a strict startup claim to the exact existing receipt class;
        # never reconstruct an issue permit, checkpoint or private candidate.
        claim = ClaimReceipt.model_validate(plan.claim.model_dump())
        original = FakeCustodySubmission(
            engine, client, schema=plan.receipts_schema, request_id=plan.request_id,
            claim=claim, transport=transport,
        )
        original.run()
    finally:
        engine.dispose()


def main():
    try:
        guard_process()
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        signal.signal(signal.SIGALRM, _alarm)
        signal.alarm(PROCESS_SECONDS)
        run_once(read_plan())
        require(os.write(1, SUCCESS) == len(SUCCESS))
        return 0
    except Exception:
        with suppress(OSError):
            os.write(2, ERROR.encode())
        return 1
    finally:
        if sys.platform == "linux":
            signal.alarm(0)


if __name__ == "__main__":
    sys.exit(main())
