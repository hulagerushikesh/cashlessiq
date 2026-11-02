"""Offline fault injection; fake gateway only, no database or paid calls."""

import ast
import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from importlib.resources import files
from uuid import uuid4

import pytest
from pydantic import ValidationError

from ciq_api.agent_contracts import (
    MAX_RESPONSE_BYTES,
    AgentContext,
    AgentContractError,
    AgentInput,
    canonical_json,
    capture_input,
    parse_candidate,
    validate_candidate,
)
from ciq_api.agent_simulation import (
    comparison_for_publication,
    receive_fake_result,
    reserve_fake_call,
    uncertain_fake_call,
)
from ciq_api.assessment import calculate, calculate_rules

NOW = datetime(2026, 11, 2, 5, tzinfo=UTC)
POLICY = json.loads(files("ciq_api").joinpath("fixtures/policy-template.json").read_text())


def capture(index=0, **changes):
    kwargs = dict(
        tenant_id=uuid4(),
        request_id="REQ-FAKE-ONLY",
        policy_id=uuid4(),
        input_revision=1,
        review_version=2,
        correlation_id=uuid4(),
        facts=deepcopy(POLICY["examples"][index]["facts"]),
        policy=deepcopy(POLICY),
    )
    return capture_input(**{**kwargs, **changes})


def context(snapshot, **changes):
    return AgentContext(
        **{
            "binding": snapshot.binding,
            "tenant_active": True,
            "policy_approved": True,
            "clinical_authorized": True,
            "review_open": True,
            **changes,
        }
    )


def candidate(snapshot, run_id):
    facts, policy = snapshot.snapshots()
    result = calculate_rules(
        snapshot.binding.request_id,
        facts,
        {k: policy[k] for k in ("product_id", "version", "rules")},
    )
    refs = {(ref.kind, ref.source_id): ref.model_dump(mode="json") for ref in snapshot.evidence()}
    return {
        "binding": snapshot.binding.model_dump(mode="json"),
        "run_id": str(run_id),
        "outcome": result["outcome"],
        "claimed_inr": result["claimed_inr"],
        "payable_inr": result["payable_inr"],
        "lines": [
            {
                **{k: line[k] for k in ("item", "claimed_inr", "payable_inr", "deduction_inr")},
                "citations": [refs[(c["type"], c["id"])] for c in line["citations"]],
            }
            for line in result["payable"]["lines"]
        ]
        if result["payable"]
        else [],
        "citations": [
            refs[("record", snapshot.binding.request_id)],
            *(refs[("clause", cid)] for cid in result["clause_ids"]),
        ],
        "explanation": "Synthetic fake explanation; human review required.",
    }


class FakeGateway:
    def __init__(self, *, fault=None):
        self.calls = []
        self.fault = fault

    def invoke(self, run):
        self.calls.append(run.run_id)
        if self.fault is not None:
            raise self.fault
        return canonical_json(candidate(run.snapshot, run.run_id)).encode()


def submit_fake(snapshot, current, gateway, *, prior=None):
    run = reserve_fake_call(
        snapshot,
        current,
        run_id=uuid4(),
        fence_id=uuid4(),
        now=NOW,
        deadline=NOW + timedelta(seconds=120),
        prior=prior,
    )
    try:
        raw = gateway.invoke(run)
    except (TimeoutError, ConnectionError):
        return uncertain_fake_call(run)
    return receive_fake_result(run, current, fence_id=run.fence_id, now=NOW, raw=raw)


