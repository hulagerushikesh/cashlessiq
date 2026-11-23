"""Clinical request intent only. No grants, leases, attempts or execution authority.

The dedicated executor is not active. These held jobs must never enter the
generic three-attempt worker. A future executor must independently authorize and
recapture the exact current scope; a queued binding is not a permit.
"""

from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import HTTPException
from pydantic import Field, StrictBool, model_validator
from sqlalchemy import select

from ciq_api.agent_contracts import ImmutableContract
from ciq_api.agent_ledger_models import AgentOperation
from ciq_api.agent_scope import capture_scope
from ciq_api.assessment import fingerprint
from ciq_api.mvp import lock_who, prior_event, record_event
from ciq_api.mvp_models import SubmittedCase, WorkJob
from ciq_api.review_models import ReviewCase

KIND = "agent_comparison"


class AgentRequestCommand(ImmutableContract):
    command_id: UUID
    expected_input_revision: Annotated[int, Field(strict=True, ge=0)]
    expected_review_version: Annotated[int, Field(strict=True, ge=0)]
    synthetic_data: StrictBool

    @model_validator(mode="after")
    def fictional_only(self):
        if not self.synthetic_data:
            raise ValueError("Fictional data confirmation required")
        return self


class AgentRequestReceipt(ImmutableContract):
    job_id: UUID
    state: Literal["awaiting_executor"] = "awaiting_executor"


class AgentRequestContext(ImmutableContract):
    input_revision: int
    review_version: int


def binding_digest(snapshot):
    # Correlation identifies a capture, not a new request or execution allowance.
    return fingerprint(snapshot.binding.model_dump(mode="json", exclude={"correlation_id"}))


def waiting_request(db, who, request_id, snapshot):
    return db.scalar(
        select(WorkJob)
        .where(
            WorkJob.tenant_id == who.tenant.id,
            WorkJob.actor_id == who.user.id,
            WorkJob.kind == KIND,
            WorkJob.subject_id == request_id,
            WorkJob.state == "awaiting_executor",
            WorkJob.payload["binding_digest"].astext == binding_digest(snapshot),
        )
        .order_by(WorkJob.created_at.desc(), WorkJob.id.desc())
        .limit(1)
    )


def request_comparison(db, who, request_id, command):
    lock_who(db, who, {"medical_officer"})
    if db.get(SubmittedCase, (who.tenant.id, request_id)) is None:
        raise HTTPException(404, "Request not found")
    digest = fingerprint(
        {"agent_comparison_request": request_id, **command.model_dump(mode="json")}
    )
    # A confirmed repeat acknowledges the original intent; it never queues again,
    # even after the review changes. Membership was freshly checked above.
    prior = prior_event(db, who, command.command_id, digest)
    if prior:
        return AgentRequestReceipt.model_validate(prior.payload)
    try:
        snapshot, _ = capture_scope(db, who.tenant.id, who.user.id, request_id, uuid4())
    except (ValueError, TypeError, KeyError, RecursionError):
        raise HTTPException(409, "Comparison request scope changed") from None
    review = db.get(ReviewCase, (who.tenant.id, request_id))
    if (
        review.assignee_id != who.user.id
        or snapshot.binding.input_revision != command.expected_input_revision
        or snapshot.binding.review_version != command.expected_review_version
    ):
        raise HTTPException(409, "Comparison request scope changed")
    # Existing execution requires operator reconciliation, never a browser retry.
    if (
        db.scalar(
            select(AgentOperation.id)
            .where(
                AgentOperation.tenant_id == who.tenant.id, AgentOperation.request_id == request_id
            )
            .limit(1)
        )
        is not None
    ):
        raise HTTPException(409, "An existing comparison requires review")
    job = waiting_request(db, who, request_id, snapshot)
    if job is None:
        job = WorkJob(
            id=uuid4(),
            tenant_id=who.tenant.id,
            actor_id=who.user.id,
            kind=KIND,
            subject_id=request_id,
            state="awaiting_executor",
            attempts=0,
            # No clinical facts, policy wording, grant, epoch, credentials or paths.
            payload={
                "binding_digest": binding_digest(snapshot),
                "binding": snapshot.binding.model_dump(mode="json", exclude={"correlation_id"}),
            },
        )
        db.add(job)
        db.flush()
    receipt = AgentRequestReceipt(job_id=job.id)
    record_event(
        db,
        who,
        command.command_id,
        "agent_comparison_request",
        request_id,
        digest,
        receipt.model_dump(mode="json"),
    )
    db.commit()
    return receipt
