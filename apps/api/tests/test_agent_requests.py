"""App intent, deduplication and exclusion from generic execution/retries."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_agent_ledger import ACTOR, balance, reserve
from test_agent_ledger import setup as setup
from test_identity import bearer
from test_mvp import mvp as mvp

from ciq_api.agent_ledger_models import AgentAttempt, AgentOperation
from ciq_api.jobs import claim, complete, compute
from ciq_api.main import create_app
from ciq_api.mvp_models import MvpEvent, WorkJob
from ciq_api.review_models import ReviewCase
from ciq_api.seed import PROFILES, TENANT_ID

PATH = "/v3/requests/REQ-FAKE-0/agent-request"
RESULT = PATH.replace("agent-request", "agent-result")


def command(**values):
    return {
        "command_id": str(uuid4()),
        "expected_input_revision": 0,
        "expected_review_version": 0,
        "synthetic_data": True,
        **values,
    }


def assigned(s):
    with Session(s.engine) as db, db.begin():
        db.get(ReviewCase, (TENANT_ID, "REQ-FAKE-0")).assignee_id = ACTOR


def post(http, settings, payload=None, role="medical_officer", path=PATH):
    return http.post(path, json=payload or command(), headers=bearer(settings, role))


def test_opt_in_authentication_and_unknown_request(setup, mvp, settings):
    disabled = settings.model_copy(update={"synthetic_workflows": False})
    with TestClient(create_app(disabled, setup.engine)) as http:
        assert post(http, settings).status_code == 404
    assert mvp.post(PATH, json=command()).status_code == 401
    assert post(mvp, settings, path=PATH.replace("REQ-FAKE-0", "MISSING")).status_code == 404


@pytest.mark.parametrize(
    "role",
    [
        "processor",
        "auditor",
        "operations_lead",
        "tenant_admin",
        "policy_analyst",
        "policy_approver",
    ],
)
def test_only_clinical_role_can_request(setup, mvp, settings, role):
    assigned(setup)
    assert post(mvp, settings, role=role).status_code == 403
    with Session(setup.engine) as db:
        assert db.scalar(select(func.count()).select_from(WorkJob)) == 0


@pytest.mark.parametrize(
    "values",
    [
        {"synthetic_data": False},
        {"synthetic_data": "true"},
        {"expected_review_version": "0"},
        {"expected_input_revision": -1},
        {"tenant_id": str(uuid4())},
        {"grant_id": str(uuid4())},
    ],
)
def test_strict_intent_has_no_authority_or_identity_selectors(setup, mvp, settings, values):
    assigned(setup)
    assert post(mvp, settings, command(**values)).status_code == 422


def test_duplicate_commands_and_fresh_commands_share_one_held_intent(setup, mvp, settings):
    s = setup
    assigned(s)
    before = balance(s)
    payload = command()
    first = post(mvp, settings, payload)
    assert first.status_code == 202 and first.headers["cache-control"] == "no-store"
    receipt = first.json()
    assert receipt["state"] == "awaiting_executor"
    assert post(mvp, settings, payload).json() == receipt
    assert post(mvp, settings).json() == receipt
    with Session(s.engine) as db:
        jobs = db.scalars(select(WorkJob)).all()
        assert len(jobs) == 1
        job = jobs[0]
        assert (job.state, job.attempts, job.lease_id, job.result) == (
            "awaiting_executor",
            0,
            None,
            None,
        )
        assert set(job.payload) == {"binding", "binding_digest"}
        assert not {"facts", "policy", "grant_id", "epoch_id", "correlation_id"} & (
            job.payload.keys() | job.payload["binding"].keys()
        )
        assert db.scalar(select(func.count()).select_from(AgentOperation)) == 0
        assert db.scalar(select(func.count()).select_from(AgentAttempt)) == 0
        review = db.get(ReviewCase, (TENANT_ID, "REQ-FAKE-0"))
        assert (review.state, review.version, review.final_payable_inr) == ("DRAFT_READY", 0, None)
    assert balance(s) == before
    result = mvp.get(RESULT, headers=bearer(settings, "medical_officer")).json()
    assert result["state"] == "awaiting_executor"
    assert result["request_job_id"] == receipt["job_id"]
    assert result["request_context"] is None and result["comparison"] is None


def test_concurrent_requests_serialize_to_one_intent(setup, mvp, settings):
    assigned(setup)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: post(mvp, settings), range(2)))
    assert [r.status_code for r in results] == [202, 202]
    assert results[0].json() == results[1].json()
    with Session(setup.engine) as db:
        assert db.scalar(select(func.count()).select_from(WorkJob)) == 1


def test_one_command_cannot_be_reused_for_another_request(setup, mvp, settings):
    assigned(setup)
    payload = command()
    assert post(mvp, settings, payload).status_code == 202
    assert post(mvp, settings, payload, path=PATH.replace("FAKE-0", "FAKE-1")).status_code == 409


@pytest.mark.parametrize(
    "fault", ["unassigned", "other_assignee", "closed", "review_version", "input_version"]
)
def test_assignment_and_current_revision_are_required(setup, mvp, settings, fault):
    assigned(setup)
    payload = command()
    with Session(setup.engine) as db, db.begin():
        review = db.get(ReviewCase, (TENANT_ID, "REQ-FAKE-0"))
        if fault == "unassigned":
            review.assignee_id = None
        elif fault == "other_assignee":
            review.assignee_id = UUID(PROFILES["processor"][0])
        elif fault == "closed":
            review.state = "APPROVED"
        elif fault == "review_version":
            review.version += 1
        else:
            payload["expected_input_revision"] += 1
    assert post(mvp, settings, payload).status_code == 409
    with Session(setup.engine) as db:
        assert db.scalar(select(func.count()).select_from(WorkJob)) == 0


def test_review_change_withholds_old_intent_and_original_retry_does_not_enqueue(
    setup, mvp, settings
):
    assigned(setup)
    payload = command()
    first = post(mvp, settings, payload).json()
    with Session(setup.engine) as db, db.begin():
        db.get(ReviewCase, (TENANT_ID, "REQ-FAKE-0")).version += 1
    view = mvp.get(RESULT, headers=bearer(settings, "medical_officer")).json()
    assert view["state"] == "not_requested" and view["request_job_id"] is None
    assert view["request_context"] == {"input_revision": 0, "review_version": 1}
    assert post(mvp, settings, payload).json() == first
    assert post(mvp, settings).status_code == 409
    second = post(mvp, settings, command(expected_review_version=1)).json()
    assert second["job_id"] != first["job_id"]


def test_existing_operation_is_never_a_browser_retry(setup, mvp, settings):
    assigned(setup)
    reserve(setup)
    before = balance(setup)
    assert post(mvp, settings).status_code == 409
    view = mvp.get(RESULT, headers=bearer(settings, "medical_officer")).json()
    assert view["state"] == "reserved" and view["request_context"] is None
    assert balance(setup) == before


@pytest.mark.parametrize(
    "state,attempts",
    [
        ("awaiting_executor", 0),
        ("queued", 0),
        ("queued", 3),
        ("running", 1),
        ("running", 3),
    ],
)
def test_generic_claim_cannot_execute_or_expire_agent_intents(
    setup, mvp, settings, state, attempts
):
    assigned(setup)
    post(mvp, settings)
    with Session(setup.engine) as db, db.begin():
        job = db.scalar(select(WorkJob))
        job.state, job.attempts = state, attempts
        job.lease_id = uuid4()
        job.lease_until = datetime.now(UTC) - timedelta(seconds=1)
    assert claim(setup.engine) is None
    with Session(setup.engine) as db:
        job = db.scalar(select(WorkJob))
        assert (job.state, job.attempts, job.error_code) == (state, attempts, None)


def test_direct_generic_compute_complete_and_retry_are_denied(setup, mvp, settings):
    assigned(setup)
    post(mvp, settings)
    with Session(setup.engine) as db, db.begin():
        job = db.scalar(select(WorkJob))
        job_id, lease = job.id, uuid4()
        job.state, job.lease_id = "running", lease
        job.lease_until = datetime.now(UTC) + timedelta(seconds=30)
    with pytest.raises(ValueError, match="Lost job lease"):
        compute(setup.engine, job_id, lease)
    assert complete(setup.engine, job_id, lease, {"result": "FORGED"}) is False
    assert complete(setup.engine, job_id, lease, failed=True) is False
    with Session(setup.engine) as db, db.begin():
        db.get(WorkJob, job_id).state = "dead"
    retry = mvp.post(
        f"/v3/jobs/{job_id}/retry",
        headers=bearer(settings, "operations_lead"),
        json={"command_id": str(uuid4()), "reason": "Attempt forbidden retry"},
    )
    assert retry.status_code == 409
    with Session(setup.engine) as db:
        assert db.get(WorkJob, job_id).state == "dead"
        assert (
            db.scalar(
                select(func.count()).select_from(MvpEvent).where(MvpEvent.action == "job_retry")
            )
            == 0
        )


def test_intent_is_excluded_from_generic_job_lists_and_details(setup, mvp, settings):
    assigned(setup)
    job_id = post(mvp, settings).json()["job_id"]
    for role in ["medical_officer", "processor", "operations_lead", "auditor"]:
        headers = bearer(settings, role)
        assert mvp.get("/v3/jobs", headers=headers).json()["items"] == []
        assert mvp.get(f"/v3/jobs/{job_id}", headers=headers).status_code == 404
