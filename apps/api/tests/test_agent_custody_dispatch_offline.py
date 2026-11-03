"""Original-custody fake exchange: no server, credentials or local containers."""

import copy
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import UUID

import pytest
from test_agent_contracts import capture
from test_agent_custody_submission_offline import custody as custody
from test_agent_custody_submission_offline import instance
from test_agent_executor import ECHO
from test_agent_receipt_verifier_offline import closed
from test_agent_receipt_verifier_offline import inventory as inventory

from ciq_api import agent_custody_submission as module
from ciq_api.agent_contracts import AgentContractError
from ciq_api.agent_executor import BoundedFakeProcess, FakeProcessRequest


@pytest.fixture
def dispatch(custody, monkeypatch):
    s = custody
    row = s.engine.material['entries'][0]
    s.snapshot = capture(tenant_id=UUID(row['operation']['tenant_id']), request_id='SYN-PRIVATE')
    row['operation']['snapshot'] = s.snapshot.model_dump(mode='json')
    s.transport = BoundedFakeProcess((sys.executable, '-I', '-c', ECHO))
    s.exchange = s.transport.exchange
    s.exchanges = []

    def exchange(raw, *, timeout):
        # No connection/clinical lock is kept across child I/O. The durable
        # external issue and local checkpoint have already committed.
        assert not s.engine.active
        with s.journal._connection() as db:
            assert db.execute('SELECT state FROM receipt').fetchall() == [('issued',)]
        s.engine.calls.append('exchange')
        s.exchanges.append((raw, timeout))
        return s.exchange(raw, timeout=timeout)

    monkeypatch.setattr(s.transport, 'exchange', exchange)
    s.coordinator = instance(s, transport=s.transport)
    return s


def test_exact_private_envelope_committed_issue_before_real_child_and_no_returned_ticket(dispatch):
    s = dispatch
    s.coordinator.prepare()
    assert s.coordinator.dispatch() is None
    assert len(s.exchanges) == 1
    raw, timeout = s.exchanges[0]
    request = FakeProcessRequest.model_validate_json(raw)
    row = s.engine.material['entries'][0]
    assert request.snapshot == s.snapshot
    assert str(request.tenant_id) == row['operation']['tenant_id']
    assert str(request.operation_id) == row['operation']['id']
    assert str(request.attempt_id) == row['attempt']['id']
    assert str(request.submission_id) == row['attempt']['submission_id']
    assert request.config_digest == row['operation']['config_digest']
    assert request.source_digest == row['operation']['source_digest']
    assert request.deadline == datetime.fromisoformat(s.engine.issue_projection['deadline'])
    assert 0 < timeout <= 10
    assert s.coordinator._candidate[1] == b'{}'  # private, not clinically validated/published
    assert s.engine.calls[-4:] == ['observe', 'issue', 'commit', 'exchange']
    closed(s.coordinator.dispatch)
    closed(s.coordinator.issue)
    closed(s.coordinator.prepare)


@pytest.mark.parametrize('transport', [{}, (), 'command', lambda: None, object()])
def test_transport_must_be_fixed_typed_trusted_construction_before_connection(custody, transport):
    closed(lambda: instance(custody, transport=transport))
    assert custody.engine.calls == []


@pytest.mark.parametrize('stage', ['unprepared', 'issue_only', 'replacement', 'no_transport'])
def test_no_later_or_reconstructed_dispatch_permission(dispatch, stage):
    s = dispatch
    peer = s.coordinator
    if stage != 'unprepared':
        s.coordinator.prepare()
    if stage == 'issue_only':
        s.coordinator.issue()
    elif stage == 'replacement':
        peer = instance(s, transport=s.transport)
    elif stage == 'no_transport':
        peer = instance(s)
    closed(peer.dispatch)
    assert not s.exchanges
    if stage in {'replacement', 'no_transport'}:
        assert s.coordinator.dispatch() is None


