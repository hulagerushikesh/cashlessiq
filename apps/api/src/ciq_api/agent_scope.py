"""Fresh locked clinical context shared by inactive execution and read-only views.

This module grants no execution capability and writes no product records.
"""

from sqlalchemy import select

from ciq_api.agent_contracts import AgentContext, AgentContractError, capture_input, require_current
from ciq_api.assessment import fingerprint
from ciq_api.models import AppUser, Membership, Tenant
from ciq_api.mvp_models import CaseInputRevision, MvpEvent, PolicyVersion, SubmittedCase
from ciq_api.review_models import ReviewCase


def lock_row(db, model, *conditions):
    return db.scalar(
        select(model).where(*conditions).with_for_update().execution_options(populate_existing=True)
    )


def capture_scope(db, tenant_id, actor_id, request_id, correlation_id):
    """Fresh trusted rows, same tenant-first lock order as current MVP writers."""
    tenant = lock_row(db, Tenant, Tenant.id == tenant_id)
    user = lock_row(db, AppUser, AppUser.id == actor_id)
    member = lock_row(
        db, Membership, Membership.tenant_id == tenant_id, Membership.user_id == actor_id
    )
    if not (
        tenant
        and tenant.active
        and user
        and user.active
        and member
        and member.active
        and member.role == "medical_officer"
    ):
        raise AgentContractError("scope_unavailable")
    case = lock_row(
        db,
        SubmittedCase,
        SubmittedCase.tenant_id == tenant_id,
        SubmittedCase.request_id == request_id,
    )
    if not case or not case.record:
        raise AgentContractError("scope_unavailable")
    policy = lock_row(
        db, PolicyVersion, PolicyVersion.tenant_id == tenant_id, PolicyVersion.id == case.policy_id
    )
    review = lock_row(
        db, ReviewCase, ReviewCase.tenant_id == tenant_id, ReviewCase.request_id == request_id
    )
    revision = db.scalar(
        select(CaseInputRevision)
        .where(
            CaseInputRevision.tenant_id == tenant_id,
            CaseInputRevision.request_id == request_id,
        )
        .order_by(CaseInputRevision.revision.desc())
        .limit(1)
    )
    if (
        not policy
        or not review
        or not revision
        or revision.digest != fingerprint(case.inputs)
        or revision.digest != fingerprint(revision.inputs)
        or case.record.get("input_digest") != revision.digest
        or case.record.get("policy_version") != policy.version
        or case.record.get("rules_digest") != fingerprint(policy.proposal["rules"])
    ):
        raise AgentContractError("scope_unavailable")
    decisions = set(
        db.scalars(
            select(MvpEvent.action).where(
                MvpEvent.tenant_id == tenant_id,
                MvpEvent.subject_id == str(policy.id),
                MvpEvent.action.in_(("policy_approve", "policy_reject")),
            )
        )
    )
    snapshot = capture_input(
        tenant_id=tenant_id,
        request_id=request_id,
        policy_id=policy.id,
        input_revision=revision.revision,
        review_version=review.version,
        correlation_id=correlation_id,
        facts=case.inputs,
        policy=policy.proposal,
    )
    context = AgentContext(
        binding=snapshot.binding,
        tenant_active=True,
        clinical_authorized=True,
        policy_approved="policy_approve" in decisions and "policy_reject" not in decisions,
        review_open=review.state in {"DRAFT_READY", "IN_REVIEW"}
        and review.assignee_id in {None, actor_id},
    )
    require_current(snapshot, context)
    return snapshot, context
