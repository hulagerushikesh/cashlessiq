"""Actual receipt-observer logins in the guarded disposable PostgreSQL CI only."""

import os
import sys

import pytest

if (
    sys.platform != 'linux'
    or os.environ.get('GITHUB_ACTIONS') != 'true'
    or os.environ.get('GITHUB_REPOSITORY') != 'hulagerushikesh/cashlessiq'
    or os.environ.get('CIQ_AGENT_CONTROLLER_TEST') != '1'
):
    pytest.skip('Dedicated disposable controller privilege job required', allow_module_level=True)

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from psycopg import sql
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from test_agent_controller_capture import controller_database as controller_database
from test_agent_controller_capture import engine as engine
from test_agent_controller_capture import scope as scope
from test_agent_controller_capture import setup as setup
from test_agent_ledger import ACTOR, balance, payload, reserve, submission

from ciq_api.agent_admission import (
    ERROR,
    FakeCheckpoint,
    FakeEpochPin,
    FakeReceiptJournal,
    checkpoint,
)
from ciq_api.agent_contracts import AgentContractError
from ciq_api.agent_ledger_models import AgentAttempt, AgentOperation
from ciq_api.agent_receipt_verifier import FakeReceiptVerifier
from ciq_api.seed import TENANT_ID

PACKAGE = Path(__file__).resolve().parents[3] / 'deploy/agent-controller/receipt-observer.sql'


@pytest.fixture
def observer(scope):
    s = scope
    suffix = uuid4().hex[:24]
    s.receipt_owner = 'ciq_receipt_owner_' + suffix
    s.receipt_login = 'ciq_receipt_login_' + suffix
    s.receipts = 'ciq_agent_receipts_' + suffix
    password = uuid4().hex
    runtime = None
    try:
        with s.admin.begin() as db:
            raw = db.connection.driver_connection
            raw.execute(sql.SQL(PACKAGE.read_text()).format(
                owner=sql.Identifier(s.receipt_owner), receipts=sql.Identifier(s.receipts),
                product=sql.Identifier(s.product),
            ))
            raw.execute(sql.SQL(
                'CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE '
                'NOREPLICATION NOBYPASSRLS PASSWORD {}'
            ).format(sql.Identifier(s.receipt_login), sql.Literal(password)))
            raw.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}').format(
                sql.Identifier(s.admin.url.database), sql.Identifier(s.receipt_login)
            ))
            raw.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO {}').format(
                sql.Identifier(s.receipts), sql.Identifier(s.receipt_login)
            ))
            raw.execute(sql.SQL('GRANT EXECUTE ON FUNCTION {}.inventory_fake() TO {}').format(
                sql.Identifier(s.receipts), sql.Identifier(s.receipt_login)
            ))
            pin = s.setup.admission.journal.pin
            now = datetime.now(UTC)
            raw.execute(sql.SQL(
                'INSERT INTO {}.principal SELECT oid,rolname,%s,%s,%s,%s,true '
                'FROM pg_roles WHERE rolname=%s'
            ).format(sql.Identifier(s.receipts)), (
                pin.database_id, pin.epoch_id, now, now + timedelta(minutes=5), s.receipt_login,
            ))
        runtime = create_engine(
            s.admin.url.set(username=s.receipt_login, password=password),
            connect_args={
                'options': '-cstatement_timeout=5000 -cidle_in_transaction_session_timeout=10000'
            },
        )
        s.observer_runtime = runtime
        s.verifier = FakeReceiptVerifier(runtime, s.setup.admission.journal, schema=s.receipts)
        yield s
    finally:
        if runtime:
            runtime.dispose()
        with s.admin.begin() as db:
            raw = db.connection.driver_connection
            raw.execute(sql.SQL('DROP SCHEMA IF EXISTS {} CASCADE').format(
                sql.Identifier(s.receipts)
            ))
            for role in (s.receipt_login, s.receipt_owner):
                if raw.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (role,)).fetchone():
                    raw.execute(sql.SQL('DROP OWNED BY {}').format(sql.Identifier(role)))
                    raw.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(role)))


def closed(call):
    with pytest.raises(AgentContractError, match=f'^{ERROR}$') as caught:
        call()
    assert caught.value.__suppress_context__


def mutate(s, statement, params=None):
    with s.admin.begin() as db:
        db.execute(text(statement), params or {})


def inventory(s):
    with s.observer_runtime.begin() as db:
        return db.scalar(text(f'SELECT "{s.receipts}".inventory_fake()'))


