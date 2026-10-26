"""Synthetic ingestion to human review, leases, policy governance and file isolation."""

import io
import json
from datetime import UTC, datetime, timedelta
from importlib.resources import files
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from test_identity import bearer
from test_reviews import command

from ciq_api.auth import LOCAL_ISSUER, Principal, resolve_identity
from ciq_api.jobs import claim, complete, compute, mirror_outbox, run_once
from ciq_api.main import create_app
from ciq_api.models import AppUser, Membership, Tenant
from ciq_api.mvp import lock_who
from ciq_api.mvp_contracts import PolicyProposal
from ciq_api.mvp_models import (
    AnalyticsEvent,
    CaseInputRevision,
    DocumentUpload,
    MvpEvent,
    PolicyVersion,
    SubmittedCase,
    WorkJob,
)
from ciq_api.reviews import lock_actor
from ciq_api.seed import MVP_PROFILES, PROFILES, TENANT_ID


@pytest.fixture
def mvp(settings, engine):
    settings.synthetic_workflows = True
    with Session(engine) as db, db.begin():
        for role, (user_id, name) in MVP_PROFILES.items():
            db.add(AppUser(id=UUID(user_id), issuer=LOCAL_ISSUER, subject=role, display_name=name))
            db.flush()
            db.add(Membership(tenant_id=TENANT_ID, user_id=UUID(user_id), role=role))
    with TestClient(create_app(settings, engine)) as http:
        yield http


def template():
    value = json.loads(files("ciq_api").joinpath("fixtures/policy-template.json").read_text())
    value["command_id"] = str(uuid4())
    return value


def propose(http, settings, proposal=None):
    result = http.post(
        "/v3/policies", headers=bearer(settings, "policy_analyst"), json=proposal or template()
    )
    assert result.status_code == 202, result.text
    return result.json()


def policy_action(http, settings, policy_id, action, **fields):
    return http.post(
        f"/v3/policies/{policy_id}/commands",
        headers=bearer(settings, "policy_approver"),
        json={
            "command_id": str(uuid4()),
            "action": action,
            "reason": "Synthetic human review",
            **fields,
        },
    )


def active_policy(http, settings, engine, proposal=None):
    p = propose(http, settings, proposal)
    assert run_once(engine)
    assert policy_action(http, settings, p["policy_id"], "approve").status_code == 200
    assert policy_action(http, settings, p["policy_id"], "activate").status_code == 200
    return p


def submission(facts=None):
    return {
        "command_id": str(uuid4()),
        "product_id": "AS_NIA_V02_2425",
        "synthetic_data": True,
        "facts": facts or template()["examples"][0]["facts"],
    }


