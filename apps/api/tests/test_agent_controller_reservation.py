"""Actual restricted-login reservation commands in the opted-in disposable DB.

No provider submission, production install, local Docker or GCP resource use.
"""

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

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier
from uuid import uuid4

from psycopg import sql
from psycopg.types.json import Jsonb
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from test_agent_controller_capture import controller_database as controller_database
from test_agent_controller_capture import engine as engine
from test_agent_controller_capture import scope as scope
from test_agent_controller_capture import setup as setup
from test_agent_ledger import ACTOR, balance

from ciq_api.agent_contracts import AgentContractError
from ciq_api.agent_controller_reservation import ControllerReservation, FakeReservationApproval
from ciq_api.agent_ledger import FakeGrantSpec, OperationReceipt, operation_key
from ciq_api.agent_ledger_models import AgentExecutionGrant, AgentOperation
from ciq_api.mvp_models import SubmittedCase
from ciq_api.review_models import ReviewCase
from ciq_api.seed import PROFILES, TENANT_ID

PACKAGE = Path(__file__).resolve().parents[3] / "deploy/agent-controller/reservation.sql"


def stage(s, index=0, **changes):
    approval = FakeReservationApproval(
        epoch=s.setup.admission.journal.pin,
        grant_id=s.setup.grant_id,
        snapshot=s.setup.snapshots[index],
        config_digest=s.setup.spec.config_digest,
        source_digest=s.setup.spec.source_digest,
    ).staging_values()
    approval.update(changes)
    columns = ["login_oid", *approval]
    with s.admin.begin() as db:
        raw = db.connection.driver_connection
        oid = raw.execute("SELECT oid FROM pg_roles WHERE rolname=%s", (s.login,)).fetchone()[0]
        raw.execute(
            sql.SQL("INSERT INTO {}.reservation_scope ({}) VALUES ({})").format(
                sql.Identifier(s.capture),
                sql.SQL(", ").join(map(sql.Identifier, columns)),
                sql.SQL(", ").join(sql.Placeholder() for _ in columns),
            ),
            [oid, *(Jsonb(v) if type(v) is dict else v for v in approval.values())],
        )


@pytest.fixture
def commands(scope):
    s = scope
    with s.admin.begin() as db:
        raw = db.connection.driver_connection
        raw.execute(
            sql.SQL(PACKAGE.read_text()).format(
                owner=sql.Identifier(s.owner),
                capture=sql.Identifier(s.capture),
                product=sql.Identifier(s.product),
            )
        )
        for signature in ("reserve_fake(text, integer)", "lease_fake(text, uuid, integer, uuid)"):
            # Signature is a fixed trusted test constant, never a request value.
            raw.execute(
                sql.SQL("GRANT EXECUTE ON FUNCTION {}.{} TO {}").format(
                    sql.Identifier(s.capture), sql.SQL(signature), sql.Identifier(s.login)
                )
            )
        raw.execute(
            sql.SQL("UPDATE {}.principal SET request_ids=%s").format(sql.Identifier(s.capture)),
            ([f"REQ-FAKE-{i}" for i in range(3)],),
        )
    # Approval identity is immutable. Create a new fake grant at the real DB
    # test window; never rewrite the earlier owner-ledger fixture's approval.
    now = datetime.now(UTC)
    s.setup.spec = FakeGrantSpec.model_validate(
        {
            **s.setup.spec.model_dump(),
            "starts_at": now - timedelta(seconds=1),
            "ends_at": now + timedelta(minutes=10),
        }
    )
    s.setup.grant_id = s.setup.ledger.create_fake_grant(TENANT_ID, s.setup.spec)
    for index in range(3):
        stage(s, index, enabled=True)
    s.commands = ControllerReservation(s.runtime, schema=s.capture)
    return s


def reserve(s, index=0, **kwargs):
    return s.commands.reserve(f"REQ-FAKE-{index}", **kwargs)


def operation(s, receipt):
    with Session(s.admin) as db:
        return db.get(AgentOperation, (TENANT_ID, receipt.operation_id))


def mutate(s, statement, **params):
    with s.admin.begin() as db:
        db.execute(text(statement), params)


def new_approval(s, **changes):
    s.setup.spec = FakeGrantSpec.model_validate({**s.setup.spec.model_dump(), **changes})
    s.setup.grant_id = s.setup.ledger.create_fake_grant(TENANT_ID, s.setup.spec)
    mutate(s, f'DELETE FROM "{s.capture}".reservation_scope')
    for index in range(3):
        stage(s, index, enabled=True)


