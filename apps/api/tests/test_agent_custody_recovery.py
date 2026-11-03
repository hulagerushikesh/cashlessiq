"""Actual restricted recovery logins; disposable Linux CI only."""

import os
import sys

import pytest

if (
    sys.platform != "linux"
    or os.environ.get("GITHUB_ACTIONS") != "true"
    or os.environ.get("GITHUB_REPOSITORY") != "hulagerushikesh/cashlessiq"
    or os.environ.get("CIQ_AGENT_CONTROLLER_TEST") != "1"
):
    pytest.skip("Dedicated disposable controller privilege job required", allow_module_level=True)

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier
from uuid import uuid4

from psycopg import sql
from sqlalchemy import event, text
from sqlalchemy.exc import DBAPIError
from test_agent_controller_capture import controller_database as controller_database
from test_agent_controller_capture import engine as engine
from test_agent_controller_capture import scope as scope
from test_agent_controller_capture import setup as setup
from test_agent_controller_reservation import commands as commands
from test_agent_controller_reservation import historical_reservation, mutate
from test_agent_custody_dispatch import dispatch as dispatch
from test_agent_custody_publication import publication as publication
from test_agent_custody_publication import ready
from test_agent_custody_submission import coordinator, rows
from test_agent_custody_submission import custody as custody
from test_agent_ledger import ACTOR, balance
from test_agent_receipt_verifier import closed
from test_agent_receipt_verifier import observer as observer

from ciq_api.agent_admission import FakeCheckpoint
from ciq_api.agent_custody_recovery import FakeCustodyRecovery
from ciq_api.seed import TENANT_ID

ROOT = Path(__file__).resolve().parents[3] / "deploy/agent-controller"
SIGNATURES = ("recover_submitted_fake(text, uuid)", "recover_verified_fake(text, uuid)")


def install(s):
    with s.admin.begin() as db:
        raw = db.connection.driver_connection
        raw.execute(
            sql.SQL((ROOT / "custody-recovery.sql").read_text()).format(
                owner=sql.Identifier(s.receipt_owner),
                receipts=sql.Identifier(s.receipts),
                product=sql.Identifier(s.product),
            )
        )
        for signature in SIGNATURES:
            raw.execute(
                sql.SQL("GRANT EXECUTE ON FUNCTION {}.{} TO {}").format(
                    sql.Identifier(s.receipts),
                    sql.SQL(signature),
                    sql.Identifier(s.receipt_login),
                )
            )
    s.recovery = recovery(s)
    return s


def recovery(s, **changes):
    return FakeCustodyRecovery(
        s.observer_runtime,
        s.setup.admission.journal,
        **{
            "schema": s.receipts,
            "request_id": "REQ-FAKE-0",
            "operation_id": s.claim.operation_id,
            **changes,
        },
    )


@pytest.fixture
def recovered(publication):
    return install(publication)


@pytest.fixture
def unsubmitted(commands, observer):
    s = commands
    assert s is observer
    # Valid historical INSERT, never change immutable operation/grant identity,
    # disable triggers or supply a fake wall clock to the recovery command.
    now = datetime.now(UTC)
    s.claim = historical_reservation(
        s,
        created_at=now - timedelta(seconds=120),
        deadline=now - timedelta(seconds=1),
    )
    with s.admin.begin() as db:
        raw = db.connection.driver_connection
        raw.execute(
            sql.SQL((ROOT / "custody-submission.sql").read_text()).format(
                owner=sql.Identifier(s.receipt_owner),
                receipts=sql.Identifier(s.receipts),
                product=sql.Identifier(s.product),
                capture=sql.Identifier(s.capture),
            )
        )
        raw.execute(
            sql.SQL((ROOT / "custody-publication.sql").read_text()).format(
                owner=sql.Identifier(s.receipt_owner),
                receipts=sql.Identifier(s.receipts),
                product=sql.Identifier(s.product),
            )
        )
        raw.execute(
            sql.SQL(
                "INSERT INTO {}.submission_scope SELECT custody.oid,%s,controller.oid,"
                "controller.rolname,%s,%s,%s,true FROM pg_roles custody, pg_roles controller "
                "WHERE custody.rolname=%s AND controller.rolname=%s"
            ).format(sql.Identifier(s.receipts)),
            (
                "REQ-FAKE-0",
                TENANT_ID,
                ACTOR,
                s.claim.operation_id,
                s.receipt_login,
                s.login,
            ),
        )
    return install(s)


def expire_lease(s):
    mutate(
        s,
        "UPDATE agent_operation SET lease_until=clock_timestamp()-interval '1 second',"
        "version=version+1",
    )


def damage(s, fault):
    journal = s.setup.admission.journal
    if fault == "missing":
        journal.path.unlink()
    elif fault == "closed":
        journal.quarantine()
    elif fault == "forgotten":
        journal.prepare(
            FakeCheckpoint(
                tenant_id=uuid4(),
                request_id="FORGOTTEN-OTHER-TENANT",
                operation_id=uuid4(),
                submission_id=uuid4(),
                digest="d" * 64,
            )
        )
    elif fault == "malformed":
        journal.path.write_bytes(b"not a journal")
    elif fault == "observer_denied":
        with s.admin.begin() as db:
            db.connection.driver_connection.execute(
                sql.SQL("REVOKE EXECUTE ON FUNCTION {}.inventory_fake() FROM {}").format(
                    sql.Identifier(s.receipts), sql.Identifier(s.receipt_login)
                )
            )


