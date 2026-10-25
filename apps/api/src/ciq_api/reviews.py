"""Tenant-scoped synthetic commands; receipt, state, audit and outbox commit once."""

import json
from datetime import UTC, datetime
from hashlib import sha256
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ciq_api.contracts import MeResponse, UserView
from ciq_api.models import AppUser, Membership, Tenant
from ciq_api.review_contracts import (
    ReviewAuditView,
    ReviewCommand,
    ReviewCommentView,
    ReviewPeople,
    ReviewReceipt,
    ReviewView,
)
from ciq_api.review_models import (
    ReviewAudit,
    ReviewCase,
    ReviewCommandReceipt,
    ReviewComment,
    ReviewOutbox,
)

FINAL = {"APPROVED", "APPROVED_WITH_DEDUCTIONS"}


def user_view(session, user_id):
    if user_id is None:
        return None
    user = session.get(AppUser, user_id)
    return UserView(id=user.id, display_name=user.display_name)


def review_view(session, who, request_id, page=1):
    case = session.get(ReviewCase, (who.tenant.id, request_id))
    audit_filter = (ReviewAudit.tenant_id == who.tenant.id, ReviewAudit.request_id == request_id)
    comments_filter = (
        ReviewComment.tenant_id == who.tenant.id,
        ReviewComment.request_id == request_id,
    )
    if who.role != "medical_officer":
        comments_filter += (ReviewComment.visibility == "team",)
    audit = session.scalars(
        select(ReviewAudit)
        .where(*audit_filter)
        .order_by(ReviewAudit.aggregate_version.desc())
        .offset((page - 1) * 50)
        .limit(50)
    ).all()
    comments = session.scalars(
        select(ReviewComment)
        .where(*comments_filter)
        .order_by(ReviewComment.created_at.desc(), ReviewComment.id)
        .offset((page - 1) * 50)
        .limit(50)
    ).all()
    return ReviewView(
        request_id=request_id,
        version=case.version if case else 0,
        state=case.state if case else "DRAFT_READY",
        assignee=user_view(session, case.assignee_id) if case else None,
        final_payable_inr=case.final_payable_inr if case else None,
        clinical_notes_restricted=who.role != "medical_officer",
        history_page=page,
        audit_total=session.scalar(
            select(func.count()).select_from(ReviewAudit).where(*audit_filter)
        ),
        comments_total=session.scalar(
            select(func.count()).select_from(ReviewComment).where(*comments_filter)
        ),
        comments=[
            ReviewCommentView(
                id=c.id,
                actor=user_view(session, c.actor_id),
                visibility=c.visibility,
                body=c.body,
                created_at=c.created_at,
            )
            for c in comments
        ],
        audit=[
            ReviewAuditView(
                event_id=e.event_id,
                aggregate_version=e.aggregate_version,
                actor=user_view(session, e.actor_id),
                actor_role=e.actor_role,
                action=e.action,
                occurred_at=e.occurred_at,
                payload=e.payload,
            )
            for e in audit
        ],
    )


def lock_actor(session, who):
    # A tenant lock serializes this small synthetic MVP's writes. Locks on all
    # identity rows keep revocation from racing a committed reviewer action.
    tenant = session.scalar(select(Tenant).where(Tenant.id == who.tenant.id).with_for_update())
    user = session.scalar(select(AppUser).where(AppUser.id == who.user.id).with_for_update())
    member = session.scalar(
        select(Membership)
        .where(Membership.tenant_id == who.tenant.id, Membership.user_id == who.user.id)
        .with_for_update()
    )
    if (
        not tenant
        or not tenant.active
        or not user
        or not user.active
        or not member
        or not member.active
    ):
        raise HTTPException(403, "Active membership required")
    if member.role != who.role or member.role not in {
        "processor",
        "medical_officer",
        "operations_lead",
    }:
        raise HTTPException(403, "Reviewer write access required")


def append_audit(session, who, case, action, command_id, event_payload, *, now=None, event_id=None):
    now, event_id = now or datetime.now(UTC), event_id or uuid4()
    request_id = case.request_id
    case.version += 1
    case.updated_at = now
    event_payload["state"] = case.state
    session.add(
        ReviewAudit(
            event_id=event_id,
            tenant_id=who.tenant.id,
            request_id=request_id,
            aggregate_version=case.version,
            actor_id=who.user.id,
            actor_role=who.role,
            action=action,
            command_id=command_id,
            payload=event_payload,
            occurred_at=now,
        )
    )
    session.flush()
    session.add(
        ReviewOutbox(
            event_id=event_id,
            tenant_id=who.tenant.id,
            event={
                "event_id": str(event_id),
                "event_type": "cashlessiq.review." + action,
                "schema_version": 1,
                "occurred_at": now.isoformat(),
                "tenant_id": str(who.tenant.id),
                "aggregate_id": request_id,
                "aggregate_version": case.version,
                "correlation_id": str(command_id),
                "causation_id": str(command_id),
                "actor_id": str(who.user.id),
                "actor_role": who.role,
                "payload": event_payload,
            },
        )
    )
    result = ReviewReceipt(
        request_id=request_id, version=case.version, state=case.state, event_id=event_id
    )
    return result