@pytest.mark.parametrize('changes', [
    {'checked_at': None}, {'deadline': None}, {'checked_at': '2026-11-03T12:00:00'},
    {'deadline': '2026-11-03T12:00:00'}, {'deadline': '2000-01-01T00:00:00Z'},
    {'deadline': '2100-01-01T00:00:00Z'}, {'extra': 'private'},
])
def test_bad_or_expanded_issue_budget_never_consumes_or_dispatches(dispatch, changes):
    s = dispatch
    s.coordinator.prepare()
    s.engine.issue_projection.update(changes)
    closed(s.coordinator.dispatch)
    closed(s.coordinator.dispatch)
    assert not s.exchanges and s.coordinator._candidate is None
    with s.journal._connection() as db:
        assert db.execute('SELECT state FROM receipt').fetchall() == [('prepared',)]


@pytest.mark.parametrize('fault', ['snapshot', 'tenant', 'request'])
def test_independently_read_snapshot_must_be_valid_and_exact_before_issue(dispatch, fault):
    s = dispatch
    row = s.engine.material['entries'][0]
    if fault == 'snapshot':
        row['operation']['snapshot'] = {'private': 'invalid snapshot'}
    else:
        changes = {'tenant_id': UUID(int=1)} if fault == 'tenant' else {'request_id': 'other'}
        row['operation']['snapshot'] = capture(**changes).model_dump(mode='json')
    # Prepare binds even this full material, but dispatch independently validates
    # AgentInput and its tenant/request before single-use issue or child startup.
    s.coordinator.prepare()
    closed(s.coordinator.dispatch)
    assert not s.exchanges


@pytest.mark.parametrize('at', ['before_issue', 'external_issue', 'local_commit', 'child_return'])
def test_elapsed_budget_is_consumed_across_all_boundaries_and_never_retried(
    dispatch, monkeypatch, at,
):
    s = dispatch
    s.coordinator.prepare()
    clock = [100.0]
    monkeypatch.setattr(module, 'monotonic', lambda: clock[0])
    if at in {'before_issue', 'external_issue'}:
        name = 'check' if at == 'before_issue' else 'issue'
        original = getattr(s.journal, name)

        def delayed(*args):
            original(*args)
            clock[0] += 120

        monkeypatch.setattr(s.journal, name, delayed)
    elif at == 'local_commit':
        # Engine appends this marker only after its transaction succeeds.
        class DelayedCalls(list):
            def append(self, value):
                super().append(value)
                if value == 'commit':
                    clock[0] += 120

        s.engine.calls = DelayedCalls(s.engine.calls)
    else:
        original = s.transport.exchange

        def delayed(raw, *, timeout):
            result = original(raw, timeout=timeout)
            clock[0] += 120
            return result

        monkeypatch.setattr(s.transport, 'exchange', delayed)
    closed(s.coordinator.dispatch)
    closed(s.coordinator.dispatch)
    assert len(s.exchanges) == (at == 'child_return')
    assert s.coordinator._candidate is None
    with s.journal._connection() as db:
        assert db.execute('SELECT state FROM receipt').fetchall() == [
            ('prepared' if at == 'before_issue' else 'issued',)
        ]


def test_local_wall_clock_behind_cannot_expand_database_budget(dispatch, monkeypatch):
    s = dispatch
    s.coordinator.prepare()
    now = datetime.now(UTC)
    s.engine.issue_projection = {
        'checked_at': now.isoformat(), 'deadline': (now + timedelta(seconds=3)).isoformat(),
    }

    class Behind:
        @staticmethod
        def now(_zone):
            return now - timedelta(days=1)

    monkeypatch.setattr(module, 'datetime', Behind)
    s.coordinator.dispatch()
    assert 0 < s.exchanges[0][1] <= 1  # DB three seconds minus two-second margin


