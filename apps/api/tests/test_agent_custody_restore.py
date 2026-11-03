"""Encrypted 22-table restore followed by actual restricted fake commands.

Only explicitly opted-in disposable public Linux CI. Owners prepare source data,
restore into a new database, install reviewed packages/bindings and assert rows.
No restored operation calls FakeAgentLedger; no provider/local Docker is started.
"""

import os
import sys

import pytest

if (
    sys.platform != "linux"
    or os.environ.get("GITHUB_ACTIONS") != "true"
    or os.environ.get("GITHUB_REPOSITORY") != "hulagerushikesh/cashlessiq"
    or os.environ.get("CIQ_AGENT_CONTROLLER_TEST") != "1"
    or not os.environ.get("CIQ_AGENT_RECOVERY_CONTAINER")
):
    pytest.skip("Dedicated disposable restricted restore job required", allow_module_level=True)

import base64
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import test_agent_controller_capture as capture_package
import test_agent_controller_reservation as reservation_package
import test_agent_custody_publication as publication_package
import test_agent_custody_recovery as recovery_package
import test_agent_receipt_verifier as observer_package
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from test_agent_contracts import candidate
from test_agent_ledger import ACTOR, NOW, balance, payload, reserve, rows, submission
from test_agent_ledger import setup as setup
from test_agent_ledger_recovery import receipt_digest, restored_database
from test_agent_ledger_recovery import recovery_service as recovery_service

from ciq_api.agent_contracts import AgentContractError, AgentInput
from ciq_api.agent_controller_reservation import ControllerReservation
from ciq_api.agent_custody_recovery import FakeCustodyRecovery
from ciq_api.agent_custody_submission import FakeCustodySubmission
from ciq_api.agent_executor import BoundedFakeProcess, FakeProcessRequest
from ciq_api.agent_ledger import ClaimReceipt, FakeAgentLedger, FakeGrantSpec, OperationReceipt
from ciq_api.agent_ledger_models import AgentAttempt, AgentComparison, AgentOperation
from ciq_api.review_models import ReviewCase
from ciq_api.seed import TENANT_ID

ROOT = Path(__file__).resolve().parents[3]
PACKAGES = ROOT / "deploy/agent-controller"


def reject_owner_runtime(monkeypatch):
    """Any restored owner-ledger method call is a test failure, including reads."""

    def denied(*args, **kwargs):
        pytest.fail("Restored runtime must use restricted commands, not owning ledger")

    for name, method in vars(FakeAgentLedger).items():
        if callable(method) and not name.startswith("__"):
            monkeypatch.setattr(FakeAgentLedger, name, denied)


def operation(s, index=0):
    with Session(s.engine) as db:
        return (
            db.query(AgentOperation)
            .filter_by(tenant_id=TENANT_ID, request_id=f"REQ-FAKE-{index}")
            .one()
        )


def receipt(op):
    return OperationReceipt(operation_id=op.id, state=op.state, version=op.version)


def old_claim(op):
    # A stale receipt is deliberately NOT permission to reconstruct issue.
    return ClaimReceipt(
        operation_id=op.id,
        state="reserved",
        version=max(1, op.version),
        fence_id=op.fence_id or uuid4(),
    )


def recovery(s, index=0):
    return FakeCustodyRecovery(
        s.observer_runtime,
        s.setup.admission.journal,
        schema=s.receipts,
        request_id=f"REQ-FAKE-{index}",
        operation_id=operation(s.setup, index).id,
    )


def coordinator(s, claim, *, transport=None):
    return FakeCustodySubmission(
        s.observer_runtime,
        s.setup.admission.journal,
        schema=s.receipts,
        request_id="REQ-FAKE-0",
        claim=claim,
        transport=transport,
    )


def closed(action):
    with pytest.raises(AgentContractError):
        action()


def human_digest(s):
    """Operator assertions compare content without returning clinical rows."""
    digest = hashlib.sha256()
    with s.engine.connect() as db:
        for table in (
            "tenant",
            "app_user",
            "tenant_membership",
            "submitted_case",
            "case_input_revision",
            "policy_version",
            "review_case",
            "mvp_event",
            "review_audit",
            "review_outbox",
            "analytics_event",
        ):
            digest.update(table.encode())
            for value in db.scalars(
                text(
                    f"SELECT row_to_json(t)::text FROM {table} t "
                    'ORDER BY row_to_json(t)::text COLLATE "C"'
                )
            ):
                raw = value.encode()
                digest.update(len(raw).to_bytes(8, "big"))
                digest.update(raw)
    return digest.hexdigest()


