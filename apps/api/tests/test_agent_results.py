"""Read existing fake results through HTTP; reads cannot execute or settle work."""

from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_agent_ledger import ACTOR, balance, payload, submission
from test_agent_ledger import setup as setup
from test_identity import bearer
from test_mvp import mvp as mvp

from ciq_api.agent_ledger import FakeAgentLedger
from ciq_api.agent_ledger_models import AgentOperation
from ciq_api.main import create_app
from ciq_api.models import AppUser, Membership, Tenant
from ciq_api.mvp_models import CaseInputRevision, MvpEvent, PolicyVersion, SubmittedCase
from ciq_api.review_models import ReviewCase
from ciq_api.seed import PROFILES, TENANT_ID

PATH = "/v3/requests/REQ-FAKE-0/agent-result"


def get(http, settings, role="medical_officer", path=PATH):
    return http.get(path, headers=bearer(settings, role))


def published(s):
    permit = submission(s)
    assert s.ledger.publish_fake_result(permit, payload(permit)).state == "published"


def test_read_is_opt_in_authenticated_and_not_an_execution_endpoint(setup, settings, mvp):
    disabled = settings.model_copy(update={"synthetic_workflows": False})
    with TestClient(create_app(disabled, setup.engine)) as http:
        assert get(http, settings).status_code == 404
    assert mvp.get(PATH).status_code == 401
    assert get(mvp, settings, path=PATH.replace("REQ-FAKE-0", "MISSING")).status_code == 404
    assert mvp.post(PATH, headers=bearer(settings, "medical_officer"), json={}).status_code == 405
    result = get(mvp, settings)
    assert result.status_code == 200
    assert result.headers["cache-control"] == "no-store"
    assert result.json()["state"] == "not_requested"


@pytest.mark.parametrize(
    "role",
    [
        "processor",
        "auditor",
        "operations_lead",
        "policy_analyst",
        "policy_approver",
        "tenant_admin",
    ],
)
def test_all_nonclinical_roles_are_denied_before_private_data(setup, mvp, settings, role):
    published(setup)
    result = get(mvp, settings, role)
    assert result.status_code == 403
    assert "comparison" not in result.text and "explanation" not in result.text


def test_repeated_http_reads_preserve_allowance_receipts_and_human_workflow(
    setup,
    mvp,
    settings,
    monkeypatch,
):
    s = setup
    published(s)
    before = balance(s)
    with Session(s.engine) as db:
        op = db.scalar(select(AgentOperation))
        original = (op.state, op.version, op.fence_id, op.lease_until, op.snapshot)

    def forbidden(*args, **kwargs):
        pytest.fail("A result read must not call the owning execution ledger")

    for name in (
        "capture",
        "reserve",
        "claim",
        "begin_submission",
        "publish_fake_result",
        "recover_expired",
    ):
        monkeypatch.setattr(FakeAgentLedger, name, forbidden)
    for _ in range(3):
        result = get(mvp, settings)
        assert result.status_code == 200
        view = result.json()
        assert view["state"] == "published" and view["comparison"]["payable_inr"] == 95000
        assert (
            not {"snapshot", "grant_id", "submission_id", "config_digest", "source_digest"}
            & view.keys()
        )
    assert balance(s) == before
    with Session(s.engine) as db:
        op = db.scalar(select(AgentOperation))
        assert (op.state, op.version, op.fence_id, op.lease_until, op.snapshot) == original
        review = db.get(ReviewCase, (TENANT_ID, "REQ-FAKE-0"))
        assert (review.version, review.state, review.final_payable_inr) == (0, "DRAFT_READY", None)


