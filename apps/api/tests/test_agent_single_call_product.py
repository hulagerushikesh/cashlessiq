"""Original protected adapter with actual local sockets/SQLite, DB faults offline.

Fake DB projection/transaction controls are explicit here; actual PostgreSQL
authority/ACL/locking acceptance lives in the separately guarded Linux module.
"""

import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from test_agent_contracts import context
from test_agent_single_call_custody import assembly as assembly
from test_agent_single_call_custody import single_call_material as single_call_material

from ciq_api import agent_single_call_product as product
from ciq_api.agent_contracts import AgentContractError
from ciq_api.agent_provider_peer import ReviewedProviderPeerClient
from ciq_api.agent_single_call_peer import SingleCallReceiptClient


def projection(s):
    snapshot = s.snapshot
    facts, policy = snapshot.snapshots()
    b = snapshot.binding
    now = datetime.now(UTC)
    return {
        "operation_id": str(s.pin.operation_id), "pin": s.pin.canonical(),
        "pin_sha256": hashlib.sha256(s.pin.canonical().encode()).hexdigest(),
        "snapshot": snapshot.model_dump(mode="json"), "config": s.config.model_dump(mode="json"),
        "clinical": {
            "tenant_id": str(b.tenant_id), "request_id": b.request_id,
            "policy_id": str(b.policy_id),
            "facts": facts, "revision_inputs": facts, "revision_digest": b.input_digest,
            "input_revision": b.input_revision, "review_version": b.review_version,
            "record_input_digest": b.input_digest, "record_policy_version": b.policy_version,
            "record_rules_digest": b.rules_digest, "policy": policy,
        },
        "checked_at": now.isoformat(), "deadline": (now + timedelta(seconds=18)).isoformat(),
    }


def denied(call):
    with pytest.raises(AgentContractError, match=f"^{product.ERROR}$") as failure:
        call()
    assert failure.value.__suppress_context__


@pytest.fixture
def protected(assembly, monkeypatch):
    s = assembly
    state = {"phase": "staged", "open": 0, "fault": None, "published": [], "row": projection(s)}
    elapsed = [0.0]
    monkeypatch.setattr(product, "monotonic", lambda: elapsed[0])

    class Database:
        def scalar(self, statement, params):
            assert state["open"] == 1
            name = str(statement)
            assert params["operation"] == s.pin.operation_id
            if ".checkpoint(" in name:
                assert state["phase"] == "staged"
                if state["fault"] == "checkpoint":
                    raise ValueError("PRIVATE database")
                state["phase"] = "checkpointed"
            elif ".publication_context(" in name:
                assert state["phase"] == "checkpointed"
                if state["fault"] == "context":
                    raise ValueError("PRIVATE revoked scope")
            else:
                assert ".publish(" in name and state["phase"] == "checkpointed"
                if state["fault"] == "publication":
                    raise ValueError("PRIVATE write failure")
                state["published"].append(params)
                state["phase"] = "published"
                return None
            return deepcopy(state["row"])

    class Engine:
        @contextmanager
        def begin(self):
            before = state["phase"], deepcopy(state["published"])
            state["open"] += 1
            try:
                yield Database()
                if state["fault"] == "commit-before":
                    raise ValueError("PRIVATE failed COMMIT")
            except Exception:
                state["phase"], state["published"] = before
                raise
            finally:
                state["open"] -= 1
            if state["fault"] == "commit-after":
                raise ValueError("PRIVATE lost COMMIT acknowledgment")
            if state["fault"] == "slow-commit":
                elapsed[0] = 30
                s.state["elapsed"] = 30

    engine = Engine()
    exchange = ReviewedProviderPeerClient.exchange

    def checked_exchange(client, body, *, timeout):
        assert state["phase"] == "checkpointed" and state["open"] == 0
        return exchange(client, body, timeout=timeout)

    monkeypatch.setattr(ReviewedProviderPeerClient, "exchange", checked_exchange)

    def make(**changes):
        return product.ProductSingleCall(engine, **({
            "operation_id": s.pin.operation_id, "receipt": SingleCallReceiptClient(s.pin),
            "provider": ReviewedProviderPeerClient(s.journal.pin_sha256),
        } | changes))

    return SimpleNamespace(assembly=s, state=state, make=make, elapsed=elapsed)


