"""Original assembly through actual local sockets/retention, no provider I/O."""

import hashlib
import json
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from single_call_fixtures import call_material, response_bytes
from test_agent_contracts import context

from ciq_api import agent_provider_peer as provider_peer
from ciq_api import agent_single_call_custody as custody
from ciq_api import agent_single_call_peer as receipt_peer
from ciq_api.agent_contracts import AgentContractError, canonical_json
from ciq_api.agent_single_call_journal import SingleCallJournal


def denied(call):
    with pytest.raises(AgentContractError, match=f"^{custody.ERROR}$") as caught:
        call()
    assert caught.value.__suppress_context__


@pytest.fixture
def assembly(tmp_path, monkeypatch):
    snapshot, config, pin, body = call_material()
    journal = SingleCallJournal.provision(tmp_path / "retained", pin)
    state = {"fault": None, "calls": [], "commands": [],
             "raw": response_bytes(snapshot, pin.operation_id),
             "elapsed": 0.0, "wall": datetime.now(UTC), "errors": []}
    directory = tempfile.TemporaryDirectory(prefix="ciq-assembly-", dir="/tmp")
    root = Path(directory.name)
    monkeypatch.setattr(provider_peer, "ENDPOINT", root / "provider.sock")
    monkeypatch.setattr(receipt_peer, "ENDPOINT", root / "receipt.sock")
    for module, names in ((provider_peer, ("_path", "_custody_guard", "provider_guard", "_peer")),
                          (receipt_peer, ("_path", "_guard", "_peer"))):
        for name in names:
            monkeypatch.setattr(module, name, lambda *args, **kwargs: None)
    monkeypatch.setattr(receipt_peer, "IPC_SECONDS", 0.5)
    monkeypatch.setattr(custody, "monotonic", lambda: state["elapsed"])

    class Clock:
        @staticmethod
        def now(_tz):
            return state["wall"]

    monkeypatch.setattr(custody, "datetime", Clock)

    class Attempt:
        def exchange_reviewed(self, received, *, timeout, pin_sha256):
            assert journal.status().phase == "issued"
            assert received == body and pin_sha256 == journal.pin_sha256
            state["calls"].append((received, timeout))
            if state.get("entered"):
                state["entered"].set()
                assert state["release"].wait(2)
            if state["fault"] == "provider":
                raise ValueError("PRIVATE provider diagnostic")
            return state["raw"]

    monkeypatch.setattr(provider_peer, "PrivateProviderAttempt", Attempt)
    send = receipt_peer._send

    def receipt_send(connection, marker, value, end):
        if marker == receipt_peer._RESPONSE and state["fault"] == value.command + "-ack":
            raise OSError("PRIVATE lost acknowledgment")
        return send(connection, marker, value, end)

    monkeypatch.setattr(receipt_peer, "_send", receipt_send)

    def serve(server, call, endpoint, *, provider=False):
        endpoint.unlink(missing_ok=True)  # Fixture's own quiescent endpoint only.
        server.bind()

        def run():
            try:
                if provider:
                    server.serve_once(timeout=0.5)
                else:
                    server.serve_once()
            except ValueError as error:
                state["errors"].append(str(error))

        thread = threading.Thread(target=run)
        thread.start()
        try:
            return call()
        finally:
            thread.join(2)
            assert not thread.is_alive()
            server.close()

    original_issue = receipt_peer.SingleCallReceiptClient.issue
    original_observe = receipt_peer.SingleCallReceiptClient.observe
    original_exchange = provider_peer.ReviewedProviderPeerClient.exchange

    def issue(client):
        state["commands"].append("issue")
        if state["fault"] == "issue-before":
            raise OSError("PRIVATE unavailable custody")
        result = serve(receipt_peer.SingleCallReceiptPeer(journal),
                       lambda: original_issue(client), receipt_peer.ENDPOINT)
        state["elapsed"] += state.get("issue_elapsed", 0)
        state["wall"] += state.get("issue_wall", timedelta(0))
        return result

    def observe(client, *args, **kwargs):
        state["commands"].append("observe")
        result = serve(receipt_peer.SingleCallReceiptPeer(journal),
                       lambda: original_observe(client, *args, **kwargs), receipt_peer.ENDPOINT)
        state["elapsed"] += state.get("observe_elapsed", 0)
        return result

    def exchange(client, received, *, timeout):
        result = serve(provider_peer.ReviewedProviderPeer(client.pin_sha256),
                       lambda: original_exchange(client, received, timeout=timeout),
                       provider_peer.ENDPOINT, provider=True)
        state["elapsed"] += state.get("provider_elapsed", 0)
        state["wall"] += state.get("provider_wall", timedelta(0))
        state["budget"] = timeout
        return result

    monkeypatch.setattr(receipt_peer.SingleCallReceiptClient, "issue", issue)
    monkeypatch.setattr(receipt_peer.SingleCallReceiptClient, "observe", observe)
    monkeypatch.setattr(provider_peer.ReviewedProviderPeerClient, "exchange", exchange)

    def make(**changes):
        kwargs = dict(snapshot=snapshot, current=context(snapshot), config=config, pin=pin,
                      receipt=receipt_peer.SingleCallReceiptClient(pin),
                      provider=provider_peer.ReviewedProviderPeerClient(journal.pin_sha256))
        return custody.PreparedSingleCallCustody(**(kwargs | changes))

    yield SimpleNamespace(state=state, snapshot=snapshot, config=config, pin=pin, body=body,
                          journal=journal, make=make)
    assert all(error in (receipt_peer.ERROR, provider_peer.ERROR) for error in state["errors"])
    directory.cleanup()