def transition(s, state):
    mutate(s, "UPDATE agent_operation SET state=:state, version=version+1", state=state)


def historical_reservation(s, **changes):
    now = datetime.now(UTC)
    op = AgentOperation(
        tenant_id=TENANT_ID,
        id=uuid4(),
        request_id="REQ-FAKE-0",
        actor_id=ACTOR,
        grant_id=s.setup.grant_id,
        operation_key=operation_key(
            s.setup.snapshots[0], s.setup.spec.config_digest, s.setup.spec.source_digest
        ),
        config_digest=s.setup.spec.config_digest,
        source_digest=s.setup.spec.source_digest,
        snapshot=s.setup.snapshots[0].model_dump(mode="json"),
        state="reserved",
        version=0,
        created_at=now,
        deadline=now + timedelta(seconds=120),
    )
    for name, value in changes.items():
        setattr(op, name, value)
    receipt = OperationReceipt(operation_id=op.id, state="reserved", version=0)
    with Session(s.admin) as db, db.begin():
        db.add(op)
        db.execute(
            text(
                "UPDATE agent_execution_grant SET admitted=1, in_flight=1, "
                "reserved_units=10 WHERE id=:id"
            ),
            {"id": s.setup.grant_id},
        )
    return receipt


def closed(call):
    with pytest.raises(AgentContractError, match=r"^reservation_unavailable$") as failure:
        call()
    assert failure.value.__suppress_context__


def test_owned_reserve_claim_heartbeat_and_minimal_committed_receipts(commands):
    s = commands
    receipt = reserve(s)
    assert receipt.state == "reserved" and receipt.version == 0
    assert balance(s.setup) == (1, 1, 10, 0, 0)
    original = operation(s, receipt)
    claim = s.commands.claim("REQ-FAKE-0", receipt)
    heart = s.commands.heartbeat("REQ-FAKE-0", claim)
    assert heart.version == 2 and heart.fence_id == claim.fence_id
    op = operation(s, receipt)
    assert op.deadline == original.deadline and op.created_at == original.created_at
    assert op.snapshot == s.setup.snapshots[0].model_dump(mode="json")
    assert op.actor_id == ACTOR and op.grant_id == s.setup.grant_id
    assert op.created_at < op.lease_until <= op.deadline
    assert set(heart.model_dump()) == {"operation_id", "version", "state", "fence_id"}
    with Session(s.admin) as db:
        assert db.get(ReviewCase, (TENANT_ID, "REQ-FAKE-0")).version == 0
        assert db.get(ReviewCase, (TENANT_ID, "REQ-FAKE-0")).final_payable_inr is None
        for table in ("agent_attempt", "agent_comparison", "review_audit", "review_outbox"):
            assert db.scalar(text(f"SELECT count(*) FROM {table}")) == 0


def test_concurrent_duplicates_hold_one_allowance_and_deadline(commands):
    s = commands
    barrier = Barrier(2)

    def run():
        barrier.wait(timeout=3)
        return reserve(s)

    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = list(pool.map(lambda _: run(), range(2)))
    assert a == b and balance(s.setup) == (1, 1, 10, 0, 0)
    before = operation(s, a)
    assert reserve(s, timeout_seconds=1) == a
    assert operation(s, a).deadline == before.deadline


def test_concurrent_different_cases_cannot_overbook_concurrency(commands):
    s = commands
    new_approval(s, concurrency_limit=1)
    barrier = Barrier(2)

    def run(index):
        barrier.wait(timeout=3)
        try:
            return reserve(s, index).state
        except AgentContractError:
            return "denied"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(run, range(2))) == ["denied", "reserved"]
    assert balance(s.setup) == (1, 1, 10, 0, 0)


@pytest.mark.parametrize(
    "change",
    [
        "enabled=false",
        "epoch_id='00000000-0000-0000-0000-000000000000'",
        "database_id='00000000-0000-0000-0000-000000000000'",
        "grant_id='00000000-0000-0000-0000-000000000000'",
        "config_digest=repeat('c',64)",
        "source_digest=repeat('c',64)",
        "operation_key=repeat('c',64)",
    ],
)
def test_approval_scope_cannot_be_widened_or_rebound(commands, change):
    s = commands
    mutate(s, f'UPDATE "{s.capture}".reservation_scope SET {change}')
    closed(lambda: reserve(s))
    assert balance(s.setup) == (0, 0, 0, 0, 0)


