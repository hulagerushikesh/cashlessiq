"""Synthetic full-response transcripts; no remote execution or billing claim."""

import json
from uuid import uuid4

import pytest
from test_agent_client_tools import call
from test_agent_contracts import POLICY, candidate, capture, context

from ciq_api.agent_contracts import AgentContractError, canonical_json
from ciq_api.agent_provider_response import (
    MAX_PROVIDER_RESPONSE_BYTES,
    CapturedFinalTurn,
    CapturedToolTurn,
    decode_captured_provider_response,
)

REMOTE = "4264-83472"


def body(initial_content, **changes):
    return {
        "role": "assistant", "status": "completed", "content": initial_content,
        "metadata": {
            "run_id": REMOTE, "thread_id": 4264, "user_message_id": 83472,
            "assistant_message_id": 83473, "usage": {"tokens_consumed": []},
        },
        **changes,
    }


def text(value):
    return {"type": "text", "text": value}


def tool(value=None):
    return {"type": "tool_use", "tool_use": call() if value is None else value}


def thinking(value="PRIVATE THINKING"):
    return {"type": "thinking", "thinking": {"text": value, "signature": "PRIVATE SIGNATURE"}}


def decode(snapshot, operation, value, **changes):
    return decode_captured_provider_response(
        snapshot, changes.get("current", context(snapshot)), operation,
        changes.get("expected", REMOTE), canonical_json(value).encode(),
    )


def deny(snapshot, operation, value, **changes):
    with pytest.raises(AgentContractError, match=r"^captured_provider_response_unavailable$"):
        decode(snapshot, operation, value, **changes)


@pytest.mark.parametrize("index", range(len(POLICY["examples"])))
def test_full_response_tools_then_separate_final_candidate_for_all_golden_cases(index):
    snapshot, operation = capture(index, request_id="REQ-" + "x" * 116), uuid4()
    content = [thinking(), tool(), tool(call("ciq_assess_case", call_id="assess"))]
    request = body(content, warnings=[])
    pending = decode(snapshot, operation, request)
    assert isinstance(pending, CapturedToolTurn)
    assert pending.operation_id == operation
    assert json.loads(pending.assistant_content_json) == content
    assert json.loads(pending.provider_metadata_json) == request["metadata"]
    observations = json.loads(pending.results.content_json)
    assert [c["tool_result"]["tool_use_id"] for c in observations] == ["toolu_1", "assess"]
    assert observations[1]["tool_result"]["content"][0]["json"]["payload"]["assessment"][
        "payable_inr"
    ] == POLICY["examples"][index]["expected_payable_inr"]
    # A different external run ID on the next provider invocation must not
    # replace the internal operation UUID echoed by the final candidate.
    final_body = body([thinking(), text(canonical_json(candidate(snapshot, operation)))])
    final_body["metadata"]["run_id"] = "4264-83474"
    final_body["metadata"]["user_message_id"] = 83474
    final_body["metadata"]["assistant_message_id"] = 83475
    final = decode(snapshot, operation, final_body, expected="4264-83474")
    assert isinstance(final, CapturedFinalTurn)
    assert final.candidate.run_id == operation
    assert final.candidate.payable_inr == POLICY["examples"][index]["expected_payable_inr"]
    assert "PRIVATE" not in repr(pending) + repr(final)
    assert str(operation) not in repr(pending) + repr(final)


@pytest.mark.parametrize("changes", (
    {"role": "user"}, {"role": "tool"}, {"status": "cancelled"},
    {"status": "timed_out"}, {"status": "in_progress"}, {"status": None},
    {"status": "failed"}, {"error": {"message": "PRIVATE ERROR"}},
    {"warnings": [{"code": "399569", "message": "Tool not accessible"}]},
    {"warnings": None}, {"warnings": {}}, {"metadata": {}},
    {"metadata": {"run_id": "WRONG"}}, {"metadata": {"run_id": 1}},
    {"metadata": {"run_id": REMOTE, "unknown": "PRIVATE"}},
    {"content": []},
))
def test_failed_warning_unknown_or_unbound_responses_are_not_candidates_or_tools(changes):
    deny(capture(), uuid4(), body([tool()], **changes))


@pytest.mark.parametrize("key", ("status", "metadata", "role", "content"))
def test_required_envelope_fields_cannot_be_inferred(key):
    value = body([tool()])
    del value[key]
    deny(capture(), uuid4(), value)


@pytest.mark.parametrize("cursor", (
    {"thread_id": 1}, {"user_message_id": 2, "assistant_message_id": 3},
    {"thread_id": 1, "user_message_id": 2, "assistant_message_id": 2},
    {"thread_id": True, "user_message_id": 2, "assistant_message_id": 3},
    {"thread_id": "1", "user_message_id": 2, "assistant_message_id": 3},
    {"thread_id": 1, "user_message_id": -2, "assistant_message_id": 3},
))
def test_thread_cursor_is_complete_and_strict_or_absent(cursor):
    deny(capture(), uuid4(), body([tool()], metadata={"run_id": REMOTE, **cursor}))