@contextmanager
def rebound(s, *, enabled=True):
    """EXPLICIT trusted disposable reinstallation, not automatic restore/startup.

    Product dump excludes private registries and ACLs. Recreate random nonlogin
    definers/separate logins, then stage exact original epoch/grant/op assignments.
    Never copy old OIDs, create an epoch/grant, change a deadline or reset custody.
    Existing fixture installers clean only these created schemas/roles.
    """
    with s.engine.connect() as db:
        schema = db.scalar(text("SELECT current_schema()"))
        assert (
            db.scalar(text("SELECT count(*) FROM pg_namespace WHERE nspname LIKE 'ciq_agent_%'"))
            == 0
        )
        assert (
            db.scalar(
                text(
                    "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                    "WHERE n.nspname=:schema AND c.relkind='r'"
                ),
                {"schema": schema},
            )
            == 22
        )  # Exact normal backup inventory, including Alembic version.
    assert s.ledger is None
    # Source-owner reservation adds its own correlation ID. Restage the exact
    # restored immutable snapshot, never the fixture's earlier capture with a
    # different correlation. Unused allowlisted requests keep their original
    # validated source snapshot. This is trusted binding preparation only.
    existing = {op.request_id: op for op in rows(s, AgentOperation)}
    s.snapshots = [
        AgentInput.model_validate_json(json.dumps(existing[f"REQ-FAKE-{index}"].snapshot))
        if f"REQ-FAKE-{index}" in existing
        else snapshot
        for index, snapshot in enumerate(s.snapshots)
    ]
    human_before = human_digest(s)
    with s.engine.begin() as db:
        raw = db.connection.driver_connection
        raw.execute(
            sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(
                sql.Identifier(s.engine.url.database)
            )
        )
        raw.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
    with (
        contextmanager(capture_package.scope.__wrapped__)(s) as c,
        contextmanager(observer_package.observer.__wrapped__)(c),
    ):
        with c.admin.begin() as db:
            raw = db.connection.driver_connection
            raw.execute(
                sql.SQL((PACKAGES / "reservation.sql").read_text()).format(
                    owner=sql.Identifier(c.owner),
                    capture=sql.Identifier(c.capture),
                    product=sql.Identifier(c.product),
                )
            )
            raw.execute(
                sql.SQL("UPDATE {}.principal SET request_ids=%s,enabled=%s").format(
                    sql.Identifier(c.capture)
                ),
                ([f"REQ-FAKE-{i}" for i in range(3)], enabled),
            )
            raw.execute(
                sql.SQL("UPDATE {}.principal SET enabled=%s").format(sql.Identifier(c.receipts)),
                (enabled,),
            )
            for name in (
                "custody-submission.sql",
                "custody-publication.sql",
                "custody-recovery.sql",
            ):
                raw.execute(
                    sql.SQL((PACKAGES / name).read_text()).format(
                        owner=sql.Identifier(c.receipt_owner),
                        receipts=sql.Identifier(c.receipts),
                        product=sql.Identifier(c.product),
                        capture=sql.Identifier(c.capture),
                    )
                )
            for namespace, login, signatures in (
                (
                    c.capture,
                    c.login,
                    (
                        "reserve_fake(text, integer)",
                        "lease_fake(text, uuid, integer, uuid)",
                    ),
                ),
                (
                    c.receipts,
                    c.receipt_login,
                    (
                        "checkpoint_fake(text, uuid, integer, uuid)",
                        "issue_fake(text, uuid, integer, uuid, uuid)",
                        *publication_package.SIGNATURES,
                        *recovery_package.SIGNATURES,
                    ),
                ),
            ):
                for signature in signatures:
                    raw.execute(
                        sql.SQL("GRANT EXECUTE ON FUNCTION {}.{} TO {}").format(
                            sql.Identifier(namespace),
                            sql.SQL(signature),
                            sql.Identifier(login),
                        )
                    )
            for op in rows(s, AgentOperation):
                raw.execute(
                    sql.SQL(
                        "INSERT INTO {}.submission_scope SELECT custody.oid,%s,controller.oid,"
                        "controller.rolname,%s,%s,%s,%s FROM pg_roles custody,"
                        "pg_roles controller "
                        "WHERE custody.rolname=%s AND controller.rolname=%s"
                    ).format(sql.Identifier(c.receipts)),
                    (
                        op.request_id,
                        TENANT_ID,
                        ACTOR,
                        op.id,
                        enabled,
                        c.receipt_login,
                        c.login,
                    ),
                )
        for index in range(3):
            reservation_package.stage(c, index, enabled=enabled)
        c.commands = ControllerReservation(c.runtime, schema=c.capture)
        # These are two actual separately authenticated runtime connections.
        for runtime, login in ((c.runtime, c.login), (c.observer_runtime, c.receipt_login)):
            with runtime.connect() as db:
                assert db.scalar(text("SELECT session_user")) == login
                assert db.scalar(text("SELECT current_user")) == login
                assert not db.scalar(
                    text("SELECT rolsuper FROM pg_roles WHERE rolname=session_user")
                )
                assert not db.scalar(
                    text("SELECT has_database_privilege(current_database(),'TEMP')")
                )
            for statement in (
                f'SELECT * FROM "{c.product}".agent_operation',
                f'UPDATE "{c.product}".agent_execution_grant SET admitted=0',
                f'SELECT * FROM "{c.capture}".principal',
                f'SELECT * FROM "{c.receipts}".submission_scope',
            ):
                with pytest.raises(DBAPIError) as denied, runtime.begin() as db:
                    db.execute(text(statement))
                assert denied.value.orig.sqlstate == "42501"
        yield c
        assert human_digest(s) == human_before


