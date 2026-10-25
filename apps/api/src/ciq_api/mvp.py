"""Authenticated synthetic MVP endpoints; local workflows never invoke paid services."""

import json
from datetime import UTC, datetime, timedelta
from importlib.resources import files
from types import SimpleNamespace
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ciq_api.assessment import fingerprint
from ciq_api.contracts import MeResponse
from ciq_api.jobs import enqueue
from ciq_api.models import AppUser, Membership, Tenant
from ciq_api.mvp_contracts import (
    Amendment,
    MembershipCommand,
    PolicyAction,
    PolicyProposal,
    RequestSubmission,
    RetryCommand,
)
from ciq_api.mvp_models import (
    AnalyticsEvent,
    CaseInputRevision,
    DocumentUpload,
    MvpEvent,
    PolicyActive,
    PolicyVersion,
    SubmittedCase,
    WorkJob,
)
from ciq_api.pdf_extract import MAX_UPLOAD
from ciq_api.seed import MVP_PROFILES, PROFILES


def lock_who(db, who, roles):
    tenant = db.scalar(
        select(Tenant)
        .where(Tenant.id == who.tenant.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    user = db.scalar(
        select(AppUser)
        .where(AppUser.id == who.user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    member = db.scalar(
        select(Membership)
        .where(Membership.tenant_id == who.tenant.id, Membership.user_id == who.user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if (
        not tenant
        or not tenant.active
        or not user
        or not user.active
        or not member
        or not member.active
        or member.role != who.role
        or who.role not in roles
    ):
        raise HTTPException(403, "Active authorised membership required")


def prior_event(db, who, command_id, digest):
    event = db.scalar(
        select(MvpEvent).where(
            MvpEvent.tenant_id == who.tenant.id,
            MvpEvent.actor_id == who.user.id,
            MvpEvent.command_id == command_id,
        )
    )
    if event and event.fingerprint != digest:
        raise HTTPException(409, "Command ID was already used for another request")
    return event


def record_event(db, who, command_id, action, subject, digest, payload):
    event = MvpEvent(
        id=uuid4(),
        tenant_id=who.tenant.id,
        actor_id=who.user.id,
        actor_role=who.role,
        command_id=command_id,
        action=action,
        subject_id=str(subject),
        fingerprint=digest,
        payload=payload,
    )
    db.add(event)
    db.flush()
    return event


def owned(db, model, identifier, who):
    item = db.get(model, identifier)
    if item is None or item.tenant_id != who.tenant.id:
        raise HTTPException(404, "Not found")
    return item


def submitted_snapshot(db, who, request_id):
    item = db.get(SubmittedCase, (who.tenant.id, request_id))
    if item is None:
        return None
    if not item.record:
        raise HTTPException(409, "Assessment is not ready")
    result = item.record
    return SimpleNamespace(
        request_id=request_id,
        claimed_inr=result["claimed_inr"],
        payable_inr=result["payable_inr"],
        lines=result["payable"]["lines"] if result["payable"] else [],
        baseline_commit=result["rules_digest"],
        policy_version=result["policy_version"],
    )


def policy_status(db, policy):
    events = db.scalars(
        select(MvpEvent).where(
            MvpEvent.tenant_id == policy.tenant_id,
            MvpEvent.subject_id == str(policy.id),
            MvpEvent.action.in_(["policy_approve", "policy_reject"]),
        )
    ).all()
    if any(e.action == "policy_reject" for e in events):
        return "rejected"
    return "approved" if any(e.action == "policy_approve" for e in events) else "proposed"


def regression_job(db, policy):
    return db.scalar(
        select(WorkJob)
        .where(
            WorkJob.tenant_id == policy.tenant_id,
            WorkJob.kind == "regression",
            WorkJob.subject_id == str(policy.id),
        )
        .order_by(WorkJob.created_at.desc())
        .limit(1)
    )


def policy_view(db, policy):
    job = regression_job(db, policy)
    active = db.get(PolicyActive, (policy.tenant_id, policy.product_id))
    previous = (
        owned(
            db,
            PolicyVersion,
            active.version_id,
            SimpleNamespace(tenant=SimpleNamespace(id=policy.tenant_id)),
        )
        if active
        else None
    )
    return {
        "id": policy.id,
        "product_id": policy.product_id,
        "version": policy.version,
        "author_id": policy.author_id,
        "proposal": policy.proposal,
        "status": policy_status(db, policy),
        "active": bool(active and active.version_id == policy.id),
        "activation_id": active.event_id if active else None,
        "regression_job_id": job.id if job else None,
        "regression_state": job.state if job else "missing",
        "regression": job.result if job and job.state == "succeeded" else None,
        "previous_rules": previous.proposal["rules"] if previous else [],
        "previous_clauses": previous.proposal["clauses"] if previous else [],
    }


def register_mvp(app, config, identity, get_session, case_repository):
    def enabled():
        if not config.synthetic_workflows:
            raise HTTPException(404, "Not found")

    router = APIRouter(prefix="/v3", tags=["synthetic MVP"], dependencies=[Depends(enabled)])
    Identity = Annotated[MeResponse, Depends(identity)]
    Database = Annotated[Session, Depends(get_session)]

    def existing_case(db, who, request_id):
        if (
            db.get(SubmittedCase, (who.tenant.id, request_id)) is None
            and case_repository(who).get_case(who.tenant.id, request_id) is None
        ):
            raise HTTPException(404, "Case not found")

    @router.get("/requests", operation_id="list_submitted_requests")
    def requests(who: Identity, db: Database, page: Annotated[int, Query(ge=1, le=10000)] = 1):
        rows = db.scalars(
            select(SubmittedCase)
            .where(SubmittedCase.tenant_id == who.tenant.id)
            .order_by(SubmittedCase.due_at, SubmittedCase.request_id)
            .offset((page - 1) * 50)
            .limit(50)
        ).all()
        from ciq_api.review_models import ReviewCase

        workflow = {r.request_id: db.get(ReviewCase, (who.tenant.id, r.request_id)) for r in rows}
        assignee_ids = {item.assignee_id for item in workflow.values() if item and item.assignee_id}
        assignees = {
            u.id: u.display_name
            for u in db.scalars(select(AppUser).where(AppUser.id.in_(assignee_ids)))
        }
        return {
            "total": db.scalar(
                select(func.count())
                .select_from(SubmittedCase)
                .where(SubmittedCase.tenant_id == who.tenant.id)
            ),
            "page_size": 50,
            "items": [
                {
                    "request_id": r.request_id,
                    "workflow_state": workflow[r.request_id].state
                    if workflow[r.request_id]
                    else ("DRAFT_READY" if r.record else "READY_FOR_ASSESSMENT"),
                    "assignee_id": workflow[r.request_id].assignee_id
                    if workflow[r.request_id]
                    else None,
                    "assignee_name": assignees.get(workflow[r.request_id].assignee_id)
                    if workflow[r.request_id]
                    else None,
                    "member_reference": r.inputs["member_reference"],
                    "priority": r.priority,
                    "received_at": r.created_at,
                    "due_at": r.due_at,
                    "sla_breached": datetime.now(UTC) > r.due_at
                    and (
                        not workflow[r.request_id]
                        or workflow[r.request_id].state
                        not in {"APPROVED", "APPROVED_WITH_DEDUCTIONS"}
                    ),
                    "outcome": r.record["outcome"] if r.record else None,
                    "payable_inr": r.record["payable_inr"] if r.record else None,
                }
                for r in rows
            ],
            "page": page,
        }

    @router.post("/requests", status_code=202, operation_id="submit_request")
    def submit(payload: RequestSubmission, who: Identity, db: Database):
        lock_who(db, who, {"processor", "medical_officer"})
        digest = fingerprint(payload.model_dump(mode="json"))
        prior = prior_event(db, who, payload.command_id, digest)
        if prior:
            return prior.payload
        active = db.get(PolicyActive, (who.tenant.id, payload.product_id))
        if active is None:
            raise HTTPException(409, "No approved active policy for this product")
        policy = owned(db, PolicyVersion, active.version_id, who)
        proposal = PolicyProposal.model_validate(policy.proposal)
        effective = payload.facts.admission_date or datetime.now(UTC).date()
        if effective < proposal.effective_from or (
            proposal.effective_to and effective > proposal.effective_to
        ):
            raise HTTPException(409, "Policy is not effective for this admission")
        request_id = "REQ-" + uuid4().hex[:20]
        case = SubmittedCase(
            tenant_id=who.tenant.id,
            request_id=request_id,
            actor_id=who.user.id,
            command_id=payload.command_id,
            fingerprint=digest,
            policy_id=policy.id,
            inputs=payload.facts.model_dump(mode="json"),
            priority=payload.priority,
            due_at=datetime.now(UTC)
            + timedelta(minutes=30 if payload.priority == "urgent" else 60),
        )
        db.add(case)
        db.flush()
        db.add(
            CaseInputRevision(
                tenant_id=who.tenant.id,
                request_id=request_id,
                revision=0,
                actor_id=who.user.id,
                inputs=case.inputs,
                digest=fingerprint(case.inputs),
            )
        )
        job = enqueue(
            db, who, "assessment", request_id, {"policy_id": str(policy.id), "inputs": case.inputs}
        )
        response = {"request_id": request_id, "job_id": str(job.id)}
        record_event(db, who, payload.command_id, "request_submit", request_id, digest, response)
        db.commit()
        return response

    @router.get("/requests/{request_id}", operation_id="get_submitted_request")
    def request_detail(request_id: str, who: Identity, db: Database):
        case = db.get(SubmittedCase, (who.tenant.id, request_id))
        if case is None:
            raise HTTPException(404, "Case not found")
        facts = dict(case.inputs)
        result = case.record
        if who.role != "medical_officer":
            facts = {
                key: value
                for key, value in facts.items()
                if key
                not in {
                    "diagnosis",
                    "procedure",
                    "clinical_note",
                    "icd10_code",
                    "declared_conditions",
                }
            }
            result = (
                {
                    key: result[key]
                    for key in (
                        "request_id",
                        "outcome",
                        "claimed_inr",
                        "payable_inr",
                        "policy_version",
                        "input_digest",
                        "rules_digest",
                        "policy_id",
                    )
                }
                if result
                else None
            )
        return {
            "request_id": request_id,
            "facts": facts,
            "assessment": result,
            "clinical_restricted": who.role != "medical_officer",
            "due_at": case.due_at,
        }

    @router.post("/requests/{request_id}/amend", status_code=202, operation_id="amend_request")
    def amend(request_id: str, payload: Amendment, who: Identity, db: Database):
        from ciq_api.review_models import ReviewCase, ReviewComment
        from ciq_api.reviews import append_audit

        lock_who(db, who, {"processor", "medical_officer"})
        digest = fingerprint({"request_id": request_id, **payload.model_dump(mode="json")})
        prior = prior_event(db, who, payload.command_id, digest)
        if prior:
            return prior.payload
        case = db.scalar(
            select(SubmittedCase)
            .where(SubmittedCase.tenant_id == who.tenant.id, SubmittedCase.request_id == request_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if case is None:
            raise HTTPException(404, "Submitted case not found")
        review = db.scalar(
            select(ReviewCase)
            .where(ReviewCase.tenant_id == who.tenant.id, ReviewCase.request_id == request_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if (
            not review
            or review.version != payload.expected_version
            or review.state != "NEEDS_INFORMATION"
        ):
            raise HTTPException(409, "Fact updates require the latest information-request version")
        if review.assignee_id != who.user.id:
            raise HTTPException(403, "Only the assigned reviewer may amend facts")
        policy = PolicyProposal.model_validate(
            owned(db, PolicyVersion, case.policy_id, who).proposal
        )
        admission = payload.facts.admission_date
        if admission and (
            admission < policy.effective_from
            or (policy.effective_to and admission > policy.effective_to)
        ):
            raise HTTPException(409, "The pinned policy is not effective for this admission")
        previous = fingerprint(case.inputs)
        case.inputs, case.record = payload.facts.model_dump(mode="json"), None
        revision = (
            db.scalar(
                select(func.max(CaseInputRevision.revision)).where(
                    CaseInputRevision.tenant_id == who.tenant.id,
                    CaseInputRevision.request_id == request_id,
                )
            )
            + 1
        )
        db.add(
            CaseInputRevision(
                tenant_id=who.tenant.id,
                request_id=request_id,
                revision=revision,
                actor_id=who.user.id,
                inputs=case.inputs,
                digest=fingerprint(case.inputs),
            )
        )
        note_id = uuid4()
        db.add(
            ReviewComment(
                id=note_id,
                tenant_id=who.tenant.id,
                request_id=request_id,
                actor_id=who.user.id,
                visibility="clinical" if who.role == "medical_officer" else "team",
                body=payload.reason,
            )
        )
        receipt = append_audit(
            db,
            who,
            review,
            "amend",
            payload.command_id,
            {
                "previous_input_digest": previous,
                "input_digest": fingerprint(case.inputs),
                "revision": revision,
                "comment_id": str(note_id),
            },
        )
        job = enqueue(
            db,
            who,
            "assessment",
            request_id,
            {"policy_id": str(case.policy_id), "inputs": case.inputs},
        )
        response = {**receipt.model_dump(mode="json"), "job_id": str(job.id)}
        record_event(db, who, payload.command_id, "request_amend", request_id, digest, response)
        db.commit()
        return response

    @router.get("/jobs", operation_id="list_jobs")
    def jobs(who: Identity, db: Database):
        rows = db.scalars(
            select(WorkJob)
            .where(WorkJob.tenant_id == who.tenant.id)
            .order_by(WorkJob.created_at.desc())
            .limit(50)
        ).all()
        return {
            "items": [
                {
                    "id": j.id,
                    "kind": j.kind,
                    "subject_id": j.subject_id,
                    "state": j.state,
                    "attempts": j.attempts,
                    "error_code": j.error_code,
                }
                for j in rows
            ]
        }

    @router.get("/jobs/{job_id}", operation_id="get_job")
    def job_detail(job_id: UUID, who: Identity, db: Database):
        job = owned(db, WorkJob, job_id, who)
        return {
            "id": job.id,
            "kind": job.kind,
            "state": job.state,
            "attempts": job.attempts,
            "error_code": job.error_code,
            "result": job.result
            if who.role == "medical_officer" or job.kind == "regression"
            else None,
        }

    @router.post("/jobs/{job_id}/retry", operation_id="retry_job")
    def retry(job_id: UUID, payload: RetryCommand, who: Identity, db: Database):
        lock_who(db, who, {"operations_lead", "tenant_admin"})
        job = owned(db, WorkJob, job_id, who)
        digest = fingerprint({"retry_job": str(job_id), **payload.model_dump(mode="json")})
        prior = prior_event(db, who, payload.command_id, digest)
        if prior:
            return prior.payload
        job = db.scalar(
            select(WorkJob)
            .where(WorkJob.id == job_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if job.state != "dead":
            raise HTTPException(409, "Only dead jobs can be explicitly retried")
        previous_attempts = job.attempts
        job.state, job.attempts, job.available_at = "queued", 0, datetime.now(UTC)
        response = {
            "job_id": str(job_id),
            "state": "queued",
            "previous_attempts": previous_attempts,
            "reason": payload.reason,
        }
        record_event(db, who, payload.command_id, "job_retry", job_id, digest, response)
        db.commit()
        return response

    @router.post("/policies", status_code=202, operation_id="propose_policy")
    def propose(payload: PolicyProposal, who: Identity, db: Database):
        lock_who(db, who, {"policy_analyst"})
        digest = fingerprint(payload.model_dump(mode="json"))
        prior = prior_event(db, who, payload.command_id, digest)
        if prior:
            return prior.payload
        if payload.wording_document_id:
            document = owned(db, DocumentUpload, payload.wording_document_id, who)
            if document.request_id != "POLICY-WORDING" or document.state != "extracted":
                raise HTTPException(409, "Policy wording must finish safe text extraction first")
        if db.scalar(
            select(PolicyVersion.id).where(
                PolicyVersion.tenant_id == who.tenant.id,
                PolicyVersion.product_id == payload.product_id,
                PolicyVersion.version == payload.version,
            )
        ):
            raise HTTPException(409, "This product version already exists; propose a new version")
        policy = PolicyVersion(
            id=uuid4(),
            tenant_id=who.tenant.id,
            product_id=payload.product_id,
            version=payload.version,
            author_id=who.user.id,
            command_id=payload.command_id,
            fingerprint=digest,
            proposal=payload.model_dump(mode="json"),
        )
        db.add(policy)
        db.flush()
        job = enqueue(db, who, "regression", policy.id, {"proposal_digest": digest})
        response = {"policy_id": str(policy.id), "job_id": str(job.id)}
        record_event(db, who, payload.command_id, "policy_propose", policy.id, digest, response)
        db.commit()
        return response

    @router.get("/policies", operation_id="list_policies")
    def policies(who: Identity, db: Database):
        rows = db.scalars(
            select(PolicyVersion)
            .where(PolicyVersion.tenant_id == who.tenant.id)
            .order_by(PolicyVersion.created_at.desc())
            .limit(50)
        ).all()
        return {
            "items": [
                {
                    "id": p.id,
                    "product_id": p.product_id,
                    "version": p.version,
                    "name": p.proposal["name"],
                    "status": policy_status(db, p),
                    "author_id": p.author_id,
                }
                for p in rows
            ]
        }

    @router.get("/policies/{policy_id}", operation_id="get_policy")
    def policy(policy_id: UUID, who: Identity, db: Database):
        return policy_view(db, owned(db, PolicyVersion, policy_id, who))

    @router.post("/policies/{policy_id}/commands", operation_id="command_policy")
    def policy_command(policy_id: UUID, payload: PolicyAction, who: Identity, db: Database):
        lock_who(db, who, {"policy_approver"})
        policy = owned(db, PolicyVersion, policy_id, who)
        if who.user.id == policy.author_id:
            raise HTTPException(403, "A different person must approve and activate this policy")
        digest = fingerprint({"policy_id": str(policy_id), **payload.model_dump(mode="json")})
        prior = prior_event(db, who, payload.command_id, digest)
        if prior:
            return prior.payload
        status = policy_status(db, policy)
        job = regression_job(db, policy)
        passed = (
            job
            and job.state == "succeeded"
            and job.result
            and job.result.get("passed") is True
            and job.result.get("proposal_digest") == policy.fingerprint
        )
        if payload.action in {"approve", "reject"}:
            if status != "proposed":
                raise HTTPException(409, "This immutable proposal already has a review decision")
            if payload.action == "approve" and not passed:
                raise HTTPException(409, "Passing regression on this exact proposal is required")
        else:
            if status != "approved" or not passed:
                raise HTTPException(409, "Only approved regression-passing policies can activate")
            proposal = PolicyProposal.model_validate(policy.proposal)
            today = datetime.now(UTC).date()
            if today < proposal.effective_from or (
                proposal.effective_to and today > proposal.effective_to
            ):
                raise HTTPException(409, "Policy is not currently effective")
        active = db.get(PolicyActive, (who.tenant.id, policy.product_id))
        if payload.action == "activate" and payload.expected_activation != (
            active.event_id if active else None
        ):
            raise HTTPException(409, "Active policy changed; refresh before activation")
        response = {
            "policy_id": str(policy.id),
            "action": payload.action,
            "reason": payload.reason,
            "previous_policy_id": str(active.version_id) if active else None,
        }
        event = record_event(
            db, who, payload.command_id, "policy_" + payload.action, policy_id, digest, response
        )
        if payload.action == "activate":
            if active:
                active.version_id, active.event_id = policy.id, event.id
            else:
                db.add(
                    PolicyActive(
                        tenant_id=who.tenant.id,
                        product_id=policy.product_id,
                        version_id=policy.id,
                        event_id=event.id,
                    )
                )
        db.commit()
        return response

    async def store_document(request_id, request, who, db, command_id, synthetic, roles):
        if synthetic != "true" or request.headers.get("content-type") != "application/pdf":
            raise HTTPException(415, "Only explicitly synthetic PDF documents are supported")
        content = bytearray()
        async for chunk in request.stream():
            content.extend(chunk)
            if len(content) > MAX_UPLOAD:
                raise HTTPException(413, "PDF exceeds 2 MiB")
        if not content.startswith(b"%PDF-"):
            raise HTTPException(422, "PDF header is missing")
        lock_who(db, who, roles)
        from hashlib import sha256

        checksum = sha256(content).hexdigest()
        digest = fingerprint({"request_id": request_id, "document_digest": checksum})
        prior = prior_event(db, who, command_id, digest)
        if prior:
            return prior.payload
        # Bound retained synthetic data even if a client submits many small files.
        total = db.scalar(
            select(func.coalesce(func.sum(func.octet_length(DocumentUpload.content)), 0)).where(
                DocumentUpload.tenant_id == who.tenant.id
            )
        )
        if total + len(content) > 20 * MAX_UPLOAD:
            raise HTTPException(409, "Synthetic document storage limit reached")
        document = DocumentUpload(
            id=uuid4(),
            tenant_id=who.tenant.id,
            actor_id=who.user.id,
            command_id=command_id,
            request_id=request_id,
            digest=checksum,
            content=bytes(content),
            state="quarantined",
        )
        db.add(document)
        job = enqueue(db, who, "extraction", document.id, {"document_digest": checksum})
        response = {"document_id": str(document.id), "job_id": str(job.id), "state": "quarantined"}
        record_event(db, who, command_id, "document_upload", document.id, digest, response)
        db.commit()
        return response

    @router.post(
        "/requests/{request_id}/documents", status_code=202, operation_id="upload_document"
    )
    async def upload(
        request_id: str,
        request: Request,
        who: Identity,
        db: Database,
        command_id: Annotated[UUID, Header(alias="Idempotency-Key")],
        synthetic: Annotated[str, Header(alias="X-Synthetic-Data")] = "",
    ):
        existing_case(db, who, request_id)
        return await store_document(
            request_id, request, who, db, command_id, synthetic, {"processor", "medical_officer"}
        )

    @router.post("/policy-documents", status_code=202, operation_id="upload_policy_document")
    async def upload_policy(
        request: Request,
        who: Identity,
        db: Database,
        command_id: Annotated[UUID, Header(alias="Idempotency-Key")],
        synthetic: Annotated[str, Header(alias="X-Synthetic-Data")] = "",
    ):
        return await store_document(
            "POLICY-WORDING", request, who, db, command_id, synthetic, {"policy_analyst"}
        )

    @router.get("/policy-documents", operation_id="list_policy_documents")
    def policy_documents(who: Identity, db: Database):
        if who.role not in {"policy_analyst", "policy_approver"}:
            raise HTTPException(403, "Policy access required")
        rows = db.scalars(
            select(DocumentUpload)
            .where(
                DocumentUpload.tenant_id == who.tenant.id,
                DocumentUpload.request_id == "POLICY-WORDING",
            )
            .order_by(DocumentUpload.created_at.desc())
            .limit(50)
        ).all()
        return {
            "items": [
                {"id": d.id, "digest": d.digest, "state": d.state, "text": d.extracted_text}
                for d in rows
            ]
        }

    @router.get("/requests/{request_id}/documents", operation_id="list_documents")
    def documents(request_id: str, who: Identity, db: Database):
        existing_case(db, who, request_id)
        rows = db.scalars(
            select(DocumentUpload)
            .where(
                DocumentUpload.tenant_id == who.tenant.id, DocumentUpload.request_id == request_id
            )
            .order_by(DocumentUpload.created_at)
            .limit(50)
        ).all()
        return {
            "items": [
                {
                    "id": d.id,
                    "digest": d.digest,
                    "state": d.state,
                    "text": d.extracted_text if who.role == "medical_officer" else None,
                }
                for d in rows
            ],
            "clinical_restricted": who.role != "medical_officer",
        }

    @router.get("/documents/{document_id}/content", operation_id="download_document")
    def download(document_id: UUID, who: Identity, db: Database):
        document = owned(db, DocumentUpload, document_id, who)
        policy_access = document.request_id == "POLICY-WORDING" and who.role in {
            "policy_analyst",
            "policy_approver",
        }
        if who.role != "medical_officer" and not policy_access:
            raise HTTPException(403, "Medical or policy document access required")
        if document.state != "extracted":
            raise HTTPException(409, "Document is quarantined, rejected or needs manual extraction")
        return Response(
            content=document.content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": 'attachment; filename="synthetic-document.pdf"',
                "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": "sandbox; default-src 'none'",
                "Cache-Control": "no-store",
            },
        )

    @router.get("/analytics", operation_id="read_local_analytics")
    def analytics(who: Identity, db: Database):
        if who.role not in {"auditor", "operations_lead", "tenant_admin"}:
            raise HTTPException(403, "Reporting access required")
        event_type = AnalyticsEvent.event["event_type"].astext
        rows = db.execute(
            select(event_type, func.count())
            .where(AnalyticsEvent.tenant_id == who.tenant.id)
            .group_by(event_type)
        ).all()
        return {
            "sink": "local_postgresql",
            "snowflake_publishing": "disabled",
            "counts": {kind: count for kind, count in rows},
        }

    @router.get("/admin/memberships", operation_id="list_memberships")
    def members(who: Identity, db: Database):
        if who.role != "tenant_admin":
            raise HTTPException(403, "Tenant administrator required")
        rows = db.execute(
            select(AppUser, Membership)
            .join(Membership, Membership.user_id == AppUser.id)
            .where(Membership.tenant_id == who.tenant.id)
            .order_by(AppUser.display_name)
            .limit(100)
        ).all()
        return {
            "items": [
                {"user_id": u.id, "name": u.display_name, "role": m.role, "active": m.active}
                for u, m in rows
            ],
            "roles": list(PROFILES | MVP_PROFILES),
        }

    @router.post("/admin/memberships/{user_id}", operation_id="change_membership")
    def change_member(user_id: UUID, payload: MembershipCommand, who: Identity, db: Database):
        lock_who(db, who, {"tenant_admin"})
        if user_id == who.user.id:
            raise HTTPException(409, "Ask another administrator to change your access")
        digest = fingerprint({"member_id": str(user_id), **payload.model_dump(mode="json")})
        prior = prior_event(db, who, payload.command_id, digest)
        if prior:
            return prior.payload
        member = db.scalar(
            select(Membership)
            .where(Membership.tenant_id == who.tenant.id, Membership.user_id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if member is None:
            raise HTTPException(404, "Membership not found")
        if member.role != payload.expected_role or member.active != payload.expected_active:
            raise HTTPException(409, "Membership changed; refresh before saving")
        previous = {"role": member.role, "active": member.active}
        member.role, member.active = payload.role, payload.active
        response = {
            "user_id": str(user_id),
            "previous": previous,
            "role": member.role,
            "active": member.active,
            "reason": payload.reason,
        }
        record_event(db, who, payload.command_id, "membership_change", user_id, digest, response)
        db.commit()
        return response

    @router.get("/policy-template", operation_id="get_policy_template")
    def template(who: Identity):
        if who.role not in {"policy_analyst", "policy_approver"}:
            raise HTTPException(403, "Policy access required")
        return json.loads(files("ciq_api").joinpath("fixtures/policy-template.json").read_text())

    @router.get("/events", operation_id="list_governance_events")
    def events(who: Identity, db: Database, page: Annotated[int, Query(ge=1, le=10000)] = 1):
        if who.role not in {"auditor", "policy_approver", "operations_lead", "tenant_admin"}:
            raise HTTPException(403, "Governance read access required")
        rows = db.scalars(
            select(MvpEvent)
            .where(MvpEvent.tenant_id == who.tenant.id)
            .order_by(MvpEvent.occurred_at.desc(), MvpEvent.id)
            .offset((page - 1) * 50)
            .limit(50)
        ).all()
        return {
            "page": page,
            "items": [
                {
                    "event_id": e.id,
                    "actor_id": e.actor_id,
                    "actor_role": e.actor_role,
                    "action": e.action,
                    "subject_id": e.subject_id,
                    "occurred_at": e.occurred_at,
                    "payload": e.payload,
                }
                for e in rows
            ],
        }

    app.include_router(router)