@pytest.mark.parametrize("index", range(len(POLICY["examples"])))
def test_all_thirty_golden_inputs_validate_without_agent_parity_claim(index):
    snapshot = capture(index)
    expected = POLICY["examples"][index]
    gateway = FakeGateway()
    run = submit_fake(snapshot, context(snapshot), gateway)
    output = comparison_for_publication(
        run, context(snapshot), fence_id=run.fence_id, now=NOW + timedelta(seconds=1)
    )
    assert len(gateway.calls) == 1
    assert output.outcome == expected["expected_outcome"]
    assert output.payable_inr == expected["expected_payable_inr"]
    # Shared calculation entry points stay identical, including every monetary
    # line, check, query and citation; this is fake comparison, not live parity.
    facts, policy = snapshot.snapshots()
    assert calculate(snapshot.binding.request_id, facts, POLICY) == calculate_rules(
        snapshot.binding.request_id,
        facts,
        {k: policy[k] for k in ("product_id", "version", "rules")},
    )
    if output.outcome in {"QUERY", "REFER"}:
        assert output.payable_inr is None and output.lines == ()


def test_snapshot_is_deeply_immutable_and_digests_cover_wording_and_facts():
    facts, policy = deepcopy(POLICY["examples"][0]["facts"]), deepcopy(POLICY)
    snapshot = capture(facts=facts, policy=policy)
    original = snapshot.model_dump_json()
    facts["cost_breakup"][0]["claimed_inr"] = 1
    policy["clauses"][0]["text"] = "Changed wording"
    read_facts, read_policy = snapshot.snapshots()
    read_facts["cost_breakup"].clear()
    read_policy["rules"].clear()
    assert snapshot.model_dump_json() == original
    assert "clinical_note" not in repr(snapshot)
    assert "examples" not in snapshot.policy_json
    assert "SYN-GOL002" not in snapshot.policy_json
    assert set(snapshot.snapshots()[1]) == {
        "product_id",
        "version",
        "effective_from",
        "effective_to",
        "wording_document_id",
        "clauses",
        "rules",
    }
    with pytest.raises(ValidationError):
        snapshot.facts_json = "{}"
    for field in ["facts_json", "policy_json"]:
        value = snapshot.model_dump()
        obj = json.loads(value[field])
        if field == "facts_json":
            obj["clinical_note"] = "Changed clinical facts"
        else:
            obj["clauses"][0]["text"] = "Changed wording"
        value[field] = canonical_json(obj)
        with pytest.raises(ValueError):
            AgentInput.model_validate(value)


BINDING_CHANGES = {
    "tenant_id": lambda: uuid4(),
    "request_id": lambda: "REQ-OTHER",
    "policy_id": lambda: uuid4(),
    "product_id": lambda: "OTHER",
    "policy_version": lambda: "new",
    "input_revision": lambda: 2,
    "review_version": lambda: 3,
    "input_digest": lambda: "f" * 64,
    "rules_digest": lambda: "f" * 64,
    "policy_digest": lambda: "f" * 64,
    "evidence_digest": lambda: "f" * 64,
    "correlation_id": lambda: uuid4(),
}


@pytest.mark.parametrize("field", BINDING_CHANGES)
def test_wrong_or_stale_scope_is_rejected_before_fake_io(field):
    snapshot = capture()
    changed = snapshot.binding.model_dump()
    changed[field] = BINDING_CHANGES[field]()
    gateway = FakeGateway()
    with pytest.raises(AgentContractError, match="stale_or_wrong_scope"):
        submit_fake(snapshot, context(snapshot, binding=changed), gateway)
    assert gateway.calls == []


@pytest.mark.parametrize(
    "flag",
    [
        "tenant_active",
        "policy_approved",
        "clinical_authorized",
        "review_open",
    ],
)
def test_revoked_or_unapproved_context_has_no_fake_io(flag):
    snapshot, gateway = capture(), FakeGateway()
    with pytest.raises(AgentContractError, match="scope_unavailable"):
        submit_fake(snapshot, context(snapshot, **{flag: False}), gateway)
    assert not gateway.calls


@pytest.mark.parametrize("field", BINDING_CHANGES)
def test_stale_result_cannot_cross_hypothetical_publication_boundary(field):
    snapshot = capture()
    run = submit_fake(snapshot, context(snapshot), FakeGateway())
    changed = snapshot.binding.model_dump()
    changed[field] = BINDING_CHANGES[field]()
    with pytest.raises(AgentContractError):
        comparison_for_publication(
            run, context(snapshot, binding=changed), fence_id=run.fence_id, now=NOW
        )


