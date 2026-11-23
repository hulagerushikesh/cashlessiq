"""App intent -> restricted atomic claim. Explicit disposable PostgreSQL CI only."""

import os
import sys

import pytest

if (
    sys.platform != "linux" or os.environ.get("GITHUB_ACTIONS") != "true"
    or os.environ.get("GITHUB_REPOSITORY") != "hulagerushikesh/cashlessiq"
    or os.environ.get("CIQ_AGENT_CONTROLLER_TEST") != "1"
):
    pytest.skip("Dedicated disposable controller privilege job required", allow_module_level=True)

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from test_agent_controller_capture import controller_database as controller_database
from test_agent_controller_capture import engine as engine
from test_agent_controller_capture import scope as scope
from test_agent_controller_capture import setup as setup
from test_agent_controller_reservation import commands as commands
from test_agent_controller_reservation import mutate, reserve
from test_agent_ledger import ACTOR, balance
from test_identity import bearer

from ciq_api.agent_contracts import AgentContractError
from ciq_api.agent_ledger_models import AgentAttempt, AgentOperation
from ciq_api.main import create_app
from ciq_api.mvp_models import WorkJob
from ciq_api.review_models import ReviewCase
from ciq_api.seed import TENANT_ID

REQUEST = "REQ-FAKE-0"
PATH = f"/v3/requests/{REQUEST}"


@pytest.fixture
def requested(commands, settings):
    s = commands
    settings.synthetic_workflows = True
    with Session(s.admin) as db, db.begin():
        db.get(ReviewCase, (TENANT_ID, REQUEST)).assignee_id = ACTOR
    s.headers = bearer(settings, "medical_officer")
    with TestClient(create_app(settings, s.admin)) as http:
        s.http = http
        response = http.post(PATH + "/agent-request", headers=s.headers, json={
            "command_id": str(uuid4()), "expected_input_revision": 0,
            "expected_review_version": 0, "synthetic_data": True,
        })
        assert response.status_code == 202
        s.job_id = UUID(response.json()["job_id"])
        yield s


def claim(s, job_id=None):
    return s.commands.claim_requested(REQUEST, job_id or s.job_id)


def unchanged(s):
    assert balance(s.setup) == (0, 0, 0, 0, 0)
    with Session(s.admin) as db:
        assert db.query(AgentOperation).count() == db.query(AgentAttempt).count() == 0


def test_atomic_claim_consumes_intent_once_without_attempt_or_human_change(requested):
    s = requested
    receipt = claim(s)
    assert receipt.state == "reserved" and receipt.version == 1
    assert balance(s.setup) == (1, 1, 10, 0, 0)
    with Session(s.admin) as db:
        job = db.get(WorkJob, s.job_id)
        assert job.state == "executor_claimed" and job.attempts == 0 and job.lease_id is None
        assert job.result == {"operation_id": str(receipt.operation_id)}
        assert db.query(AgentAttempt).count() == 0
        review = db.get(ReviewCase, (TENANT_ID, REQUEST))
        assert (review.version, review.state, review.final_payable_inr) == (0, "DRAFT_READY", None)
    with pytest.raises(AgentContractError):
        claim(s)
    assert s.http.get(PATH + "/agent-result", headers=s.headers).json()["state"] == "reserved"
    assert balance(s.setup) == (1, 1, 10, 0, 0)


@pytest.mark.parametrize("fault", [
    "kind", "subject", "actor", "state", "attempts", "lease", "lease_until",
    "result", "error", "binding", "extra_payload", "digest", "missing_digest",
])
def test_malformed_or_different_intent_cannot_hold_allowance(requested, fault):
    s = requested
    with Session(s.admin) as db, db.begin():
        job = db.get(WorkJob, s.job_id)
        if fault == "kind":
            job.kind = "assessment"
        elif fault == "subject":
            job.subject_id = "REQ-FAKE-1"
        elif fault == "actor":
            from ciq_api.seed import PROFILES
            job.actor_id = UUID(PROFILES["processor"][0])
        elif fault == "state":
            job.state = "queued"
        elif fault == "attempts":
            job.attempts = 1
        elif fault == "lease":
            job.lease_id = uuid4()
        elif fault == "lease_until":
            job.lease_until = db.scalar(text("SELECT clock_timestamp()"))
        elif fault == "result":
            job.result = {}
        elif fault == "error":
            job.error_code = "failed"
        elif fault == "binding":
            job.payload = {**job.payload, "binding": {}}
        elif fault == "extra_payload":
            job.payload = {**job.payload, "grant_id": str(s.setup.grant_id)}
        elif fault == "digest":
            # Well-formed but false canonical digest must roll back the SQL hold.
            job.payload = {**job.payload, "binding_digest": "f" * 64}
        else:
            job.payload = {"binding": job.payload["binding"]}
    with pytest.raises(AgentContractError, match=r"^reservation_unavailable$"):
        claim(s)
    unchanged(s)


@pytest.mark.parametrize("fault", [
    "unassigned", "review_changed", "membership", "principal", "approval", "unknown_job",
])
def test_fresh_scope_and_explicit_operator_authority_are_required(requested, fault):
    s = requested
    statements = {
        "unassigned": "UPDATE review_case SET assignee_id=NULL",
        "review_changed": "UPDATE review_case SET version=version+1",
        "membership": "UPDATE tenant_membership SET active=false",
        "principal": f'UPDATE "{s.capture}".principal SET enabled=false',
        "approval": f'UPDATE "{s.capture}".reservation_scope SET enabled=false',
    }
    if fault in statements:
        mutate(s, statements[fault])
    with pytest.raises(AgentContractError):
        claim(s, uuid4() if fault == "unknown_job" else s.job_id)
    unchanged(s)


def test_existing_operation_prevents_claim_even_before_any_submission(requested):
    s = requested
    original = reserve(s)
    with pytest.raises(AgentContractError):
        claim(s)
    with Session(s.admin) as db:
        assert db.query(AgentOperation).one().id == original.operation_id
        assert db.get(WorkJob, s.job_id).state == "awaiting_executor"
    assert balance(s.setup) == (1, 1, 10, 0, 0)


def test_two_restricted_claimers_cannot_consume_one_request_twice(requested):
    s = requested
    barrier = Barrier(2)

    def contender():
        barrier.wait(timeout=5)
        try:
            return claim(s)
        except AgentContractError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: contender(), range(2)))
    assert sum(result is not None for result in results) == 1
    assert balance(s.setup) == (1, 1, 10, 0, 0)


def test_runtime_cannot_read_or_mutate_queue_directly(requested):
    s = requested
    for statement in (
        f'SELECT payload FROM "{s.product}".work_job',
        f'UPDATE "{s.product}".work_job SET state=\'awaiting_executor\'',
    ):
        with pytest.raises(DBAPIError) as failure, s.runtime.begin() as db:
            db.execute(text(statement))
        assert failure.value.orig.sqlstate == "42501"
    unchanged(s)
