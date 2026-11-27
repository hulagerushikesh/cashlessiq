"""Synthetic captured-profile exchange through fake framing; no network or DB."""

import base64
import hashlib
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from test_agent_contracts import POLICY, candidate, capture, context
from test_agent_provider_response import REMOTE, body, text, tool

from ciq_api.agent_captured_exchange import (
    MAX_FIXTURE_BYTES,
    respond_captured_fake,
)
from ciq_api.agent_contracts import AgentContractError, canonical_json
from ciq_api.agent_executor import BoundedFakeProcess, FakeProcessRequest, decode_reply
from ciq_api.agent_one_shot import CapturedOneShotConfig, prepare_captured_one_shot

CONFIG = CapturedOneShotConfig(model="reviewed-test-model-v1", seconds=5, tokens=4096)
HELPER = Path(__file__).with_name("captured_exchange_child.py")


def packet(snapshot=None, *, now=None):
    snapshot = capture() if snapshot is None else snapshot
    operation = uuid4()
    prepared = prepare_captured_one_shot(snapshot, context(snapshot), operation, CONFIG)
    return FakeProcessRequest(
        operation_id=operation, attempt_id=uuid4(), submission_id=uuid4(),
        tenant_id=snapshot.binding.tenant_id, config_digest=prepared.config_digest,
        source_digest="b" * 64, snapshot=snapshot,
        deadline=(datetime.now(UTC) if now is None else now) + timedelta(seconds=30),
    ).wire()


def fixture_for(raw, *, response=None, config=CONFIG):
    request = FakeProcessRequest.model_validate_json(raw)
    prepared = prepare_captured_one_shot(
        request.snapshot, context(request.snapshot), request.operation_id, config,
    )
    if response is None:
        response = body([text(canonical_json(candidate(request.snapshot, request.operation_id)))])
    return {
        "protocol": "ciq-captured-fake-exchange-v1",
        "packet_sha256": hashlib.sha256(raw).hexdigest(),
        "prepared_request_digest": prepared.request_digest,
        "config": config.model_dump(mode="json"), "expected_provider_run_id": REMOTE,
        "response_base64": base64.b64encode(canonical_json(response).encode()).decode(),
    }


def respond(raw, fixture, *, now=None):
    return respond_captured_fake(
        raw, canonical_json(fixture).encode(), now=datetime.now(UTC) if now is None else now,
    )


@pytest.mark.parametrize("index", range(len(POLICY["examples"])))
def test_all_golden_full_provider_responses_roundtrip_through_existing_fake_protocol(index):
    raw = packet(capture(index, request_id="REQ-" + "x" * 116))
    request = FakeProcessRequest.model_validate_json(raw)
    result = decode_reply(respond(raw, fixture_for(raw)), raw)
    assert json.loads(result) == candidate(request.snapshot, request.operation_id)


@pytest.mark.parametrize("field", (
    "operation_id", "attempt_id", "submission_id", "tenant_id", "source_digest", "deadline",
))
def test_fixture_cannot_be_reused_for_changed_packet(field):
    raw = packet()
    fixture = fixture_for(raw)
    changed = json.loads(raw)
    changed[field] = (
        (datetime.now(UTC) + timedelta(seconds=20)).isoformat() if field == "deadline"
        else "c" * 64 if field == "source_digest" else str(uuid4())
    )
    with pytest.raises(AgentContractError, match=r"^captured_fake_exchange_unavailable$"):
        respond(canonical_json(changed).encode(), fixture)


@pytest.mark.parametrize("change", (
    {"protocol": "live"}, {"packet_sha256": "0" * 64},
    {"prepared_request_digest": "0" * 64}, {"expected_provider_run_id": "other"},
    {"response_base64": "!"}, {"response_base64": ""}, {"endpoint": "https://other"},
    {"credential": "PRIVATE"}, {"retry": True},
))
def test_bad_fixture_pins_or_execution_selectors_have_fixed_errors(change):
    raw = packet()
    with pytest.raises(AgentContractError, match=r"^captured_fake_exchange_unavailable$"):
        respond(raw, {**fixture_for(raw), **change})


def test_even_repinned_fixture_cannot_use_wrong_tenant_or_another_configuration():
    raw = packet()
    for field, value in (("tenant_id", str(uuid4())), ("config_digest", "c" * 64)):
        changed = canonical_json({**json.loads(raw), field: value}).encode()
        fixture = fixture_for(changed)
        with pytest.raises(AgentContractError, match=r"^captured_fake_exchange_unavailable$"):
            respond(changed, fixture)


@pytest.mark.parametrize("fault", ("money", "tool", "warning", "run", "binding"))
def test_invalid_provider_reply_cannot_be_reframed_as_a_candidate(fault):
    raw = packet()
    request = FakeProcessRequest.model_validate_json(raw)
    value = candidate(request.snapshot, request.operation_id)
    if fault == "money":
        value["payable_inr"] = 1
    elif fault == "run":
        value["run_id"] = str(uuid4())
    elif fault == "binding":
        value["binding"]["review_version"] += 1
    response = body([tool()] if fault == "tool" else [text(canonical_json(value))])
    if fault == "warning":
        response["warnings"] = [{"code": "399569", "message": "PRIVATE"}]
    with pytest.raises(AgentContractError, match=r"^captured_fake_exchange_unavailable$"):
        respond(raw, fixture_for(raw, response=response))


@pytest.mark.parametrize("offset,naive", ((-121, False), (30, False), (31, False), (0, True)))
def test_expired_extended_or_naive_clock_cannot_use_fixture(offset, naive):
    now = datetime.now(UTC)
    raw = packet(now=now)
    # Deadline is now+30: checking at now-121 widens beyond 120; at now+30 expires.
    check_at = now + timedelta(seconds=offset)
    if naive:
        check_at = check_at.replace(tzinfo=None)
    with pytest.raises(AgentContractError, match=r"^captured_fake_exchange_unavailable$"):
        respond(raw, fixture_for(raw), now=check_at)


@pytest.mark.parametrize("malformed", (
    b"", b"{}", b"null", b"\xff", b"[" * 2000, b'{"config":NaN}',
    b'{"protocol":"one","protocol":"two"}', b" " * (MAX_FIXTURE_BYTES + 1),
))
def test_malformed_fixture_cannot_echo_private_payload(malformed):
    with pytest.raises(AgentContractError, match=r"^captured_fake_exchange_unavailable$") as error:
        respond_captured_fake(packet(), malformed, now=datetime.now(UTC))
    assert error.value.__suppress_context__


def test_actual_child_has_one_exchange_and_no_inherited_secrets(tmp_path, monkeypatch):
    raw = packet()
    fixture = tmp_path / "captured.json"
    fixture.write_text(canonical_json(fixture_for(raw)))
    fixture.chmod(0o600)
    monkeypatch.setenv("SNOWFLAKE_TOKEN", "PRIVATE PARENT TOKEN")
    monkeypatch.setenv("DATABASE_URL", "PRIVATE PARENT DATABASE")
    transport = BoundedFakeProcess((sys.executable, "-I", str(HELPER), str(fixture)))
    request = FakeProcessRequest.model_validate_json(raw)
    assert json.loads(transport.exchange(raw, timeout=5)) == candidate(
        request.snapshot, request.operation_id,
    )
    with pytest.raises(AgentContractError, match=r"^fake_transport_unavailable$"):
        transport.exchange(raw, timeout=5)