def test_no_approval_defaults_closed_and_runtime_cannot_enable_it(commands):
    s = commands
    mutate(s, f'DELETE FROM "{s.capture}".reservation_scope')
    stage(s)  # Trusted helper stages disabled, with no auto-enable.
    closed(lambda: reserve(s))
    with pytest.raises(DBAPIError) as failure, s.runtime.begin() as db:
        db.execute(text(f'UPDATE "{s.capture}".reservation_scope SET enabled=true'))
    assert failure.value.orig.sqlstate == "42501"
    assert balance(s.setup) == (0, 0, 0, 0, 0)


@pytest.mark.parametrize("change", ["revoked", "assigned", "final", "review", "facts", "policy"])
def test_fresh_clinical_changes_deny_before_accounting(commands, change):
    s = commands
    if change == "revoked":
        mutate(s, "UPDATE tenant_membership SET active=false WHERE role='medical_officer'")
    elif change == "assigned":
        mutate(s, "UPDATE review_case SET assignee_id=:a", a=PROFILES["processor"][0])
    elif change == "final":
        mutate(s, "UPDATE review_case SET state='APPROVED'")
    elif change == "review":
        mutate(s, "UPDATE review_case SET version=version+1")
    else:
        with Session(s.admin) as db, db.begin():
            case = db.get(SubmittedCase, (TENANT_ID, "REQ-FAKE-0"))
            if change == "facts":
                case.inputs = {**case.inputs, "member_reference": "changed"}
            else:
                case.record = {**case.record, "rules_digest": "0" * 64}
    closed(lambda: reserve(s))
    assert balance(s.setup) == (0, 0, 0, 0, 0)


@pytest.mark.parametrize("command", ["reserve", "claim", "heartbeat"])
def test_no_active_principal_cannot_use_any_write_command(commands, command):
    s = commands
    receipt = reserve(s)
    claim = s.commands.claim("REQ-FAKE-0", receipt)
    mutate(s, f'UPDATE "{s.capture}".principal SET enabled=false')
    calls = {
        "reserve": lambda: reserve(s),
        "claim": lambda: s.commands.claim("REQ-FAKE-0", receipt),
        "heartbeat": lambda: s.commands.heartbeat("REQ-FAKE-0", claim),
    }
    closed(calls[command])
    assert operation(s, receipt).version == 1 and balance(s.setup) == (1, 1, 10, 0, 0)


@pytest.mark.parametrize(
    "change",
    [
        "future",
        "expired",
        "admitted=case_limit",
        "in_flight=concurrency_limit, admitted=case_limit",
        "consumed_units=unit_limit",
        "uncertain_units=unit_limit",
        "reserved_units=unit_limit",
        "unapproved_key",
    ],
)
def test_window_and_all_accounting_limits_are_database_enforced(commands, change):
    s = commands
    now = datetime.now(UTC)
    if change == "future":
        new_approval(s, starts_at=now + timedelta(hours=1), ends_at=now + timedelta(hours=2))
    elif change == "expired":
        new_approval(s, starts_at=now - timedelta(hours=2), ends_at=now - timedelta(hours=1))
    elif change == "unapproved_key":
        new_approval(s, operation_keys=tuple(letter * 64 for letter in "cde"))
    else:
        mutate(s, f"UPDATE agent_execution_grant SET {change} WHERE id=:id", id=s.setup.grant_id)
    before = balance(s.setup)
    closed(lambda: reserve(s))
    assert balance(s.setup) == before


def test_approved_timeout_and_principal_window_bound_deadline(commands):
    s = commands
    mutate(s, f'UPDATE "{s.capture}".reservation_scope SET timeout_seconds=20')
    closed(lambda: reserve(s, timeout_seconds=21))
    mutate(
        s, f"UPDATE \"{s.capture}\".principal SET ends_at=clock_timestamp()+interval '5 seconds'"
    )
    receipt = reserve(s, timeout_seconds=20)
    op = operation(s, receipt)
    assert timedelta(seconds=0) < op.deadline - op.created_at < timedelta(seconds=6)


def test_new_grant_cannot_repurchase_or_rebind_existing_operation(commands):
    s = commands
    first = reserve(s)
    grant = s.setup.ledger.create_fake_grant(TENANT_ID, s.setup.spec)
    mutate(s, f'UPDATE "{s.capture}".reservation_scope SET grant_id=:g', g=grant)
    assert reserve(s) == first
    assert operation(s, first).grant_id == s.setup.grant_id
    closed(lambda: s.commands.claim("REQ-FAKE-0", first))
    with Session(s.admin) as db:
        other = db.get(AgentExecutionGrant, (TENANT_ID, grant))
        assert other.admitted == other.reserved_units == 0


