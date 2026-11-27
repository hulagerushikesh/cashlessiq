"""Synthetic captured call material. Never owner approval or live identity data."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from test_agent_contracts import candidate, capture, context

from ciq_api.agent_contracts import canonical_json
from ciq_api.agent_one_shot import CapturedOneShotConfig, prepare_captured_one_shot
from ciq_api.agent_single_call_custody import captured_call_source_sha256
from ciq_api.agent_single_call_journal import ReviewedCallPin
from ciq_api.assessment import fingerprint


def call_material(index=0):
    snapshot, operation = capture(index), uuid4()
    config = CapturedOneShotConfig(model="reviewed-test-model-v1", seconds=8, tokens=256)
    request = prepare_captured_one_shot(snapshot, context(snapshot), operation, config)
    now = datetime.now(UTC)
    pin = ReviewedCallPin(
        grant_id=uuid4(), database_id=uuid4(), epoch_id=uuid4(), operation_id=operation,
        submission_id=uuid4(), approval_sha256="a" * 64,
        binding_sha256=fingerprint(snapshot.binding.model_dump(mode="json")),
        request_sha256=request.request_digest, config_sha256=request.config_digest,
        source_sha256=captured_call_source_sha256(snapshot), provider_identity_sha256="f" * 64,
        hostname="reviewed-account.snowflakecomputing.com", starts_at=now - timedelta(seconds=5),
        ends_at=now + timedelta(minutes=5), reserved_units=20, provider_seconds=8, max_tokens=256,
    )
    return snapshot, config, pin, request.body_json.encode()


def response_body(snapshot, operation):
    return {
        "role": "assistant", "status": "completed",
        "content": [{"type": "text", "text": canonical_json(candidate(snapshot, operation))}],
        "metadata": {"run_id": "opaque-observed-id", "usage": {"tokens_consumed": []}},
    }


def response_bytes(snapshot, operation):
    return canonical_json(response_body(snapshot, operation)).encode()