@pytest.mark.parametrize(
    'phase', ['empty', 'reserved', 'prepared', 'issued', 'published', 'unknown']
)
def test_actual_login_matches_shared_checkpoint_and_retained_history(observer, phase):
    s = observer
    permit = None
    if phase == 'reserved':
        reserve(s.setup)
    elif phase not in {'empty', 'reserved'}:
        permit = submission(s.setup)
        if phase == 'issued':
            s.setup.ledger.authorize_fake_io(permit)
        elif phase == 'published':
            s.setup.ledger.publish_fake_result(permit, payload(permit))
        elif phase == 'unknown':
            s.setup.clock[0] += timedelta(seconds=121)
            s.setup.ledger.recover_expired(TENANT_ID, permit.operation_id)
    before = balance(s.setup)
    assert s.verifier.check() is None
    raw = inventory(s)
    assert len(raw['entries']) == (1 if permit else 0)
    if permit:
        with Session(s.admin) as db:
            expected = checkpoint(db, db.get(AgentAttempt, (TENANT_ID, permit.attempt_id)))
        # The separate restricted connection's projection hashes identically.
        from ciq_api.agent_admission import checkpoint_from_material
        from ciq_api.agent_receipt_verifier import _Material
        material = _Material.model_validate(raw['entries'][0])
        assert checkpoint_from_material(
            material.operation, material.grant, material.attempt
        ) == expected
        assert set(raw['entries'][0]) == {'operation', 'grant', 'attempt'}
        assert 'candidate' not in str(raw) and 'record' not in str(raw)
    assert balance(s.setup) == before


@pytest.mark.parametrize('fault', [
    'disabled', 'future', 'expired', 'wrong_oid', 'wrong_name', 'database_id', 'epoch_id',
    'inherit', 'createdb', 'createrole', 'replication', 'bypassrls', 'membership',
])
def test_binding_and_role_properties_fail_closed(observer, fault):
    s = observer
    if fault in {'disabled', 'future', 'expired', 'wrong_oid', 'wrong_name',
                 'database_id', 'epoch_id'}:
        expression = {
            'disabled': 'enabled=false',
            'future': "starts_at=clock_timestamp()+interval '1 minute'",
            'expired': "starts_at=clock_timestamp()-interval '2 minutes', "
                       "ends_at=clock_timestamp()-interval '1 minute'",
            'wrong_oid': 'login_oid=0', 'wrong_name': "login_name='not_the_login'",
            'database_id': 'database_id=gen_random_uuid()',
            'epoch_id': 'epoch_id=gen_random_uuid()',
        }[fault]
        mutate(s, f'UPDATE "{s.receipts}".principal SET {expression}')
    else:
        with s.admin.begin() as db:
            raw = db.connection.driver_connection
            if fault == 'membership':
                raw.execute(sql.SQL('GRANT {} TO {}').format(
                    sql.Identifier(s.owner), sql.Identifier(s.receipt_login)
                ))
            else:
                raw.execute(sql.SQL('ALTER ROLE {} {}').format(
                    sql.Identifier(s.receipt_login), sql.SQL(fault.upper())
                ))
    closed(s.verifier.check)


@pytest.mark.parametrize('state', ['prepared', 'issued', 'closed', 'missing'])
def test_external_history_cannot_be_supplied_hidden_or_reset_by_caller(observer, state):
    s = observer
    journal = s.setup.admission.journal
    receipt = FakeCheckpoint(
        tenant_id=TENANT_ID, request_id='REQ-FORGOTTEN', operation_id=uuid4(),
        submission_id=uuid4(), digest='d' * 64,
    )
    journal.prepare(receipt)  # independently retained work missing from local DB
    if state == 'issued':
        journal.issue(receipt)
    elif state == 'closed':
        journal.quarantine()
    elif state == 'missing':
        journal.path.unlink()
    closed(s.verifier.check)
    assert balance(s.setup) == (0, 0, 0, 0, 0)
    assert inventory(s)['entries'] == []


def test_local_attempt_without_external_receipt_is_denied(observer, tmp_path):
    s = observer
    submission(s.setup)
    journal = FakeReceiptJournal.provision(tmp_path / 'other', s.setup.admission.journal.pin)
    verifier = FakeReceiptVerifier(s.observer_runtime, journal, schema=s.receipts)
    closed(verifier.check)
    assert balance(s.setup) == (1, 1, 10, 0, 0)


def test_changed_external_identity_is_denied_even_when_inventory_empty(observer):
    s = observer
    pin = FakeEpochPin(database_id=uuid4(), epoch_id=s.setup.admission.journal.pin.epoch_id)
    wrong = FakeReceiptJournal(s.setup.admission.journal.directory, pin)
    closed(FakeReceiptVerifier(s.observer_runtime, wrong, schema=s.receipts).check)