def test_workflow_lists_paginate_and_search_without_crossing_tenants(mvp, settings, engine):
    policy = active_policy(mvp, settings, engine)
    other_tenant = uuid4()
    with Session(engine) as db, db.begin():
        db.add(Tenant(id=other_tenant, name="Other synthetic tenant"))
        db.flush()
        for tenant, count in [(TENANT_ID, 55), (other_tenant, 1)]:
            for index in range(count):
                definition = template()
                definition["name"] = "List title"
                version = PolicyVersion(
                    id=uuid4(),
                    tenant_id=tenant,
                    product_id=f"LIST_{index:03}",
                    version="List version",
                    author_id=UUID(MVP_PROFILES["policy_analyst"][0]),
                    command_id=uuid4(),
                    fingerprint="0" * 64,
                    proposal=definition,
                )
                db.add(version)
                db.flush()
                db.add(
                    SubmittedCase(
                        tenant_id=tenant,
                        request_id=f"REQ-LIST-{index:03}",
                        actor_id=UUID(PROFILES["processor"][0]),
                        command_id=uuid4(),
                        fingerprint="0" * 64,
                        policy_id=version.id,
                        inputs={"member_reference": f"SYN-LIST-{index:03}"},
                        priority="normal",
                        due_at=datetime.now(UTC),
                    )
                )
    for path, identifier in [("policies", "id"), ("requests", "request_id")]:
        seen = set()
        for page, expected_size in [(1, 20), (2, 20), (3, 15)]:
            result = mvp.get(
                f"/v3/{path}?q=list&page_size=20&page={page}", headers=bearer(settings)
            ).json()
            assert result["total"] == 55 and result["page"] == page
            assert result["page_size"] == 20 and len(result["items"]) == expected_size
            ids = {row[identifier] for row in result["items"]}
            assert not ids & seen
            seen |= ids
        assert len(seen) == 55
        for query in ["%", "' OR 1=1 --"]:
            assert (
                mvp.get(f"/v3/{path}", params={"q": query}, headers=bearer(settings)).json()[
                    "total"
                ]
                == 0
            )
        for params in [{"page": 0}, {"page": 10001}, {"page_size": 51}, {"q": "x" * 121}]:
            assert (
                mvp.get(f"/v3/{path}", params=params, headers=bearer(settings)).status_code == 422
            )
    assert mvp.get("/v3/policies?q=LIST_054", headers=bearer(settings)).json()["total"] == 1
    assert mvp.get("/v3/policies?q=title", headers=bearer(settings)).json()["total"] == 55
    assert mvp.get("/v3/policies?q=version", headers=bearer(settings)).json()["total"] == 55
    assert mvp.get("/v3/requests?q=syn-list-054", headers=bearer(settings)).json()["total"] == 1
    active = mvp.get("/v3/policies?active_only=true", headers=bearer(settings)).json()
    assert active["total"] == 1 and active["items"][0]["id"] == policy["policy_id"]


def test_complete_submitted_request_assessment_review_and_analytics(mvp, settings, engine):
    active_policy(mvp, settings, engine)
    payload = submission()
    first = mvp.post("/v3/requests", headers=bearer(settings), json=payload)
    assert first.status_code == 202, first.text
    assert mvp.post("/v3/requests", headers=bearer(settings), json=payload).json() == first.json()
    case = first.json()["request_id"]
    assert mvp.get(f"/v3/reviews/{case}", headers=bearer(settings)).status_code == 409
    assert run_once(engine)
    detail = mvp.get(f"/v3/requests/{case}", headers=bearer(settings)).json()
    assert detail["assessment"]["payable_inr"] == 95000
    assert "diagnosis" not in detail["facts"] and "clinical_note" not in detail["facts"]
    assert (
        command(
            mvp,
            settings,
            0,
            "assign",
            "medical_officer",
            case=case,
            assignee_id=PROFILES["medical_officer"][0],
        ).status_code
        == 200
    )
    decision = command(
        mvp,
        settings,
        1,
        "approve_with_deductions",
        "medical_officer",
        case=case,
        note="Reviewed the cited calculation",
        payable_inr=95000,
    )
    assert decision.status_code == 200, decision.text
    queue = mvp.get("/v3/requests", headers=bearer(settings)).json()["items"]
    assert queue[0]["workflow_state"] == "APPROVED_WITH_DEDUCTIONS"
    assert queue[0]["assignee_name"] == "Dr. Neel Shah"
    assert queue[0]["sla_breached"] is False
    assert mirror_outbox(engine) == 2
    assert mirror_outbox(engine) == 0
    analytics = mvp.get("/v3/analytics", headers=bearer(settings, "auditor")).json()
    assert (
        analytics["sink"] == "local_postgresql" and analytics["snowflake_publishing"] == "disabled"
    )
    assert analytics["counts"]["cashlessiq.review.approve_with_deductions"] == 1
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(AnalyticsEvent)) == 2


def test_policy_gate_second_person_failing_regression_and_immutability(mvp, settings, engine):
    proposal = template()
    proposal["examples"][0]["expected_payable_inr"] = 1
    p = propose(mvp, settings, proposal)
    assert policy_action(mvp, settings, p["policy_id"], "approve").status_code == 409
    assert run_once(engine)
    assert policy_action(mvp, settings, p["policy_id"], "approve").status_code == 409
    assert policy_action(mvp, settings, p["policy_id"], "reject").status_code == 200
    assert policy_action(mvp, settings, p["policy_id"], "activate").status_code == 409
    # A role change cannot turn the proposal author into a valid second person.
    with Session(engine) as db, db.begin():
        db.get(
            Membership, (TENANT_ID, UUID(MVP_PROFILES["policy_analyst"][0]))
        ).role = "policy_approver"
    denied = mvp.post(
        f"/v3/policies/{p['policy_id']}/commands",
        headers=bearer(settings, "policy_analyst"),
        json={"command_id": str(uuid4()), "action": "approve", "reason": "self approve"},
    )
    assert denied.status_code == 403
    for table in ("policy_version", "mvp_event"):
        with pytest.raises(DBAPIError), engine.begin() as conn:
            conn.execute(text(f"DELETE FROM {table}"))