def assert_no_human_changes(s):
    with s.engine.connect() as db:
        for table in ("review_audit", "review_outbox", "analytics_event"):
            assert db.scalar(text(f"SELECT count(*) FROM {table}")) == 0
        assert (
            db.scalar(text("SELECT count(*) FROM review_case WHERE final_payable_inr IS NOT NULL"))
            == 0
        )


@pytest.mark.parametrize(
    "state",
    [
        "reserved",
        "claimed",
        "submitting",
        "unknown",
        "rejected",
        "published",
        "superseded",
        "expired",
    ],
)
def test_fourteen_journeys_restored_states_recover_through_restricted_login(
    recovery_service,
    setup,
    tmp_path,
    monkeypatch,
    state,
):
    s = setup
    baseline = submission(s, 1)
    s.ledger.publish_fake_result(baseline, payload(baseline))
    subject = reserve(s)
    claim = permit = None
    if state not in {"reserved", "expired"}:
        claim = s.ledger.claim(TENANT_ID, ACTOR, subject.operation_id)
    if state not in {"reserved", "claimed", "expired"}:
        permit = s.ledger.begin_submission(TENANT_ID, ACTOR, claim)
    reserve(s, 2)
    if state == "published":
        s.ledger.publish_fake_result(permit, payload(permit))
    elif state == "rejected":
        s.ledger.publish_fake_result(permit, b"invalid fake output")
    elif state == "superseded":
        with Session(s.engine) as db, db.begin():
            db.get(ReviewCase, (TENANT_ID, "REQ-FAKE-0")).version += 1
        s.ledger.publish_fake_result(permit, payload(permit))
    elif state in {"unknown", "expired"}:
        s.clock[0] = NOW + timedelta(seconds=121)
        s.ledger.recover_expired(TENANT_ID, subject.operation_id)
    before, digest = balance(s), receipt_digest(s)
    with restored_database(
        s, recovery_service, tmp_path / "backup", owner_ledger=False
    ) as restored:
        assert balance(restored) == before and receipt_digest(restored) == digest
        reject_owner_runtime(monkeypatch)
        with rebound(restored) as c:
            original = operation(restored)
            assert recovery(c).recover() is None
            expected = {"reserved": "expired", "claimed": "expired", "submitting": "unknown"}.get(
                state, state
            )
            op = operation(restored)
            assert op.state == expected and op.deadline == original.deadline
            assert op.snapshot == original.snapshot and op.fence_id == original.fence_id
            assert recovery(c).recover() is None and operation(restored).version == op.version
            assert recovery(c, 2).recover() is None and operation(restored, 2).state == "expired"
            assert recovery(c, 1).recover() is None and operation(restored, 1).state == "published"
            stale = coordinator(c, old_claim(original))
            for action in (
                stale.prepare,
                stale.issue,
                stale.dispatch,
                stale.publish,
                stale.heartbeat,
            ):
                closed(action)
            closed(lambda: c.commands.claim("REQ-FAKE-0", receipt(op)))
            # Same stable computation returns its old receipt, never repurchases.
            # Superseded clinical revision correctly denies the old snapshot.
            if state == "superseded":
                closed(lambda: c.commands.reserve("REQ-FAKE-0"))
            else:
                assert c.commands.reserve("REQ-FAKE-0") == receipt(op)
            uncertain = expected == "unknown"
            consumed = 20 if expected in {"published", "rejected", "superseded"} else 10
            assert balance(restored) == (3, int(uncertain), 0, consumed, 10 if uncertain else 0)
            assert receipt_digest(restored) == digest
            assert_no_human_changes(restored)
            # Restored trigger protections still apply even to operator assertions.
            for statement in (
                "DELETE FROM agent_attempt",
                "DELETE FROM agent_operation",
                "UPDATE agent_operation SET deadline=deadline+interval '1 second'",
                "UPDATE agent_comparison SET candidate='{}'",
            ):
                with pytest.raises(DBAPIError), restored.engine.begin() as db:
                    db.execute(text(statement))