def test_prepare_commit_local_rollback_is_observed_independently(observer, monkeypatch):
    s = observer
    receipt = reserve(s.setup)
    claim = s.setup.ledger.claim(TENANT_ID, ACTOR, receipt.operation_id)
    original = s.setup.admission.prepare

    def crash(db, attempt):
        original(db, attempt)
        raise RuntimeError('fake cross-store crash')

    monkeypatch.setattr(s.setup.admission, 'prepare', crash)
    with pytest.raises(RuntimeError, match='cross-store'):
        s.setup.ledger.begin_submission(TENANT_ID, ACTOR, claim)
    closed(s.verifier.check)
    assert inventory(s)['entries'] == []
    assert balance(s.setup) == (1, 1, 10, 0, 0)


def test_history_check_needs_no_fresh_clinical_read_or_user_right(observer):
    s = observer
    submission(s.setup)
    mutate(s, 'UPDATE tenant_membership SET active=false WHERE user_id=:actor', {'actor': ACTOR})
    # Custody authority reads immutable history, not current clinical permission.
    assert s.verifier.check() is None


def test_timezone_and_search_path_cannot_change_checkpoint_digest(observer):
    s = observer
    submission(s.setup)
    with s.observer_runtime.begin() as db:
        db.execute(text("SET TIME ZONE 'Asia/Kolkata'"))
        db.execute(text('SET search_path=pg_catalog'))
    assert s.verifier.check() is None


def test_controller_cannot_invoke_observer_even_with_schema_usage(observer):
    s = observer
    with s.admin.begin() as db:
        db.connection.driver_connection.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO {}').format(
            sql.Identifier(s.receipts), sql.Identifier(s.login)
        ))
    for statement in [
        f'SELECT "{s.receipts}".inventory_fake()',
        f'SELECT * FROM "{s.receipts}".principal',
        f'UPDATE "{s.receipts}".principal SET enabled=true',
        f'SET ROLE "{s.receipt_owner}"',
        f'SET ROLE "{s.receipt_login}"',
    ]:
        with pytest.raises(DBAPIError) as error, s.runtime.begin() as db:
            db.execute(text(statement))
        assert error.value.orig.sqlstate == '42501'


def test_observer_runtime_has_no_direct_reads_writes_or_clinical_function(observer):
    s = observer
    for statement in [
        f'SELECT * FROM "{s.receipts}".principal',
        f'UPDATE "{s.product}".agent_admission_epoch SET id=1',
        f'SELECT snapshot FROM "{s.product}".agent_operation',
        f'SELECT * FROM "{s.product}".submitted_case',
        f'INSERT INTO "{s.product}".agent_attempt DEFAULT VALUES',
        f'UPDATE "{s.product}".agent_execution_grant SET reserved_units=0',
        f'SELECT "{s.capture}".capture(\'REQ-FAKE-0\')',
        f'CREATE TABLE "{s.receipts}".bad(id int)',
        f'SET ROLE "{s.receipt_owner}"',
    ]:
        with pytest.raises(DBAPIError) as error, s.observer_runtime.begin() as db:
            db.execute(text(statement))
        assert error.value.orig.sqlstate == '42501'


def test_effective_grants_and_fixed_definer_metadata(observer):
    s = observer
    with s.admin.begin() as db:
        raw = db.connection.driver_connection
        assert raw.execute(
            'SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace '
            "WHERE n.nspname IN (%s,%s,%s) AND c.relkind IN ('r','p','v','m') AND "
            '(has_table_privilege(%s,c.oid,'
            "'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN') "
            "OR has_any_column_privilege(%s,c.oid,'SELECT,INSERT,UPDATE,REFERENCES'))",
            (s.product, s.capture, s.receipts, s.receipt_login, s.receipt_login),
        ).fetchone() == (0,)
        assert raw.execute(
            'SELECT p.proname,p.prosecdef,p.proconfig,r.rolname FROM pg_proc p '
            'JOIN pg_namespace n ON n.oid=p.pronamespace JOIN pg_roles r ON r.oid=p.proowner '
            'WHERE n.nspname IN (%s,%s,%s) AND has_function_privilege(%s,p.oid,\'EXECUTE\')',
            (s.product, s.capture, s.receipts, s.receipt_login),
        ).fetchall() == [(
            'inventory_fake', True,
            ['search_path=pg_catalog, pg_temp', 'row_security=on', 'lock_timeout=2s'],
            s.receipt_owner,
        )]
        for table in ('agent_operation', 'agent_attempt', 'agent_execution_grant',
                      'agent_comparison', 'submitted_case', 'review_case'):
            assert not raw.execute(
                "SELECT has_table_privilege(%s,%s,'INSERT,UPDATE,DELETE,TRUNCATE') "
                "OR has_any_column_privilege(%s,%s,'INSERT,UPDATE')",
                (s.receipt_owner, f'{s.product}.{table}') * 2,
            ).fetchone()[0]
        assert raw.execute(
            'SELECT count(*) FROM pg_auth_members WHERE member IN '
            '(SELECT oid FROM pg_roles WHERE rolname IN (%s,%s))',
            (s.receipt_owner, s.receipt_login),
        ).fetchone() == (0,)


