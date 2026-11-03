"""Restricted fake custody commands; guarded disposable actual logins only."""

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
from pathlib import Path
from threading import Barrier
from uuid import uuid4

from psycopg import sql
from sqlalchemy import event, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from test_agent_controller_capture import controller_database as controller_database
from test_agent_controller_capture import engine as engine
from test_agent_controller_capture import scope as scope
from test_agent_controller_capture import setup as setup
from test_agent_controller_reservation import commands as commands
from test_agent_controller_reservation import mutate, reserve
from test_agent_ledger import ACTOR, balance
from test_agent_receipt_verifier import closed, inventory
from test_agent_receipt_verifier import observer as observer

from ciq_api.agent_admission import FakeCheckpoint, checkpoint
from ciq_api.agent_contracts import AgentContractError
from ciq_api.agent_custody_submission import FakeCustodySubmission
from ciq_api.agent_ledger_models import AgentAttempt, AgentComparison, AgentOperation
from ciq_api.review_models import ReviewCase
from ciq_api.seed import TENANT_ID

PACKAGE = Path(__file__).resolve().parents[3] / 'deploy/agent-controller/custody-submission.sql'


def coordinator(s, *, request='REQ-FAKE-0', claim=None):
    return FakeCustodySubmission(
        s.observer_runtime, s.setup.admission.journal,
        schema=s.receipts, request_id=request, claim=claim or s.claim,
    )


@pytest.fixture
def custody(commands, observer):
    s = commands
    assert s is observer
    s.claim = s.commands.claim('REQ-FAKE-0', reserve(s))
    with s.admin.begin() as db:
        raw = db.connection.driver_connection
        raw.execute(sql.SQL(PACKAGE.read_text()).format(
            owner=sql.Identifier(s.receipt_owner), receipts=sql.Identifier(s.receipts),
            capture=sql.Identifier(s.capture), product=sql.Identifier(s.product),
        ))
        for signature in ('checkpoint_fake(text, uuid, integer, uuid)',
                          'issue_fake(text, uuid, integer, uuid, uuid)'):
            raw.execute(sql.SQL('GRANT EXECUTE ON FUNCTION {}.{} TO {}').format(
                sql.Identifier(s.receipts), sql.SQL(signature), sql.Identifier(s.receipt_login)
            ))
        raw.execute(sql.SQL(
            'INSERT INTO {}.submission_scope SELECT custody.oid,%s,controller.oid,'
            'controller.rolname,%s,%s,%s,true FROM pg_roles custody, pg_roles controller '
            'WHERE custody.rolname=%s AND controller.rolname=%s'
        ).format(sql.Identifier(s.receipts)), (
            'REQ-FAKE-0', TENANT_ID, ACTOR,
            s.claim.operation_id, s.receipt_login, s.login,
        ))
    s.custody = coordinator(s)
    return s


def rows(s):
    with Session(s.admin) as db:
        op = db.get(AgentOperation, (TENANT_ID, s.claim.operation_id))
        attempts = db.query(AgentAttempt).all()
        return op, attempts


def test_checkpoint_then_single_issue_preserves_money_human_state_and_exact_digest(custody):
    s = custody
    before = balance(s.setup)
    original, _ = rows(s)
    assert s.custody.prepare() is None
    op, attempts = rows(s)
    assert op.state == 'submitting' and op.version == s.claim.version + 1
    assert len(attempts) == 1 and attempts[0].fence_id == s.claim.fence_id
    assert op.deadline == original.deadline and op.lease_until == original.lease_until
    with Session(s.admin) as db:
        expected = checkpoint(db, attempts[0])
        assert db.get(ReviewCase, (TENANT_ID, 'REQ-FAKE-0')).version == 0
        assert db.query(AgentComparison).count() == 0
    journal = s.setup.admission.journal
    journal.check((expected,))
    with journal._connection() as db:
        assert db.execute('SELECT state FROM receipt').fetchall() == [('prepared',)]
    assert s.custody.issue() is None
    with journal._connection() as db:
        assert db.execute('SELECT state FROM receipt').fetchall() == [('issued',)]
    closed(s.custody.issue)
    closed(s.custody.prepare)
    assert balance(s.setup) == before == (1, 1, 10, 0, 0)
    assert s.verifier.check() is None


