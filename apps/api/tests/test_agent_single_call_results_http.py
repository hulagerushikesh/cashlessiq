"""PostgreSQL-backed HTTP authorization for optional reviewed advisory reads."""

from copy import deepcopy
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from test_agent_ledger import ACTOR, balance
from test_agent_ledger import setup as setup
from test_agent_results import PATH, get
from test_agent_single_call_results import record

from ciq_api import agent_single_call_results as results
from ciq_api.agent_scope import capture_scope
from ciq_api.main import create_app
from ciq_api.review_models import ReviewCase
from ciq_api.seed import TENANT_ID


@pytest.fixture
def material(setup):
    with Session(setup.engine) as db, db.begin():
        db.get(ReviewCase, (TENANT_ID, "REQ-FAKE-0")).assignee_id = ACTOR
        snapshot, current = capture_scope(db, TENANT_ID, ACTOR, "REQ-FAKE-0", uuid4())
    row = record(snapshot)
    row["actor_id"] = ACTOR
    return row, snapshot, current


@pytest.fixture
def http(setup, settings):
    config = settings.model_copy(update={"synthetic_workflows": True,
                                         "single_call_advisory_reads": True})
    with TestClient(create_app(config, setup.engine)) as client:
        yield client


def test_optional_sql_missing_returns_safe_fallback_preserving_review(
    material, setup, http, settings,
):
    before = balance(setup)
    response = get(http, settings)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["state"] == "unavailable"
    assert response.json()["execution_profile"] == results.PROFILE
    assert "read_advisory" not in response.text
    assert balance(setup) == before
    with Session(setup.engine) as db:
        review = db.get(ReviewCase, (TENANT_ID, "REQ-FAKE-0"))
        assert (review.version, review.state, review.final_payable_inr) == (0, "DRAFT_READY", None)


def test_http_reads_only_fixed_function_and_never_fake_ledger(
    material, setup, http, settings, monkeypatch,
):
    row, _, _ = material
    original = Session.scalar
    calls = []

    def scalar(db, statement, params=None, **kwargs):
        if statement is results.READ:
            calls.append(params)
            return deepcopy(row)
        return original(db, statement, params, **kwargs)

    monkeypatch.setattr(Session, "scalar", scalar)
    before = balance(setup)
    for _ in range(3):
        response = get(http, settings)
        assert response.status_code == 200
        assert response.json()["comparison"]["payable_inr"] == 95000
        assert response.json()["request_context"] is None
    assert calls == [dict(tenant=TENANT_ID, actor=ACTOR, request="REQ-FAKE-0")] * 3
    assert balance(setup) == before
    assert http.post(PATH, json={}).status_code in {401, 405}


@pytest.mark.parametrize("role", ["processor", "auditor", "operations_lead", "tenant_admin",
                                  "policy_approver", "policy_analyst"])
def test_nonclinical_roles_never_invoke_advisory_sql(material, http, settings, monkeypatch, role):
    monkeypatch.setattr(results, "read_single_call_result", lambda *args: pytest.fail("SQL read"))
    assert get(http, settings, role).status_code == 403


def test_unassigned_review_never_invokes_advisory_sql(material, setup, http, settings, monkeypatch):
    with Session(setup.engine) as db, db.begin():
        db.get(ReviewCase, (TENANT_ID, "REQ-FAKE-0")).assignee_id = None
    monkeypatch.setattr(results, "read_single_call_result", lambda *args: pytest.fail("SQL read"))
    assert get(http, settings).json()["state"] == "unavailable"