def test_concurrent_claim_and_stale_version_fence_cannot_steal_active_lease(commands):
    s = commands
    receipt = reserve(s)
    barrier = Barrier(2)

    def claim():
        barrier.wait(timeout=3)
        try:
            return s.commands.claim("REQ-FAKE-0", receipt)
        except AgentContractError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: claim(), range(2)))
    winner = next(r for r in results if r)
    assert sum(r is not None for r in results) == 1
    closed(lambda: s.commands.claim("REQ-FAKE-0", winner))
    forged = winner.model_copy(update={"fence_id": uuid4()})
    closed(lambda: s.commands.heartbeat("REQ-FAKE-0", forged))
    current = s.commands.heartbeat("REQ-FAKE-0", winner)
    closed(lambda: s.commands.heartbeat("REQ-FAKE-0", winner))
    assert operation(s, receipt).version == current.version == 2


def test_expired_lease_reclaim_keeps_original_deadline_and_fences_previous_owner(commands):
    s = commands
    receipt = reserve(s)
    first = s.commands.claim("REQ-FAKE-0", receipt)
    original = operation(s, receipt)
    mutate(
        s,
        "UPDATE agent_operation SET lease_until=clock_timestamp()-interval '1 second', "
        "version=version+1",
    )
    expired = first.model_copy(update={"version": first.version + 1})
    closed(lambda: s.commands.heartbeat("REQ-FAKE-0", first))
    second = s.commands.claim("REQ-FAKE-0", expired)
    assert second.fence_id != first.fence_id and second.version == expired.version + 1
    closed(lambda: s.commands.heartbeat("REQ-FAKE-0", first))
    assert operation(s, receipt).deadline == original.deadline
    assert balance(s.setup) == (1, 1, 10, 0, 0)


@pytest.mark.parametrize("state", ["submitting", "unknown", "published", "expired"])
def test_lease_command_never_changes_submitted_or_terminal_operations(commands, state):
    s = commands
    receipt = reserve(s)
    if state != "expired":
        transition(s, "submitting")
    if state != "submitting":
        transition(s, state)
    receipt = receipt.model_copy(update={"version": operation(s, receipt).version})
    closed(lambda: s.commands.claim("REQ-FAKE-0", receipt))
    assert operation(s, receipt).state == state and balance(s.setup) == (1, 1, 10, 0, 0)


@pytest.mark.parametrize("field", ["request", "operation", "actor", "snapshot", "deadline"])
def test_no_cross_case_owner_stale_snapshot_or_expired_claim(commands, field):
    s = commands
    now = datetime.now(UTC)
    changes = {
        "actor": {"actor_id": PROFILES["processor"][0]},
        "snapshot": {"snapshot": {}},
        "deadline": {
            "created_at": now - timedelta(seconds=200),
            "deadline": now - timedelta(seconds=100),
        },
    }.get(field)
    receipt = historical_reservation(s, **changes) if changes else reserve(s)
    if field == "request":
        closed(lambda: s.commands.claim("REQ-FAKE-1", receipt))
    elif field == "operation":
        closed(
            lambda: s.commands.claim(
                "REQ-FAKE-0", OperationReceipt(operation_id=uuid4(), state="reserved", version=0)
            )
        )
    else:
        closed(lambda: s.commands.claim("REQ-FAKE-0", receipt))
    assert balance(s.setup) == (1, 1, 10, 0, 0)


@pytest.mark.parametrize("state", ["reserved", "unknown", "published"])
def test_mapping_fence_prevents_a_new_approved_key(commands, state):
    s = commands
    first = reserve(s)
    if state != "reserved":
        transition(s, "submitting")
        transition(s, state)
    # Create distinct operator approval, without mutating existing receipt pins.
    new_approval(
        s,
        config_digest="c" * 64,
        operation_keys=tuple(
            operation_key(snapshot, "c" * 64, s.setup.spec.source_digest)
            for snapshot in s.setup.snapshots
        ),
    )
    closed(lambda: reserve(s))
    assert operation(s, first).state == state
    assert balance(s.setup) == (0, 0, 0, 0, 0)


def test_direct_accounting_resets_helper_reads_and_execution_tables_denied(commands):
    s = commands
    targets = [
        f'UPDATE "{s.product}".agent_execution_grant SET reserved_units=0, admitted=0',
        f"UPDATE \"{s.product}\".agent_operation SET state='expired'",
        f'SELECT * FROM "{s.product}".agent_operation',
        f'SELECT * FROM "{s.capture}".reservation_scope',
        f"SELECT \"{s.capture}\"._reservation_context('REQ-FAKE-0')",
        f'INSERT INTO "{s.product}".agent_attempt DEFAULT VALUES',
        f'INSERT INTO "{s.product}".agent_comparison DEFAULT VALUES',
        f'DELETE FROM "{s.capture}".reservation_scope',
    ]
    for statement in targets:
        with pytest.raises(DBAPIError) as failure, s.runtime.begin() as db:
            db.execute(text(statement))
        assert failure.value.orig.sqlstate == "42501"


