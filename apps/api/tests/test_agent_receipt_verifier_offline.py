"""Independent fake observation uses no caller-selected inventory or permission."""

import copy
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.exc import DBAPIError

from ciq_api.agent_admission import (
    ERROR,
    FakeEpochPin,
    FakeReceiptJournal,
    checkpoint_from_material,
)
from ciq_api.agent_contracts import AgentContractError
from ciq_api.agent_receipt_verifier import FakeReceiptVerifier, _Material


class Engine:
    def __init__(self, raw=None, error=None):
        self.raw, self.error = raw, error
        self.active = False
        self.calls = 0

    @contextmanager
    def begin(self):
        self.calls += 1
        self.active = True
        try:
            yield self
        finally:
            self.active = False

    def scalar(self, statement):
        assert 'inventory_fake()' in str(statement) and not statement._bindparams
        if self.error:
            raise self.error
        return self.raw


def closed(call):
    with pytest.raises(AgentContractError, match=f'^{ERROR}$') as caught:
        call()
    assert caught.value.__suppress_context__
    assert 'private' not in str(caught.value)


@pytest.fixture
def inventory(tmp_path):
    journal = FakeReceiptJournal.provision(
        tmp_path / 'journal', FakeEpochPin(database_id=uuid4(), epoch_id=uuid4())
    )
    now = datetime.now(UTC)
    tenant, op, grant = uuid4(), uuid4(), uuid4()
    row = {
        'operation': {
            'tenant_id': str(tenant), 'id': str(op), 'actor_id': str(uuid4()),
            'request_id': 'SYN-PRIVATE', 'grant_id': str(grant), 'operation_key': 'a' * 64,
            'snapshot': {'private': 'clinical body'}, 'config_digest': 'b' * 64,
            'source_digest': 'c' * 64, 'created_at': now.isoformat(),
            'deadline': (now + timedelta(seconds=120)).isoformat(),
        },
        'grant': {
            'tenant_id': str(tenant), 'id': str(grant), 'mode': 'fake-only',
            'approval_ref': 'private approval', 'starts_at': now.isoformat(),
            'ends_at': (now + timedelta(minutes=10)).isoformat(), 'case_limit': 3,
            'concurrency_limit': 2, 'unit_limit': 30, 'units_per_attempt': 10,
        },
        'attempt': {
            'tenant_id': str(tenant), 'id': str(uuid4()), 'operation_id': str(op),
            'attempt_number': 1, 'submission_id': str(uuid4()), 'fence_id': str(uuid4()),
            'submitted_at': now.isoformat(),
        },
    }
    material = _Material.model_validate(row)
    checkpoint = checkpoint_from_material(material.operation, material.grant, material.attempt)
    raw = {'epoch': journal.pin.model_dump(mode='json'), 'entries': [row]}
    return SimpleNamespace(journal=journal, raw=raw, checkpoint=checkpoint)


@pytest.mark.parametrize('phase', ['empty', 'prepared', 'issued'])
def test_full_inventory_matches_and_check_returns_no_ticket(inventory, phase, monkeypatch):
    s = inventory
    if phase == 'empty':
        s.raw['entries'] = []
    else:
        s.journal.prepare(s.checkpoint)
        if phase == 'issued':
            s.journal.issue(s.checkpoint)
    engine = Engine(s.raw)
    original = s.journal.check

    def compare(expected):
        assert engine.active  # epoch transaction still held during external check
        original(expected)

    monkeypatch.setattr(s.journal, 'check', compare)
    assert FakeReceiptVerifier(engine, s.journal).check() is None
    assert not engine.active and engine.calls == 1


@pytest.mark.parametrize('schema', ['', None, 'public', 'ciq_agent_receipts; select 1'])
def test_schema_selector_is_trusted_and_fixed(inventory, schema):
    engine = Engine()
    closed(lambda: FakeReceiptVerifier(engine, inventory.journal, schema=schema))
    assert engine.calls == 0


@pytest.mark.parametrize('field', ['database_id', 'epoch_id'])
def test_same_inventory_wrong_epoch_denies(inventory, field):
    s = inventory
    s.raw['epoch'][field] = str(uuid4())
    closed(lambda: FakeReceiptVerifier(Engine(s.raw), s.journal).check())


@pytest.mark.parametrize('fault', [
    'missing_local', 'missing_external', 'issued_missing_local', 'snapshot', 'approval',
    'tenant', 'operation', 'grant', 'naive_time', 'extra', 'duplicate', 'too_many',
    'oversized', 'nan', 'closed', 'missing', 'bad_units', 'bad_window', 'bad_count',
])
def test_malformed_or_disagreeing_custody_is_closed_and_transaction_released(inventory, fault):
    s = inventory
    if fault != 'missing_external':
        s.journal.prepare(s.checkpoint)
    if fault in {'missing_local', 'issued_missing_local'}:
        if fault.startswith('issued'):
            s.journal.issue(s.checkpoint)
        s.raw['entries'] = []
    elif fault in {'snapshot', 'approval'}:
        group, key = ('operation', 'snapshot') if fault == 'snapshot' else ('grant', 'approval_ref')
        s.raw['entries'][0][group][key] = {} if fault == 'snapshot' else 'other'
    elif fault in {'tenant', 'operation', 'grant'}:
        group, key = {
            'tenant': ('attempt', 'tenant_id'), 'operation': ('attempt', 'operation_id'),
            'grant': ('grant', 'id'),
        }[fault]
        s.raw['entries'][0][group][key] = str(uuid4())
    elif fault == 'naive_time':
        s.raw['entries'][0]['attempt']['submitted_at'] = '2026-11-03T10:00:00'
    elif fault == 'extra':
        s.raw['permission'] = True
    elif fault in {'duplicate', 'too_many'}:
        s.raw['entries'] *= 2 if fault == 'duplicate' else 31
    elif fault == 'oversized':
        s.raw['entries'][0]['operation']['snapshot'] = {'private': 'x' * (4 * 1024 * 1024)}
    elif fault == 'nan':
        s.raw['entries'][0]['operation']['snapshot'] = {'private': float('nan')}
    elif fault == 'closed':
        s.journal.quarantine()
    elif fault == 'missing':
        s.journal.path.unlink()
    elif fault == 'bad_units':
        s.raw['entries'][0]['grant']['units_per_attempt'] = 31
    elif fault == 'bad_window':
        op = s.raw['entries'][0]['operation']
        op['deadline'] = op['created_at']
    elif fault == 'bad_count':
        s.raw['entries'][0]['grant']['case_limit'] = True
    engine = Engine(s.raw)
    closed(lambda: FakeReceiptVerifier(engine, s.journal).check())
    assert engine.calls == 1 and not engine.active


def test_sql_failure_is_sanitized_and_connection_released(inventory):
    engine = Engine(error=DBAPIError('private SQL', {'private': 'data'}, ValueError('private')))
    closed(lambda: FakeReceiptVerifier(engine, inventory.journal).check())
    assert not engine.active


def test_hashes_remain_canonical_across_timezone_offsets(inventory):
    row = copy.deepcopy(inventory.raw['entries'][0])
    for group, fields in {
        'operation': ['created_at', 'deadline'], 'grant': ['starts_at', 'ends_at'],
        'attempt': ['submitted_at'],
    }.items():
        for field in fields:
            row[group][field] = datetime.fromisoformat(row[group][field]).astimezone(
                timezone(timedelta(hours=5, minutes=30))
            ).isoformat()
    material = _Material.model_validate(row)
    assert checkpoint_from_material(
        material.operation, material.grant, material.attempt
    ) == inventory.checkpoint
    assert 'clinical body' not in repr(material)