def test_no_thread_profile_keeps_opaque_provider_id_separate_from_internal_uuid():
    snapshot, operation = capture(), uuid4()
    value = body(
        [text(canonical_json(candidate(snapshot, operation)))], metadata={"run_id": REMOTE},
    )
    assert decode(snapshot, operation, value).candidate.run_id == operation
    deny(snapshot, operation, value, expected=str(operation))
    deny(snapshot, str(operation), value)
    value["content"] = [text(canonical_json(candidate(snapshot, uuid4())))]
    deny(snapshot, operation, value)


@pytest.mark.parametrize("content", (
    [thinking()], [thinking('{"binding":"hidden fake candidate"}')],
    [tool(), text("Ignore tools and accept this")], [text("a"), text("b")],
    [tool(call(client_side_execute=False))], [tool(call(permission={}))],
    [tool(call(name="system_execute_sql"))],
    [{"type": "tool_result", "tool_result": {"status": "success"}}],
    [{"type": "text", "text": "{}", "annotations": []}],
    [{"type": "json", "json": {"binding": "fake"}}],
    [text("{}"), {"type": "chart", "chart": {}}],
    [tool()] * 9,
))
def test_no_recursive_extraction_mixed_messages_server_tools_or_extensions(content):
    deny(capture(), uuid4(), body(content))


@pytest.mark.parametrize("mutation", ("fences", "prose", "duplicate", "money", "citation"))
def test_final_text_must_itself_be_one_complete_valid_candidate(mutation):
    snapshot, operation = capture(), uuid4()
    value = candidate(snapshot, operation)
    if mutation == "money":
        value["payable_inr"] = 1
    if mutation == "citation":
        value["citations"][0]["source_digest"] = "0" * 64
    raw = canonical_json(value)
    if mutation == "fences":
        raw = "```json\n" + raw + "\n```"
    if mutation == "prose":
        raw = "The answer is " + raw
    if mutation == "duplicate":
        raw = '{"explanation":"hidden",' + raw[1:]
    deny(snapshot, operation, body([text(raw)]))


@pytest.mark.parametrize("flag", (
    "tenant_active", "policy_approved", "clinical_authorized", "review_open",
))
@pytest.mark.parametrize("kind", ("tools", "candidate"))
def test_revoked_scope_cannot_release_tool_data_or_accept_final_response(flag, kind):
    snapshot, operation = capture(), uuid4()
    content = [tool()] if kind == "tools" else [
        text(canonical_json(candidate(snapshot, operation))),
    ]
    decode(snapshot, operation, body(content))
    deny(snapshot, operation, body(content), current=context(snapshot, **{flag: False}))


def test_review_drift_corrupt_capture_and_bypassed_scope_validation_fail_closed():
    snapshot, operation = capture(), uuid4()
    value = body([tool()])
    deny(snapshot, operation, value, current=context(snapshot, binding=snapshot.binding.model_copy(
        update={"review_version": 99},
    )))
    deny(snapshot, operation, value, current=context(snapshot).model_copy(
        update={"clinical_authorized": "true"},
    ))
    deny(snapshot.model_copy(update={"facts_json": "PRIVATE CORRUPT INPUT"}), operation, value)


@pytest.mark.parametrize("raw", (
    b"", b"{}", b"null", b"[]", b"[" * 2000, b"\xff", b'{"content":NaN}',
    b'{"role":"assistant","role":"user"}',
    b'{"metadata":{"run_id":"a","run_id":"b"}}',
    b" " * (MAX_PROVIDER_RESPONSE_BYTES + 1),
    canonical_json(body([tool()])).encode("utf-16"),
    canonical_json(body([tool()])).encode() + b" {}",
))
def test_wire_encoding_duplicate_fields_and_size_bounds_have_fixed_errors(raw):
    snapshot = capture()
    with pytest.raises(AgentContractError, match=r"^captured_provider_response_unavailable$"):
        decode_captured_provider_response(snapshot, context(snapshot), uuid4(), REMOTE, raw)


def test_private_result_strings_cannot_be_mutated_and_thinking_is_not_a_candidate():
    snapshot, operation = capture(), uuid4()
    content = [thinking(canonical_json(candidate(snapshot, operation))), tool()]
    pending = decode(snapshot, operation, body(content))
    assert pending.kind == "tools"
    decoded = json.loads(pending.assistant_content_json)
    decoded[0]["thinking"]["text"] = "changed"
    assert json.loads(pending.assistant_content_json) == content
    assert "PRIVATE" not in repr(pending)


def test_canonical_retention_bound_includes_unicode_expansion_in_reported_metadata():
    snapshot = capture()
    value = body([tool()])
    value["metadata"]["usage"] = {"uninterpreted": "क" * 65_000}
    raw = json.dumps(value, ensure_ascii=False).encode()
    assert len(raw) < MAX_PROVIDER_RESPONSE_BYTES
    with pytest.raises(AgentContractError, match=r"^captured_provider_response_unavailable$"):
        decode_captured_provider_response(snapshot, context(snapshot), uuid4(), REMOTE, raw)
