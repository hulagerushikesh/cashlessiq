"""Actual restricted publication/heartbeat logins, only disposable Linux CI."""

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

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from uuid import uuid4

from psycopg import sql
from sqlalchemy import event, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from test_agent_contracts import candidate
from test_agent_controller_capture import controller_database as controller_database
from test_agent_controller_capture import engine as engine
from test_agent_controller_capture import scope as scope
from test_agent_controller_capture import setup as setup
from test_agent_controller_reservation import commands as commands
from test_agent_controller_reservation import mutate
from test_agent_custody_dispatch import dispatch as dispatch
from test_agent_custody_submission import coordinator, rows
from test_agent_custody_submission import custody as custody
from test_agent_ledger import ACTOR, balance
from test_agent_receipt_verifier import closed
from test_agent_receipt_verifier import observer as observer

from ciq_api import agent_custody_submission as module
from ciq_api.agent_contracts import AgentContractError
from ciq_api.agent_ledger_models import AgentComparison
from ciq_api.mvp_models import MvpEvent
from ciq_api.review_models import ReviewCase
from ciq_api.seed import TENANT_ID

PACKAGE = Path(__file__).resolve().parents[3] / 'deploy/agent-controller/custody-publication.sql'
SIGNATURES = (
    'publication_context_fake(text, uuid, integer, uuid, uuid)',
    'heartbeat_submitted_fake(text, uuid, integer, uuid, uuid)',
    'publish_comparison_fake(text, uuid, integer, uuid, uuid, jsonb)',
)


@pytest.fixture
def publication(dispatch):
    s = dispatch
    with s.admin.begin() as db:
        raw = db.connection.driver_connection
        raw.execute(sql.SQL(PACKAGE.read_text()).format(
            owner=sql.Identifier(s.receipt_owner), receipts=sql.Identifier(s.receipts),
            product=sql.Identifier(s.product),
        ))
        for signature in SIGNATURES:
            raw.execute(sql.SQL('GRANT EXECUTE ON FUNCTION {}.{} TO {}').format(
                sql.Identifier(s.receipts), sql.SQL(signature), sql.Identifier(s.receipt_login),
            ))
    return s


def ready(s):
    s.custody.prepare()
    s.prepared_backup = s.setup.admission.journal.path.read_bytes()
    s.custody.dispatch()


def comparisons(s):
    with Session(s.admin) as db:
        return db.query(AgentComparison).all()


def test_restricted_publication_consumes_units_atomically_and_leaves_human_records_unchanged(
    publication, monkeypatch,
):
    s = publication
    ready(s)
    original = rows(s)[0]
    with s.admin.connect() as db:
        events = db.scalar(text('SELECT count(*) FROM mvp_event'))
        outbox = db.scalar(text('SELECT count(*) FROM review_outbox'))
    validator = module.validate_candidate

    def locked(*args):
        # Operator assertion only, never the coordinator's connection. Clinical
        # and epoch locks stay held during Python deterministic/citation checks.
        for statement in (
            'SELECT id FROM agent_admission_epoch FOR UPDATE NOWAIT',
            'SELECT tenant_id FROM submitted_case FOR UPDATE NOWAIT',
            'SELECT tenant_id FROM review_case FOR UPDATE NOWAIT',
        ):
            with pytest.raises(DBAPIError) as error, s.admin.begin() as db:
                db.execute(text(statement))
            assert error.value.orig.sqlstate == '55P03'
        assert not comparisons(s)
        return validator(*args)

    monkeypatch.setattr(module, 'validate_candidate', locked)
    assert s.custody.publish() is None
    op, attempts = rows(s)
    saved = comparisons(s)
    assert op.state == 'published' and op.version == original.version + 1
    assert op.deadline == original.deadline and op.lease_until == original.lease_until
    assert op.fence_id == original.fence_id and len(attempts) == len(saved) == 1
    assert saved[0].candidate == candidate(s.setup.snapshots[0], op.id)
    assert saved[0].attempt_id == attempts[0].id
    assert balance(s.setup) == (1, 0, 0, 10, 0)
    with Session(s.admin) as db:
        assert db.get(ReviewCase, (TENANT_ID, 'REQ-FAKE-0')).version == 0
        assert db.scalar(text('SELECT count(*) FROM mvp_event')) == events
        assert db.scalar(text('SELECT count(*) FROM review_outbox')) == outbox
    closed(s.custody.publish)
    closed(s.custody.dispatch)
    closed(coordinator(s, transport=s.transport).publish)
    assert len(s.exchanges) == 1 and s.verifier.check() is None


def test_restricted_submitted_heartbeat_preserves_fence_attempt_and_original_deadline(publication):
    s = publication
    ready(s)
    original, attempts = rows(s)
    private = s.custody._candidate
    assert s.custody.heartbeat() is None
    op, after = rows(s)
    assert op.state == 'submitting' and op.version == original.version + 1
    assert original.lease_until <= op.lease_until <= op.deadline == original.deadline
    assert op.fence_id == original.fence_id and after[0].id == attempts[0].id
    assert s.custody._candidate[1:] == private[1:]
    assert not comparisons(s) and balance(s.setup) == (1, 1, 10, 0, 0)
    assert s.custody.publish() is None
    assert len(comparisons(s)) == len(s.exchanges) == 1
    assert balance(s.setup) == (1, 0, 0, 10, 0)