@pytest.mark.parametrize(
    "flag",
    [
        "tenant_active",
        "policy_approved",
        "clinical_authorized",
        "review_open",
    ],
)
@pytest.mark.parametrize("phase", ["receive", "publish"])
def test_revocation_and_final_human_review_block_late_results(flag, phase):
    snapshot = capture()
    run = reserve_fake_call(
        snapshot,
        context(snapshot),
        run_id=uuid4(),
        fence_id=uuid4(),
        now=NOW,
        deadline=NOW + timedelta(seconds=120),
    )
    raw = canonical_json(candidate(snapshot, run.run_id)).encode()
    if phase == "publish":
        run = receive_fake_result(run, context(snapshot), fence_id=run.fence_id, now=NOW, raw=raw)
    with pytest.raises(AgentContractError):
        if phase == "publish":
            comparison_for_publication(
                run, context(snapshot, **{flag: False}), fence_id=run.fence_id, now=NOW
            )
        else:
            receive_fake_result(
                run, context(snapshot, **{flag: False}), fence_id=run.fence_id, now=NOW, raw=raw
            )


@pytest.mark.parametrize("field", BINDING_CHANGES)
def test_response_scope_cannot_override_server_binding(field):
    snapshot, run_id = capture(), uuid4()
    value = candidate(snapshot, run_id)
    value["binding"][field] = (
        str(BINDING_CHANGES[field]())
        if field
        in {
            "tenant_id",
            "policy_id",
            "correlation_id",
        }
        else BINDING_CHANGES[field]()
    )
    with pytest.raises(AgentContractError, match="response_binding_mismatch"):
        validate_candidate(snapshot, context(snapshot), run_id, canonical_json(value).encode())


@pytest.mark.parametrize("version", [True, "1", 1.0, 0, 2])
def test_protocol_version_is_exact_integer(version):
    snapshot, run_id = capture(), uuid4()
    value = candidate(snapshot, run_id)
    value["binding"]["schema_version"] = version
    with pytest.raises(AgentContractError, match="invalid_agent_response"):
        validate_candidate(snapshot, context(snapshot), run_id, canonical_json(value).encode())


@pytest.mark.parametrize("index", [26, 27, 29])
@pytest.mark.parametrize("fault", ["zero_payable", "invented_line", "missing_evidence"])
def test_query_and_referral_cannot_claim_a_completed_calculation(index, fault):
    snapshot, run_id = capture(index), uuid4()
    value = candidate(snapshot, run_id)
    if fault == "zero_payable":
        value["payable_inr"] = 0
    elif fault == "invented_line":
        value["lines"] = [
            {
                "item": "Invented",
                "claimed_inr": 0,
                "payable_inr": 0,
                "deduction_inr": 0,
                "citations": [value["citations"][0]],
            }
        ]
    else:
        value["citations"] = []
    with pytest.raises(AgentContractError):
        validate_candidate(snapshot, context(snapshot), run_id, canonical_json(value).encode())


def test_missing_estimate_stays_unknown_and_cannot_be_fabricated():
    facts = deepcopy(POLICY["examples"][26]["facts"])
    facts["estimated_total_inr"] = None
    snapshot = capture(facts=facts)
    run = submit_fake(snapshot, context(snapshot), FakeGateway())
    assert run.candidate.claimed_inr is None and run.candidate.payable_inr is None
    value = candidate(snapshot, run.run_id)
    value["claimed_inr"] = 0
    with pytest.raises(AgentContractError, match="deterministic_mismatch"):
        validate_candidate(snapshot, context(snapshot), run.run_id, canonical_json(value).encode())


