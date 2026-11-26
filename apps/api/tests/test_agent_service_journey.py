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

from psycopg import sql
from scripts import test_agent_service_journey as runner
from scripts.agent_controller_lifecycle import (
    CLINICAL,
    CUSTODY,
    Target,
    command,
    revoke_fake,
    role_pin,
)
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from test_agent_contracts import candidate
from test_agent_controller_capture import controller_database as controller_database
from test_agent_controller_capture import engine as engine
from test_agent_controller_capture import scope as scope
from test_agent_controller_capture import setup as setup
from test_agent_controller_lifecycle import product_digest
from test_agent_controller_reservation import commands as commands
from test_agent_custody_publication import install as install_publication
from test_agent_custody_submission import install as install_custody
from test_agent_custody_submission import rows
from test_agent_ledger import balance
from test_agent_receipt_verifier import closed
from test_agent_receipt_verifier import observer as observer
from test_agent_requested_dispatch import PATH
from test_agent_requested_dispatch import requested as requested
from test_identity import bearer

from ciq_api.agent_admission import checkpoint
from ciq_api.agent_contracts import AgentContractError
from ciq_api.agent_controller_capture import ControllerCapture
from ciq_api.agent_ledger import ClaimReceipt
from ciq_api.agent_ledger_models import AgentComparison
from ciq_api.agent_receipt_verifier import FakeReceiptVerifier
from ciq_api.mvp_models import WorkJob
from ciq_api.review_models import ReviewCase
from ciq_api.seed import TENANT_ID

packages, policy = runner.packages, runner.policy
RETAINED = policy.STORAGE / "receipts/retained"
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
        services.lease.check()
        sources = tuple(runner.source.SOURCE / runner.plans.TARGETS[role][1]
                        for role in runner.source.ROLES)
        for path in (*packages.FILES, packages.FILES[1].with_name("candidate.json"),
                     SOCKET, *sources):
            path.unlink(missing_ok=True)
        if RETAINED.exists():
            shutil.rmtree(RETAINED)
        assert not SOCKET.exists() and not RETAINED.exists()
        assert not any(path.exists() or path.is_symlink() for path in sources)


def credentials(s, engine):
    with s.admin.connect() as db:
        oid = db.scalar(text("SELECT oid FROM pg_catalog.pg_database "
                             "WHERE datname=current_database()"))
        login_oid = db.scalar(text("SELECT oid FROM pg_catalog.pg_roles WHERE rolname=:name"),
                              {"name": engine.url.username})
    return {"database": engine.url.database, "database_oid": oid,
            "login": engine.url.username, "login_oid": login_oid, "password": engine.url.password}