@pytest.mark.parametrize('action', ['publish', 'heartbeat'])
@pytest.mark.parametrize('fault', [
    'assignment', 'clinical', 'reservation', 'revoked', 'processor', 'policy', 'review',
    'facts', 'fence', 'version', 'lease', 'custody_window', 'clinical_window',
    'missing_custody', 'closed_custody', 'prepared_custody',
])
def test_post_exchange_revocation_and_stale_scope_deny_without_refund_or_replay(
    publication, action, fault,
):
    s = publication
    ready(s)
    statements = {
        'assignment': f'UPDATE "{s.receipts}".submission_scope SET enabled=false',
        'clinical': f'UPDATE "{s.capture}".principal SET enabled=false',
        'reservation': f'UPDATE "{s.capture}".reservation_scope SET enabled=false',
        'revoked': 'UPDATE tenant_membership SET active=false',
        'processor': "UPDATE tenant_membership SET role='processor'",
        'review': "UPDATE review_case SET state='APPROVED',version=version+1",
        'facts': "UPDATE submitted_case SET inputs=inputs || '{\"member_reference\":\"stale\"}'",
        'fence': 'UPDATE agent_operation SET fence_id=gen_random_uuid(),version=version+1',
        'version': 'UPDATE agent_operation SET version=version+1',
        'lease': "UPDATE agent_operation SET lease_until=clock_timestamp()-interval '1 second',"
                 'version=version+1',
        'custody_window': f'UPDATE "{s.receipts}".principal SET '
                         "starts_at=clock_timestamp()-interval '1 minute',"
                         "ends_at=clock_timestamp()-interval '1 second'",
        'clinical_window': f'UPDATE "{s.capture}".principal SET '
                           "starts_at=clock_timestamp()-interval '1 minute',"
                           "ends_at=clock_timestamp()-interval '1 second'",
    }
    if fault == 'missing_custody':
        s.setup.admission.journal.path.unlink()
    elif fault == 'closed_custody':
        s.setup.admission.journal.quarantine()
    elif fault == 'prepared_custody':
        s.setup.admission.journal.path.write_bytes(s.prepared_backup)
    elif fault == 'policy':
        with Session(s.admin) as db, db.begin():
            db.add(MvpEvent(
                id=uuid4(), tenant_id=TENANT_ID, actor_id=ACTOR,
                actor_role='medical_officer', command_id=uuid4(), action='policy_reject',
                subject_id=str(s.setup.policy_id), fingerprint='0' * 64, payload={},
            ))
    else:
        mutate(s, statements[fault])
    closed(getattr(s.custody, action))
    closed(s.custody.publish)
    closed(s.custody.heartbeat)
    closed(s.custody.dispatch)
    assert not comparisons(s) and balance(s.setup) == (1, 1, 10, 0, 0)
    assert len(s.exchanges) == len(rows(s)[1]) == 1 and s.custody._candidate is None


@pytest.mark.parametrize('change', [
    'money_type', 'money_value', 'citation', 'tenant', 'run', 'line',
])
def test_invalid_private_reply_never_creates_comparison_or_settles_allowance(publication, change):
    s = publication
    # Test fixed transport delivers a framed but clinically invalid candidate.
    # Production publish has no raw-response/validated flag parameter.
    import json
    original = s.exchange

    def corrupted(raw, *, timeout):
        body = json.loads(original(raw, timeout=timeout))
        if change == 'money_type':
            body['payable_inr'] = '95000'
        elif change == 'money_value':
            body['payable_inr'] = 1
        elif change == 'citation':
            body['citations'][0]['source_digest'] = '0' * 64
        elif change == 'tenant':
            body['binding']['tenant_id'] = str(uuid4())
        elif change == 'run':
            body['run_id'] = str(uuid4())
        else:
            body['lines'][0]['payable_inr'] += 1
        return json.dumps(body).encode()

    s.exchange = corrupted
    ready(s)
    closed(s.custody.publish)
    closed(s.custody.publish)
    assert not comparisons(s) and balance(s.setup) == (1, 1, 10, 0, 0)
    assert len(s.exchanges) == 1


@pytest.mark.parametrize('action', ['publish', 'heartbeat'])
def test_restricted_commit_failure_sacrifices_candidate_without_retry(publication, action):
    s = publication
    ready(s)
    original = rows(s)[0]

    def ambiguous(connection):
        raise DBAPIError('private commit', {}, ValueError('private'))

    event.listen(s.observer_runtime, 'commit', ambiguous)
    try:
        closed(getattr(s.custody, action))
    finally:
        event.remove(s.observer_runtime, 'commit', ambiguous)
    closed(s.custody.publish)
    closed(s.custody.heartbeat)
    op, attempts = rows(s)
    assert op.version == original.version and op.state == 'submitting'
    assert not comparisons(s) and len(attempts) == len(s.exchanges) == 1
    assert balance(s.setup) == (1, 1, 10, 0, 0)


