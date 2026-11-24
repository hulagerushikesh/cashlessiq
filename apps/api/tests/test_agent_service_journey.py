"""Exact installed manual units + real HTTP/PG/peer/canned child, disposable CI only."""

import os
import sys

import pytest

if (sys.platform != "linux" or os.geteuid() != 0
    or os.environ.get("GITHUB_ACTIONS") != "true"
    or os.environ.get("GITHUB_REPOSITORY") != "hulagerushikesh/cashlessiq"
    or os.environ.get("CIQ_AGENT_SERVICE_JOURNEY_TEST") != "1"
    or os.environ.get("CIQ_AGENT_PACKAGE_TEST") != "1"
    or os.environ.get("CIQ_AGENT_SERVICE_TEST") != "1"
    or os.environ.get("CIQ_AGENT_CONTROLLER_TEST") != "1"):
    pytest.skip("Exact service journeys require explicit disposable root CI",
                allow_module_level=True)

import hashlib
import shutil
import sqlite3
from uuid import uuid4

from scripts import test_agent_service_journey as runner
from sqlalchemy import text
from sqlalchemy.orm import Session
from test_agent_contracts import candidate
from test_agent_controller_capture import controller_database as controller_database
from test_agent_controller_capture import engine as engine
from test_agent_controller_capture import scope as scope
from test_agent_controller_capture import setup as setup
from test_agent_controller_reservation import commands as commands
from test_agent_custody_publication import install as install_publication
from test_agent_custody_submission import install as install_custody
from test_agent_custody_submission import rows
from test_agent_ledger import balance
from test_agent_receipt_verifier import observer as observer
from test_agent_requested_dispatch import PATH
from test_agent_requested_dispatch import requested as requested
from test_identity import bearer

from ciq_api.agent_admission import checkpoint
from ciq_api.agent_ledger import ClaimReceipt
from ciq_api.agent_ledger_models import AgentComparison
from ciq_api.mvp_models import WorkJob
from ciq_api.review_models import ReviewCase
from ciq_api.seed import TENANT_ID

packages, policy = runner.packages, runner.policy
RETAINED = policy.PLANS[2] / "journal-parent/retained"
SOCKET = policy.PLANS[2] / "ipc/peer.sock"


@pytest.fixture(scope="module", autouse=True)
def services():
    # Higher-scoped guard/setup runs before any per-test database fixture.
    with runner.installed_services() as installed:
        yield installed


@pytest.fixture
def journey(requested, observer, services):
    assert requested is observer
    try:
        yield requested, services
    finally:
        # Quiesce actual services before DB fixtures revoke/drop anything, and
        # before the trusted fixture removes its own stale endpoint/private files.
        services.stop()
        for path in (*packages.FILES, packages.FILES[1].with_name("candidate.json"), SOCKET):
            path.unlink(missing_ok=True)
        if RETAINED.exists():
            shutil.rmtree(RETAINED)
        assert not SOCKET.exists() and not RETAINED.exists()


def credentials(s, engine):
    with s.admin.connect() as db:
        oid = db.scalar(text("SELECT oid FROM pg_catalog.pg_database "
                             "WHERE datname=current_database()"))
        login_oid = db.scalar(text("SELECT oid FROM pg_catalog.pg_roles WHERE rolname=:name"),
                              {"name": engine.url.username})
    return {"database": engine.url.database, "database_oid": oid,
            "login": engine.url.username, "login_oid": login_oid, "password": engine.url.password}


def deliver(index, body, *, name=None):
    path = packages.FILES[index]
    if name:
        path = path.with_name(name)
    packages.stage(path, packages.ACCOUNTS[index][1], body, None, "unused")


