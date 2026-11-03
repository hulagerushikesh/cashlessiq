"""Private deterministic publication on the retained restricted transaction, offline."""

import base64
import copy
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from test_agent_contracts import POLICY, candidate, capture
from test_agent_custody_dispatch_offline import dispatch as dispatch
from test_agent_custody_submission_offline import custody as custody
from test_agent_custody_submission_offline import instance
from test_agent_receipt_verifier_offline import closed
from test_agent_receipt_verifier_offline import inventory as inventory

from ciq_api import agent_custody_submission as module
from ciq_api.agent_contracts import AgentContractError, canonical_json
from ciq_api.agent_executor import BoundedFakeProcess, FakeProcessRequest

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def publication(dispatch, tmp_path, monkeypatch):
    s = dispatch
    fixture = tmp_path / 'fixture.json'
    s.transport = BoundedFakeProcess((
        sys.executable, '-I', str(ROOT / 'apps/agent-transport/tests/exchange_fixture.py'),
        str(ROOT / 'apps/agent-transport/fake_transport.py'), str(fixture),
    ))
    original = s.transport.exchange
    s.response_change = lambda body: None

    def exchange(raw, *, timeout):
        assert not s.engine.active
        request = FakeProcessRequest.model_validate_json(raw)
        body = candidate(request.snapshot, request.operation_id)
        s.response_change(body)
        fixture.write_text(json.dumps({
            'request_sha256': hashlib.sha256(raw).hexdigest(),
            'candidate_base64': base64.b64encode(json.dumps(body).encode()).decode(),
        }))
        fixture.chmod(0o600)
        s.exchanges.append((raw, timeout))
        return original(raw, timeout=timeout)

    monkeypatch.setattr(s.transport, 'exchange', exchange)
    s.coordinator = instance(s, transport=s.transport)
    scalar = s.engine.scalar
    s.writes = []
    s.context_change = lambda projection: None

    def run(statement, params=None):
        assert s.engine.active
        name = str(statement)
        if 'publication_context_fake' in name:
            s.engine.calls.append('context')
            facts, policy = s.snapshot.snapshots()
            b = s.snapshot.binding
            row = {
                'checkpoint': copy.deepcopy(s.engine.receipt), **s.engine.issue_projection,
                'window_end': s.engine.issue_projection['deadline'],
                'clinical': {
                    'tenant_id': str(b.tenant_id), 'request_id': b.request_id,
                    'policy_id': str(b.policy_id), 'input_revision': b.input_revision,
                    'review_version': b.review_version, 'revision_digest': b.input_digest,
                    'record_input_digest': b.input_digest, 'record_rules_digest': b.rules_digest,
                    'record_policy_version': b.policy_version,
                    'facts': facts, 'revision_inputs': copy.deepcopy(facts), 'policy': policy,
                },
            }
            s.context_change(row)
            return row
        if any(n in name for n in ('publish_comparison_fake', 'heartbeat_submitted_fake')):
            s.engine.calls.append('publish' if 'publish_comparison_fake' in name else 'heartbeat')
            s.writes.append(copy.deepcopy(params))
            return {**s.engine.receipt, 'version': params['version'] + 1}
        return scalar(statement, params)

    monkeypatch.setattr(s.engine, 'scalar', run)
    return s


def ready(s):
    s.coordinator.prepare()
    s.prepared_backup = s.journal.path.read_bytes()
    s.coordinator.dispatch()


@pytest.mark.parametrize('index', range(len(POLICY['examples'])))
def test_every_golden_candidate_validates_under_same_transaction_before_private_write(
    publication, monkeypatch, index,
):
    s = publication
    s.snapshot = capture(
        index, tenant_id=s.snapshot.binding.tenant_id, request_id='SYN-PRIVATE',
    )
    s.engine.material['entries'][0]['operation']['snapshot'] = s.snapshot.model_dump(mode='json')
    ready(s)
    original = module.validate_candidate

    def validated(*args):
        assert s.engine.active
        assert s.engine.calls[-1] == 'context' and not s.writes
        return original(*args)

    monkeypatch.setattr(module, 'validate_candidate', validated)
    assert s.coordinator.publish() is None
    assert json.loads(s.writes[0]['candidate']) == candidate(s.snapshot, s.claim.operation_id)
    assert s.engine.calls[-4:] == ['observe', 'context', 'publish', 'commit']
    assert s.coordinator._candidate is None and len(s.exchanges) == 1
    closed(s.coordinator.publish)
    closed(s.coordinator.dispatch)
    closed(instance(s, transport=s.transport).publish)


@pytest.mark.parametrize('field,value', [
    ('payable_inr', '95000'), ('payable_inr', True), ('payable_inr', -1),
    ('payable_inr', 1), ('outcome', 'QUERY'), ('run_id', str(uuid4())),
    ('citations', []), ('extra', 'private'),
])
def test_invalid_money_result_citations_and_binding_never_reach_write(publication, field, value):
    s = publication
    s.response_change = lambda body: body.update({field: value})
    ready(s)
    closed(s.coordinator.publish)
    closed(s.coordinator.publish)
    assert not s.writes and len(s.exchanges) == 1


@pytest.mark.parametrize('change', ['citation_content', 'line_money', 'binding'])
def test_full_nested_candidate_validation_precedes_write(publication, change):
    s = publication

    def alter(body):
        if change == 'citation_content':
            body['citations'][0]['source_digest'] = '0' * 64
        elif change == 'line_money':
            body['lines'][0]['payable_inr'] += 1
        else:
            body['binding']['tenant_id'] = str(uuid4())

    s.response_change = alter
    ready(s)
    closed(s.coordinator.publish)
    assert not s.writes