def current_fixture(s):
    # Trusted SOURCE fixture only; immutable identity is never rewritten.
    s.clock[0] = datetime.now(UTC)
    s.spec = FakeGrantSpec.model_validate(
        {
            **s.spec.model_dump(),
            "starts_at": s.clock[0] - timedelta(seconds=1),
            "ends_at": s.clock[0] + timedelta(minutes=10),
        }
    )
    s.grant_id = s.ledger.create_fake_grant(TENANT_ID, s.spec)
    baseline = submission(s, 1)
    s.ledger.publish_fake_result(baseline, payload(baseline))
    subject = reserve(s)
    reserve(s, 2)
    return subject


def transport(c, path, monkeypatch):
    fixture = path / "canned.json"
    process = BoundedFakeProcess(
        (
            sys.executable,
            "-I",
            str(ROOT / "apps/agent-transport/tests/exchange_fixture.py"),
            str(ROOT / "apps/agent-transport/fake_transport.py"),
            str(fixture),
        )
    )
    original = process.exchange
    exchanges = []

    def exchange(raw, *, timeout):
        request = FakeProcessRequest.model_validate_json(raw)
        op = operation(c.setup)
        assert request.operation_id == op.id and op.state == "submitting"
        assert request.deadline <= min(op.deadline, op.lease_until)
        assert request.snapshot == c.setup.snapshots[0]
        with c.admin.begin() as db:
            db.execute(text("SELECT id FROM agent_admission_epoch FOR UPDATE NOWAIT"))
        body = json.dumps(candidate(request.snapshot, op.id)).encode()
        fixture.write_text(
            json.dumps(
                {
                    "request_sha256": hashlib.sha256(raw).hexdigest(),
                    "candidate_base64": base64.b64encode(body).decode(),
                }
            )
        )
        fixture.chmod(0o600)
        exchanges.append(request.submission_id)
        return original(raw, timeout=timeout)

    monkeypatch.setattr(process, "exchange", exchange)
    return process, exchanges


@pytest.mark.parametrize("already_claimed", [False, True])
def test_fourteen_journeys_restore_finishes_first_attempt_once_with_original_deadline(
    recovery_service,
    setup,
    tmp_path,
    monkeypatch,
    already_claimed,
):
    s = setup
    subject = current_fixture(s)
    claim = s.ledger.claim(TENANT_ID, ACTOR, subject.operation_id) if already_claimed else None
    with restored_database(
        s, recovery_service, tmp_path / "backup", owner_ledger=False
    ) as restored:
        reject_owner_runtime(monkeypatch)
        with rebound(restored) as c:
            original = operation(restored)
            assert recovery(c).recover() is None and operation(restored).state == "reserved"
            # Resume an existing valid fence, or claim an unclaimed reservation.
            claim = (
                c.commands.heartbeat("REQ-FAKE-0", claim)
                if claim
                else c.commands.claim("REQ-FAKE-0", receipt(original))
            )
            process, exchanges = transport(c, tmp_path, monkeypatch)
            custody = coordinator(c, claim, transport=process)
            assert custody.prepare() is None
            closed(coordinator(c, claim, transport=process).prepare)
            assert custody.dispatch() is None
            assert custody.publish() is None
            for action in (custody.prepare, custody.issue, custody.dispatch, custody.publish):
                closed(action)
            op = operation(restored)
            assert op.state == "published" and op.deadline == original.deadline
            assert op.snapshot == original.snapshot and op.created_at == original.created_at
            assert len(exchanges) == 1
            assert len(rows(restored, AgentAttempt)) == len(rows(restored, AgentComparison)) == 2
            assert balance(restored) == (3, 1, 10, 20, 0)
            assert c.commands.reserve("REQ-FAKE-0") == receipt(op)
            assert recovery(c).recover() is None and operation(restored).version == op.version
            assert_no_human_changes(restored)