def test_restart_cannot_reconstruct_issue_permission_even_from_committed_rows(custody):
    s = custody
    s.custody.prepare()
    replacement = coordinator(s)
    closed(replacement.issue)
    closed(replacement.prepare)
    # Failed reconstruction cannot steal the original process's permission.
    assert s.custody.issue() is None
    assert len(rows(s)[1]) == 1


@pytest.mark.parametrize('fault', [
    'disabled', 'wrong_oid', 'wrong_controller_oid', 'wrong_controller_name',
    'wrong_operation', 'wrong_actor', 'wrong_tenant', 'clinical_disabled',
    'reservation_disabled', 'stale_facts', 'wrong_epoch', 'wrong_grant',
    'revoked', 'processor', 'final', 'controller_membership',
])
def test_exact_operator_assignment_and_fresh_clinical_scope_before_checkpoint(custody, fault):
    s = custody
    changes = {
        'disabled': 'enabled=false', 'wrong_oid': 'login_oid=0',
        'wrong_controller_oid': 'controller_oid=0',
        'wrong_controller_name': "controller_name='unbound'",
        'wrong_operation': 'operation_id=gen_random_uuid()',
        'wrong_actor': 'actor_id=gen_random_uuid()', 'wrong_tenant': 'tenant_id=gen_random_uuid()',
    }
    if fault == 'wrong_oid':
        # Keep the protected foreign key valid while moving to a different
        # existing observer principal OID: no enabled scope matches this session.
        mutate(s, f'DELETE FROM "{s.receipts}".submission_scope')
    elif fault in changes:
        mutate(s, f'UPDATE "{s.receipts}".submission_scope SET {changes[fault]}')
    elif fault == 'clinical_disabled':
        mutate(s, f'UPDATE "{s.capture}".principal SET enabled=false')
    elif fault == 'reservation_disabled':
        mutate(s, f'UPDATE "{s.capture}".reservation_scope SET enabled=false')
    elif fault == 'stale_facts':
        mutate(s, "UPDATE submitted_case SET inputs=inputs || '{\"member_reference\":\"stale\"}'")
    elif fault == 'wrong_epoch':
        mutate(s, f'UPDATE "{s.capture}".reservation_scope SET epoch_id=gen_random_uuid()')
    elif fault == 'wrong_grant':
        mutate(s, f'UPDATE "{s.capture}".reservation_scope SET grant_id=gen_random_uuid()')
    elif fault in {'revoked', 'processor'}:
        mutate(s, 'UPDATE tenant_membership SET ' + (
            'active=false' if fault == 'revoked' else "role='processor'"
        ))
    elif fault == 'final':
        mutate(s, "UPDATE review_case SET state='APPROVED',version=version+1")
    elif fault == 'controller_membership':
        with s.admin.begin() as db:
            db.connection.driver_connection.execute(sql.SQL('GRANT {} TO {}').format(
                sql.Identifier(s.owner), sql.Identifier(s.login)
            ))
    closed(s.custody.prepare)
    assert len(rows(s)[1]) == 0 and balance(s.setup) == (1, 1, 10, 0, 0)


@pytest.mark.parametrize('fault', ['binding', 'clinical', 'fence', 'version', 'lease', 'custody'])
def test_issue_rechecks_scope_and_consumes_process_permission_on_any_failure(custody, fault):
    s = custody
    s.custody.prepare()
    if fault == 'binding':
        mutate(s, f'UPDATE "{s.receipts}".submission_scope SET enabled=false')
    elif fault == 'clinical':
        mutate(s, f'UPDATE "{s.capture}".principal SET enabled=false')
    elif fault in {'fence', 'version', 'lease'}:
        change = {'fence': 'fence_id=gen_random_uuid()', 'version': 'state=state',
                  'lease': "lease_until=clock_timestamp()-interval '1 second'"}[fault]
        mutate(s, f'UPDATE agent_operation SET {change},version=version+1')
    else:
        s.setup.admission.journal.quarantine()
    closed(s.custody.issue)
    # Restoring a binding does not restore original ephemeral issue permission.
    if fault in {'binding', 'clinical'}:
        schema = s.receipts if fault == 'binding' else s.capture
        table = 'submission_scope' if fault == 'binding' else 'principal'
        mutate(s, f'UPDATE "{schema}".{table} SET enabled=true')
    closed(s.custody.issue)
    assert balance(s.setup) == (1, 1, 10, 0, 0)


