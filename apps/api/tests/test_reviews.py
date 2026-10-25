"""Real PostgreSQL workflow transactions, authority, conflicts and durable evidence."""

from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from test_identity import bearer

from ciq_api.main import create_app
from ciq_api.models import AppUser, Membership, Tenant
from ciq_api.review_models import ReviewAudit, ReviewCase, ReviewCommandReceipt, ReviewOutbox
from ciq_api.seed import PROFILES, TENANT_ID

CASE = "GOL001"


@pytest.fixture
def reviews(settings, engine):
    settings.synthetic_workflows = True
    with TestClient(create_app(settings, engine)) as client:
        yield client


def command(client, settings, version, action, profile="processor", case=CASE, **fields):
    return client.post(
        f"/v3/reviews/{case}/commands",
        headers=bearer(settings, profile),
        json={"command_id": str(uuid4()), "expected_version": version, "action": action, **fields},
    )


def claim(client, settings, profile="processor", version=0):
    return command(client, settings, version, "assign", profile, assignee_id=PROFILES[profile][0])


def test_disabled_and_no_store(client, settings):
    result = client.get(f"/v3/reviews/{CASE}", headers=bearer(settings))
    assert result.status_code == 404
    assert result.headers["cache-control"] == "no-store"


def test_claim_persists_audit_outbox_and_replay(reviews, settings, engine):
    payload = {
        "command_id": str(uuid4()),
        "expected_version": 0,
        "action": "assign",
        "assignee_id": PROFILES["processor"][0],
    }
    endpoint = f"/v3/reviews/{CASE}/commands"
    first = reviews.post(endpoint, json=payload, headers=bearer(settings))
    assert first.status_code == 200, first.text
    replay = reviews.post(endpoint, json=payload, headers=bearer(settings))
    assert replay.json() == first.json()
    assert replay.headers["cache-control"] == "no-store"
    conflict = reviews.post(endpoint, json=payload | {"note": "changed"}, headers=bearer(settings))
    assert conflict.status_code == 409
    with Session(engine) as db:
        assert db.get(ReviewCase, (TENANT_ID, CASE)).version == 1
        for table in (ReviewAudit, ReviewOutbox, ReviewCommandReceipt):
            assert db.scalar(select(func.count()).select_from(table)) == 1
        envelope = db.scalar(select(ReviewOutbox)).event
        assert envelope["tenant_id"] == str(TENANT_ID)
        assert envelope["aggregate_version"] == 1
    # A fresh app process reads durable state, not an in-memory mutation.
    with TestClient(create_app(settings, engine)) as fresh:
        saved = fresh.get(f"/v3/reviews/{CASE}", headers=bearer(settings)).json()
        assert saved["version"] == 1 and saved["state"] == "IN_REVIEW"


def test_optimistic_conflict_rolls_back_everything(reviews, settings, engine):
    assert claim(reviews, settings).status_code == 200
    assert command(reviews, settings, 0, "comment", note="Stale").status_code == 409
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(ReviewCommandReceipt)) == 1
        assert db.scalar(select(func.count()).select_from(ReviewAudit)) == 1


def test_concurrent_claims_have_one_winner(reviews, settings, engine):
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: claim(reviews, settings), range(2)))
    assert sorted(r.status_code for r in results) == [200, 409]
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(ReviewAudit)) == 1


def test_clinical_notes_not_exposed_in_comments_audit_or_outbox(reviews, settings, engine):
    assert claim(reviews, settings, "medical_officer").status_code == 200
    result = command(
        reviews,
        settings,
        1,
        "comment",
        "medical_officer",
        note="SYNTHETIC PRIVATE CLINICAL NOTE",
        visibility="clinical",
    )
    assert result.status_code == 200, result.text
    for role in ("processor", "auditor"):
        view = reviews.get(f"/v3/reviews/{CASE}", headers=bearer(settings, role))
        assert "PRIVATE CLINICAL" not in view.text
        assert view.json()["comments"] == []
        assert view.json()["clinical_notes_restricted"] is True
    medical = reviews.get(f"/v3/reviews/{CASE}", headers=bearer(settings, "medical_officer"))
    assert "PRIVATE CLINICAL" in medical.text
    with Session(engine) as db:
        assert "PRIVATE CLINICAL" not in str(
            [row.event for row in db.scalars(select(ReviewOutbox))]
        )
    assert (
        command(reviews, settings, 2, "comment", note="hidden", visibility="clinical").status_code
        == 403
    )