def test_original_dispatch_observes_before_private_candidate_and_cannot_reissue(assembly):
    s = assembly
    original = s.make()
    assert original.dispatch(context(s.snapshot)) is None
    status = s.journal.status()
    assert status.phase == "observed" and status.uncertain_units == s.pin.reserved_units
    assert status.response_sha256 == hashlib.sha256(s.state["raw"]).hexdigest()
    assert status.reported_usage.input_tokens is status.reported_usage.output_tokens is None
    assert s.state["commands"] == ["issue", "observe"]
    assert len(s.state["calls"]) == 1 and 0 < s.state["budget"] <= 12
    final = original.take_candidate(context(s.snapshot))
    assert final.candidate.binding == s.snapshot.binding
    assert final.observation.provider_run_id == "opaque-observed-id"
    for call in (lambda: original.dispatch(context(s.snapshot)),
                 lambda: original.take_candidate(context(s.snapshot)),
                 lambda: s.make().dispatch(context(s.snapshot))):
        denied(call)
    assert len(s.state["calls"]) == 1 and s.journal.status() == status


@pytest.mark.parametrize("field,value", [
    ("operation_id", uuid4()), ("binding_sha256", "0" * 64),
    ("request_sha256", "0" * 64), ("config_sha256", "0" * 64),
    ("source_sha256", "0" * 64), ("provider_identity_sha256", "0" * 64),
    ("approval_sha256", "0" * 64), ("epoch_id", uuid4()), ("database_id", uuid4()),
    ("grant_id", uuid4()), ("submission_id", uuid4()), ("reserved_units", 21),
    ("provider_seconds", 7), ("max_tokens", 512),
    ("hostname", "another-reviewed.snowflakecomputing.com"), ("reserved_units", True),
])
def test_changed_or_unsafe_pin_cannot_reach_either_peer(assembly, field, value):
    denied(lambda: assembly.make(pin=assembly.pin.model_copy(update={field: value})))
    assert not assembly.state["commands"] and not assembly.state["calls"]


@pytest.mark.parametrize("replacement", ["receipt", "provider", "config", "snapshot"])
def test_unreviewed_types_cannot_be_injected(assembly, replacement):
    denied(lambda: assembly.make(**{replacement: SimpleNamespace(PRIVATE="selector")}))
    assert not assembly.state["commands"]


@pytest.mark.parametrize("fault,phase,attempts", [
    ("issue-before", "ready", 0), ("issue-ack", "issued", 0),
    ("provider", "issued", 1), ("observe-ack", "observed", 1),
])
def test_commit_and_ack_ambiguity_holds_history_and_never_dispatches_twice(
    assembly, fault, phase, attempts,
):
    s = assembly
    s.state["fault"] = fault
    original = s.make()
    denied(lambda: original.dispatch(context(s.snapshot)))
    denied(lambda: original.dispatch(context(s.snapshot)))
    denied(lambda: original.take_candidate(context(s.snapshot)))
    assert s.journal.status().phase == phase and len(s.state["calls"]) == attempts
    if phase != "ready":
        assert s.journal.status().uncertain_units == s.pin.reserved_units
        s.state["fault"] = None
        denied(lambda: s.make().dispatch(context(s.snapshot)))
        assert len(s.state["calls"]) == attempts


@pytest.mark.parametrize("flag", ["tenant_active", "policy_approved", "clinical_authorized",
                                   "review_open"])
def test_revoked_scope_before_issue_or_handoff_does_not_publish(assembly, flag):
    s = assembly
    original = s.make()
    denied(lambda: original.dispatch(context(s.snapshot, **{flag: False})))
    assert not s.state["commands"] and s.journal.status().phase == "ready"
    original = s.make()
    original.dispatch(context(s.snapshot))
    denied(lambda: original.take_candidate(context(s.snapshot, **{flag: False})))
    denied(lambda: original.take_candidate(context(s.snapshot)))
    assert s.journal.status().phase == "observed" and len(s.state["calls"]) == 1


