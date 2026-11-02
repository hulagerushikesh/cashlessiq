"""Pure fake-stage lifecycle for contract tests, never an execution adapter.

No worker imports this module. Receipts are immutable in-memory simulation
values, NOT durable duplicate-call protection. A real stage still needs a
transactional run ledger, lease renewal/fencing and an approved cost policy.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, model_validator

from ciq_api.agent_contracts import (
    AgentCandidate,
    AgentContext,
    AgentContractError,
    AgentInput,
    ImmutableContract,
    require_current,
    validate_candidate,
)


class SimulatedRun(ImmutableContract):
    run_id: UUID
    fence_id: UUID
    snapshot: AgentInput
    reserved_at: AwareDatetime
    deadline: AwareDatetime
    state: Literal["reserved", "unknown", "rejected", "validated"] = "reserved"
    candidate: AgentCandidate | None = None

    @model_validator(mode="after")
    def coherent(self):
        if not 0 < (self.deadline - self.reserved_at).total_seconds() <= 120:
            raise ValueError("Invalid simulated deadline")
        if (self.state == "validated") != (self.candidate is not None):
            raise ValueError("Invalid simulated result state")
        if self.candidate is not None and (
            self.candidate.binding != self.snapshot.binding or self.candidate.run_id != self.run_id
        ):
            raise ValueError("Invalid simulated result binding")
        return self


def reserve_fake_call(
    snapshot: AgentInput,
    current: AgentContext,
    *,
    run_id: UUID,
    fence_id: UUID,
    now: datetime,
    deadline: datetime,
    prior: SimulatedRun | None = None,
) -> SimulatedRun:
    require_current(snapshot, current)
    # Conservatively deny replay of every prior state, including uncertain calls.
    if prior is not None:
        raise AgentContractError("automatic_retry_forbidden")
    return SimulatedRun(
        run_id=run_id, fence_id=fence_id, snapshot=snapshot, reserved_at=now, deadline=deadline
    )


def _require_receipt(run, current, fence_id, now):
    require_current(run.snapshot, current)
    if now.tzinfo is None or now.utcoffset() is None:
        raise AgentContractError("invalid_clock")
    if (
        run.state != "reserved"
        or run.fence_id != fence_id
        or not run.reserved_at <= now < run.deadline
    ):
        raise AgentContractError("expired_or_lost_run")


def uncertain_fake_call(run: SimulatedRun) -> SimulatedRun:
    """Timeout/disconnect does not mean the remote operation stopped or was free."""
    if run.state != "reserved":
        raise AgentContractError("invalid_run_transition")
    return SimulatedRun(**{**run.model_dump(), "state": "unknown"})


def receive_fake_result(
    run: SimulatedRun, current: AgentContext, *, fence_id: UUID, now: datetime, raw: bytes
) -> SimulatedRun:
    _require_receipt(run, current, fence_id, now)
    try:
        candidate = validate_candidate(run.snapshot, current, run.run_id, raw)
    except AgentContractError:
        return SimulatedRun(**{**run.model_dump(), "state": "rejected"})
    return SimulatedRun(
        **{
            **run.model_dump(),
            "state": "validated",
            "candidate": candidate,
        }
    )


def comparison_for_publication(
    run: SimulatedRun, current: AgentContext, *, fence_id: UUID, now: datetime
) -> AgentCandidate:
    """Recheck current scope at the hypothetical transaction boundary; no I/O."""
    require_current(run.snapshot, current)
    if (
        now.tzinfo is None
        or now.utcoffset() is None
        or run.state != "validated"
        or run.fence_id != fence_id
        or not run.reserved_at <= now < run.deadline
    ):
        raise AgentContractError("publication_forbidden")
    # Revalidate even if a receipt was reconstructed by a caller.
    return validate_candidate(
        run.snapshot, current, run.run_id, run.candidate.model_dump_json().encode()
    )