@pytest.mark.parametrize("phase", ["checkpoint", "issued", "published", "quarantined"])
def test_fourteen_journeys_old_backup_cannot_erase_later_independent_custody(
    recovery_service,
    setup,
    tmp_path,
    monkeypatch,
    phase,
):
    s = setup
    baseline = submission(s, 1)
    s.ledger.publish_fake_result(baseline, payload(baseline))
    subject = reserve(s)
    reserve(s, 2)
    claim = s.ledger.claim(TENANT_ID, ACTOR, subject.operation_id)

    def after_backup():
        permit = s.ledger.begin_submission(TENANT_ID, ACTOR, claim)
        if phase in {"issued", "published"}:
            s.ledger.authorize_fake_io(permit)
        if phase == "published":
            s.ledger.publish_fake_result(permit, payload(permit))
        if phase == "quarantined":
            s.admission.journal.quarantine()

    with restored_database(
        s,
        recovery_service,
        tmp_path / "backup",
        after_backup=after_backup,
        owner_ledger=False,
    ) as restored:
        reject_owner_runtime(monkeypatch)
        with rebound(restored) as c:
            before, digest = balance(restored), receipt_digest(restored)
            closed(c.verifier.check)
            process, exchanges = transport(c, tmp_path, monkeypatch)
            fresh = coordinator(c, claim, transport=process)
            for action in (fresh.prepare, fresh.issue, fresh.dispatch, fresh.publish):
                closed(action)
            # Reservation/lease have no external I/O authority. Original exact
            # mapping may be read but never treated as a recovered issue permit.
            assert c.commands.reserve("REQ-FAKE-0").operation_id == subject.operation_id
            assert recovery(c).recover() is None
            assert operation(restored).state == "reserved"
            assert not exchanges and balance(restored) == before
            assert receipt_digest(restored) == digest
            assert_no_human_changes(restored)


@pytest.mark.parametrize(
    "fault",
    [
        "disabled",
        "wrong_epoch",
        "wrong_assignment",
        "wrong_login_name",
        "revoked",
        "expired_window",
        "missing_history",
        "closed_history",
        "orphan_history",
    ],
)
def test_restored_credential_binding_and_history_faults_hold_allowance(
    recovery_service,
    setup,
    tmp_path,
    monkeypatch,
    fault,
):
    s = setup
    baseline = submission(s, 1)
    s.ledger.publish_fake_result(baseline, payload(baseline))
    subject = reserve(s)
    s.ledger.claim(TENANT_ID, ACTOR, subject.operation_id)
    with restored_database(
        s, recovery_service, tmp_path / "backup", owner_ledger=False
    ) as restored:
        reject_owner_runtime(monkeypatch)
        with rebound(restored, enabled=fault != "disabled") as c:
            before, digest = balance(restored), receipt_digest(restored)
            if fault.endswith("history"):
                recovery_package.damage(
                    c,
                    {
                        "missing_history": "missing",
                        "closed_history": "closed",
                        "orphan_history": "forgotten",
                    }[fault],
                )
            else:
                statements = {
                    "disabled": f'UPDATE "{c.receipts}".principal SET enabled=false',
                    "wrong_epoch": (
                        f'UPDATE "{c.receipts}".principal SET epoch_id=gen_random_uuid()'
                    ),
                    "wrong_assignment": (
                        f'UPDATE "{c.receipts}".submission_scope SET actor_id=gen_random_uuid()'
                    ),
                    "wrong_login_name": (
                        f"UPDATE \"{c.receipts}\".principal SET login_name='unbound'"
                    ),
                    "revoked": f'REVOKE EXECUTE ON FUNCTION "{c.receipts}".'
                    "recover_verified_fake(text,uuid), "
                    f'"{c.receipts}".recover_submitted_fake(text,uuid) FROM "{c.receipt_login}"',
                    "expired_window": f'UPDATE "{c.receipts}".principal SET '
                    "starts_at=clock_timestamp()-interval '1 minute',"
                    "ends_at=clock_timestamp()-interval '1 second'",
                }
                with c.admin.begin() as db:
                    db.execute(text(statements[fault]))
            if fault.endswith("history"):
                assert recovery(c).recover() is None  # Status cannot refund reserved.
            else:
                closed(recovery(c).recover)
            assert balance(restored) == before and receipt_digest(restored) == digest
            assert operation(restored).state == "reserved"
            assert_no_human_changes(restored)


