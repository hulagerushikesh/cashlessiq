"""Restricted logins + original-custody fake child, only disposable Linux CI."""

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

import base64
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier
from uuid import uuid4

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
from test_agent_custody_submission import coordinator, rows
from test_agent_custody_submission import custody as custody
from test_agent_ledger import ACTOR, balance
from test_agent_receipt_verifier import closed
from test_agent_receipt_verifier import observer as observer

from ciq_api import agent_custody_submission as module
from ciq_api.agent_contracts import AgentContractError
from ciq_api.agent_executor import BoundedFakeProcess, FakeProcessRequest
from ciq_api.agent_ledger_models import AgentComparison
from ciq_api.mvp_models import MvpEvent
from ciq_api.review_models import ReviewCase
from ciq_api.seed import TENANT_ID

ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT / 'apps/agent-transport/fake_transport.py'
HELPER = ROOT / 'apps/agent-transport/tests/exchange_fixture.py'


@pytest.fixture
def dispatch(custody, tmp_path, monkeypatch):
    s = custody
    fixture = tmp_path / 'canned.json'
    s.transport = BoundedFakeProcess((
        sys.executable, '-I', str(HELPER), str(RUNTIME), str(fixture),
    ))
    s.exchange = s.transport.exchange
    s.exchanges = []

    def exchange(raw, *, timeout):
        request = FakeProcessRequest.model_validate_json(raw)
        # Test operator observes committed rows. These owner reads are assertions,
        # NOT a connection or permission used by the custody coordinator/child.
        op, attempts = rows(s)
        assert op.state == 'submitting' and len(attempts) == 1
        assert request.operation_id == op.id and request.attempt_id == attempts[0].id
        assert request.submission_id == attempts[0].submission_id
        assert request.tenant_id == TENANT_ID and request.snapshot == s.setup.snapshots[0]
        assert request.deadline <= min(op.deadline, op.lease_until)
        assert balance(s.setup) == (1, 1, 10, 0, 0)
        with s.admin.begin() as db:
            db.execute(text('SELECT id FROM agent_admission_epoch FOR UPDATE NOWAIT'))
        with s.setup.admission.journal._connection() as db:
            assert db.execute('SELECT state FROM receipt').fetchall() == [('issued',)]
        s.exchanges.append((request, timeout))
        # Trusted fixture construction only: child sees a fixed canned response
        # pinned to the exact independently observed packet, never DB credentials.
        body = candidate(request.snapshot, request.operation_id)
        fixture.write_text(json.dumps({
            'request_sha256': hashlib.sha256(raw).hexdigest(),
            'candidate_base64': base64.b64encode(json.dumps(body).encode()).decode(),
        }))
        fixture.chmod(0o600)
        return s.exchange(raw, timeout=timeout)

    monkeypatch.setattr(s.transport, 'exchange', exchange)
    s.custody = coordinator(s, transport=s.transport)
    return s


def test_restricted_custody_dispatches_exact_canned_request_once_with_no_publication(dispatch):
    s = dispatch
    original = rows(s)[0]
    s.custody.prepare()
    assert s.custody.dispatch() is None
    assert len(s.exchanges) == 1 and 0 < s.exchanges[0][1] <= 10
    assert json.loads(s.custody._candidate[1]) == candidate(
        s.setup.snapshots[0], s.claim.operation_id,
    )
    closed(s.custody.dispatch)
    closed(s.custody.issue)
    closed(coordinator(s, transport=s.transport).dispatch)
    op, attempts = rows(s)
    assert op.deadline == original.deadline and op.lease_until == original.lease_until
    assert len(attempts) == 1 and op.state == 'submitting'
    assert balance(s.setup) == (1, 1, 10, 0, 0)
    with Session(s.admin) as db:
        assert db.query(AgentComparison).count() == 0
        assert db.get(ReviewCase, (TENANT_ID, 'REQ-FAKE-0')).version == 0
    assert s.verifier.check() is None


