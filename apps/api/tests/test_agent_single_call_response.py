"""Strict observed response association, never independently verified provider ID."""

import hashlib
from uuid import uuid4

import pytest
from single_call_fixtures import response_body, response_bytes
from test_agent_contracts import POLICY, capture, context

from ciq_api.agent_contracts import AgentContractError, canonical_json
from ciq_api.agent_single_call_response import (
    ERROR,
    decode_single_call_final,
    inspect_single_call_response,
)


@pytest.mark.parametrize("index", range(len(POLICY["examples"])))
def test_all_golden_answers_preserve_internal_id_money_nulls_and_observed_remote_id(index):
    snapshot, operation = capture(index), uuid4()
    raw = response_bytes(snapshot, operation)
    final = decode_single_call_final(snapshot, context(snapshot), operation, raw)
    assert final.candidate.run_id == operation
    assert final.candidate.payable_inr == POLICY["examples"][index]["expected_payable_inr"]
    assert final.observation.provider_run_id == "opaque-observed-id"
    assert final.observation.response_sha256 == hashlib.sha256(raw).hexdigest()
    assert final.observation.reported_usage.input_tokens is None
    assert final.observation.reported_usage.output_tokens is None
    assert "opaque" not in repr(final) and str(operation) not in repr(final)


@pytest.mark.parametrize("usage", [None, {}, {"input_tokens": 0, "output_tokens": 0},
                                    {"tokens_consumed": [{"input_tokens": "PRIVATE"}]}])
def test_unreviewed_usage_mapping_is_unknown_without_inference(usage):
    snapshot, operation = capture(), uuid4()
    value = response_body(snapshot, operation)
    value["metadata"]["usage"] = usage
    observed = inspect_single_call_response(canonical_json(value).encode())
    assert observed.reported_usage.input_tokens is None
    assert observed.reported_usage.output_tokens is None


@pytest.mark.parametrize("change", ["money", "citation", "operation", "tools", "two-texts"])
def test_invalid_clinical_answer_can_be_observed_but_never_validated_or_resolved(
    change, monkeypatch,
):
    snapshot, operation = capture(), uuid4()
    value = response_body(snapshot, operation)
    if change in {"money", "citation", "operation"}:
        import json
        answer = json.loads(value["content"][0]["text"])
        if change == "money":
            answer["payable_inr"] = 1
        elif change == "citation":
            answer["citations"][0]["source_digest"] = "0" * 64
        else:
            answer["run_id"] = str(uuid4())
        value["content"][0]["text"] = canonical_json(answer)
    elif change == "two-texts":
        value["content"] *= 2
    else:
        value["content"].append({"type": "tool_use", "tool_use": {"PRIVATE": "selector"}})
    calls = []
    monkeypatch.setattr("ciq_api.agent_provider_response.resolve_captured_tool_calls",
                        lambda *args: calls.append(args))
    raw = canonical_json(value).encode()
    assert inspect_single_call_response(raw).response_sha256 == hashlib.sha256(raw).hexdigest()
    with pytest.raises(AgentContractError, match=f"^{ERROR}$"):
        decode_single_call_final(snapshot, context(snapshot), operation, raw)
    assert not calls


@pytest.mark.parametrize("fault", ["duplicate", "extra", "status", "warning", "id", "utf8",
                                    "oversize", "trailing", "empty", "wrong-type"])
def test_malformed_or_failed_aggregate_has_no_accounting_projection(fault):
    snapshot, operation = capture(), uuid4()
    value = response_body(snapshot, operation)
    if fault == "extra":
        value["PRIVATE"] = "diagnostic"
    elif fault == "status":
        value["status"] = "in_progress"
    elif fault == "warning":
        value["warnings"] = [{"message": "PRIVATE provider warning"}]
    elif fault == "id":
        value["metadata"]["run_id"] = "bad\nid"
    raw = canonical_json(value).encode()
    raw = {"duplicate": b'{"role":"assistant",' + raw[1:], "utf8": b"\xff",
           "oversize": b"x" * 384_001, "trailing": raw + b"{}", "empty": b"",
           "wrong-type": bytearray(raw)}.get(fault, raw)
    with pytest.raises(AgentContractError, match=f"^{ERROR}$") as caught:
        inspect_single_call_response(raw)
    assert caught.value.__suppress_context__


@pytest.mark.parametrize("flag", ["tenant_active", "policy_approved", "clinical_authorized",
                                   "review_open"])
def test_fresh_context_required_before_candidate_handoff(flag):
    snapshot, operation = capture(), uuid4()
    with pytest.raises(AgentContractError, match=f"^{ERROR}$"):
        decode_single_call_final(snapshot, context(snapshot, **{flag: False}), operation,
                                 response_bytes(snapshot, operation))
