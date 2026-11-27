"""Real retained SQLite and child, simulated clinical DB transaction boundary."""

import json
import sys

import pytest
from test_agent_captured_exchange import CONFIG, HELPER, fixture_for
from test_agent_contracts import candidate, context
from test_agent_custody_dispatch_offline import dispatch as dispatch
from test_agent_custody_publication_offline import publication as publication
from test_agent_custody_submission_offline import custody as custody
from test_agent_custody_submission_offline import instance
from test_agent_provider_response import body, text, tool
from test_agent_receipt_verifier_offline import closed
from test_agent_receipt_verifier_offline import inventory as inventory

from ciq_api.agent_contracts import canonical_json
from ciq_api.agent_executor import BoundedFakeProcess, FakeProcessRequest
from ciq_api.agent_one_shot import prepare_captured_one_shot


@pytest.fixture
def captured(publication, tmp_path, monkeypatch):
    s = publication
    prepared = prepare_captured_one_shot(
        s.snapshot, context(s.snapshot), s.claim.operation_id, CONFIG,
    )
    s.engine.material["entries"][0]["operation"]["config_digest"] = prepared.config_digest
    path = tmp_path / "captured.json"
    s.transport = BoundedFakeProcess((sys.executable, "-I", str(HELPER), str(path)))
    original = s.transport.exchange
    s.fault = None
    s.exchanges = []

    def exchange(raw, *, timeout):
        assert not s.engine.active  # No simulated clinical transaction across child I/O.
        with s.journal._connection() as db:
            assert db.execute("SELECT state FROM receipt").fetchall() == [("issued",)]
        packet = FakeProcessRequest.model_validate_json(raw)
        value = candidate(packet.snapshot, packet.operation_id)
        if s.fault == "money":
            value["payable_inr"] = 1
        response = body([tool()] if s.fault == "tool" else [text(canonical_json(value))])
        if s.fault == "warning":
            response["warnings"] = [{"code": "399569", "message": "PRIVATE"}]
        path.write_text(canonical_json(fixture_for(raw, response=response)))
        path.chmod(0o600)
        s.exchanges.append(raw)
        return original(raw, timeout=timeout)

    monkeypatch.setattr(s.transport, "exchange", exchange)
    s.coordinator = instance(s, transport=s.transport)
    return s


def test_captured_profile_runs_after_durable_issue_and_publishes_only_validated_candidate(captured):
    s = captured
    assert s.coordinator.run() is None
    assert len(s.exchanges) == len(s.writes) == 1
    assert json.loads(s.writes[0]["candidate"]) == candidate(s.snapshot, s.claim.operation_id)
    assert s.engine.calls[-4:] == ["observe", "context", "publish", "commit"]
    closed(s.coordinator.run)
    closed(instance(s, transport=s.transport).dispatch)


@pytest.mark.parametrize("fault", ("money", "tool", "warning"))
def test_rejected_provider_aggregate_keeps_issued_tombstone_and_never_retries(captured, fault):
    s = captured
    s.fault = fault
    closed(s.coordinator.run)
    assert len(s.exchanges) == 1 and not s.writes and s.coordinator._candidate is None
    with s.journal._connection() as db:
        assert db.execute("SELECT state FROM receipt").fetchall() == [("issued",)]
    closed(s.coordinator.run)
    closed(s.coordinator.dispatch)
    closed(instance(s, transport=s.transport).dispatch)


def test_validated_child_reply_still_requires_fresh_publication_scope(captured):
    s = captured
    s.coordinator.prepare()
    s.coordinator.dispatch()
    s.context_change = lambda projection: projection["clinical"].update(review_version=99)
    closed(s.coordinator.publish)
    assert len(s.exchanges) == 1 and not s.writes
    closed(s.coordinator.dispatch)