@pytest.mark.parametrize(
    "fault", ["ok", "missing", "closed", "forgotten", "malformed", "observer_denied"]
)
@pytest.mark.parametrize("phase", ["prepared", "issued"])
def test_submitted_expiry_keeps_slot_and_uncertain_units_even_without_custody(
    recovered, fault, phase
):
    s = recovered
    if phase == "prepared":
        s.custody.prepare()
    else:
        ready(s)
    expire_lease(s)
    before, attempts = rows(s)
    damage(s, fault)
    assert s.recovery.recover() is None
    op, after = rows(s)
    assert op.state == "unknown" and op.version == before.version + 1
    assert op.deadline == before.deadline and op.fence_id == before.fence_id
    assert op.lease_until == before.lease_until and after[0].id == attempts[0].id
    assert balance(s.setup) == (1, 1, 0, 0, 10)
    # Fresh instances are allowed status checks only; no issue reconstruction.
    assert recovery(s).recover() is None
    assert rows(s)[0].version == op.version and balance(s.setup) == (1, 1, 0, 0, 10)
    closed(coordinator(s, transport=s.transport).dispatch)
    closed(s.custody.publish)
    assert len(s.exchanges) == (phase == "issued")


@pytest.mark.parametrize(
    "fault", ["ok", "missing", "closed", "forgotten", "malformed", "observer_denied"]
)
def test_unused_reservation_refund_requires_available_agreeing_full_epoch_history(
    unsubmitted, fault
):
    s = unsubmitted
    before = rows(s)[0]
    damage(s, fault)
    assert s.recovery.recover() is None
    op, attempts = rows(s)
    verified = fault == "ok"
    assert op.state == ("expired" if verified else "reserved")
    assert op.version == before.version + int(verified) and op.deadline == before.deadline
    assert balance(s.setup) == (1, 0 if verified else 1, 0 if verified else 10, 0, 0)
    assert not attempts
    assert recovery(s).recover() is None
    assert rows(s)[0].version == op.version


def test_status_only_command_cannot_refund_even_when_history_is_healthy(unsubmitted):
    s = unsubmitted
    with s.observer_runtime.begin() as db:
        db.scalar(
            text(f'SELECT "{s.receipts}".recover_submitted_fake(:request,:operation)'),
            {
                "request": "REQ-FAKE-0",
                "operation": s.claim.operation_id,
            },
        )
    assert rows(s)[0].state == "reserved" and balance(s.setup) == (1, 1, 10, 0, 0)


@pytest.mark.parametrize("phase", ["reserved", "prepared", "published"])
def test_live_or_final_work_has_no_recovery_transition(recovered, phase):
    s = recovered
    if phase == "prepared":
        s.custody.prepare()
    elif phase == "published":
        ready(s)
        s.custody.publish()
    before = rows(s)[0]
    before_balance = balance(s.setup)
    assert s.recovery.recover() is None
    assert rows(s)[0].state == before.state and rows(s)[0].version == before.version
    assert balance(s.setup) == before_balance


@pytest.mark.parametrize("fault", ["clinical_disabled", "revoked", "final_review", "stale_facts"])
def test_status_recovery_requires_no_current_clinical_capability(recovered, fault):
    s = recovered
    s.custody.prepare()
    expire_lease(s)
    statements = {
        "clinical_disabled": f'UPDATE "{s.capture}".principal SET enabled=false',
        "revoked": "UPDATE tenant_membership SET active=false",
        "final_review": "UPDATE review_case SET state='APPROVED',version=version+1",
        "stale_facts": (
            'UPDATE submitted_case SET inputs=inputs || \'{"member_reference":"stale"}\''
        ),
    }
    mutate(s, statements[fault])
    # Lock ALL clinical rows from an independent operator transaction. Recovery
    # must still complete without waiting for or capturing any clinical row.
    with s.admin.begin() as db:
        for table in ("submitted_case", "review_case", "tenant_membership", "policy_version"):
            db.execute(text(f"SELECT * FROM {table} FOR UPDATE"))
        assert s.recovery.recover() is None
    assert rows(s)[0].state == "unknown" and balance(s.setup) == (1, 1, 0, 0, 10)