def test_principal_expiry_is_rechecked_after_epoch_lock_wait(observer):
    s = observer
    mutate(s, f'UPDATE "{s.receipts}".principal SET '
           "ends_at=clock_timestamp()+interval '400 milliseconds'")
    with s.admin.begin() as db, ThreadPoolExecutor(max_workers=1) as pool:
        db.execute(text('SELECT id FROM agent_admission_epoch FOR UPDATE'))
        future = pool.submit(s.verifier.check)
        time.sleep(.65)
        db.commit()
        closed(lambda: future.result(timeout=4))


def test_epoch_lock_covers_external_check_and_releases_on_failure(observer, monkeypatch):
    s = observer

    def compare(_):
        with pytest.raises(DBAPIError) as error, s.admin.begin() as db:
            db.execute(text("SET LOCAL lock_timeout='100ms'"))
            db.execute(text('SELECT id FROM agent_admission_epoch FOR UPDATE'))
        assert error.value.orig.sqlstate == '55P03'
        raise AgentContractError(ERROR)

    monkeypatch.setattr(s.setup.admission.journal, 'check', compare)
    closed(s.verifier.check)
    with s.admin.begin() as db:
        db.execute(text("SET LOCAL lock_timeout='100ms'"))
        db.execute(text('SELECT id FROM agent_admission_epoch FOR UPDATE'))


def test_inventory_bound_refuses_31_instead_of_silently_truncating(observer):
    s = observer
    # Explicit trusted historical fixture inserts; no guard is disabled/reset.
    now = datetime.now(UTC)
    with Session(s.admin) as db, db.begin():
        for i in range(31):
            op_id = uuid4()
            db.add(AgentOperation(
                tenant_id=TENANT_ID, id=op_id, request_id='REQ-FAKE-0', actor_id=ACTOR,
                grant_id=s.setup.grant_id, operation_key=f'{i:064x}', config_digest='a' * 64,
                source_digest='b' * 64, snapshot=s.setup.snapshots[0].model_dump(mode='json'),
                state='submitting', version=0, created_at=now,
                deadline=now + timedelta(seconds=120),
            ))
            db.flush()
            db.add(AgentAttempt(
                tenant_id=TENANT_ID, id=uuid4(), operation_id=op_id, attempt_number=1,
                submission_id=uuid4(), fence_id=uuid4(), submitted_at=now,
            ))
    with pytest.raises(DBAPIError) as caught:
        inventory(s)
    assert caught.value.orig.sqlstate == '42501'
    closed(s.verifier.check)


def test_unknown_principal_denies_even_if_execute_was_accidentally_granted(observer):
    s = observer
    with s.admin.begin() as db:
        raw = db.connection.driver_connection
        raw.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO {}').format(
            sql.Identifier(s.receipts), sql.Identifier(s.login)
        ))
        raw.execute(sql.SQL('GRANT EXECUTE ON FUNCTION {}.inventory_fake() TO {}').format(
            sql.Identifier(s.receipts), sql.Identifier(s.login)
        ))
    closed(FakeReceiptVerifier(
        s.runtime, s.setup.admission.journal, schema=s.receipts
    ).check)


def test_sql_inventory_byte_bound_denies_before_returning_clinical_material(observer):
    s = observer
    now = datetime.now(UTC)
    op_id = uuid4()
    with Session(s.admin) as db, db.begin():
        db.add(AgentOperation(
            tenant_id=TENANT_ID, id=op_id, request_id='REQ-FAKE-0', actor_id=ACTOR,
            grant_id=s.setup.grant_id, operation_key='f' * 64, config_digest='a' * 64,
            source_digest='b' * 64, snapshot={'private': 'x' * (4 * 1024 * 1024)},
            state='submitting', version=0, created_at=now,
            deadline=now + timedelta(seconds=120),
        ))
        db.flush()
        db.add(AgentAttempt(
            tenant_id=TENANT_ID, id=uuid4(), operation_id=op_id, attempt_number=1,
            submission_id=uuid4(), fence_id=uuid4(), submitted_at=now,
        ))
    with pytest.raises(DBAPIError) as caught:
        inventory(s)
    assert caught.value.orig.sqlstate == '42501'
    closed(s.verifier.check)
