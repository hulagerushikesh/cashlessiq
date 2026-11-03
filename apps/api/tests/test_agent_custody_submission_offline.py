"""Transaction sequencing and fail-closed fake custody, no database/server."""

import ast
import copy
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import DBAPIError
from test_agent_receipt_verifier_offline import closed
from test_agent_receipt_verifier_offline import inventory as inventory

from ciq_api.agent_custody_submission import FakeCustodySubmission
from ciq_api.agent_ledger import ClaimReceipt


class Engine:
    def __init__(self, material):
        self.material = copy.deepcopy(material)
        self.raw = {'epoch': material['epoch'], 'entries': []}
        row = material['entries'][0]
        self.receipt = {
            'operation_id': row['operation']['id'], 'version': 2,
            'fence_id': row['attempt']['fence_id'], 'attempt_id': row['attempt']['id'],
            'submission_id': row['attempt']['submission_id'],
        }
        self.active = False
        self.calls = []
        self.commit_error = False
        self.sql_error = False

    @contextmanager
    def begin(self):
        before = copy.deepcopy(self.raw)
        self.active = True
        try:
            yield self
            if self.commit_error:
                raise DBAPIError('private commit', {}, ValueError('private'))
            self.calls.append('commit')
        except BaseException:
            self.raw = before
            self.calls.append('rollback')
            raise
        finally:
            self.active = False

    def scalar(self, statement, params=None):
        if 'inventory_fake()' in str(statement):
            assert params is None
            self.calls.append('observe')
            return self.raw
        assert set(params) <= {'request', 'operation', 'version', 'fence', 'submission'}
        if self.sql_error:
            raise DBAPIError('private SQL', params, ValueError('private'))
        if 'checkpoint_fake' in str(statement):
            self.calls.append('checkpoint')
            self.raw = copy.deepcopy(self.material)
        else:
            assert 'issue_fake' in str(statement)
            self.calls.append('issue')
        return self.receipt


def instance(s, **changes):
    return FakeCustodySubmission(s.engine, s.journal, **{
        'request_id': 'SYN-PRIVATE', 'claim': s.claim, **changes,
    })


@pytest.fixture
def custody(inventory):
    s = inventory
    s.engine = Engine(s.raw)
    s.claim = ClaimReceipt(
        operation_id=UUID(s.raw['entries'][0]['operation']['id']), state='reserved',
        version=1, fence_id=UUID(s.raw['entries'][0]['attempt']['fence_id']),
    )
    s.coordinator = instance(s)
    return s


def test_prepare_commit_then_original_single_use_issue_no_transferable_result(custody, monkeypatch):
    s = custody
    for phase in ('check', 'prepare', 'issue'):
        original = getattr(s.journal, phase)

        def retained(*args, _original=original, _phase=phase):
            assert s.engine.active
            s.engine.calls.append('external_' + _phase)
            _original(*args)

        monkeypatch.setattr(s.journal, phase, retained)
    assert s.coordinator.prepare() is None
    assert s.engine.calls == [
        'observe', 'external_check', 'checkpoint', 'observe',
        'external_prepare', 'external_check', 'commit',
    ]
    assert s.coordinator.issue() is None
    assert s.engine.calls[-5:] == ['observe', 'external_check', 'issue', 'external_issue', 'commit']
    closed(s.coordinator.prepare)
    closed(s.coordinator.issue)
    assert not s.engine.active


@pytest.mark.parametrize('changes', [
    {'request_id': None}, {'request_id': ''}, {'request_id': 'x' * 121}, {'claim': {}},
    {'schema': 'public'}, {'schema': 'ciq_agent_receipts;SELECT 1'},
    {'state': 'submitting'}, {'version': 0}, {'version': True}, {'version': 2_147_483_647},
    {'operation_id': 'not-uuid'}, {'fence_id': None},
])
def test_trusted_selector_and_claim_validation_before_connecting(custody, changes):
    s = custody
    changes = dict(changes)
    if not set(changes) & {'request_id', 'claim', 'schema'}:
        changes = {'claim': s.claim.model_copy(update=changes)}
    closed(lambda: instance(s, **changes))
    assert s.engine.calls == []