def retire_and_rotate(s, services):
    """Trusted CI rehearsal only: no live secret source or automatic reauthorization."""
    services.stop()  # All three units/cgroups, before any SQL retirement or pool closure.
    before = product_digest(s)
    retained = (RETAINED / "fake-receipts.sqlite3").read_bytes()
    private_files = (*packages.FILES, *(runner.source.SOURCE / runner.plans.TARGETS[role][1]
                                       for role in runner.source.ROLES))
    plans = {path: path.read_bytes() for path in private_files}
    with s.admin.begin() as db:
        raw = db.connection.driver_connection
        database_oid = raw.execute(
            "SELECT oid FROM pg_database WHERE datname=current_database()"
        ).fetchone()[0]
        target = Target(
            database=s.admin.url.database, database_oid=database_oid,
            product=s.product, capture=s.capture, receipts=s.receipts,
            installer=role_pin(raw, "postgres"), clinical_definer=role_pin(raw, s.owner),
            custody_definer=role_pin(raw, s.receipt_owner),
            clinical=role_pin(raw, s.login), custody=role_pin(raw, s.receipt_login),
        )
    for clinical, runtime_engine, role, schema in (
        (True, s.runtime, target.clinical, s.capture),
        (False, s.observer_runtime, target.custody, s.receipts),
    ):
        # Password rotation alone does not invalidate an already authenticated session.
        with runtime_engine.connect() as idle:
            pid = idle.scalar(text("SELECT pg_backend_pid()"))
            idle.commit()
            for _ in range(2):  # Explicit idempotence assertion, not a retry on failure.
                with s.admin.begin() as db:
                    db.execute(text("SELECT 1"))
                    revoke_fake(db.connection.driver_connection, target, clinical=clinical)
            assert idle.scalar(text("SELECT pg_backend_pid()")) == pid
            idle.commit()
            expression = "capture('REQ-FAKE-0')" if clinical else "inventory_fake()"
            with pytest.raises(DBAPIError) as denied:
                idle.execute(text(f'SELECT "{schema}".{expression}'))
            assert denied.value.orig.sqlstate == "42501"
            idle.rollback()
        runtime_engine.dispose()  # Returned idle connections must also close before rotation.

        def no_sessions(name=role.name):
            with s.admin.connect() as db:
                return db.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE usename=:name"),
                                 {"name": name}) == 0

        policy.wait_for(no_sessions, 3)
        with s.admin.connect() as db:
            assert db.scalar(text("SELECT rolcanlogin FROM pg_roles WHERE oid=:oid"),
                             {"oid": role.oid}) is False
        password = uuid4().hex  # Dummy, memory-only, never logged or returned.
        with s.admin.begin() as db:
            raw = db.connection.driver_connection
            raw.execute(sql.SQL("ALTER ROLE {} PASSWORD {} LOGIN").format(
                sql.Identifier(role.name), sql.Literal(password)))
            raw.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(target.database), sql.Identifier(role.name)))
            raw.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
                sql.Identifier(schema), sql.Identifier(role.name)))
            # This journey installs publication, not the separate recovery package.
            for signature in CLINICAL if clinical else CUSTODY[:6]:
                command(raw, "GRANT", schema, signature, role.name)
            # No principal, reservation or submission approval is re-enabled.
        wrong = create_engine(runtime_engine.url)
        rotated = create_engine(runtime_engine.url.set(password=password))
        try:
            # libpq authentication errors need not expose a SQLSTATE; successful
            # fresh authentication below independently confirms the same endpoint.
            with pytest.raises(DBAPIError), wrong.connect():
                pytest.fail("Retired dummy password authenticated")
            with rotated.begin() as db:
                assert db.scalar(text("SELECT oid FROM pg_roles "
                                      "WHERE rolname=session_user AND session_user=current_user")) \
                    == role.oid
            with s.admin.connect() as db:
                for table in ("principal", "reservation_scope" if clinical else "submission_scope"):
                    assert db.scalar(text(f'SELECT count(*) FROM "{schema}"."{table}" '
                                          'WHERE enabled')) == 0
            if clinical:
                with pytest.raises(AgentContractError):
                    ControllerCapture(rotated, schema=schema).capture("REQ-FAKE-0")
            else:
                closed(FakeReceiptVerifier(rotated, s.setup.admission.journal,
                                           schema=schema).check)
            # Old private files are preserved. Their stale password must fail in
            # the actual installed module under its unchanged service policy.
            service = "claim" if clinical else "custody"
            services.start(service)  # Explicit denial probe, never automatic recovery.
            assert services.finish(service, 1) == [
                "fake_claim_unavailable" if clinical else "fake_custody_unavailable",
            ]
        finally:
            wrong.dispose()
            rotated.dispose()
        services.stop()
        assert product_digest(s) == before
        assert (RETAINED / "fake-receipts.sqlite3").read_bytes() == retained
        assert {path: path.read_bytes() for path in private_files} == plans
    print("PASS: retired service credentials and rotated passwords restore no authority",
          flush=True)


@pytest.mark.parametrize("scenario", ["published", "invalid-held", "unassigned-held"])
def test_http_to_installed_services_and_validated_result(journey, settings, scenario):
    s, services = journey
    # Only the restricted clinical login and this held intent reach the claim UID.
    runner.provision_plan("claim", {**credentials(s, s.runtime), "protocol": "ciq-fake-claim-v1",
                "capture_schema": s.capture, "request_id": "REQ-FAKE-0",
                "job_id": str(s.job_id)})
    services.deliver_private("claim")
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
    runner.provision_plan("receipt", {"protocol": "ciq-fake-receipt-v1", "epoch": epoch,
                "custody_uid": packages.ACCOUNTS[1][1]})
    runner.provision_plan("custody", {**credentials(s, s.observer_runtime),
                "protocol": "ciq-fake-custody-v1",
                "receipts_schema": s.receipts, "request_id": "REQ-FAKE-0",
                "claim": s.claim.model_dump(mode="json"), "epoch": epoch,
                "receipt_uid": packages.ACCOUNTS[2][1]})
    services.deliver_private("receipt")
    services.deliver_private("custody")
    print("PASS: root-only sources deny all service UIDs before private delivery", flush=True)
    body = candidate(s.setup.snapshots[0], s.claim.operation_id)
    if scenario == "invalid-held":
        body["payable_inr"] = 1
    services.deliver("candidate", body)
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
    retire_and_rotate(s, services)
    print("PASS: exact services " + scenario + " preserve one-shot ledger and human review",
          flush=True)