def test_definer_has_no_refund_settlement_attempt_publication_or_approval_privileges(commands):
    s = commands
    with s.admin.begin() as db:
        raw = db.connection.driver_connection
        for table, column in [
            ("agent_execution_grant", "consumed_units"),
            ("agent_execution_grant", "uncertain_units"),
            ("agent_execution_grant", "case_limit"),
            ("agent_operation", "state"),
            ("agent_operation", "deadline"),
            ("agent_operation", "snapshot"),
        ]:
            assert raw.execute(
                "SELECT has_column_privilege(%s,%s,%s,'UPDATE')",
                (s.owner, f"{s.product}.{table}", column),
            ).fetchone() == (False,)
        for table in ["agent_attempt", "agent_comparison", "agent_execution_grant"]:
            assert raw.execute(
                "SELECT has_table_privilege(%s,%s,'INSERT,DELETE,TRUNCATE')",
                (s.owner, f"{s.product}.{table}"),
            ).fetchone() == (False,)
        assert raw.execute(
            "SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace, "
            "LATERAL aclexplode(p.proacl) a WHERE n.nspname=%s AND a.grantee=0",
            (s.capture,),
        ).fetchone() == (0,)
        granted = raw.execute(
            "SELECT p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
            "WHERE n.nspname=%s AND has_function_privilege(%s,p.oid,'EXECUTE') ORDER BY 1",
            (s.capture, s.login),
        ).fetchall()
        assert granted == [("capture",), ("lease_fake",), ("reserve_fake",)]
        assert raw.execute(
            "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname IN (%s,%s) AND c.relkind IN ('r','p','v','m') AND "
            "(has_table_privilege(%s,c.oid,"
            "'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN') "
            "OR has_any_column_privilege(%s,c.oid,'SELECT,INSERT,UPDATE,REFERENCES'))",
            (s.product, s.capture, s.login, s.login),
        ).fetchone() == (0,)
        functions = raw.execute(
            "SELECT p.prosecdef, p.proconfig, r.rolname FROM pg_proc p "
            "JOIN pg_namespace n ON n.oid=p.pronamespace JOIN pg_roles r ON r.oid=p.proowner "
            "WHERE n.nspname=%s",
            (s.capture,),
        ).fetchall()
        assert len(functions) == 4 and all(
            row
            == (
                True,
                ["search_path=pg_catalog, pg_temp", "row_security=on", "lock_timeout=2s"],
                s.owner,
            )
            for row in functions
        )


def test_failed_accounting_rolls_back_insert_and_leaves_allowance(commands):
    s = commands
    with s.admin.begin() as db:
        raw = db.connection.driver_connection
        raw.execute(
            sql.SQL("REVOKE UPDATE(admitted) ON {}.agent_execution_grant FROM {}").format(
                sql.Identifier(s.product), sql.Identifier(s.owner)
            )
        )
    closed(lambda: reserve(s))
    assert balance(s.setup) == (0, 0, 0, 0, 0)
    with s.admin.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM agent_operation")) == 0


@pytest.mark.parametrize("phase", ["reserve", "claim", "heartbeat"])
def test_window_rechecked_after_waiting_for_allowance_lock(commands, phase):
    s = commands
    receipt = reserve(s) if phase != "reserve" else None
    claim = s.commands.claim("REQ-FAKE-0", receipt) if phase == "heartbeat" else None
    mutate(
        s,
        f'UPDATE "{s.capture}".principal SET '
        "ends_at=clock_timestamp()+interval '400 milliseconds'",
    )
    calls = {
        "reserve": lambda: reserve(s),
        "claim": lambda: s.commands.claim("REQ-FAKE-0", receipt),
        "heartbeat": lambda: s.commands.heartbeat("REQ-FAKE-0", claim),
    }
    with s.admin.begin() as admin, ThreadPoolExecutor(max_workers=1) as pool:
        admin.execute(text("SELECT id FROM agent_execution_grant FOR UPDATE"))
        future = pool.submit(calls[phase])
        time.sleep(0.65)
        admin.commit()
        closed(lambda: future.result(timeout=4))
    assert balance(s.setup) == ((0, 0, 0, 0, 0) if phase == "reserve" else (1, 1, 10, 0, 0))