def test_concurrent_original_publication_has_one_durable_comparison_and_settlement(publication):
    s = publication
    ready(s)
    barrier = Barrier(2)

    def run(_):
        barrier.wait(timeout=3)
        try:
            s.custody.publish()
            return True
        except AgentContractError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(run, range(2))) == [False, True]
    assert len(comparisons(s)) == len(s.exchanges) == 1
    assert balance(s.setup) == (1, 0, 0, 10, 0)


def test_effective_publication_acl_still_has_no_direct_runtime_access_or_human_writes(publication):
    s = publication
    with s.admin.connect() as db:
        raw = db.connection.driver_connection
        accessible = raw.execute(
            'SELECT p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace '
            "WHERE n.nspname IN (%s,%s) AND has_function_privilege(%s,p.oid,'EXECUTE') ORDER BY 1",
            (s.receipts, s.capture, s.receipt_login),
        ).fetchall()
        assert accessible == [(name,) for name in sorted([
            'checkpoint_fake', 'inventory_fake', 'issue_fake', 'publication_context_fake',
            'heartbeat_submitted_fake', 'publish_comparison_fake',
        ])]
        assert raw.execute(
            'SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace '
            "WHERE n.nspname IN (%s,%s,%s) AND c.relkind IN ('r','p','v','m') AND "
            '(has_table_privilege(%s,c.oid,'
            "'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN') OR "
            "has_any_column_privilege(%s,c.oid,'SELECT,INSERT,UPDATE,REFERENCES'))",
            (s.product, s.capture, s.receipts, s.receipt_login, s.receipt_login),
        ).fetchone() == (0,)
        for table in ('review_case', 'mvp_event', 'review_outbox'):
            assert not raw.execute("SELECT has_table_privilege(%s,%s,'INSERT,UPDATE,DELETE')", (
                s.receipt_owner, f'{s.product}.{table}',
            )).fetchone()[0]
        for column in ('uncertain_units', 'case_limit', 'unit_limit', 'ends_at'):
            assert not raw.execute("SELECT has_column_privilege(%s,%s,%s,'UPDATE')", (
                s.receipt_owner, f'{s.product}.agent_execution_grant', column,
            )).fetchone()[0]
        for column in ('deadline', 'snapshot', 'fence_id'):
            assert not raw.execute("SELECT has_column_privilege(%s,%s,%s,'UPDATE')", (
                s.receipt_owner, f'{s.product}.agent_operation', column,
            )).fetchone()[0]
        assert raw.execute(
            'SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace, '
            'LATERAL aclexplode(p.proacl) a WHERE n.nspname IN (%s,%s) AND a.grantee=0',
            (s.capture, s.receipts),
        ).fetchone() == (0,)


def test_clinical_login_cannot_use_publication_even_after_accidental_execute_grant(publication):
    s = publication
    ready(s)
    with s.admin.begin() as db:
        raw = db.connection.driver_connection
        raw.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO {}').format(
            sql.Identifier(s.receipts), sql.Identifier(s.login),
        ))
        raw.execute(sql.SQL('GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA {} TO {}').format(
            sql.Identifier(s.receipts), sql.Identifier(s.login),
        ))
    op, attempts = rows(s)
    for name in ('publication_context_fake', 'heartbeat_submitted_fake', 'publish_comparison_fake'):
        extra = ", '{}'::jsonb" if name == 'publish_comparison_fake' else ''
        with pytest.raises(DBAPIError) as failure, s.runtime.begin() as db:
            db.execute(text(
                f'SELECT "{s.receipts}".{name}'
                f'(:request,:operation,:version,:fence,:submission{extra})'
            ), {
                'request': 'REQ-FAKE-0', 'operation': op.id, 'version': op.version,
                'fence': op.fence_id, 'submission': attempts[0].submission_id,
            })
        assert failure.value.orig.sqlstate == '42501'
    assert s.custody.publish() is None and balance(s.setup) == (1, 0, 0, 10, 0)


def test_database_expiry_after_python_validation_denies_publication_even_without_local_clock_guard(
    publication, monkeypatch,
):
    import time
    s = publication
    ready(s)
    mutate(s, f'UPDATE "{s.receipts}".principal SET '
              "ends_at=clock_timestamp()+interval '400 milliseconds'")
    original = module.validate_candidate

    def delayed(*args):
        result = original(*args)
        time.sleep(0.65)
        return result

    # Fault injection: DB must enforce fresh wall time even with a failed local
    # timing guard. Production does not offer these knobs to callers.
    monkeypatch.setattr(module.FakeCustodySubmission, '_budget', staticmethod(lambda *args: 10))
    monkeypatch.setattr(module, 'validate_candidate', delayed)
    closed(s.custody.publish)
    assert not comparisons(s) and balance(s.setup) == (1, 1, 10, 0, 0)
    assert len(s.exchanges) == 1