def test_activation_compare_and_swap_rollback_and_pinned_assessment(mvp, settings, engine):
    first = active_policy(mvp, settings, engine)
    initial = mvp.get(f"/v3/policies/{first['policy_id']}", headers=bearer(settings)).json()
    submitted = mvp.post("/v3/requests", headers=bearer(settings), json=submission()).json()
    second_proposal = template()
    second_proposal["version"] = "Synthetic second version"
    second = propose(mvp, settings, second_proposal)
    # Drain both pending assessment and regression.
    assert run_once(engine) and run_once(engine)
    assert policy_action(mvp, settings, second["policy_id"], "approve").status_code == 200
    assert policy_action(mvp, settings, second["policy_id"], "activate").status_code == 409
    assert (
        policy_action(
            mvp,
            settings,
            second["policy_id"],
            "activate",
            expected_activation=initial["activation_id"],
        ).status_code
        == 200
    )
    current = mvp.get(f"/v3/policies/{second['policy_id']}", headers=bearer(settings)).json()
    assert (
        policy_action(
            mvp,
            settings,
            first["policy_id"],
            "activate",
            expected_activation=current["activation_id"],
        ).status_code
        == 200
    )
    saved = mvp.get(f"/v3/requests/{submitted['request_id']}", headers=bearer(settings)).json()
    assert saved["assessment"]["policy_id"] == first["policy_id"]
    with Session(engine) as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(MvpEvent)
                .where(MvpEvent.action == "policy_activate")
            )
            == 3
        )


def test_expired_lease_recovery_rejects_old_worker_completion(mvp, settings, engine):
    p = propose(mvp, settings)
    first = claim(engine)
    assert first and claim(engine) is None
    with Session(engine) as db, db.begin():
        db.get(WorkJob, first[0]).lease_until = datetime.now(UTC) - timedelta(seconds=1)
    second = claim(engine)
    assert second[0] == first[0] and second[1] != first[1]
    assert complete(engine, *first, {"passed": True}) is False
    assert complete(engine, *second, compute(engine, *second)) is True
    status = mvp.get(f"/v3/jobs/{p['job_id']}", headers=bearer(settings)).json()
    assert status["state"] == "succeeded" and status["attempts"] == 2


def test_retry_budget_dead_letter_and_explicit_retry(mvp, settings, engine):
    p = propose(mvp, settings)
    for _ in range(3):
        lease = claim(engine)
        assert lease
        assert complete(engine, *lease, failed=True)
        with Session(engine) as db, db.begin():
            db.get(WorkJob, lease[0]).available_at = datetime.now(UTC) - timedelta(seconds=1)
    assert claim(engine) is None
    retry = {"command_id": str(uuid4()), "reason": "Resolved test fault"}
    endpoint = f"/v3/jobs/{p['job_id']}/retry"
    assert mvp.post(endpoint, headers=bearer(settings), json=retry).status_code == 403
    response = mvp.post(endpoint, headers=bearer(settings, "operations_lead"), json=retry)
    assert response.status_code == 200, response.text
    assert (
        mvp.post(endpoint, headers=bearer(settings, "operations_lead"), json=retry).json()
        == response.json()
    )
    assert run_once(engine)


def pdf(*, script=False, encrypted=False, pages=1):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    if script:
        writer.add_js("app.alert('unsupported')")
    if encrypted:
        writer.encrypt("synthetic")
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