@pytest.mark.parametrize('phase', ['prepare', 'issue'])
def test_external_orphan_or_missing_custody_denies_without_refund(custody, phase):
    s = custody
    if phase == 'issue':
        s.custody.prepare()
    s.setup.admission.journal.prepare(FakeCheckpoint(
        tenant_id=uuid4(), request_id='FORGOTTEN-OTHER-TENANT', operation_id=uuid4(),
        submission_id=uuid4(), digest='d' * 64,
    ))
    closed(getattr(s.custody, phase))
    assert balance(s.setup) == (1, 1, 10, 0, 0)
    assert len(rows(s)[1]) == (phase == 'issue')


@pytest.mark.parametrize('phase', ['prepare', 'issue'])
def test_external_commit_precedes_local_commit_and_failure_never_replays(custody, phase):
    s = custody
    if phase == 'issue':
        s.custody.prepare()

    def crash(connection):
        raise DBAPIError('private commit', {}, ValueError('private'))

    event.listen(s.observer_runtime, 'commit', crash)
    try:
        closed(getattr(s.custody, phase))
    finally:
        event.remove(s.observer_runtime, 'commit', crash)
    journal = s.setup.admission.journal
    with journal._connection() as db:
        assert db.execute('SELECT state FROM receipt').fetchall() == [
            ('prepared' if phase == 'prepare' else 'issued',)
        ]
    assert len(rows(s)[1]) == (phase == 'issue')
    closed(getattr(s.custody, phase))
    replacement = coordinator(s)
    closed(replacement.issue)
    closed(replacement.prepare)
    assert balance(s.setup) == (1, 1, 10, 0, 0)


@pytest.mark.parametrize('phase', ['prepare', 'issue'])
def test_epoch_remains_locked_across_independent_external_writes(custody, phase, monkeypatch):
    s = custody
    if phase == 'issue':
        s.custody.prepare()
    journal = s.setup.admission.journal
    original = getattr(journal, phase)

    def retained(*args):
        with pytest.raises(DBAPIError) as failure, s.admin.begin() as db:
            db.execute(text('SELECT id FROM agent_admission_epoch FOR UPDATE NOWAIT'))
        assert failure.value.orig.sqlstate == '55P03'
        original(*args)

    monkeypatch.setattr(journal, phase, retained)
    assert getattr(s.custody, phase)() is None
    with s.admin.begin() as db:
        db.execute(text('SELECT id FROM agent_admission_epoch FOR UPDATE NOWAIT'))


def test_concurrent_checkpoint_has_one_winner_and_one_independent_receipt(custody):
    s = custody
    peers = [s.custody, coordinator(s)]
    barrier = Barrier(2)

    def prepare(peer):
        barrier.wait(timeout=3)
        try:
            peer.prepare()
            return peer
        except AgentContractError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(prepare, peers))
    winners = [p for p in results if p]
    assert len(winners) == len(rows(s)[1]) == len(inventory(s)['entries']) == 1
    assert winners[0].issue() is None
    assert balance(s.setup) == (1, 1, 10, 0, 0)