@pytest.mark.parametrize(
    "fault",
    [
        "total",
        "outcome",
        "deny",
        "line_amount",
        "offset_lines",
        "line_claimed",
        "line_deduction",
        "line_item",
        "line_missing",
        "line_extra",
        "line_order",
        "citation_missing",
        "citation_extra",
        "citation_duplicate",
        "citation_digest",
        "citation_kind",
        "line_citation_missing",
        "line_citation_digest",
        "line_citation_extra",
        "binding",
        "run",
        "string_money",
        "float_money",
        "bool_money",
        "negative_money",
        "null_money",
        "extra_field",
        "extra_line_field",
        "empty_explanation",
    ],
)
def test_untrusted_fault_never_becomes_validated_result(fault):
    snapshot = capture()
    run = reserve_fake_call(
        snapshot,
        context(snapshot),
        run_id=uuid4(),
        fence_id=uuid4(),
        now=NOW,
        deadline=NOW + timedelta(seconds=120),
    )
    value = candidate(snapshot, run.run_id)
    if fault == "total":
        value["payable_inr"] += 1
    elif fault in {"outcome", "deny"}:
        value["outcome"] = "QUERY" if fault == "outcome" else "DENY"
    elif fault == "line_amount":
        value["lines"][0]["payable_inr"] += 1
    elif fault == "offset_lines":
        value["lines"][0]["payable_inr"] += 1
        value["lines"][0]["deduction_inr"] -= 1
        value["lines"][1]["payable_inr"] -= 1
        value["lines"][1]["deduction_inr"] += 1
    elif fault in {"line_claimed", "line_deduction"}:
        value["lines"][0]["claimed_inr" if fault == "line_claimed" else "deduction_inr"] += 1
    elif fault == "line_item":
        value["lines"][0]["item"] = "Other item"
    elif fault == "line_missing":
        value["lines"].pop()
    elif fault == "line_extra":
        value["lines"].append(deepcopy(value["lines"][0]))
    elif fault == "line_order":
        value["lines"].reverse()
    elif fault == "citation_missing":
        value["citations"].pop(0)
    elif fault == "citation_extra":
        value["citations"].append(
            {
                "kind": "clause",
                "source_id": "NOT-OWNED",
                "source_digest": "a" * 64,
            }
        )
    elif fault == "citation_duplicate":
        value["citations"].append(value["citations"][0])
    elif fault == "citation_digest":
        value["citations"][0]["source_digest"] = "a" * 64
    elif fault == "citation_kind":
        value["citations"][0]["kind"] = "clause"
    elif fault == "line_citation_missing":
        value["lines"][0]["citations"] = []
    elif fault == "line_citation_digest":
        value["lines"][0]["citations"][0]["source_digest"] = "a" * 64
    elif fault == "line_citation_extra":
        value["lines"][0]["citations"].append(value["citations"][0])
    elif fault == "binding":
        value["binding"]["product_id"] = "OTHER"
    elif fault == "run":
        value["run_id"] = str(uuid4())
    elif fault in {"string_money", "float_money", "bool_money", "negative_money", "null_money"}:
        value["payable_inr"] = {
            "string_money": "95000",
            "float_money": 95000.0,
            "bool_money": True,
            "negative_money": -1,
            "null_money": None,
        }[fault]
    elif fault == "extra_field":
        value["credential"] = "MUST-NOT-APPEAR-IN-ERROR"
    elif fault == "extra_line_field":
        value["lines"][0]["reason"] = "Uncontracted reason"
    elif fault == "empty_explanation":
        value["explanation"] = ""
    result = receive_fake_result(
        run, context(snapshot), fence_id=run.fence_id, now=NOW, raw=canonical_json(value).encode()
    )
    assert result.state == "rejected" and result.candidate is None
    with pytest.raises(AgentContractError):
        comparison_for_publication(result, context(snapshot), fence_id=run.fence_id, now=NOW)


@pytest.mark.parametrize(
    "raw",
    [
        b"not json",
        b"\xff",
        b"[]",
        b"null",
        b"{}{}",
        b'{"outcome":"QUERY","outcome":"REFER"}',
        b"x" * (MAX_RESPONSE_BYTES + 1),
        b"[" * 1500 + b"]" * 1500,
        b'{"explanation":"PRIVATE-CLINICAL-RAW","unexpected":"PRIVATE-CLINICAL-RAW"}',
    ],
)
def test_parser_failure_is_bounded_and_redacts_raw_values(raw):
    with pytest.raises(AgentContractError) as error:
        parse_candidate(raw)
    assert str(error.value) == "invalid_agent_response"
    assert error.value.__suppress_context__


