"""Inactive PostgreSQL ledger exercised only with a fake gateway in tests.

No routes, scheduling, transport, credentials or live grants. Each method owns a
short transaction. In particular, begin_submission commits BEFORE the caller's
fake I/O. A crashed caller cannot obtain a second submission permit. These
permits are local execution receipts, not provider idempotency guarantees.
"""

from datetime import datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import AwareDatetime, Field, TypeAdapter, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ciq_api.agent_contracts import (
    AgentContext,
    AgentContractError,
    AgentInput,
    Digest,
    ImmutableContract,
    capture_input,
    require_current,
    validate_candidate,
)
from ciq_api.agent_ledger_models import (
    AgentAttempt,
    AgentComparison,
    AgentExecutionGrant,
    AgentOperation,
)
from ciq_api.assessment import fingerprint
from ciq_api.models import AppUser, Membership, Tenant
from ciq_api.mvp_models import CaseInputRevision, MvpEvent, PolicyVersion, SubmittedCase
from ciq_api.review_models import ReviewCase

Limit = Annotated[int, Field(strict=True, ge=1, le=30)]
Units = Annotated[int, Field(strict=True, ge=1, le=1_000_000)]


class FakeGrantSpec(ImmutableContract):
    mode: Literal["fake-only"] = "fake-only"
    approval_ref: str = Field(min_length=1, max_length=120, repr=False)
    operation_keys: tuple[Digest, ...] = Field(min_length=1, max_length=30)
    config_digest: Digest
    source_digest: Digest
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    case_limit: Limit
    concurrency_limit: Limit
    units_per_attempt: Units
    unit_limit: Annotated[int, Field(strict=True, ge=1, le=30_000_000)]

    @model_validator(mode="after")
    def coherent(self):
        if (
            self.ends_at <= self.starts_at
            or len(set(self.operation_keys)) != len(self.operation_keys)
            or self.case_limit > len(self.operation_keys)
            or self.concurrency_limit > self.case_limit
            or self.unit_limit < self.units_per_attempt
        ):
            raise ValueError("invalid_fake_grant")
        return self


class OperationReceipt(ImmutableContract):
    operation_id: UUID
    state: str
    version: int


class ClaimReceipt(OperationReceipt):
    fence_id: UUID


class SubmissionPermit(ClaimReceipt):
    tenant_id: UUID
    actor_id: UUID
    attempt_id: UUID
    submission_id: UUID
    snapshot: AgentInput = Field(repr=False)


def operation_key(snapshot: AgentInput, config_digest: str, source_digest: str) -> str:
    """Stable computation identity; correlation, assignment and command IDs buy no call."""
    # Validate configuration hashes even when this helper is used independently.
    config_digest = TypeAdapter(Digest).validate_python(config_digest)
    source_digest = TypeAdapter(Digest).validate_python(source_digest)
    binding = snapshot.binding.model_dump(mode="json", exclude={"correlation_id", "review_version"})
    return fingerprint(
        {
            "key_version": 1,
            "binding": binding,
            "config_digest": config_digest,
            "source_digest": source_digest,
        }
    )


def _now(db) -> datetime:
    # PostgreSQL clock, not a worker-provided timestamp or transaction start time.
    return db.scalar(select(func.clock_timestamp()))


def _lock(db, model, *conditions):
    return db.scalar(
        select(model).where(*conditions).with_for_update().execution_options(populate_existing=True)
    )