@pytest.mark.parametrize(
    "content,expected",
    [
        (b"%PDF-invalid", "rejected"),
        (pdf(script=True), "rejected"),
        (pdf(encrypted=True), "rejected"),
        (pdf(pages=21), "rejected"),
        (pdf(), "needs_manual_extraction"),
    ],
    ids=["invalid", "script", "encrypted", "page-limit", "scanned"],
)
def test_pdf_quarantine_restrictions_and_no_automatic_fact_promotion(
    mvp, settings, engine, content, expected
):
    headers = bearer(settings) | {
        "Content-Type": "application/pdf",
        "Idempotency-Key": str(uuid4()),
        "X-Synthetic-Data": "true",
    }
    endpoint = "/v3/requests/GOL001/documents"
    response = mvp.post(endpoint, headers=headers, content=content)
    assert response.status_code == 202, response.text
    assert mvp.post(endpoint, headers=headers, content=content).json() == response.json()
    document = response.json()["document_id"]
    assert (
        mvp.get(
            f"/v3/documents/{document}/content", headers=bearer(settings, "medical_officer")
        ).status_code
        == 409
    )
    assert run_once(engine)
    with Session(engine) as db:
        stored = db.get(DocumentUpload, UUID(document))
        assert stored.state == expected
    assert mvp.get(f"/v3/documents/{document}/content", headers=bearer(settings)).status_code == 403
    view = mvp.get("/v3/requests/GOL001/documents", headers=bearer(settings)).json()
    assert view["items"][0]["text"] is None


def test_upload_size_header_tenant_scope_and_document_idempotency(mvp, settings, engine):
    headers = bearer(settings) | {
        "Content-Type": "application/pdf",
        "Idempotency-Key": str(uuid4()),
        "X-Synthetic-Data": "true",
    }
    assert (
        mvp.post("/v3/requests/FOREIGN/documents", headers=headers, content=pdf()).status_code
        == 404
    )
    assert (
        mvp.post(
            "/v3/requests/GOL001/documents",
            headers=headers,
            content=b"%PDF-" + b"x" * (2 * 1024**2),
        ).status_code
        == 413
    )
    assert (
        mvp.post(
            "/v3/requests/GOL001/documents",
            headers=headers | {"X-Synthetic-Data": "false"},
            content=pdf(),
        ).status_code
        == 415
    )
    first = mvp.post("/v3/requests/GOL001/documents", headers=headers, content=pdf())
    assert first.status_code == 202
    assert (
        mvp.post("/v3/requests/GOL024/documents", headers=headers, content=pdf()).status_code == 409
    )
    tenant = uuid4()
    with Session(engine) as db, db.begin():
        db.add(Tenant(id=tenant, name="Foreign tenant"))
        db.flush()
        db.add(
            Membership(
                tenant_id=tenant,
                user_id=UUID(PROFILES["medical_officer"][0]),
                role="medical_officer",
            )
        )
    assert (
        mvp.get(
            f"/v3/documents/{first.json()['document_id']}/content",
            headers=bearer(settings, "medical_officer", tenant),
        ).status_code
        == 404
    )


def test_admin_revocation_conflicts_and_no_self_lockout(mvp, settings):
    actor = MVP_PROFILES["tenant_admin"][0]
    target = PROFILES["processor"][0]
    payload = {
        "command_id": str(uuid4()),
        "reason": "Suspend test reviewer",
        "expected_role": "processor",
        "role": "processor",
        "expected_active": True,
        "active": False,
    }
    assert (
        mvp.post(
            f"/v3/admin/memberships/{target}", headers=bearer(settings), json=payload
        ).status_code
        == 403
    )
    assert (
        mvp.post(
            f"/v3/admin/memberships/{target}",
            headers=bearer(settings, "tenant_admin"),
            json=payload,
        ).status_code
        == 200
    )
    assert mvp.get("/v1/me", headers=bearer(settings)).status_code == 403
    assert (
        mvp.post(
            f"/v3/admin/memberships/{target}",
            headers=bearer(settings, "tenant_admin"),
            json=payload | {"command_id": str(uuid4())},
        ).status_code
        == 409
    )
    assert (
        mvp.post(
            f"/v3/admin/memberships/{actor}",
            headers=bearer(settings, "tenant_admin"),
            json=payload | {"expected_role": "tenant_admin"},
        ).status_code
        == 409
    )