def execute(session, who, snapshot, payload):
    request_id = snapshot.request_id
    fingerprint = sha256(
        json.dumps(
            {"request_id": request_id, **payload.model_dump(mode="json")},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    try:
        with session.begin_nested():
            lock_actor(session, who)
            session.execute(
                insert(ReviewCommandReceipt)
                .values(
                    tenant_id=who.tenant.id,
                    actor_id=who.user.id,
                    command_id=payload.command_id,
                    request_hash=fingerprint,
                )
                .on_conflict_do_nothing()
            )
            receipt = session.scalar(
                select(ReviewCommandReceipt)
                .where(
                    ReviewCommandReceipt.tenant_id == who.tenant.id,
                    ReviewCommandReceipt.actor_id == who.user.id,
                    ReviewCommandReceipt.command_id == payload.command_id,
                )
                .with_for_update()
            )
            if receipt.request_hash != fingerprint:
                raise HTTPException(409, "Command ID was already used for another request")
            if receipt.response is not None:
                return ReviewReceipt.model_validate(receipt.response)
            session.execute(
                insert(ReviewCase)
                .values(
                    tenant_id=who.tenant.id, request_id=request_id, version=0, state="DRAFT_READY"
                )
                .on_conflict_do_nothing()
            )
            case = session.scalar(
                select(ReviewCase)
                .where(ReviewCase.tenant_id == who.tenant.id, ReviewCase.request_id == request_id)
                .with_for_update()
            )
            if case.version != payload.expected_version:
                raise HTTPException(409, "Case changed; refresh before submitting again")
            action, note = payload.action, payload.note.strip()
            if who.role == "operations_lead" and action not in {"assign", "comment"}:
                raise HTTPException(403, "Operations access permits assignment and comments")
            if payload.visibility == "clinical" and who.role != "medical_officer":
                raise HTTPException(403, "Clinical notes require a medical officer")
            if action != "assign" and payload.assignee_id is not None:
                raise HTTPException(422, "Assignee applies only to assignment")
            if (
                action not in {"approve", "approve_with_deductions"}
                and payload.payable_inr is not None
            ):
                raise HTTPException(422, "Payable applies only to an approval")
            if action != "comment" and case.state in FINAL and action != "reopen":
                raise HTTPException(409, "Reopen the completed review before changing it")
            previous, previous_assignee = case.state, case.assignee_id
            event_payload = {"previous_state": previous}
            if action == "assign":
                if who.role == "processor" and (
                    payload.assignee_id != who.user.id
                    or case.assignee_id not in {None, who.user.id}
                ):
                    raise HTTPException(403, "Processors can claim only an unassigned case")
                if payload.assignee_id is not None:
                    target = session.execute(
                        select(AppUser, Membership)
                        .join(Membership, Membership.user_id == AppUser.id)
                        .where(
                            AppUser.id == payload.assignee_id, Membership.tenant_id == who.tenant.id
                        )
                        .with_for_update()
                    ).one_or_none()
                    if (
                        target is None
                        or not target[0].active
                        or not target[1].active
                        or target[1].role not in {"processor", "medical_officer"}
                    ):
                        raise HTTPException(
                            422, "Assignee must be an active reviewer in this tenant"
                        )
                if (
                    previous_assignee is not None
                    and previous_assignee != payload.assignee_id
                    and not note
                ):
                    raise HTTPException(422, "Reassignment requires a reason")
                case.assignee_id = payload.assignee_id
                if case.state in {"DRAFT_READY", "IN_REVIEW"}:
                    case.state = "IN_REVIEW" if case.assignee_id else "DRAFT_READY"
                event_payload["assignee_id"] = str(case.assignee_id) if case.assignee_id else None
            else:
                if action not in {"comment", "reopen"} and case.assignee_id != who.user.id:
                    raise HTTPException(403, "Claim or assign the case before acting on it")
                if not note:
                    raise HTTPException(422, "A comment or action reason is required")
                if (
                    action in {"query", "refer", "approve", "approve_with_deductions"}
                    and case.state != "IN_REVIEW"
                ):
                    raise HTTPException(409, "This action requires an active review")
                if action == "query":
                    case.state = "NEEDS_INFORMATION"
                elif action == "refer":
                    case.state = "REFERRED"
                elif action == "resume":
                    if case.state not in {"NEEDS_INFORMATION", "REFERRED"}:
                        raise HTTPException(409, "Only a query or referral can be resumed")
                    if case.state == "REFERRED" and who.role != "medical_officer":
                        raise HTTPException(403, "A medical officer must resume a referral")
                    case.state = "IN_REVIEW"
                elif action == "reopen":
                    if who.role != "medical_officer":
                        raise HTTPException(403, "A medical officer must reopen a final review")
                    if case.state not in FINAL:
                        raise HTTPException(409, "Only completed reviews can be reopened")
                    case.state, case.final_payable_inr = "IN_REVIEW", None
                    case.assignee_id = who.user.id
                    event_payload["assignee_id"] = str(who.user.id)
                elif action in {"approve", "approve_with_deductions"}:
                    if who.role != "medical_officer":
                        raise HTTPException(403, "Final approval requires a medical officer")
                    amount = payload.payable_inr
                    if snapshot.payable_inr is None or not snapshot.lines:
                        raise HTTPException(409, "A validated payable calculation is required")
                    if (
                        amount is None
                        or snapshot.claimed_inr is None
                        or amount > snapshot.claimed_inr
                    ):
                        raise HTTPException(422, "Payable must be between zero and claimed amount")
                    if (action == "approve") != (amount == snapshot.claimed_inr):
                        raise HTTPException(
                            422, "Use approval with deductions for a reduced payable"
                        )
                    case.state = "APPROVED" if action == "approve" else "APPROVED_WITH_DEDUCTIONS"
                    case.final_payable_inr = amount
                    event_payload.update(
                        payable_inr=amount,
                        baseline_payable_inr=snapshot.payable_inr,
                        adjustment_inr=amount - snapshot.payable_inr,
                        calculation_basis="saved_calculation"
                        if amount == snapshot.payable_inr
                        else "human_adjustment",
                        baseline_commit=snapshot.baseline_commit,
                        policy_version=snapshot.policy_version,
                    )
            now, event_id = datetime.now(UTC), uuid4()
            if note:
                comment_id = uuid4()
                session.add(
                    ReviewComment(
                        id=comment_id,
                        tenant_id=who.tenant.id,
                        request_id=request_id,
                        actor_id=who.user.id,
                        visibility=payload.visibility,
                        body=note,
                        created_at=now,
                    )
                )
                event_payload["comment_id"] = str(comment_id)
            result = append_audit(
                session,
                who,
                case,
                action,
                payload.command_id,
                event_payload,
                now=now,
                event_id=event_id,
            )
            receipt.response = result.model_dump(mode="json")
        session.commit()
        return result
    except Exception:
        session.rollback()
        raise


def register_reviews(app, config, identity, get_session, case_repository):
    def enabled():
        if not config.synthetic_workflows:
            raise HTTPException(404, "Not found")

    router = APIRouter(
        prefix="/v3/reviews", tags=["synthetic review workflows"], dependencies=[Depends(enabled)]
    )
    Identity = Annotated[MeResponse, Depends(identity)]
    Database = Annotated[Session, Depends(get_session)]

    def snapshot(session, who, request_id):
        from ciq_api.mvp import submitted_snapshot

        record = submitted_snapshot(session, who, request_id)
        if record is None:
            record = case_repository(who).get_case(who.tenant.id, request_id)
        if record is None:
            raise HTTPException(404, "Case not found")
        return record

    @router.get("/people", response_model=ReviewPeople, operation_id="list_review_people")
    def people(who: Identity, session: Database):
        users = session.scalars(
            select(AppUser)
            .join(Membership, Membership.user_id == AppUser.id)
            .where(
                Membership.tenant_id == who.tenant.id,
                Membership.active.is_(True),
                AppUser.active.is_(True),
                Membership.role.in_(["processor", "medical_officer"]),
            )
            .order_by(AppUser.display_name)
            .limit(100)
        ).all()
        return ReviewPeople(items=[UserView(id=u.id, display_name=u.display_name) for u in users])

    @router.get("/{request_id}", response_model=ReviewView, operation_id="get_review")
    def read(
        request_id: str,
        who: Identity,
        session: Database,
        history_page: Annotated[int, Query(ge=1, le=10000)] = 1,
    ):
        snapshot(session, who, request_id)
        return review_view(session, who, request_id, history_page)

    @router.post(
        "/{request_id}/commands", response_model=ReviewReceipt, operation_id="command_review"
    )
    def command(request_id: str, payload: ReviewCommand, who: Identity, session: Database):
        return execute(session, who, snapshot(session, who, request_id), payload)

    app.include_router(router)