@pytest.mark.parametrize(
    "fault",
    [
        "input_amended",
        "policy_rejected",
        "review_version",
        "final_review",
        "assigned_elsewhere",
        "member_disabled",
        "role_changed",
        "tenant_disabled",
        "user_disabled",
    ],
)
def test_fresh_scope_changes_withhold_previous_result(setup, mvp, settings, fault):
    s = setup
    published(s)
    before = balance(s)
    with Session(s.engine) as db, db.begin():
        review = db.get(ReviewCase, (TENANT_ID, "REQ-FAKE-0"))
        if fault == "input_amended":
            case = db.get(SubmittedCase, (TENANT_ID, "REQ-FAKE-0"))
            case.inputs = {**case.inputs, "clinical_note": "CHANGED PRIVATE FACTS"}
        elif fault == "policy_rejected":
            db.add(
                MvpEvent(
                    id=uuid4(),
                    tenant_id=TENANT_ID,
                    actor_id=ACTOR,
                    actor_role="medical_officer",
                    command_id=uuid4(),
                    action="policy_reject",
                    subject_id=str(s.policy_id),
                    fingerprint="0" * 64,
                    payload={},
                )
            )
        elif fault == "review_version":
            review.version += 1
        elif fault == "final_review":
            review.state = "APPROVED_WITH_DEDUCTIONS"
            review.final_payable_inr = 95000
        elif fault == "assigned_elsewhere":
            review.assignee_id = UUID(PROFILES["processor"][0])
        elif fault == "member_disabled":
            db.get(Membership, (TENANT_ID, ACTOR)).active = False
        elif fault == "role_changed":
            db.get(Membership, (TENANT_ID, ACTOR)).role = "processor"
        elif fault == "tenant_disabled":
            db.get(Tenant, TENANT_ID).active = False
        else:
            db.get(AppUser, ACTOR).active = False
    result = get(mvp, settings)
    if result.status_code == 200:
        assert result.json()["state"] in {"stale", "unavailable"}
        assert result.json()["comparison"] is result.json()["operation_id"] is None
    else:
        assert result.status_code == 403
    assert "CHANGED PRIVATE FACTS" not in result.text
    assert balance(s) == before


def test_expired_submitted_read_does_not_retry_or_recover(setup, mvp, settings):
    s = setup
    submission(s)
    s.clock[0] += timedelta(minutes=3)
    before = balance(s)
    for _ in range(2):
        result = get(mvp, settings).json()
        assert result["state"] == "submitting" and result["comparison"] is None
    assert balance(s) == before


def test_tenant_is_server_selected_even_with_a_matching_request_id(setup, mvp, settings):
    s = setup
    published(s)
    other = uuid4()
    with Session(s.engine) as db, db.begin():
        db.add(Tenant(id=other, name="Other synthetic tenant"))
        db.flush()
        db.add(Membership(tenant_id=other, user_id=ACTOR, role="medical_officer"))
        original = db.get(SubmittedCase, (TENANT_ID, "REQ-FAKE-0"))
        policy = db.get(PolicyVersion, s.policy_id)
        new_policy_id = uuid4()
        db.add(
            PolicyVersion(
                id=new_policy_id,
                tenant_id=other,
                product_id=policy.product_id,
                version=policy.version,
                author_id=ACTOR,
                command_id=uuid4(),
                fingerprint=policy.fingerprint,
                proposal=policy.proposal,
            )
        )
        db.flush()
        db.add(
            MvpEvent(
                id=uuid4(),
                tenant_id=other,
                actor_id=ACTOR,
                actor_role="medical_officer",
                command_id=uuid4(),
                action="policy_approve",
                subject_id=str(new_policy_id),
                fingerprint="0" * 64,
                payload={},
            )
        )
        db.add(
            SubmittedCase(
                tenant_id=other,
                request_id=original.request_id,
                actor_id=ACTOR,
                command_id=uuid4(),
                fingerprint=original.fingerprint,
                policy_id=new_policy_id,
                inputs=original.inputs,
                record=original.record,
                priority="normal",
                due_at=original.due_at,
            )
        )
        db.flush()
        db.add(
            CaseInputRevision(
                tenant_id=other,
                request_id=original.request_id,
                revision=0,
                actor_id=ACTOR,
                inputs=original.inputs,
                digest=original.record["input_digest"],
            )
        )
        db.add(
            ReviewCase(
                tenant_id=other, request_id=original.request_id, version=0, state="DRAFT_READY"
            )
        )
    response = mvp.get(PATH, headers=bearer(settings, "medical_officer", other))
    assert response.status_code == 200
    assert response.json()["state"] == "not_requested"
    assert str(TENANT_ID) not in response.text