def test_contract_rejects_unsupported_rules_unsafe_amounts_and_missing_citations():
    proposal = template()
    assert len(PolicyProposal.model_validate(proposal).examples) == 30
    for mutation in ("unknown", "parameter", "citation", "duplicate"):
        value = json.loads(json.dumps(proposal))
        if mutation == "unknown":
            value["rules"][0]["rule_type"] = "DENY"
        elif mutation == "parameter":
            value["rules"][0]["params"]["pct_of_si"] = True
        elif mutation == "citation":
            value["rules"][0]["clause_id"] = "MISSING"
        else:
            value["rules"].append(value["rules"][0])
        with pytest.raises(ValueError):
            PolicyProposal.model_validate(value)


def test_query_correction_keeps_inputs_history_and_requires_latest_version(mvp, settings, engine):
    active_policy(mvp, settings, engine)
    facts = template()["examples"][0]["facts"]
    missing = facts | {"diagnosis": None}
    response = mvp.post("/v3/requests", headers=bearer(settings), json=submission(missing))
    case = response.json()["request_id"]
    assert run_once(engine)
    assert (
        command(
            mvp,
            settings,
            0,
            "assign",
            "medical_officer",
            case=case,
            assignee_id=PROFILES["medical_officer"][0],
        ).status_code
        == 200
    )
    assert (
        command(
            mvp, settings, 1, "query", "medical_officer", case=case, note="Need diagnosis"
        ).status_code
        == 200
    )
    amendment = {
        "command_id": str(uuid4()),
        "expected_version": 2,
        "reason": "Received verified synthetic information",
        "facts": facts,
    }
    endpoint = f"/v3/requests/{case}/amend"
    assert mvp.post(endpoint, headers=bearer(settings), json=amendment).status_code == 403
    result = mvp.post(endpoint, headers=bearer(settings, "medical_officer"), json=amendment)
    assert result.status_code == 202, result.text
    assert (
        mvp.post(endpoint, headers=bearer(settings, "medical_officer"), json=amendment).json()
        == result.json()
    )
    assert run_once(engine)
    assert (
        mvp.post(
            endpoint,
            headers=bearer(settings, "medical_officer"),
            json=amendment | {"command_id": str(uuid4())},
        ).status_code
        == 409
    )
    assert (
        command(
            mvp, settings, 3, "resume", "medical_officer", case=case, note="Reassessment verified"
        ).status_code
        == 200
    )
    assert (
        command(
            mvp,
            settings,
            4,
            "approve_with_deductions",
            "medical_officer",
            case=case,
            note="Reviewed",
            payable_inr=95000,
        ).status_code
        == 200
    )
    with Session(engine) as db:
        versions = db.scalars(select(CaseInputRevision).order_by(CaseInputRevision.revision)).all()
        assert len(versions) == 2
        assert versions[0].inputs["diagnosis"] is None
        assert versions[1].inputs["diagnosis"] == facts["diagnosis"]
    with pytest.raises(DBAPIError), engine.begin() as conn:
        conn.execute(text("DELETE FROM case_input_revision"))


def text_pdf():
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=200)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
    )
    content = DecodedStreamObject()
    content.set_data(
        b"BT /F1 12 Tf 10 100 Td (Fictional policy wording for synthetic testing.) Tj ET"
    )
    page[NameObject("/Contents")] = writer._add_object(content)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def test_policy_wording_upload_extraction_and_version_binding(mvp, settings, engine):
    headers = bearer(settings, "policy_analyst") | {
        "Content-Type": "application/pdf",
        "Idempotency-Key": str(uuid4()),
        "X-Synthetic-Data": "true",
    }
    result = mvp.post("/v3/policy-documents", headers=headers, content=text_pdf())
    assert result.status_code == 202, result.text
    document = result.json()["document_id"]
    proposal = template() | {"wording_document_id": document}
    assert (
        mvp.post(
            "/v3/policies", headers=bearer(settings, "policy_analyst"), json=proposal
        ).status_code
        == 409
    )
    assert run_once(engine)
    view = mvp.get("/v3/policy-documents", headers=bearer(settings, "policy_approver")).json()
    assert view["items"][0]["state"] == "extracted"
    assert "Fictional policy wording" in view["items"][0]["text"]
    content = mvp.get(
        f"/v3/documents/{document}/content", headers=bearer(settings, "policy_approver")
    )
    assert content.status_code == 200 and content.content == text_pdf()
    assert content.headers["content-disposition"].startswith("attachment;")
    assert content.headers["cache-control"] == "no-store"
    proposed = propose(mvp, settings, proposal)
    assert run_once(engine)
    saved = mvp.get(f"/v3/policies/{proposed['policy_id']}", headers=bearer(settings)).json()
    assert saved["proposal"]["wording_document_id"] == document


