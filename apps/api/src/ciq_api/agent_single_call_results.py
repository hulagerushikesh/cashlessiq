"""Read-only advisory projection. No receipt, provider, recovery or execution I/O.

The trusted API supplies authenticated identity and freshly locked clinical
context. The separately granted SQL function returns a private scoped record;
only a revalidated, current candidate can cross the HTTP boundary.
"""

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from ciq_api.agent_contracts import (
    AgentContext,
    AgentContractError,
    AgentInput,
    ImmutableContract,
    canonical_json,
    require_current,
    validate_candidate,
)
from ciq_api.agent_results import AgentResultView, ComparisonResult

PROFILE = "reviewed-single-call"
READ = text("SELECT ciq_agent_single_call.read_advisory(:tenant, :actor, :request)")


class _Advisory(ImmutableContract):
    operation_id: UUID
    tenant_id: UUID
    actor_id: UUID
    request_id: str = Field(min_length=1, max_length=120)
    phase: Literal["staged", "checkpointed", "published"]
    snapshot: AgentInput = Field(repr=False)
    checkpoint_at: AwareDatetime | None
    deadline: AwareDatetime | None
    published_at: AwareDatetime | None
    candidate: dict | None = Field(repr=False)


def single_call_result(row, current: AgentContext, actor_id: UUID) -> AgentResultView:
    """Pure projection; corrupt, foreign or stale records disclose no metadata."""
    def view(state, **values):
        return AgentResultView(state=state, execution_profile=PROFILE, **values)

    if row is None:
        return view("not_requested")
    try:
        record = _Advisory.model_validate(row)
        snapshot, binding = record.snapshot, record.snapshot.binding
        if not (
            record.actor_id == actor_id
            and record.tenant_id == current.binding.tenant_id == binding.tenant_id
            and record.request_id == current.binding.request_id == binding.request_id
        ):
            raise AgentContractError("scope_unavailable")
        context = current.model_copy(update={"binding": current.binding.model_copy(
            update={"correlation_id": binding.correlation_id},
        )})
        try:
            require_current(snapshot, context)
        except AgentContractError:
            return view("stale")
        details = None
        if record.phase == "staged":
            if any(value is not None for value in (
                record.checkpoint_at, record.deadline, record.published_at, record.candidate,
            )):
                raise AgentContractError("comparison_unavailable")
            state = "reserved"
        else:
            if not (record.checkpoint_at and record.deadline
                    and record.checkpoint_at < record.deadline):
                raise AgentContractError("comparison_unavailable")
            # A consumed checkpoint is NOT evidence that provider I/O happened
            # or failed. Reads never inspect retained history or authorize retry.
            state = "unknown"
            if record.phase == "published":
                if not (record.published_at
                        and record.checkpoint_at <= record.published_at < record.deadline):
                    raise AgentContractError("comparison_unavailable")
                candidate = validate_candidate(snapshot, context, record.operation_id,
                    canonical_json(record.candidate).encode())
                details = ComparisonResult.model_validate(candidate.model_dump(include={
                    "outcome", "claimed_inr", "payable_inr", "lines", "citations", "explanation",
                }))
                state = "published"
            elif record.candidate is not None or record.published_at is not None:
                raise AgentContractError("comparison_unavailable")
        return view(state, operation_id=record.operation_id, created_at=record.checkpoint_at,
                    deadline=record.deadline, published_at=record.published_at,
                    policy_version=binding.policy_version, input_revision=binding.input_revision,
                    review_version=binding.review_version, comparison=details)
    except (ValueError, TypeError, KeyError, RecursionError):
        return view("unavailable")


def read_single_call_result(db, current: AgentContext, actor_id: UUID) -> AgentResultView:
    """One fixed optional SQL read, retaining the caller's clinical locks.

    A savepoint contains a missing package/grant or rejected SQL read without
    rolling back the authenticated clinical transaction. Never fall back to a
    fake result or expose database errors or private plan/observation fields.
    """
    try:
        with db.begin_nested():
            row = db.scalar(READ, {"tenant": current.binding.tenant_id,
                                  "actor": actor_id, "request": current.binding.request_id})
        return single_call_result(row, current, actor_id)
    except DBAPIError:
        return AgentResultView(state="unavailable", execution_profile=PROFILE)
