"""Synthetic client-tool transcripts; no provider calls or source-parity claim."""

import json
from copy import deepcopy
from uuid import uuid4

import pytest
from test_agent_contracts import POLICY, candidate, capture, context

from ciq_api.agent_client_tools import (
    MAX_CALL_BYTES,
    MAX_CALLS,
    MAX_RESULT_BYTES,
    captured_tool_definitions,
    resolve_captured_tool_calls,
)
from ciq_api.agent_contracts import AgentContractError, canonical_json, validate_candidate


def call(name="ciq_read_case", *, call_id="toolu_1", arguments=None, **changes):
    return {
        "tool_use_id": call_id, "type": "generic", "name": name,
        "input": arguments if arguments is not None else {}, "client_side_execute": True,
        **changes,
    }


def resolve(snapshot, calls, current=None):
    return resolve_captured_tool_calls(
        snapshot, current if current is not None else context(snapshot),
        canonical_json(calls).encode(),
    )


def observation(result):
    return result["tool_result"]["content"][0]["json"]


@pytest.mark.parametrize("index", range(len(POLICY["examples"])))
def test_captured_tools_and_separate_synthetic_candidate_complete_the_offline_transcript(index):
    snapshot = capture(index, request_id="REQ-" + "x" * 116)
    run_id = uuid4()
    first = resolve(snapshot, [call(), call("ciq_assess_case", call_id="toolu_2")])
    content = json.loads(first.content_json)
    assert first.binding == snapshot.binding
    assert [c["tool_result"]["tool_use_id"] for c in content] == ["toolu_1", "toolu_2"]
    assert observation(content[0])["payload"]["facts"] == json.loads(snapshot.facts_json)
    assessed = observation(content[1])
    assert assessed["origin"] == "shared-deterministic-rules"
    expected = POLICY["examples"][index]
    assert assessed["payload"]["assessment"]["outcome"] == expected["expected_outcome"]
    assert assessed["payload"]["assessment"]["payable_inr"] == expected["expected_payable_inr"]
    ids = assessed["payload"]["assessment"]["clause_ids"]
    if ids:
        # A later synthetic model turn asks for the exact clauses. Fresh context
        # is supplied by the trusted test caller, not cached by the codec.
        second = resolve(snapshot, [
            call("ciq_read_clause", call_id=f"clause_{i}", arguments={"clause_id": clause_id})
            for i, clause_id in enumerate(ids)
        ])
        clauses = [observation(c)["payload"] for c in json.loads(second.content_json)]
        assert [c["clause"]["clause_id"] for c in clauses] == ids
        refs = assessed["payload"]["evidence"][1:]
        assert [c["evidence"] for c in clauses] == refs
    # The codec never manufactures the provider's final binding, money,
    # explanation or citations from tool observations. This fake response is
    # independently supplied by the existing test gateway fixture.
    final = canonical_json(candidate(snapshot, run_id)).encode()
    validated = validate_candidate(snapshot, context(snapshot), run_id, final)
    assert validated.payable_inr == expected["expected_payable_inr"]
    with pytest.raises(AgentContractError):
        validate_candidate(snapshot, context(snapshot), run_id, first.content_json.encode())
    with pytest.raises(AgentContractError):
        validate_candidate(snapshot, context(snapshot), run_id, final.replace(
            b'"run_id":"' + str(run_id).encode(), b'"run_id":"' + str(uuid4()).encode(),
        ))


@pytest.mark.parametrize("change", (
    {"name": "run_sql"}, {"name": "TOOL_CASE"}, {"name": "ciq_read_case; rm -rf /"},
    {"type": "cortex_search"}, {"client_side_execute": False},
    {"client_side_execute": "true"}, {"client_side_execute": 1},
    {"permission": {}}, {"permission": {"options": ["Allow Once", "Deny"]}},
    {"tool_use_id": ""}, {"tool_use_id": "x" * 121}, {"tool_use_id": 1},
    {"input": {"request_id": "OTHER"}}, {"input": {"tenant_id": str(uuid4())}},
    {"input": {"sql": "SELECT PRIVATE"}}, {"input": []},
    {"unexpected": "PRIVATE VALUE"},
))
def test_model_cannot_select_records_sources_privileges_or_commands(change):
    snapshot = capture()
    with pytest.raises(AgentContractError, match=r"^captured_client_tools_unavailable$"):
        resolve(snapshot, [call(**change)])


@pytest.mark.parametrize("arguments", (
    {}, {"clause_id": "MISSING"}, {"clause_id": None}, {"clause_id": True},
    {"clause_id": 1}, {"clause_id": ""}, {"clause_id": "x" * 121},
    {"clause_id": "../OTHER_POLICY"},
    {"clause_id": POLICY["clauses"][0]["clause_id"], "policy_id": "OTHER"},
))
def test_clause_arguments_are_exact_and_owned(arguments):
    with pytest.raises(AgentContractError, match=r"^captured_client_tools_unavailable$"):
        resolve(capture(), [call("ciq_read_clause", arguments=arguments)])