@pytest.mark.parametrize("scenario", ["published", "invalid-held", "unassigned-held"])
def test_http_to_installed_services_and_validated_result(journey, settings, scenario):
    s, services = journey
    # Only the restricted clinical login and this held intent reach the claim UID.
    deliver(0, {**credentials(s, s.runtime), "protocol": "ciq-fake-claim-v1",
                "capture_schema": s.capture, "request_id": "REQ-FAKE-0",
                "job_id": str(s.job_id)})
    services.start("claim")
    private = services.finish("claim", 0)
    assert len(private) == 1
    s.claim = ClaimReceipt.model_validate_json(private[0])
    assert balance(s.setup) == (1, 1, 10, 0, 0) and not rows(s)[1]
    # Explicit negative probe, never an automatic retry or authority adoption.
    services.start("claim")
    assert services.finish("claim", 1) == ["fake_claim_unavailable"]

    # Trusted independent operator assigns custody only AFTER confirmed claim.
    install_custody(s)
    install_publication(s)
    if scenario == "unassigned-held":
        with s.admin.begin() as db:
            db.execute(text(f'UPDATE "{s.receipts}".submission_scope SET enabled=false'))
    epoch = s.setup.admission.journal.pin.model_dump(mode="json")
    runner.provision(epoch)
    deliver(2, {"protocol": "ciq-fake-receipt-v1", "epoch": epoch,
                "custody_uid": packages.ACCOUNTS[1][1]})
    deliver(1, {**credentials(s, s.observer_runtime), "protocol": "ciq-fake-custody-v1",
                "receipts_schema": s.receipts, "request_id": "REQ-FAKE-0",
                "claim": s.claim.model_dump(mode="json"), "epoch": epoch,
                "receipt_uid": packages.ACCOUNTS[2][1]})
    body = candidate(s.setup.snapshots[0], s.claim.operation_id)
    if scenario == "invalid-held":
        body["payable_inr"] = 1
    deliver(1, body, name="candidate.json")
    # All private plans/candidate/authority are staged before the short idle window.
    services.start("receipt")
    services.receipt_ready()
    assert SOCKET.is_socket() and SOCKET.stat().st_uid == packages.ACCOUNTS[2][1]
    services.start("custody")
    published = scenario == "published"
    assert services.finish("custody", 0 if published else 1) == [
        "fake_custody_published" if published else "fake_custody_unavailable",
    ]
    services.start("custody")  # Explicit replay-denial assertion only.
    assert services.finish("custody", 1) == ["fake_custody_unavailable"]
    op, attempts = rows(s)
    assert len(attempts) == (0 if scenario == "unassigned-held" else 1)
    with sqlite3.connect(f"file:{RETAINED}/fake-receipts.sqlite3?mode=ro", uri=True) as db:
        receipts = db.execute("SELECT * FROM receipt").fetchall()
    if attempts:
        with Session(s.admin) as db:
            expected = checkpoint(db, db.merge(attempts[0]))
        assert receipts == [(*expected.values(), "issued")]
    else:
        assert receipts == []
    assert balance(s.setup) == ((1, 0, 0, 10, 0) if published else (1, 1, 10, 0, 0))
    view = s.http.get(PATH + "/agent-result", headers=s.headers)
    assert view.status_code == 200 and view.headers["cache-control"] == "no-store"
    assert view.json()["state"] == ("published" if published else
                                     "reserved" if scenario == "unassigned-held" else "submitting")
    assert view.json()["request_context"] is None
    if published:
        assert view.json()["comparison"]["payable_inr"] == 95000
    else:
        assert view.json()["comparison"] is None
    for role in ("processor", "auditor"):
        assert s.http.get(PATH + "/agent-result", headers=bearer(settings, role)).status_code == 403
    assert s.http.post(PATH + "/agent-request", headers=s.headers, json={
        "command_id": str(uuid4()), "expected_input_revision": 0,
        "expected_review_version": 0, "synthetic_data": True,
    }).status_code == 409
    with Session(s.admin) as db:
        assert db.query(AgentComparison).count() == (1 if published else 0)
        job = db.get(WorkJob, s.job_id)
        assert job.state == "executor_claimed" and job.attempts == 0
        assert job.result == {"operation_id": str(op.id)}
        review = db.get(ReviewCase, (TENANT_ID, "REQ-FAKE-0"))
        assert (review.state, review.version, review.final_payable_inr) == ("DRAFT_READY", 0, None)
        assert db.scalar(text("SELECT count(*) FROM review_outbox")) == 0
        # Policy approval and held intent; the agent adds no human event/outbox.
        assert db.scalar(text("SELECT count(*) FROM mvp_event")) == 2
    # Original bounded idle exit, no reset/unlink/restart, unchanged retained bytes.
    digest = hashlib.sha256((RETAINED / "fake-receipts.sqlite3").read_bytes()).digest()
    assert services.finish("receipt", 1) == ["fake_receipt_ready", "fake_receipt_unavailable"]
    assert SOCKET.is_socket()
    assert hashlib.sha256((RETAINED / "fake-receipts.sqlite3").read_bytes()).digest() == digest
    print("PASS: exact services " + scenario + " preserve one-shot ledger and human review",
          flush=True)