@pytest.mark.parametrize('field', [
    'operation_id', 'version', 'fence_id', 'attempt_id', 'submission_id',
])
def test_invalid_checkpoint_projection_rolls_back_without_external_prepare(custody, field):
    s = custody
    s.engine.receipt[field] = 5 if field == 'version' else str(uuid4())
    closed(s.coordinator.prepare)
    s.journal.check(())
    assert s.engine.calls[-1] == 'rollback' and not s.engine.active
    closed(s.coordinator.prepare)


@pytest.mark.parametrize('phase', ['prepare', 'issue'])
def test_commit_failure_after_external_write_retains_history_and_blocks_replay(custody, phase):
    s = custody
    if phase == 'issue':
        s.coordinator.prepare()
    s.engine.commit_error = True
    closed(getattr(s.coordinator, phase))
    s.engine.commit_error = False
    s.journal.check((s.checkpoint,))
    with s.journal._connection() as db:
        assert db.execute('SELECT state FROM receipt').fetchall() == [
            ('prepared' if phase == 'prepare' else 'issued',)
        ]
    closed(getattr(s.coordinator, phase))
    replacement = instance(s)
    closed(replacement.issue)
    if phase == 'prepare':
        closed(replacement.prepare)  # rollback gap independently detected
    assert not s.engine.active


@pytest.mark.parametrize('phase', ['prepare', 'issue'])
def test_sql_failure_consumes_attempted_stage_without_private_error(custody, phase):
    s = custody
    if phase == 'issue':
        s.coordinator.prepare()
    s.engine.sql_error = True
    closed(getattr(s.coordinator, phase))
    s.engine.sql_error = False
    closed(getattr(s.coordinator, phase))
    assert not s.engine.active


@pytest.mark.parametrize('phase', ['prepare', 'issue'])
@pytest.mark.parametrize('fault', ['missing', 'closed', 'extra_history'])
def test_custody_failures_before_mutation_or_issue(custody, phase, fault):
    s = custody
    if phase == 'issue':
        s.coordinator.prepare()
    if fault == 'missing':
        s.journal.path.unlink()
    elif fault == 'closed':
        s.journal.quarantine()
    else:
        from ciq_api.agent_admission import FakeCheckpoint
        s.journal.prepare(FakeCheckpoint(
            tenant_id=uuid4(), request_id='forgotten', operation_id=uuid4(),
            submission_id=uuid4(), digest='a' * 64,
        ))
    before = len(s.engine.calls)
    closed(getattr(s.coordinator, phase))
    assert s.engine.calls[before:] == ['observe', 'rollback']
    assert not s.engine.active


def test_restart_never_issues_using_only_database_or_checkpoint_identity(custody):
    s = custody
    s.coordinator.prepare()
    replacement = instance(s)
    before = list(s.engine.calls)
    closed(replacement.issue)
    assert s.engine.calls == before
    assert s.coordinator.issue() is None


def test_issue_rejects_changed_returned_identity_and_loses_pending_permission(custody):
    s = custody
    s.coordinator.prepare()
    s.engine.receipt['submission_id'] = str(uuid4())
    closed(s.coordinator.issue)
    closed(s.coordinator.issue)
    with s.journal._connection() as db:
        assert db.execute('SELECT state FROM receipt').fetchall() == [('prepared',)]


def test_module_is_inactive_and_has_no_dispatch_sdk_or_api_imports():
    root = Path(__file__).resolve().parents[1] / 'src/ciq_api'
    allowed = {'agent_custody_submission.py'}
    for path in root.glob('*.py'):
        if path.name in allowed:
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or '').endswith('agent_custody_submission')
            elif isinstance(node, ast.Import):
                assert not any(n.name.endswith('agent_custody_submission') for n in node.names)