@pytest.mark.parametrize('phase', ['prepare', 'issue'])
def test_expiry_after_clinical_lock_wait_denies(custody, phase):
    s = custody
    if phase == 'issue':
        s.custody.prepare()
    mutate(s, f'UPDATE "{s.receipts}".principal SET '
              "ends_at=clock_timestamp()+interval '400 milliseconds'")
    with s.admin.begin() as admin, ThreadPoolExecutor(max_workers=1) as pool:
        admin.execute(text('SELECT tenant_id FROM submitted_case FOR UPDATE'))
        future = pool.submit(getattr(s.custody, phase))
        time.sleep(0.65)
        admin.commit()
        closed(lambda: future.result(timeout=4))
    assert len(rows(s)[1]) == (phase == 'issue')


def test_direct_sql_and_private_delegation_denied_to_clinical_controller(custody):
    s = custody
    with s.admin.begin() as db:
        raw = db.connection.driver_connection
        raw.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO {}').format(
            sql.Identifier(s.receipts), sql.Identifier(s.login)
        ))
        # Even an accidentally granted public command cannot authenticate this
        # session as the distinct custody principal / assignment.
        raw.execute(sql.SQL('GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA {} TO {}').format(
            sql.Identifier(s.receipts), sql.Identifier(s.login)
        ))
    for statement in [
        f'SELECT "{s.receipts}".checkpoint_fake(\'REQ-FAKE-0\', '
        f"'{s.claim.operation_id}',{s.claim.version},'{s.claim.fence_id}')",
        f'SELECT "{s.receipts}".issue_fake(\'REQ-FAKE-0\', '
        f"'{s.claim.operation_id}',{s.claim.version},'{s.claim.fence_id}','{uuid4()}')",
        f'SELECT "{s.capture}"._capture_bound(0,\'REQ-FAKE-0\')',
        f'SELECT "{s.capture}"._reservation_context_for(0,\'REQ-FAKE-0\')',
        f'UPDATE "{s.receipts}".submission_scope SET enabled=true',
    ]:
        with pytest.raises(DBAPIError) as failure, s.runtime.begin() as db:
            db.execute(text(statement))
        assert failure.value.orig.sqlstate == '42501'
    assert rows(s)[1] == []


def test_effective_custody_acl_has_only_commands_no_product_or_registry_access(custody):
    s = custody
    with s.admin.connect() as db:
        raw = db.connection.driver_connection
        accessible = raw.execute(
            'SELECT p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace '
            "WHERE n.nspname IN (%s,%s) AND has_function_privilege(%s,p.oid,'EXECUTE') ORDER BY 1",
            (s.receipts, s.capture, s.receipt_login),
        ).fetchall()
        assert accessible == [('checkpoint_fake',), ('inventory_fake',), ('issue_fake',)]
        assert raw.execute(
            'SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace '
            "WHERE n.nspname IN (%s,%s,%s) AND c.relkind IN ('r','p','v','m') AND "
            '(has_table_privilege(%s,c.oid,'
            "'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN') OR "
            "has_any_column_privilege(%s,c.oid,'SELECT,INSERT,UPDATE,REFERENCES'))",
            (s.product, s.capture, s.receipts, s.receipt_login, s.receipt_login),
        ).fetchone() == (0,)
        assert raw.execute(
            'SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace, '
            'LATERAL aclexplode(p.proacl) a WHERE n.nspname IN (%s,%s) AND a.grantee=0',
            (s.capture, s.receipts),
        ).fetchone() == (0,)
        assert raw.execute(
            'SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace '
            'WHERE n.nspname=%s AND (NOT p.prosecdef OR p.proconfig <> %s::text[])',
            (s.receipts, ['search_path=pg_catalog, pg_temp', 'row_security=on', 'lock_timeout=2s']),
        ).fetchone() == (0,)
        for table in ('agent_execution_grant', 'agent_comparison', 'review_case'):
            assert not raw.execute('SELECT has_table_privilege(%s,%s,\'UPDATE\')', (
                s.receipt_owner, f'{s.product}.{table}',
            )).fetchone()[0]
        for column in ('consumed_units', 'uncertain_units', 'reserved_units', 'in_flight'):
            assert not raw.execute('SELECT has_column_privilege(%s,%s,%s,\'UPDATE\')', (
                s.receipt_owner, f'{s.product}.agent_execution_grant', column,
            )).fetchone()[0]
