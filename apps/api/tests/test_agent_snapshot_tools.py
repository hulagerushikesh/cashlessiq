"""Captured clinical tool observations, without a database or remote provider."""

import json
from copy import deepcopy
from uuid import uuid4

import pytest
from test_agent_contracts import POLICY, capture, context

from ciq_api.agent_contracts import AgentContractError, canonical_json, parse_candidate
from ciq_api.agent_snapshot_tools import (
    assess_captured_case,
    read_captured_case,
    read_captured_clause,
)
from ciq_api.assessment import fingerprint


def invoke(tool, snapshot, current):
    if tool is read_captured_clause:
        return tool(snapshot, current, POLICY["clauses"][0]["clause_id"])
    return tool(snapshot, current)


TOOLS = (read_captured_case, assess_captured_case, read_captured_clause)


@pytest.mark.parametrize("index", range(len(POLICY["examples"])))
def test_golden_assessments_preserve_outcome_money_and_owned_evidence(index):
    snapshot = capture(index)
    reply = assess_captured_case(snapshot, context(snapshot))
    payload = json.loads(reply.payload_json)
    expected = POLICY["examples"][index]
    result = payload["assessment"]
    assert result["outcome"] == expected["expected_outcome"]
    assert result["payable_inr"] == expected["expected_payable_inr"]
    assert reply.origin == "shared-deterministic-rules"
    assert reply.binding == snapshot.binding
    refs = {(ref["kind"], ref["source_id"]): ref for ref in payload["evidence"]}
    assert refs[("record", snapshot.binding.request_id)]["source_digest"] == fingerprint(
        json.loads(snapshot.facts_json)
    )
    for clause_id in result["clause_ids"]:
        clause = read_captured_clause(snapshot, context(snapshot), clause_id)
        detail = json.loads(clause.payload_json)
        assert refs[("clause", clause_id)] == detail["evidence"]
        assert detail["evidence"]["source_digest"] == fingerprint(detail["clause"])
    if result["outcome"] in {"QUERY", "REFER"}:
        assert result["payable_inr"] is None and result["payable"] is None
    else:
        assert sum(line["payable_inr"] for line in result["payable"]["lines"]) == (
            expected["expected_payable_inr"]
        )


@pytest.mark.parametrize("tool", TOOLS)
@pytest.mark.parametrize("flag", (
    "tenant_active", "policy_approved", "clinical_authorized", "review_open",
))
def test_revocation_denies_each_tool_without_reusing_previous_scope(tool, flag):
    snapshot = capture()
    invoke(tool, snapshot, context(snapshot))
    with pytest.raises(AgentContractError, match=r"^snapshot_tools_unavailable$"):
        invoke(tool, snapshot, context(snapshot, **{flag: False}))


@pytest.mark.parametrize("tool", TOOLS)
@pytest.mark.parametrize("change", (
    {"tenant_id": uuid4()}, {"policy_id": uuid4()}, {"input_revision": 99},
))
def test_wrong_tenant_policy_or_amended_input_cannot_read_captured_data(tool, change):
    snapshot = capture()
    wrong = context(snapshot, binding=snapshot.binding.model_copy(update=change))
    with pytest.raises(AgentContractError, match=r"^snapshot_tools_unavailable$"):
        invoke(tool, snapshot, wrong)


@pytest.mark.parametrize("tool", TOOLS)
def test_corrupted_capture_and_constructed_scope_do_not_bypass_validation(tool):
    snapshot = capture()
    facts = json.loads(snapshot.facts_json)
    facts["clinical_note"] = "PRIVATE CHANGED FACTS"
    corrupt = snapshot.model_copy(update={"facts_json": canonical_json(facts)})
    with pytest.raises(AgentContractError, match=r"^snapshot_tools_unavailable$"):
        invoke(tool, corrupt, context(corrupt))
    forged = context(snapshot).model_copy(update={"clinical_authorized": "true"})
    with pytest.raises(AgentContractError, match=r"^snapshot_tools_unavailable$"):
        invoke(tool, snapshot, forged)


@pytest.mark.parametrize("value", (True, "100,000", 100000.0))
def test_strict_money_survives_the_tool_boundary(value):
    snapshot = capture()
    facts = json.loads(snapshot.facts_json)
    facts["sum_insured_inr"] = value
    corrupt = snapshot.model_copy(update={"facts_json": canonical_json(facts)})
    with pytest.raises(AgentContractError, match=r"^snapshot_tools_unavailable$"):
        read_captured_case(corrupt, context(corrupt))


def test_case_preserves_new_request_namespace_nulls_and_captured_remaining_cover():
    facts = deepcopy(POLICY["examples"][0]["facts"])
    facts.update(cost_breakup=[], estimated_total_inr=None, si_remaining_inr=45000,
                 diagnosis=None, clinical_note="PRIVATE NOTE")
    snapshot = capture(facts=facts, request_id="REQ-" + "x" * 116)
    reply = read_captured_case(snapshot, context(snapshot))
    payload = json.loads(reply.payload_json)
    assert payload["facts"] == json.loads(snapshot.facts_json)
    assert payload["facts"]["estimated_total_inr"] is None
    assert payload["facts"]["si_remaining_inr"] == 45000
    assert payload["evidence"]["source_id"] == snapshot.binding.request_id
    assert len(payload["evidence"]["source_id"]) == 120
    assert reply.origin == "captured-product-snapshot"
    assert "PRIVATE NOTE" not in repr(reply)
    assert "REQ-" not in repr(reply)
    # Returned mutable JSON cannot modify the captured facts or a subsequent read.
    payload["facts"]["si_remaining_inr"] = 0
    assert read_captured_case(snapshot, context(snapshot)) == reply


@pytest.mark.parametrize("clause_id", ("MISSING", "../POLICY", "", None, True))
def test_unknown_clause_never_searches_or_falls_back(clause_id):
    snapshot = capture()
    with pytest.raises(AgentContractError, match=r"^snapshot_tools_unavailable$"):
        read_captured_clause(snapshot, context(snapshot), clause_id)


def test_same_clause_id_changed_wording_has_distinct_content_and_policy_binding():
    first = capture()
    policy = deepcopy(POLICY)
    policy["clauses"][0]["text"] = "Changed approved wording"
    second = capture(policy=policy)
    clause_id = policy["clauses"][0]["clause_id"]
    before = read_captured_clause(first, context(first), clause_id)
    after = read_captured_clause(second, context(second), clause_id)
    assert json.loads(after.payload_json)["clause"] == policy["clauses"][0]
    assert json.loads(before.payload_json)["evidence"] != json.loads(after.payload_json)["evidence"]
    assert before.binding.policy_digest != after.binding.policy_digest
    assert before.binding.policy_id != after.binding.policy_id


@pytest.mark.parametrize("tool", TOOLS)
def test_tool_observations_are_not_agent_candidates(tool):
    snapshot = capture()
    reply = invoke(tool, snapshot, context(snapshot))
    with pytest.raises(AgentContractError, match=r"^invalid_agent_response$"):
        parse_candidate(reply.model_dump_json().encode())