@pytest.mark.parametrize(
    "fault",
    [
        "assignment",
        "principal",
        "expired",
        "wrong_actor",
        "wrong_tenant",
        "wrong_request",
        "wrong_op",
    ],
)
def test_recovery_still_authenticates_exact_current_custody_assignment(recovered, fault):
    s = recovered
    s.custody.prepare()
    expire_lease(s)
    statements = {
        "assignment": f'UPDATE "{s.receipts}".submission_scope SET enabled=false',
        "principal": f'UPDATE "{s.receipts}".principal SET enabled=false',
        "expired": f'UPDATE "{s.receipts}".principal SET '
        "starts_at=clock_timestamp()-interval '1 minute',"
        "ends_at=clock_timestamp()-interval '1 second'",
        "wrong_actor": f'UPDATE "{s.receipts}".submission_scope SET actor_id=gen_random_uuid()',
        "wrong_tenant": f'UPDATE "{s.receipts}".submission_scope SET tenant_id=gen_random_uuid()',
    }
    if fault in statements:
        mutate(s, statements[fault])
        command = s.recovery
    else:
        command = recovery(
            s,
            **(
                {"request_id": "REQ-FAKE-1"}
                if fault == "wrong_request"
                else {"operation_id": uuid4()}
            ),
        )
    closed(command.recover)
    assert rows(s)[0].state == "submitting" and balance(s.setup) == (1, 1, 10, 0, 0)


@pytest.mark.parametrize("fixture", ["recovered", "unsubmitted"])
def test_concurrent_recovery_settles_exactly_once(request, fixture):
    s = request.getfixturevalue(fixture)
    submitted = fixture == "recovered"
    if submitted:
        s.custody.prepare()
        expire_lease(s)
    before = rows(s)[0]
    barrier = Barrier(2)

    def run(_):
        barrier.wait(timeout=3)
        return recovery(s).recover()

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(run, range(2))) == [None, None]
    assert rows(s)[0].version == before.version + 1
    assert balance(s.setup) == ((1, 1, 0, 0, 10) if submitted else (1, 0, 0, 0, 0))


@pytest.mark.parametrize("fixture", ["recovered", "unsubmitted"])
def test_recovery_commit_failure_rolls_back_without_journal_mutation(request, fixture):
    s = request.getfixturevalue(fixture)
    if fixture == "recovered":
        s.custody.prepare()
        expire_lease(s)
    before = rows(s)[0]
    journal = s.setup.admission.journal.path.read_bytes()

    def fail(connection):
        raise DBAPIError("private commit", {}, ValueError("private"))

    event.listen(s.observer_runtime, "commit", fail)
    try:
        closed(s.recovery.recover)
    finally:
        event.remove(s.observer_runtime, "commit", fail)
    assert rows(s)[0].version == before.version and rows(s)[0].state == before.state
    assert balance(s.setup) == (1, 1, 10, 0, 0)
    assert s.setup.admission.journal.path.read_bytes() == journal
    assert recovery(s).recover() is None


def test_recovery_acl_no_direct_tables_private_flag_or_human_writes(recovered):
    s = recovered
    with s.admin.connect() as db:
        raw = db.connection.driver_connection
        assert not raw.execute(
            "SELECT has_function_privilege(%s,%s,'EXECUTE')",
            (
                s.receipt_login,
                f"{s.receipts}._recover_fake(text,uuid,boolean)",
            ),
        ).fetchone()[0]
        for table in (
            "agent_execution_grant",
            "agent_operation",
            "agent_attempt",
            "agent_comparison",
        ):
            assert not raw.execute(
                "SELECT has_any_column_privilege(%s,%s,'SELECT,UPDATE,INSERT')",
                (
                    s.receipt_login,
                    f"{s.product}.{table}",
                ),
            ).fetchone()[0]
        for table in (
            "review_case",
            "review_audit",
            "review_outbox",
            "mvp_event",
            "analytics_event",
        ):
            assert not raw.execute(
                "SELECT has_table_privilege(%s,%s,'INSERT,UPDATE,DELETE')",
                (
                    s.receipt_owner,
                    f"{s.product}.{table}",
                ),
            ).fetchone()[0]
        assert raw.execute(
            "SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace, "
            "LATERAL aclexplode(p.proacl) a WHERE n.nspname=%s AND a.grantee=0",
            (s.receipts,),
        ).fetchone() == (0,)


def test_clinical_login_denied_even_after_accidental_recovery_execute_grants(recovered):
    s = recovered
    s.custody.prepare()
    expire_lease(s)
    with s.admin.begin() as db:
        raw = db.connection.driver_connection
        raw.execute(
            sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
                sql.Identifier(s.receipts),
                sql.Identifier(s.login),
            )
        )
        for signature in SIGNATURES:
            raw.execute(
                sql.SQL("GRANT EXECUTE ON FUNCTION {}.{} TO {}").format(
                    sql.Identifier(s.receipts),
                    sql.SQL(signature),
                    sql.Identifier(s.login),
                )
            )
    for name in ("recover_submitted_fake", "recover_verified_fake"):
        with pytest.raises(DBAPIError) as error, s.runtime.begin() as db:
            db.scalar(
                text(f'SELECT "{s.receipts}".{name}(:request,:operation)'),
                {
                    "request": "REQ-FAKE-0",
                    "operation": s.claim.operation_id,
                },
            )
        assert error.value.orig.sqlstate == "42501"
    assert s.recovery.recover() is None
    assert balance(s.setup) == (1, 1, 0, 0, 10)