@pytest.mark.parametrize("submitted", [False, True])
def test_restricted_concurrent_status_after_encrypted_restore_settles_once(
    recovery_service,
    setup,
    tmp_path,
    monkeypatch,
    submitted,
):
    s = setup
    baseline = submission(s, 1)
    s.ledger.publish_fake_result(baseline, payload(baseline))
    if submitted:
        submission(s)
    else:
        reserve(s)
    with restored_database(
        s, recovery_service, tmp_path / "backup", owner_ledger=False
    ) as restored:
        reject_owner_runtime(monkeypatch)
        with rebound(restored) as c:
            before, digest = operation(restored), receipt_digest(restored)
            barrier = Barrier(2)

            def run():
                barrier.wait(timeout=5)
                return recovery(c).recover()

            with ThreadPoolExecutor(max_workers=2) as pool:
                assert list(pool.map(lambda _: run(), range(2))) == [None, None]
            op = operation(restored)
            assert op.state == ("unknown" if submitted else "expired")
            assert op.version == before.version + 1
            assert balance(restored) == (2, int(submitted), 0, 10, 10 if submitted else 0)
            assert receipt_digest(restored) == digest
            assert_no_human_changes(restored)


@pytest.mark.parametrize("principal", ["clinical", "custody"])
def test_recreated_same_name_login_cannot_inherit_restored_oid_authority(
    recovery_service,
    setup,
    tmp_path,
    monkeypatch,
    principal,
):
    s = setup
    subject = current_fixture(s)
    claim = s.ledger.claim(TENANT_ID, ACTOR, subject.operation_id)
    with restored_database(
        s,
        recovery_service,
        tmp_path / "backup",
        owner_ledger=False,
    ) as restored:
        reject_owner_runtime(monkeypatch)
        with rebound(restored) as c:
            runtime, login, namespace, signatures = (
                (c.runtime, c.login, c.capture, ("capture(text)",))
                if principal == "clinical"
                else (
                    c.observer_runtime,
                    c.receipt_login,
                    c.receipts,
                    (
                        "inventory_fake()",
                        *recovery_package.SIGNATURES,
                    ),
                )
            )
            runtime.dispose()
            with c.admin.begin() as db:
                raw = db.connection.driver_connection
                old_oid = raw.execute(
                    "SELECT oid FROM pg_roles WHERE rolname=%s",
                    (login,),
                ).fetchone()[0]
                raw.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(login)))
                raw.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(login)))
                raw.execute(
                    sql.SQL(
                        "CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE "
                        "NOREPLICATION NOBYPASSRLS PASSWORD {}"
                    ).format(sql.Identifier(login), sql.Literal(runtime.url.password))
                )
                new_oid = raw.execute(
                    "SELECT oid FROM pg_roles WHERE rolname=%s",
                    (login,),
                ).fetchone()[0]
                assert new_oid != old_oid
                raw.execute(
                    sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                        sql.Identifier(c.admin.url.database),
                        sql.Identifier(login),
                    )
                )
                raw.execute(
                    sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
                        sql.Identifier(namespace),
                        sql.Identifier(login),
                    )
                )
                for signature in signatures:
                    raw.execute(
                        sql.SQL("GRANT EXECUTE ON FUNCTION {}.{} TO {}").format(
                            sql.Identifier(namespace),
                            sql.SQL(signature),
                            sql.Identifier(login),
                        )
                    )
            before, digest = balance(restored), receipt_digest(restored)
            with runtime.connect() as db:
                assert db.scalar(text("SELECT session_user")) == login
            if principal == "custody":
                closed(recovery(c).recover)
                closed(c.verifier.check)
            else:
                # Fresh clinical capture denies the name-reused login. Status
                # recovery intentionally needs only the STILL-valid custody pin.
                closed(lambda: c.client.capture("REQ-FAKE-0"))
                assert recovery(c).recover() is None
            closed(coordinator(c, claim).prepare)
            assert balance(restored) == before and receipt_digest(restored) == digest