def test_original_adapter_commits_before_io_and_publishes_private_advisory(protected):
    s = protected
    run = s.make()
    assert run.run() is None
    assert s.state["phase"] == "published" and len(s.state["published"]) == 1
    assert s.assembly.journal.status().phase == "observed"
    assert len(s.assembly.state["calls"]) == 1
    for action in (run.run, run.dispatch, run.publish, s.make().run):
        denied(action)
    assert len(s.state["published"]) == len(s.assembly.state["calls"]) == 1


def test_premature_publication_consumes_the_original_entry_without_later_issue(protected):
    s = protected
    run = s.make()
    for action in (run.publish, run.dispatch, run.run, run.publish):
        denied(action)
    assert not s.assembly.state["commands"] and s.state["phase"] == "staged"


def test_publication_competing_with_inflight_dispatch_cannot_recover_a_later_reply(protected):
    s = protected
    s.assembly.state["entered"], s.assembly.state["release"] = threading.Event(), threading.Event()
    run = s.make()
    with ThreadPoolExecutor(max_workers=1) as pool:
        dispatched = pool.submit(run.dispatch)
        assert s.assembly.state["entered"].wait(2)
        try:
            denied(run.publish)
        finally:
            s.assembly.state["release"].set()
        denied(lambda: dispatched.result(timeout=3))
    denied(run.publish)
    assert s.assembly.journal.status().phase == "observed"
    assert not s.state["published"] and len(s.assembly.state["calls"]) == 1


@pytest.mark.parametrize("fault,phase", [
    ("checkpoint", "staged"), ("commit-before", "staged"),
    ("commit-after", "checkpointed"), ("slow-commit", "checkpointed"),
])
def test_no_issue_or_provider_after_failed_ambiguous_or_expired_checkpoint(protected, fault, phase):
    s = protected
    s.state["fault"] = fault
    run = s.make()
    denied(run.dispatch)
    s.state["fault"] = None
    denied(run.dispatch)
    denied(run.publish)
    assert s.state["phase"] == phase and not s.state["published"]
    assert s.assembly.journal.status().phase == "ready"
    assert not s.assembly.state["commands"] and not s.assembly.state["calls"]


@pytest.mark.parametrize("field", ["pin", "pin_sha256", "operation_id", "config", "clinical"])
def test_corrupt_projection_rolls_back_before_any_issue(protected, field):
    s = protected
    row = s.state["row"]
    if field == "pin":
        row[field] += " "  # Even equivalent JSON must be the exact canonical pin.
    elif field == "config":
        row[field]["tokens"] = 512
    elif field == "clinical":
        row[field]["review_version"] += 1
    else:
        row[field] = "0" * 64 if field == "pin_sha256" else str(uuid4())
    denied(s.make().dispatch)
    assert s.state["phase"] == "staged" and not s.assembly.state["commands"]


@pytest.mark.parametrize("fault", ["context", "publication", "commit-before", "commit-after"])
def test_publication_failure_never_reconstructs_response_or_retries(protected, fault):
    s = protected
    run = s.make()
    run.dispatch()
    retained = s.assembly.journal.status()
    s.state["fault"] = fault
    denied(run.publish)
    s.state["fault"] = None
    denied(run.publish)
    denied(s.make().dispatch)
    assert s.assembly.journal.status() == retained
    assert len(s.assembly.state["calls"]) == 1
    assert len(s.state["published"]) == int(fault == "commit-after")


@pytest.mark.parametrize("field", ["snapshot", "pin_sha256", "config", "deadline"])
def test_changed_publication_material_denies_original_candidate(protected, field):
    s = protected
    run = s.make()
    run.dispatch()
    if field == "snapshot":
        s.state["row"][field]["binding"]["correlation_id"] = str(uuid4())
    elif field == "pin_sha256":
        s.state["row"][field] = "0" * 64
    elif field == "config":
        s.state["row"][field]["model"] = "changed-model"
    else:
        s.state["row"][field] = s.assembly.pin.ends_at.isoformat()
    denied(run.publish)
    assert not s.state["published"] and s.assembly.journal.status().phase == "observed"


@pytest.mark.parametrize("ceiling", [None, True, "later", float("inf"), float("nan"), -1, 3])
def test_absolute_monotonic_ceiling_cannot_create_or_extend_permission(assembly, ceiling):
    run = assembly.make()
    if ceiling is None:
        run.dispatch(context(assembly.snapshot),
                     monotonic_deadline=1_000_000)
        assert assembly.state["budget"] <= 12
    else:
        with pytest.raises(AgentContractError):
            run.dispatch(context(assembly.snapshot),
                         monotonic_deadline=ceiling)
        assert not assembly.state["commands"]