@pytest.mark.parametrize("raw", (
    b"", b"null", b"{}", b"[]", b"[NaN]", b"[Infinity]", b"[true]", b"[1]",
    b"\xff", b"[" * 2000, b" " * (MAX_CALL_BYTES + 1),
    b'[{"tool_use_id":"a","tool_use_id":"b"}]',
    b'[{"input":{"clause_id":"a","clause_id":"b"}}]',
    canonical_json([call()]).encode("utf-16"),
    canonical_json([call()]).encode() + b" {}",
))
def test_malformed_duplicate_non_utf8_or_oversized_calls_have_fixed_errors(raw):
    snapshot = capture()
    with pytest.raises(AgentContractError, match=r"^captured_client_tools_unavailable$"):
        resolve_captured_tool_calls(snapshot, context(snapshot), raw)


def test_batch_is_complete_bounded_and_keeps_distinct_call_identity():
    snapshot = capture()
    for calls in (
        [call(), call()],
        [call(call_id=str(i)) for i in range(MAX_CALLS + 1)],
        [call(), call("unknown", call_id="2")],
    ):
        with pytest.raises(AgentContractError, match=r"^captured_client_tools_unavailable$"):
            resolve(snapshot, calls)
    accepted = resolve(snapshot, [call(call_id=str(i)) for i in range(MAX_CALLS)])
    assert len(json.loads(accepted.content_json)) == MAX_CALLS
    assert len(accepted.content_json.encode()) <= MAX_RESULT_BYTES


@pytest.mark.parametrize("flag", (
    "tenant_active", "policy_approved", "clinical_authorized", "review_open",
))
def test_fresh_scope_is_required_on_every_batch(flag):
    snapshot = capture()
    resolve(snapshot, [call()])
    revoked = context(snapshot, **{flag: False})
    with pytest.raises(AgentContractError, match=r"^captured_client_tools_unavailable$"):
        resolve(snapshot, [call()], revoked)


def test_amended_corrupt_or_constructed_scope_cannot_release_data():
    snapshot = capture()
    for current in (
        context(snapshot, binding=snapshot.binding.model_copy(update={"review_version": 99})),
        context(snapshot, binding=snapshot.binding.model_copy(update={"tenant_id": uuid4()})),
        context(snapshot).model_copy(update={"clinical_authorized": "true"}),
    ):
        with pytest.raises(AgentContractError, match=r"^captured_client_tools_unavailable$"):
            resolve(snapshot, [call()], current)
    corrupt = snapshot.model_copy(update={"facts_json": "PRIVATE CORRUPT JSON"})
    with pytest.raises(AgentContractError, match=r"^captured_client_tools_unavailable$"):
        resolve(corrupt, [call()])


def test_private_output_cannot_leak_through_repr_or_be_mutated_between_calls():
    facts = deepcopy(POLICY["examples"][0]["facts"])
    facts["clinical_note"] = "PRIVATE NOTE"
    snapshot = capture(facts=facts)
    first = resolve(snapshot, [call()])
    assert "PRIVATE NOTE" not in repr(first) and "REQ-" not in repr(first)
    content = json.loads(first.content_json)
    observation(content[0])["payload"]["facts"]["clinical_note"] = "changed"
    assert resolve(snapshot, [call()]) == first


def test_oversized_complete_results_are_rejected_without_returning_partial_batch():
    policy = deepcopy(POLICY)
    clause_id = policy["clauses"][0]["clause_id"]
    # Valid Unicode wording expands when escaped into the canonical wire JSON.
    policy["clauses"][0]["text"] = "क" * 10_000
    snapshot = capture(policy=policy)
    with pytest.raises(AgentContractError, match=r"^captured_client_tools_unavailable$"):
        resolve(snapshot, [
            call("ciq_read_clause", call_id=str(i), arguments={"clause_id": clause_id})
            for i in range(MAX_CALLS)
        ])


def test_tool_definitions_expose_only_fixed_snapshot_reads_and_are_fresh():
    definitions = captured_tool_definitions()
    specs = [item["tool_spec"] for item in definitions]
    assert [s["name"] for s in specs] == ["ciq_read_case", "ciq_assess_case", "ciq_read_clause"]
    assert all(s["type"] == "generic" for s in specs)
    assert all(s["input_schema"]["additionalProperties"] is False for s in specs)
    assert [s["input_schema"]["required"] for s in specs] == [[], [], ["clause_id"]]
    definitions[0]["tool_spec"]["name"] = "changed"
    assert captured_tool_definitions()[0]["tool_spec"]["name"] == "ciq_read_case"