@pytest.mark.parametrize("entity", ["membership", "user", "tenant"])
@pytest.mark.parametrize("boundary", ["review", "mvp"])
def test_write_lock_refreshes_previously_loaded_identity(engine, entity, boundary):
    from fastapi import HTTPException

    actor = UUID(PROFILES["processor"][0])
    with Session(engine) as cached:
        # Keep strong references to reproduce a session cache surviving the
        # identity read. A write lock must refresh rows, not trust cached flags.
        membership = cached.get(Membership, (TENANT_ID, actor))
        user = cached.get(AppUser, actor)
        tenant = cached.get(Tenant, TENANT_ID)
        who = resolve_identity(cached, Principal(LOCAL_ISSUER, "processor", TENANT_ID), "local")
        with Session(engine) as external, external.begin():
            target = external.get(
                {"membership": Membership, "user": AppUser, "tenant": Tenant}[entity],
                (TENANT_ID, actor)
                if entity == "membership"
                else actor
                if entity == "user"
                else TENANT_ID,
            )
            target.active = False
        assert membership.active and user.active and tenant.active
        with pytest.raises(HTTPException) as denied:
            lock_actor(cached, who) if boundary == "review" else lock_who(
                cached, who, {"processor"}
            )
        assert denied.value.status_code == 403


def test_chunked_json_is_bounded_before_parsing_or_writing(mvp, settings, engine):
    def chunks():
        yield b'{"padding":"'
        for _ in range(65):
            yield b"x" * 8192
        yield b'"}'

    result = mvp.post(
        "/v3/requests",
        headers=bearer(settings) | {"Content-Type": "application/json"},
        content=chunks(),
    )
    assert result.status_code == 413
    assert result.headers["cache-control"] == "no-store"
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(MvpEvent)) == 0


def test_policy_intake_list_separates_approval_from_activation(mvp, settings, engine):
    first = propose(mvp, settings)
    assert run_once(engine)
    assert policy_action(mvp, settings, first["policy_id"], "approve").status_code == 200
    auth = bearer(settings)
    listed = mvp.get("/v3/policies", headers=auth).json()["items"]
    assert len(listed) == 1 and listed[0]["status"] == "approved"
    assert listed[0]["active"] is False
    assert mvp.get("/v3/policies?active_only=true", headers=auth).json()["items"] == []
    assert mvp.post("/v3/requests", headers=auth, json=submission()).status_code == 409
    assert policy_action(mvp, settings, first["policy_id"], "activate").status_code == 200
    available = mvp.get("/v3/policies?active_only=true", headers=auth).json()["items"]
    assert [p["id"] for p in available] == [first["policy_id"]]
    assert available[0]["active"] is True
    assert available[0]["effective_from"] == template()["effective_from"]
    assert available[0]["effective_to"] == template()["effective_to"]
    # A newer unactivated version must not hide or replace the active version in intake.
    next_proposal = template()
    next_proposal["version"] = "V-next"
    second = propose(mvp, settings, next_proposal)
    assert run_once(engine)
    assert policy_action(mvp, settings, second["policy_id"], "approve").status_code == 200
    assert [
        p["id"] for p in mvp.get("/v3/policies?active_only=true", headers=auth).json()["items"]
    ] == [first["policy_id"]]
