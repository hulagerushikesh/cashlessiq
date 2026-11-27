"""Prepared manual custody entry; never installed, queued, retried or auto-started.

The future trusted supervisor supplies private reviewed files and separate peers.
This entry cannot create authority, provision a journal, read provider credentials,
or recover an earlier attempt. No application route imports it.
"""

import hashlib
import os
import resource
import signal
import sys
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from sqlalchemy import URL, create_engine, event
from sqlalchemy.pool import NullPool

from ciq_api.agent_claim_runner import Identifier, Oid, _alarm, _identity, guard_process
from ciq_api.agent_contracts import ImmutableContract, canonical_json
from ciq_api.agent_private_file import private_object, require
from ciq_api.agent_provider_peer import ReviewedProviderPeerClient
from ciq_api.agent_single_call_journal import ReviewedCallPin
from ciq_api.agent_single_call_peer import CUSTODY_UID, SingleCallReceiptClient, _guard
from ciq_api.agent_single_call_product import ProductSingleCall

PLAN = Path("/run/ciq-agent-custody/single-call.json")
PROCESS_SECONDS = 25
SUCCESS = b"single_call_advisory_published\n"
ERROR = b"single_call_custody_unavailable\n"


class SingleCallPlan(ImmutableContract):
    protocol: Literal["ciq-single-call-custody-v1"]
    database: Identifier
    database_oid: Oid
    login: Identifier
    login_oid: Oid
    password: SecretStr = Field(repr=False, min_length=1, max_length=1024)
    pin: ReviewedCallPin = Field(repr=False)


def read_plan():
    return SingleCallPlan.model_validate_json(canonical_json(private_object(PLAN, 8192)))


def run_once(plan):
    _guard(CUSTODY_UID)
    require(type(plan) is SingleCallPlan)
    now = datetime.now(UTC)
    require(plan.pin.starts_at <= now and (plan.pin.ends_at - now).total_seconds() >= 18)
    digest = hashlib.sha256(plan.pin.canonical().encode()).hexdigest()
    # No host/port/DSN/options/environment discovery or owner credential fallback.
    engine = create_engine(URL.create(
        "postgresql+psycopg", username=plan.login, password=plan.password.get_secret_value(),
        host="127.0.0.1", port=5432, database=plan.database,
    ), poolclass=NullPool, connect_args={
        "connect_timeout": 3, "sslmode": "disable", "gssencmode": "disable",
        "options": "-cstatement_timeout=5000 -clock_timeout=2000 "
                   "-cidle_in_transaction_session_timeout=8000",
    })
    try:
        # Pinned database and login OIDs/names, no role memberships/privilege,
        # checked on EVERY physical connection before protected SQL is exposed.
        event.listen(engine, "connect", lambda raw, _: _identity(raw, plan))
        ProductSingleCall(engine, operation_id=plan.pin.operation_id,
                          receipt=SingleCallReceiptClient(plan.pin),
                          provider=ReviewedProviderPeerClient(digest)).run()
    finally:
        engine.dispose()


def main():
    try:
        guard_process()
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        signal.signal(signal.SIGALRM, _alarm)
        signal.signal(signal.SIGTERM, _alarm)
        signal.alarm(PROCESS_SECONDS)
        _guard(CUSTODY_UID)
        run_once(read_plan())
        require(os.write(1, SUCCESS) == len(SUCCESS))
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
