"""Clinical comparison views and held request intent; no execution or recovery."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ciq_api.agent_contracts import (
    AgentContext,
    AgentContractError,
    AgentInput,
    AgentLine,
    EvidenceReference,
    ImmutableContract,
    Money,
    canonical_json,
    require_current,
    validate_candidate,
)
from ciq_api.agent_ledger_models import AgentComparison, AgentOperation
from ciq_api.agent_requests import (
    AgentRequestCommand,
    AgentRequestContext,
    AgentRequestReceipt,
    request_comparison,
    waiting_request,
)
from ciq_api.agent_scope import capture_scope
from ciq_api.contracts import MeResponse, Outcome
from ciq_api.mvp_models import SubmittedCase
from ciq_api.review_models import ReviewCase


class ComparisonResult(ImmutableContract):
    outcome: Outcome
    claimed_inr: Money | None
    payable_inr: Money | None
    lines: tuple[AgentLine, ...]
    citations: tuple[EvidenceReference, ...]
    explanation: str = Field(min_length=1, max_length=4000, repr=False)


class AgentResultView(ImmutableContract):
    mode: Literal["synthetic-only"] = "synthetic-only"
    state: Literal[
        "not_requested",
        "awaiting_executor",
        "unavailable",
        "stale",
        "reserved",
        "submitting",
        "unknown",
        "rejected",
        "published",
        "superseded",
        "expired",
    ]
    operation_id: UUID | None = None
    created_at: datetime | None = None
    deadline: datetime | None = None
    published_at: datetime | None = None
    policy_version: str | None = None
    input_revision: int | None = None
    review_version: int | None = None
    comparison: ComparisonResult | None = None
    request_context: AgentRequestContext | None = None
    request_job_id: UUID | None = None


def result_view(operation, comparison, current: AgentContext, actor_id: UUID) -> AgentResultView:
    """Project only an owned, current snapshot; revalidate stored private output."""
    if operation is None:
        return AgentResultView(state="not_requested")
    try:
        snapshot = AgentInput.model_validate(operation.snapshot)
        binding = snapshot.binding
        if (
            operation.actor_id != actor_id
            or operation.tenant_id != current.binding.tenant_id
            or operation.request_id != current.binding.request_id
        ):
            raise AgentContractError("scope_unavailable")
        # Correlation is provenance, not authority. All content and review fences
        # must still match the fresh server-owned context under clinical locks.
        context = current.model_copy(
            update={
                "binding": current.binding.model_copy(
                    update={"correlation_id": binding.correlation_id}
                )
            }
        )
        try:
            require_current(snapshot, context)
        except AgentContractError:
            return AgentResultView(state="stale")
        details = None
        published_at = None
        if operation.state == "published":
            if (
                comparison is None
                or comparison.tenant_id != operation.tenant_id
                or comparison.operation_id != operation.id
            ):
                raise AgentContractError("comparison_unavailable")
            candidate = validate_candidate(
                snapshot, context, operation.id, canonical_json(comparison.candidate).encode()
            )
            details = ComparisonResult.model_validate(
                candidate.model_dump(
                    include={
                        "outcome",
                        "claimed_inr",
                        "payable_inr",
                        "lines",
                        "citations",
                        "explanation",
                    }
                )
            )
            published_at = comparison.published_at
        return AgentResultView(
            state=operation.state,
            operation_id=operation.id,
            created_at=operation.created_at,
            deadline=operation.deadline,
            published_at=published_at,
            policy_version=binding.policy_version,
            input_revision=binding.input_revision,
            review_version=binding.review_version,
            comparison=details,
        )
    except (ValueError, TypeError, KeyError, RecursionError):
        # No Pydantic error or stored clinical body may cross the HTTP boundary.
        return AgentResultView(state="unavailable")


def register_agent_results(app, config, identity, get_session):
    def enabled():
        if not config.synthetic_workflows:
            raise HTTPException(404, "Not found")

    router = APIRouter(
        prefix="/v3", tags=["synthetic agent results"], dependencies=[Depends(enabled)]
    )
    Identity = Annotated[MeResponse, Depends(identity)]
    Database = Annotated[Session, Depends(get_session)]

    @router.get(
        "/requests/{request_id}/agent-result",
        response_model=AgentResultView,
        operation_id="get_synthetic_agent_result",
    )
    def read(request_id: str, who: Identity, db: Database):
        if who.role != "medical_officer":
            raise HTTPException(403, "Medical officer access required")
        if db.get(SubmittedCase, (who.tenant.id, request_id)) is None:
            raise HTTPException(404, "Request not found")
        try:
            snapshot, current = capture_scope(db, who.tenant.id, who.user.id, request_id, uuid4())
        except (ValueError, TypeError, KeyError, RecursionError):
            return AgentResultView(state="unavailable")
        # One statement observes atomic publication; no ledger row locks, writes,
        # receipt access, lease renewal, status recovery or generic-job retries.
        row = db.execute(
            select(AgentOperation, AgentComparison)
            .outerjoin(
                AgentComparison,
                (
                    (AgentComparison.tenant_id == AgentOperation.tenant_id)
                    & (AgentComparison.operation_id == AgentOperation.id)
                ),
            )
            .where(
                AgentOperation.tenant_id == who.tenant.id,
                AgentOperation.request_id == request_id,
            )
            .order_by(AgentOperation.created_at.desc(), AgentOperation.id.desc())
            .limit(1)
            .execution_options(populate_existing=True)
        ).first()
        view = result_view(*(row or (None, None)), current, who.user.id)
        review = db.get(ReviewCase, (who.tenant.id, request_id))
        if row is None and review.assignee_id == who.user.id:
            waiting = waiting_request(db, who, request_id, snapshot)
            if waiting:
                return view.model_copy(
                    update={
                        "state": "awaiting_executor",
                        "request_job_id": waiting.id,
                    }
                )
            return view.model_copy(
                update={
                    "request_context": AgentRequestContext(
                        input_revision=snapshot.binding.input_revision,
                        review_version=snapshot.binding.review_version,
                    )
                }
            )
        return view

    @router.post(
        "/requests/{request_id}/agent-request",
        response_model=AgentRequestReceipt,
        status_code=202,
        operation_id="request_synthetic_agent_comparison",
    )
    def request(request_id: str, payload: AgentRequestCommand, who: Identity, db: Database):
        return request_comparison(db, who, request_id, payload)

    app.include_router(router)