@pytest.mark.parametrize('fault', [
    'assignment', 'clinical', 'reservation', 'revoked', 'processor', 'policy',
    'review', 'facts', 'fence', 'version', 'lease', 'missing_custody', 'closed_custody',
])
def test_fresh_clinical_and_custody_denials_prevent_all_child_io(dispatch, fault):
    s = dispatch
    s.custody.prepare()
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
    }
    if fault == 'missing_custody':
        s.setup.admission.journal.path.unlink()
    elif fault == 'closed_custody':
        s.setup.admission.journal.quarantine()
    elif fault == 'policy':
        with Session(s.admin) as db, db.begin():
            db.add(MvpEvent(
                id=uuid4(), tenant_id=TENANT_ID, actor_id=ACTOR,
                actor_role='medical_officer', command_id=uuid4(), action='policy_reject',
                subject_id=str(s.setup.policy_id), fingerprint='0' * 64, payload={},
            ))
    else:
        mutate(s, statements[fault])
    closed(s.custody.dispatch)
    closed(s.custody.dispatch)
    assert not s.exchanges and s.custody._candidate is None
    assert balance(s.setup) == (1, 1, 10, 0, 0) and len(rows(s)[1]) == 1


@pytest.mark.parametrize('principal', ['custody', 'clinical'])
def test_dispatch_budget_honors_both_principal_windows(dispatch, principal):
    s = dispatch
    s.custody.prepare()
    schema = s.receipts if principal == 'custody' else s.capture
    mutate(s, f'UPDATE "{schema}".principal SET ends_at=clock_timestamp()+interval \'5 seconds\'')
    before = datetime.now(UTC)
    s.custody.dispatch()
    request, timeout = s.exchanges[0]
    assert 0 < (request.deadline - before).total_seconds() <= 5
    assert 0 < timeout <= 3


def test_too_short_budget_does_not_issue_or_start_child(dispatch):
    s = dispatch
    s.custody.prepare()
    mutate(s, f'UPDATE "{s.receipts}".principal SET '
              "ends_at=clock_timestamp()+interval '1 second'")
    closed(s.custody.dispatch)
    assert not s.exchanges
    with s.setup.admission.journal._connection() as db:
        assert db.execute('SELECT state FROM receipt').fetchall() == [('prepared',)]
    assert balance(s.setup) == (1, 1, 10, 0, 0)


def test_local_commit_failure_after_external_issue_sacrifices_dispatch(dispatch):
    s = dispatch
    s.custody.prepare()

    def ambiguous(connection):
        raise DBAPIError('private commit', {}, ValueError('private'))

    event.listen(s.observer_runtime, 'commit', ambiguous)
    try:
        closed(s.custody.dispatch)
    finally:
        event.remove(s.observer_runtime, 'commit', ambiguous)
    closed(s.custody.dispatch)
    closed(coordinator(s, transport=s.transport).dispatch)
    assert not s.exchanges
    with s.setup.admission.journal._connection() as db:
        assert db.execute('SELECT state FROM receipt').fetchall() == [('issued',)]
    assert balance(s.setup) == (1, 1, 10, 0, 0)


@pytest.mark.parametrize('code', [
    "import sys; sys.stderr.write('private clinical text')",
    "import sys; sys.stdout.write('private malformed response')",
    "import sys; sys.stdout.write('x'*2000000)",
    "import os; os._exit(7)",
])
def test_real_child_failure_retains_allowance_and_issued_marker_without_replay(dispatch, code):
    s = dispatch
    s.exchange = BoundedFakeProcess((sys.executable, '-I', '-c', code)).exchange
    s.custody.prepare()
    closed(s.custody.dispatch)
    closed(s.custody.dispatch)
    assert len(s.exchanges) == 1 and s.custody._candidate is None
    assert len(rows(s)[1]) == 1 and balance(s.setup) == (1, 1, 10, 0, 0)
    with s.setup.admission.journal._connection() as db:
        assert db.execute('SELECT state FROM receipt').fetchall() == [('issued',)]


def test_concurrent_original_coordinator_calls_have_one_exchange(dispatch):
    s = dispatch
    s.custody.prepare()
    barrier = Barrier(2)

    def run(_):
        barrier.wait(timeout=3)
        try:
            s.custody.dispatch()
            return True
        except AgentContractError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(run, range(2))) == [False, True]
    assert len(s.exchanges) == len(rows(s)[1]) == 1


def test_hung_child_is_bounded_and_never_replayed(dispatch, monkeypatch):
    s = dispatch
    s.exchange = BoundedFakeProcess((
        sys.executable, '-I', '-c', 'import time; time.sleep(60)',
    )).exchange
    monkeypatch.setattr(module, 'MAX_PROCESS_SECONDS', 0.2)
    s.custody.prepare()
    closed(s.custody.dispatch)
    closed(s.custody.dispatch)
    assert len(s.exchanges) == 1 and s.custody._candidate is None
    assert balance(s.setup) == (1, 1, 10, 0, 0)
    with s.setup.admission.journal._connection() as db:
        assert db.execute('SELECT state FROM receipt').fetchall() == [('issued',)]