def test_stale_revision_or_corrupt_context_is_not_normalized(assembly):
    s = assembly
    original = s.make()
    original.dispatch(context(s.snapshot))
    wrong = s.snapshot.binding.model_copy(update={"review_version": 3})
    denied(lambda: original.take_candidate(context(s.snapshot, binding=wrong)))
    invalid = s.snapshot.binding.model_copy(update={"review_version": True})
    denied(lambda: s.make(current=context(s.snapshot, binding=invalid)))
    assert s.journal.status().phase == "observed"


@pytest.mark.parametrize("fault", ["money", "citation", "operation", "tool", "malformed"])
def test_received_bad_answer_is_never_repaired_retried_or_published(assembly, fault):
    s = assembly
    value = json.loads(s.state["raw"])
    answer = json.loads(value["content"][0]["text"])
    if fault == "money":
        answer["payable_inr"] = "95000"
    elif fault == "citation":
        answer["citations"][0]["source_digest"] = "0" * 64
    elif fault == "operation":
        answer["run_id"] = str(uuid4())
    value["content"][0]["text"] = canonical_json(answer)
    if fault == "tool":
        value["content"].append({"type": "tool_use", "tool_use": {"name": "PRIVATE"}})
    s.state["raw"] = b"PRIVATE invalid aggregate" if fault == "malformed" else (
        canonical_json(value).encode()
    )
    original = s.make()
    if fault == "malformed":
        denied(lambda: original.dispatch(context(s.snapshot)))
        assert s.journal.status().phase == "issued"
    else:
        original.dispatch(context(s.snapshot))
        assert s.journal.status().phase == "observed"
    denied(lambda: original.take_candidate(context(s.snapshot)))
    denied(lambda: s.make().dispatch(context(s.snapshot)))
    assert len(s.state["calls"]) == 1


def test_receipt_time_reduces_original_provider_budget_and_never_resets_deadline(assembly):
    s = assembly
    s.state["issue_elapsed"] = 3
    original = s.make()
    original.dispatch(context(s.snapshot))
    assert s.state["budget"] == 11  # 18 - 3 - 4 reserved for cleanup/observation.
    s.state["elapsed"] = custody.ATTEMPT_SECONDS
    denied(lambda: original.take_candidate(context(s.snapshot)))
    assert s.journal.status().phase == "observed"


def test_competing_dispatches_and_handoffs_cannot_duplicate_original_attempt(assembly):
    s = assembly
    s.state.update(entered=threading.Event(), release=threading.Event())
    original = s.make()
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(original.dispatch, context(s.snapshot))
        assert s.state["entered"].wait(1)
        try:
            # Receipt commit is already visible while the original exchange is
            # still in flight. A second call cannot obtain its in-memory body.
            assert s.journal.status().phase == "issued"
            denied(lambda: original.dispatch(context(s.snapshot)))
        finally:
            s.state["release"].set()
        assert first.result(timeout=2) is None

        def handoff():
            try:
                return original.take_candidate(context(s.snapshot))
            except AgentContractError:
                return None

        results = list(executor.map(lambda _: handoff(), range(2)))
    assert sum(value is not None for value in results) == 1
    assert len(s.state["calls"]) == 1 and s.journal.status().phase == "observed"


@pytest.mark.parametrize("stage", ["before-issue", "after-issue", "after-provider",
                                    "after-observe", "handoff", "rollback"])
def test_time_and_wall_rollback_faults_consume_original_permission(assembly, stage):
    s = assembly
    original = s.make()
    if stage == "before-issue":
        s.state["wall"] = s.pin.ends_at - timedelta(seconds=17)
    elif stage == "after-issue":
        s.state["issue_elapsed"] = 5
    elif stage == "after-provider":
        s.state["provider_elapsed"] = 18
    elif stage == "after-observe":
        s.state["observe_elapsed"] = 18
    elif stage == "rollback":
        s.state["issue_wall"] = timedelta(seconds=-1)
    if stage == "handoff":
        original.dispatch(context(s.snapshot))
        s.state["elapsed"] = 18
    else:
        denied(lambda: original.dispatch(context(s.snapshot)))
    denied(lambda: original.dispatch(context(s.snapshot)))
    denied(lambda: original.take_candidate(context(s.snapshot)))
    assert len(s.state["calls"]) == (stage in {"after-provider", "after-observe", "handoff"})
    assert s.journal.status().phase == (
        "ready" if stage == "before-issue" else
        "observed" if stage in {"after-observe", "handoff"} else "issued"
    )