def test_workflow_query_referral_human_approval_and_reopen(reviews, settings):
    assert claim(reviews, settings).status_code == 200
    assert (
        command(reviews, settings, 1, "query", note="Need supporting bill").json()["state"]
        == "NEEDS_INFORMATION"
    )
    assert (
        command(reviews, settings, 2, "approve", note="invalid", payable_inr=95000).status_code
        == 409
    )
    assert command(reviews, settings, 2, "resume", note="Received bill").status_code == 200
    assert (
        command(reviews, settings, 3, "refer", note="Clinical review requested").status_code == 200
    )
    assert command(reviews, settings, 4, "resume", note="Self resolve").status_code == 403
    reassigned = command(
        reviews,
        settings,
        4,
        "assign",
        "medical_officer",
        assignee_id=PROFILES["medical_officer"][0],
        note="Medical referral accepted",
    )
    assert reassigned.status_code == 200
    assert (
        command(reviews, settings, 5, "resume", "medical_officer", note="Reviewed").status_code
        == 200
    )
    approved = command(
        reviews,
        settings,
        6,
        "approve_with_deductions",
        "medical_officer",
        note="Reviewed policy calculation",
        payable_inr=95000,
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["state"] == "APPROVED_WITH_DEDUCTIONS"
    assert command(reviews, settings, 7, "query", "medical_officer", note="late").status_code == 409
    assert (
        command(reviews, settings, 7, "reopen", "medical_officer", note="New evidence").status_code
        == 200
    )
    view = reviews.get(f"/v3/reviews/{CASE}", headers=bearer(settings)).json()
    assert view["final_payable_inr"] is None and view["version"] == 8
    approval = next(e for e in view["audit"] if e["action"] == "approve_with_deductions")
    assert approval["payload"]["calculation_basis"] == "saved_calculation"
    assert approval["payload"]["baseline_commit"]


@pytest.mark.parametrize("amount", [True, 1.5, "95000", -1, 2**53])
def test_money_requires_bounded_integer(reviews, settings, amount):
    assert (
        command(
            reviews, settings, 0, "approve", "medical_officer", note="reason", payable_inr=amount
        ).status_code
        == 422
    )


def test_auditor_read_only_unknown_cases_and_assignment_scope(reviews, settings, engine):
    assert command(reviews, settings, 0, "comment", "auditor", note="No write").status_code == 403
    assert command(reviews, settings, 0, "comment", case="FOREIGN", note="x").status_code == 404
    foreign = uuid4()
    with Session(engine) as db, db.begin():
        tenant = uuid4()
        db.add(Tenant(id=tenant, name="Other tenant"))
        db.add(AppUser(id=foreign, issuer="urn:test", subject="foreign", display_name="Foreign"))
        db.flush()
        db.add(Membership(tenant_id=tenant, user_id=foreign, role="processor"))
    assert (
        command(
            reviews, settings, 0, "assign", "medical_officer", assignee_id=str(foreign)
        ).status_code
        == 422
    )
    people = reviews.get("/v3/reviews/people", headers=bearer(settings)).json()
    assert len(people["items"]) == 2 and str(foreign) not in str(people)
    # A valid second-tenant membership still cannot read the first tenant's cases.
    with Session(engine) as db, db.begin():
        db.add(
            Membership(tenant_id=tenant, user_id=UUID(PROFILES["processor"][0]), role="processor")
        )
    assert (
        reviews.get(f"/v3/reviews/{CASE}", headers=bearer(settings, tenant_id=tenant)).status_code
        == 404
    )


def test_audit_is_immutable_at_database_boundary(reviews, settings, engine):
    assert claim(reviews, settings).status_code == 200
    for sql in ("UPDATE review_audit SET action='comment'", "DELETE FROM review_audit"):
        with pytest.raises(DBAPIError), engine.begin() as connection:
            connection.execute(text(sql))


def test_missing_calculation_cannot_be_finalised(reviews, settings):
    result = command(
        reviews,
        settings,
        0,
        "assign",
        "medical_officer",
        case="GOL024",
        assignee_id=PROFILES["medical_officer"][0],
    )
    assert result.status_code == 200
    assert (
        command(
            reviews,
            settings,
            1,
            "approve",
            "medical_officer",
            case="GOL024",
            note="No calculation",
            payable_inr=0,
        ).status_code
        == 409
    )


def test_outbox_failure_rolls_back_state_audit_comment_and_receipt(reviews, settings, engine):
    def unavailable(*_):
        raise RuntimeError("Synthetic outbox failure")

    event.listen(ReviewOutbox, "before_insert", unavailable)
    try:
        with pytest.raises(RuntimeError, match="outbox failure"):
            command(
                reviews,
                settings,
                0,
                "assign",
                assignee_id=PROFILES["processor"][0],
                note="Claim for review",
            )
    finally:
        event.remove(ReviewOutbox, "before_insert", unavailable)
    with Session(engine) as db:
        for model in (ReviewCase, ReviewAudit, ReviewCommandReceipt, ReviewOutbox):
            assert db.scalar(select(func.count()).select_from(model)) == 0