@pytest.mark.parametrize("fault", [TimeoutError("private"), ConnectionError("private")])
def test_uncertain_completion_never_retries_or_publishes(fault):
    snapshot, gateway = capture(), FakeGateway(fault=fault)
    run = submit_fake(snapshot, context(snapshot), gateway)
    assert run.state == "unknown" and run.candidate is None
    with pytest.raises(AgentContractError, match="automatic_retry_forbidden"):
        submit_fake(snapshot, context(snapshot), gateway, prior=run)
    assert len(gateway.calls) == 1
    with pytest.raises(AgentContractError):
        receive_fake_result(
            run,
            context(snapshot),
            fence_id=run.fence_id,
            now=NOW,
            raw=canonical_json(candidate(snapshot, run.run_id)).encode(),
        )


@pytest.mark.parametrize("prior_state", ["reserved", "rejected", "validated"])
def test_prior_receipt_of_any_state_blocks_automatic_second_attempt(prior_state):
    snapshot, gateway = capture(), FakeGateway()
    run = reserve_fake_call(
        snapshot,
        context(snapshot),
        run_id=uuid4(),
        fence_id=uuid4(),
        now=NOW,
        deadline=NOW + timedelta(seconds=120),
    )
    if prior_state != "reserved":
        raw = (
            b"invalid"
            if prior_state == "rejected"
            else canonical_json(candidate(snapshot, run.run_id)).encode()
        )
        run = receive_fake_result(run, context(snapshot), fence_id=run.fence_id, now=NOW, raw=raw)
    with pytest.raises(AgentContractError):
        submit_fake(snapshot, context(snapshot), gateway, prior=run)
    assert not gateway.calls


@pytest.mark.parametrize("phase", ["receive", "publish"])
@pytest.mark.parametrize("fault", ["expired", "wrong_fence", "clock_rollback", "naive_time"])
def test_run_deadline_and_fencing_at_both_boundaries(phase, fault):
    snapshot = capture()
    run = reserve_fake_call(
        snapshot,
        context(snapshot),
        run_id=uuid4(),
        fence_id=uuid4(),
        now=NOW,
        deadline=NOW + timedelta(seconds=120),
    )
    raw = canonical_json(candidate(snapshot, run.run_id)).encode()
    if phase == "publish":
        run = receive_fake_result(run, context(snapshot), fence_id=run.fence_id, now=NOW, raw=raw)
    now = {
        "expired": NOW + timedelta(seconds=120),
        "wrong_fence": NOW,
        "clock_rollback": NOW - timedelta(seconds=1),
        "naive_time": NOW.replace(tzinfo=None),
    }[fault]
    kwargs = {"fence_id": uuid4() if fault == "wrong_fence" else run.fence_id, "now": now}
    with pytest.raises(AgentContractError):
        if phase == "publish":
            comparison_for_publication(run, context(snapshot), **kwargs)
        else:
            receive_fake_result(run, context(snapshot), raw=raw, **kwargs)


def test_new_stage_has_no_routes_worker_wiring_or_transport_imports():
    for name in ["agent_contracts", "agent_simulation"]:
        tree = ast.parse(files("ciq_api").joinpath(f"{name}.py").read_text())
        imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)} | {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        assert not any(
            i
            and i.split(".")[0]
            in {
                "snowflake",
                "httpx",
                "requests",
                "sqlalchemy",
                "socket",
                "subprocess",
            }
            for i in imports
        )
    for name in ["jobs", "main", "local_worker"]:
        text = files("ciq_api").joinpath(f"{name}.py").read_text()
        assert "agent_contracts" not in text and "agent_simulation" not in text