def test_local_wall_clock_ahead_wastes_permission_without_dispatch(dispatch, monkeypatch):
    s = dispatch
    s.coordinator.prepare()

    class Ahead:
        @staticmethod
        def now(_zone):
            return datetime.now(UTC) + timedelta(days=1)

    monkeypatch.setattr(module, 'datetime', Ahead)
    closed(s.coordinator.dispatch)
    assert not s.exchanges


def test_ambiguous_commit_after_external_issue_never_starts_child(dispatch):
    s = dispatch
    s.coordinator.prepare()
    s.engine.commit_error = True
    closed(s.coordinator.dispatch)
    s.engine.commit_error = False
    closed(s.coordinator.dispatch)
    closed(instance(s, transport=s.transport).dispatch)
    assert not s.exchanges
    with s.journal._connection() as db:
        assert db.execute('SELECT state FROM receipt').fetchall() == [('issued',)]


@pytest.mark.parametrize('fault', ['missing', 'closed', 'changed', 'sql'])
def test_custody_or_fresh_issue_failure_never_dispatches_or_retries(dispatch, fault):
    s = dispatch
    s.coordinator.prepare()
    if fault == 'missing':
        s.journal.path.unlink()
    elif fault == 'closed':
        s.journal.quarantine()
    elif fault == 'changed':
        s.engine.raw = copy.deepcopy(s.engine.raw)
        s.engine.raw['entries'][0]['operation']['snapshot'] = {'private': 'drift'}
    else:
        s.engine.sql_error = True
    closed(s.coordinator.dispatch)
    closed(s.coordinator.dispatch)
    assert not s.exchanges


@pytest.mark.parametrize('code', [
    "import sys; sys.stderr.write('private clinical text')",
    "import sys; sys.stdout.write('bad private frame')",
    "import sys; sys.stdout.write('x'*2000000)",
    "import os; os._exit(7)",
])
def test_actual_child_faults_keep_issued_marker_without_candidate_or_replay(dispatch, code):
    s = dispatch
    s.exchange = BoundedFakeProcess((sys.executable, '-I', '-c', code)).exchange
    s.coordinator.prepare()
    closed(s.coordinator.dispatch)
    closed(s.coordinator.dispatch)
    assert len(s.exchanges) == 1 and s.coordinator._candidate is None
    with s.journal._connection() as db:
        assert db.execute('SELECT state FROM receipt').fetchall() == [('issued',)]


def test_concurrent_calls_on_original_instance_dispatch_at_most_once(dispatch):
    s = dispatch
    s.coordinator.prepare()
    barrier = Barrier(2)

    def run(_):
        barrier.wait(timeout=3)
        try:
            s.coordinator.dispatch()
            return True
        except AgentContractError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(run, range(2))) == [False, True]
    assert len(s.exchanges) == 1


def test_dispatch_has_no_caller_execution_or_identity_selectors(dispatch):
    s = dispatch
    s.coordinator.prepare()
    with pytest.raises(TypeError):
        s.coordinator.dispatch(tenant_id='other', command='other', checked=True)
    assert not s.exchanges
    assert s.coordinator.dispatch() is None
    assert 'credential' not in json.loads(s.exchanges[0][0])


def test_original_without_bound_transport_cannot_issue_then_dispatch(custody):
    s = custody
    s.coordinator.prepare()
    closed(s.coordinator.dispatch)
    closed(s.coordinator.issue)
    with s.journal._connection() as db:
        assert db.execute('SELECT state FROM receipt').fetchall() == [('prepared',)]


def test_hung_actual_child_is_bounded_and_permission_is_lost(dispatch, monkeypatch):
    s = dispatch
    s.exchange = BoundedFakeProcess((
        sys.executable, '-I', '-c', 'import time; time.sleep(60)',
    )).exchange
    monkeypatch.setattr(module, 'MAX_PROCESS_SECONDS', 0.2)
    s.coordinator.prepare()
    closed(s.coordinator.dispatch)
    closed(s.coordinator.dispatch)
    assert len(s.exchanges) == 1 and s.coordinator._candidate is None