def _scope(db, tenant_id, actor_id, request_id, correlation_id):
    """Fresh trusted rows, same tenant-first lock order as current MVP writers."""
    tenant = _lock(db, Tenant, Tenant.id == tenant_id)
    user = _lock(db, AppUser, AppUser.id == actor_id)
    member = _lock(
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
    case = _lock(
        db,
        SubmittedCase,
        SubmittedCase.tenant_id == tenant_id,
        SubmittedCase.request_id == request_id,
    )
    if not case or not case.record:
        raise AgentContractError("scope_unavailable")
    policy = _lock(
        db, PolicyVersion, PolicyVersion.tenant_id == tenant_id, PolicyVersion.id == case.policy_id
    )
    review = _lock(
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


def _receipt(op):
    return OperationReceipt(operation_id=op.id, state=op.state, version=op.version)


def _window(grant, now):
    if grant.mode != "fake-only" or not grant.starts_at <= now < grant.ends_at:
        raise AgentContractError("grant_unavailable")


def _lease(op, fence_id, now):
    if (
        op.fence_id != fence_id
        or op.lease_until is None
        or not op.created_at <= now < min(op.deadline, op.lease_until)
    ):
        raise AgentContractError("expired_or_lost_run")


def _settle(grant, op, state):
    """Conservative units: unknown retains a concurrency slot and all its allowance."""
    op.state = state
    op.version += 1
    grant.reserved_units -= grant.units_per_attempt
    if state == "unknown":
        grant.uncertain_units += grant.units_per_attempt
    else:
        grant.in_flight -= 1
        if state != "expired":
            grant.consumed_units += grant.units_per_attempt


def _replacement_fence(db, tenant_id, request_id, config_digest, source_digest, operation_id=None):
    """Conservative application fence, under _scope's tenant/request locks.

    Changing a manifest/configuration is not reconciliation or permission to buy
    another call. Only a never-submitted, expired reservation can be replaced.
    An unresolved attempt also blocks amended inputs under the same mapping.
    There is deliberately no automatic override or live reconciliation path.
    """
    priors = db.execute(
        select(
            AgentOperation.id,
            AgentOperation.state,
            AgentOperation.config_digest,
            AgentOperation.source_digest,
        ).where(
            AgentOperation.tenant_id == tenant_id,
            AgentOperation.request_id == request_id,
            AgentOperation.state != "expired",
        )
    )
    for prior in priors:
        if prior.id == operation_id:
            continue
        if prior.config_digest != config_digest or prior.source_digest != source_digest:
            raise AgentContractError("mapping_replacement_requires_review")
        if prior.state in {"submitting", "unknown"}:
            raise AgentContractError("unresolved_execution")


class FakeAgentLedger:
    """Engineering seam only. Fake-only schema cannot admit a live execution grant."""

    def __init__(self, engine):
        self.engine = engine

    def capture(self, tenant_id: UUID, actor_id: UUID, request_id: str) -> AgentInput:
        with Session(self.engine) as db, db.begin():
            return _scope(db, tenant_id, actor_id, request_id, uuid4())[0]

    def create_fake_grant(self, tenant_id: UUID, spec: FakeGrantSpec) -> UUID:
        # No HTTP/admin endpoint calls this. A fake approval reference is NOT live
        # spending permission. A future live grant requires a separately reviewed path.
        spec = FakeGrantSpec.model_validate(spec)
        grant_id = uuid4()
        with Session(self.engine) as db, db.begin():
            db.add(
                AgentExecutionGrant(
                    tenant_id=tenant_id,
                    id=grant_id,
                    **spec.model_dump(exclude={"operation_keys"}),
                    operation_keys=list(spec.operation_keys),
                    admitted=0,
                    in_flight=0,
                    reserved_units=0,
                    consumed_units=0,
                    uncertain_units=0,
                )
            )
        return grant_id

    def reserve(
        self,
        tenant_id: UUID,
        actor_id: UUID,
        request_id: str,
        grant_id: UUID,
        *,
        correlation_id: UUID,
        config_digest: str,
        source_digest: str,
        timeout_seconds: int = 120,
    ) -> OperationReceipt:
        if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 120:
            raise AgentContractError("invalid_deadline")
        with Session(self.engine) as db, db.begin():
            snapshot, _ = _scope(db, tenant_id, actor_id, request_id, correlation_id)
            key = operation_key(snapshot, config_digest, source_digest)
            grant = _lock(
                db,
                AgentExecutionGrant,
                AgentExecutionGrant.tenant_id == tenant_id,
                AgentExecutionGrant.id == grant_id,
            )
            if not grant:
                raise AgentContractError("grant_unavailable")
            # Identity excludes the grant: another grant cannot repurchase this operation.
            prior = _lock(
                db,
                AgentOperation,
                AgentOperation.tenant_id == tenant_id,
                AgentOperation.operation_key == key,
            )
            if prior:
                return _receipt(prior)
            _replacement_fence(db, tenant_id, request_id, config_digest, source_digest)
            now = _now(db)
            _window(grant, now)
            if (
                key not in grant.operation_keys
                or config_digest != grant.config_digest
                or source_digest != grant.source_digest
                or grant.admitted >= grant.case_limit
                or grant.in_flight >= grant.concurrency_limit
                or grant.reserved_units
                + grant.consumed_units
                + grant.uncertain_units
                + grant.units_per_attempt
                > grant.unit_limit
            ):
                raise AgentContractError("allowance_unavailable")
            op = AgentOperation(
                tenant_id=tenant_id,
                id=uuid4(),
                actor_id=actor_id,
                request_id=request_id,
                grant_id=grant_id,
                operation_key=key,
                config_digest=config_digest,
                source_digest=source_digest,
                snapshot=snapshot.model_dump(mode="json"),
                state="reserved",
                version=0,
                created_at=now,
                deadline=min(now + timedelta(seconds=timeout_seconds), grant.ends_at),
            )
            grant.admitted += 1
            grant.in_flight += 1
            grant.reserved_units += grant.units_per_attempt
            db.add(op)
            db.flush()
            return _receipt(op)

    def _owned(self, db, tenant_id, actor_id, operation_id):
        # Unlocked lookup is safe only for immutable identifiers; all authority
        # and mutable fields are re-read under locks before use.
        locator = db.get(AgentOperation, (tenant_id, operation_id))
        if not locator or locator.actor_id != actor_id:
            raise AgentContractError("scope_unavailable")
        captured = AgentInput.model_validate(locator.snapshot)
        _, current = _scope(
            db, tenant_id, actor_id, locator.request_id, captured.binding.correlation_id
        )
        grant = _lock(
            db,
            AgentExecutionGrant,
            AgentExecutionGrant.tenant_id == tenant_id,
            AgentExecutionGrant.id == locator.grant_id,
        )
        op = _lock(
            db,
            AgentOperation,
            AgentOperation.tenant_id == tenant_id,
            AgentOperation.id == operation_id,
        )
        return grant, op, captured, current

    def claim(self, tenant_id: UUID, actor_id: UUID, operation_id: UUID) -> ClaimReceipt:
        with Session(self.engine) as db, db.begin():
            grant, op, snapshot, current = self._owned(db, tenant_id, actor_id, operation_id)
            require_current(snapshot, current)
            now = _now(db)
            _window(grant, now)
            if (
                op.state != "reserved"
                or not op.created_at <= now < op.deadline
                or (op.lease_until is not None and now < op.lease_until)
            ):
                raise AgentContractError("claim_unavailable")
            op.fence_id = uuid4()
            op.lease_until = min(now + timedelta(seconds=30), op.deadline)
            op.version += 1
            db.flush()
            return ClaimReceipt(**_receipt(op).model_dump(), fence_id=op.fence_id)

    def heartbeat(self, tenant_id: UUID, actor_id: UUID, claim: ClaimReceipt) -> ClaimReceipt:
        with Session(self.engine) as db, db.begin():
            grant, op, snapshot, current = self._owned(db, tenant_id, actor_id, claim.operation_id)
            require_current(snapshot, current)
            now = _now(db)
            _window(grant, now)
            _lease(op, claim.fence_id, now)
            if op.state not in {"reserved", "submitting"} or op.version != claim.version:
                raise AgentContractError("invalid_run_transition")
            op.lease_until = min(now + timedelta(seconds=30), op.deadline)
            op.version += 1
            db.flush()
            return ClaimReceipt(**_receipt(op).model_dump(), fence_id=op.fence_id)

    def begin_submission(
        self,
        tenant_id: UUID,
        actor_id: UUID,
        claim: ClaimReceipt,
    ) -> SubmissionPermit:
        with Session(self.engine) as db, db.begin():
            grant, op, snapshot, current = self._owned(db, tenant_id, actor_id, claim.operation_id)
            require_current(snapshot, current)
            now = _now(db)
            _window(grant, now)
            _lease(op, claim.fence_id, now)
            if op.state != "reserved" or op.version != claim.version:
                raise AgentContractError("automatic_retry_forbidden")
            # Recheck immediately before the durable checkpoint, including old
            # reservations created before this application fence was introduced.
            _replacement_fence(
                db, tenant_id, op.request_id, op.config_digest, op.source_digest, op.id
            )
            attempt = AgentAttempt(
                tenant_id=tenant_id,
                id=uuid4(),
                operation_id=op.id,
                attempt_number=1,
                submission_id=uuid4(),
                fence_id=op.fence_id,
                submitted_at=now,
            )
            op.state = "submitting"
            op.version += 1
            db.add(attempt)
            db.flush()
            permit = SubmissionPermit(
                **_receipt(op).model_dump(),
                fence_id=op.fence_id,
                tenant_id=tenant_id,
                actor_id=actor_id,
                attempt_id=attempt.id,
                submission_id=attempt.submission_id,
                snapshot=snapshot,
            )
        # Commit completed before returning permission to the test fake gateway.
        return permit

    def publish_fake_result(self, permit: SubmissionPermit, raw: bytes) -> OperationReceipt:
        with Session(self.engine) as db, db.begin():
            grant, op, snapshot, current = self._owned(
                db, permit.tenant_id, permit.actor_id, permit.operation_id
            )
            now = _now(db)
            _window(grant, now)
            _lease(op, permit.fence_id, now)
            attempt = db.get(AgentAttempt, (permit.tenant_id, permit.attempt_id))
            if (
                not attempt
                or attempt.operation_id != op.id
                or attempt.submission_id != permit.submission_id
                or attempt.fence_id != permit.fence_id
                or permit.snapshot != snapshot
            ):
                raise AgentContractError("invalid_submission_receipt")
            if op.state == "published":
                return _receipt(op)
            if op.state != "submitting":
                raise AgentContractError("automatic_retry_forbidden")
            try:
                require_current(snapshot, current)
            except AgentContractError:
                _settle(grant, op, "superseded")
            else:
                try:
                    candidate = validate_candidate(snapshot, current, op.id, raw)
                except AgentContractError:
                    _settle(grant, op, "rejected")
                else:
                    db.add(
                        AgentComparison(
                            tenant_id=op.tenant_id,
                            operation_id=op.id,
                            attempt_id=attempt.id,
                            candidate=candidate.model_dump(mode="json"),
                            published_at=now,
                        )
                    )
                    # The comparison row is the atomic clinical publication receipt.
                    # No workflow record/reviewer decision/audit/outbox is modified.
                    _settle(grant, op, "published")
            db.flush()
            return _receipt(op)

    def recover_expired(self, tenant_id: UUID, operation_id: UUID) -> OperationReceipt:
        """Status-only recovery: never calls a provider or releases uncertain cost.

        Grant->operation locks only, with no later acquisition of workflow locks.
        This can conservatively account for a revoked/finalized user's abandoned
        operation without reacquiring their clinical capability.
        """
        with Session(self.engine) as db, db.begin():
            locator = db.get(AgentOperation, (tenant_id, operation_id))
            if not locator:
                raise AgentContractError("scope_unavailable")
            grant = _lock(
                db,
                AgentExecutionGrant,
                AgentExecutionGrant.tenant_id == tenant_id,
                AgentExecutionGrant.id == locator.grant_id,
            )
            op = _lock(
                db,
                AgentOperation,
                AgentOperation.tenant_id == tenant_id,
                AgentOperation.id == operation_id,
            )
            now = _now(db)
            if op.state == "reserved" and now >= op.deadline:
                _settle(grant, op, "expired")
            elif op.state == "submitting" and now >= min(op.lease_until, op.deadline):
                _settle(grant, op, "unknown")
            db.flush()
            return _receipt(op)