@pytest.mark.parametrize('field', [
    'facts', 'revision_inputs', 'revision_digest', 'record_input_digest',
    'record_policy_version', 'record_rules_digest', 'request_id', 'tenant_id',
    'policy_id', 'input_revision', 'review_version', 'policy',
])
def test_fresh_projection_is_independently_parsed_and_bound(publication, field):
    s = publication
    ready(s)

    def alter(projection):
        clinical = projection['clinical']
        if field in {'facts', 'revision_inputs'}:
            clinical[field]['member_reference'] = 'private changed facts'
        elif field == 'policy':
            clinical[field]['clauses'][0]['text'] = 'private changed wording'
        elif field in {'input_revision', 'review_version'}:
            clinical[field] += 1
        elif field in {'tenant_id', 'policy_id'}:
            clinical[field] = str(uuid4())
        else:
            clinical[field] = 'private wrong value'

    s.context_change = alter
    closed(s.coordinator.publish)
    assert not s.writes


@pytest.mark.parametrize('action', ['publish', 'heartbeat'])
@pytest.mark.parametrize('fault', ['missing', 'closed', 'extra', 'prepared', 'commit', 'expired'])
def test_post_exchange_custody_or_commit_failure_never_restores_candidate(
    publication, monkeypatch, action, fault,
):
    s = publication
    ready(s)
    if fault == 'missing':
        s.journal.path.unlink()
    elif fault == 'closed':
        s.journal.quarantine()
    elif fault == 'extra':
        from ciq_api.agent_admission import FakeCheckpoint
        s.journal.prepare(FakeCheckpoint(
            tenant_id=uuid4(), request_id='forgotten', operation_id=uuid4(),
            submission_id=uuid4(), digest='a' * 64,
        ))
    elif fault == 'prepared':
        # Simulated independent store rewind: never repair or issue it again.
        s.journal.path.write_bytes(s.prepared_backup)
    elif fault == 'commit':
        s.engine.commit_error = True
    else:
        monkeypatch.setattr(module, 'monotonic', lambda: 1e20)
    closed(getattr(s.coordinator, action))
    closed(s.coordinator.publish)
    closed(s.coordinator.heartbeat)
    closed(s.coordinator.dispatch)
    assert s.coordinator._candidate is None and len(s.exchanges) == 1
    if fault not in {'commit'}:
        assert not s.writes


def test_heartbeat_keeps_same_response_and_original_issue_budget(publication):
    s = publication
    ready(s)
    original = s.coordinator._candidate
    assert s.coordinator.heartbeat() is None
    current = s.coordinator._candidate
    assert current[0] == original[0].model_copy(update={'version': original[0].version + 1})
    assert current[1:] == original[1:] and 'candidate' not in s.writes[0]
    s.engine.receipt['version'] += 1  # simulated confirmed DB heartbeat state
    assert s.coordinator.publish() is None
    assert s.writes[-1]['version'] == current[0].version
    assert len(s.exchanges) == 1


def test_concurrent_publication_on_original_instance_has_one_winner(publication):
    s = publication
    ready(s)
    barrier = Barrier(2)

    def run(_):
        barrier.wait(timeout=3)
        try:
            s.coordinator.publish()
            return True
        except AgentContractError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(run, range(2))) == [False, True]
    assert len(s.writes) == len(s.exchanges) == 1


@pytest.mark.parametrize('action', ['publish', 'heartbeat'])
def test_no_public_candidate_identity_or_validated_attestation(publication, action):
    s = publication
    closed(getattr(s.coordinator, action))
    ready(s)
    with pytest.raises(TypeError):
        getattr(s.coordinator, action)(candidate={}, validated=True, tenant_id=uuid4())
    assert getattr(s.coordinator, action)() is None


def test_original_deadline_is_not_widened_by_fresh_projection(publication):
    s = publication
    ready(s)
    receipt, raw, _deadline, end, retained = s.coordinator._candidate
    s.coordinator._candidate = (
        receipt, raw, datetime.now(UTC) - timedelta(seconds=1), end, retained,
    )
    closed(s.coordinator.publish)
    assert not s.writes


def test_candidate_is_bounded_before_sql_even_with_large_unverified_explanation(publication):
    s = publication
    s.response_change = lambda body: body.update(explanation='private' * 1000)
    ready(s)
    closed(s.coordinator.publish)
    assert not s.writes


def test_journal_issued_check_never_returns_a_permit(publication):
    s = publication
    ready(s)
    with s.engine.begin() as db:
        _, history = s.coordinator._verifier._observe(db)
        assert s.journal.check_issued(history, history[0]) is None
    assert canonical_json(json.loads(s.coordinator._candidate[1]))


@pytest.mark.parametrize('action', ['publish', 'heartbeat'])
@pytest.mark.parametrize('field,value', [
    ('checked_at', None), ('deadline', '2000-01-01T00:00:00Z'),
    ('deadline', '2100-01-01T00:00:00Z'), ('window_end', '2100-01-01T00:00:00Z'),
    ('clinical', {'private': 'malformed'}),
])
def test_invalid_or_expanded_publication_projection_sacrifices_candidate(
    publication, action, field, value,
):
    s = publication
    ready(s)
    s.context_change = lambda projection: projection.update({field: value})
    closed(getattr(s.coordinator, action))
    closed(s.coordinator.publish)
    assert not s.writes


def test_validation_elapsed_budget_rolls_back_before_narrow_write(publication, monkeypatch):
    s = publication
    ready(s)
    original = module.validate_candidate

    def expired(*args):
        result = original(*args)
        monkeypatch.setattr(module, 'monotonic', lambda: 1e20)
        return result

    monkeypatch.setattr(module, 'validate_candidate', expired)
    closed(s.coordinator.publish)
    assert not s.writes
