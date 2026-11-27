"""Offline captured-profile bridge for the existing fake process protocol.

One exact synthetic provider-response fixture only. No network, SDK, credential,
database, service entrypoint or live mode. The test child shares custody's UID;
this is not production transport isolation or fresh clinical authorization.
"""

import base64
import hashlib
import json
from datetime import datetime
from typing import Literal

from pydantic import Field

from ciq_api.agent_contracts import (
    AgentContext,
    AgentContractError,
    Digest,
    ImmutableContract,
    canonical_json,
)
from ciq_api.agent_executor import MAX_CANDIDATE, MAX_REQUEST, FakeProcessRequest
from ciq_api.agent_one_shot import (
    CapturedOneShotConfig,
    decode_captured_one_shot,
    prepare_captured_one_shot,
)
from ciq_api.agent_provider_response import MAX_PROVIDER_RESPONSE_BYTES

MAX_FIXTURE_BYTES = 520_000
ERROR = "captured_fake_exchange_unavailable"


class CapturedExchangeFixture(ImmutableContract):
    protocol: Literal["ciq-captured-fake-exchange-v1"]
    packet_sha256: Digest
    prepared_request_digest: Digest
    config: CapturedOneShotConfig
    expected_provider_run_id: str = Field(min_length=1, max_length=200, repr=False)
    response_base64: str = Field(max_length=512_000, repr=False)


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(ERROR)
        result[key] = value
    return result


def _invalid_constant(_value):
    raise ValueError(ERROR)


def _object(raw, maximum):
    if type(raw) is not bytes or not 0 < len(raw) <= maximum:
        raise ValueError(ERROR)
    return json.loads(
        raw.decode("utf-8"), object_pairs_hook=_unique, parse_constant=_invalid_constant,
    )


def respond_captured_fake(raw: bytes, fixture_raw: bytes, *, now: datetime) -> bytes:
    """Bind fixture to packet and prepared body, then validate its final response.

    The existing original-custody coordinator must have committed its independent
    issue before invoking a test child. This pure bridge cannot establish that
    ordering, approve I/O, prevent replay or discover current scope on its own.
    Publication independently checks fresh protected clinical context again.
    """
    try:
        packet = FakeProcessRequest.model_validate(_object(raw, MAX_REQUEST))
        fixture = CapturedExchangeFixture.model_validate(_object(fixture_raw, MAX_FIXTURE_BYTES))
        if (
            type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None
            or not 0 < (packet.deadline - now).total_seconds() <= 120
            or packet.tenant_id != packet.snapshot.binding.tenant_id
            or fixture.packet_sha256 != hashlib.sha256(raw).hexdigest()
        ):
            raise ValueError(ERROR)
        # Synthetic context asserts the captured scope only. It is not a
        # substitute for issue/publication's fresh, protected database checks.
        current = AgentContext(
            binding=packet.snapshot.binding, tenant_active=True, policy_approved=True,
            clinical_authorized=True, review_open=True,
        )
        prepared = prepare_captured_one_shot(
            packet.snapshot, current, packet.operation_id, fixture.config,
        )
        if (
            prepared.config_digest != packet.config_digest
            or prepared.request_digest != fixture.prepared_request_digest
        ):
            raise ValueError(ERROR)
        response = base64.b64decode(fixture.response_base64, validate=True)
        if not 0 < len(response) <= MAX_PROVIDER_RESPONSE_BYTES:
            raise ValueError(ERROR)
        final = decode_captured_one_shot(
            packet.snapshot, current, packet.operation_id,
            fixture.expected_provider_run_id, response,
        )
        candidate = canonical_json(final.candidate.model_dump(mode="json")).encode("utf-8")
        if not 0 < len(candidate) <= MAX_CANDIDATE:
            raise ValueError(ERROR)
        return canonical_json({
            "protocol": "ciq-fake-process-v1", "request_sha256": hashlib.sha256(raw).hexdigest(),
            "candidate_base64": base64.b64encode(candidate).decode("ascii"),
        }).encode("utf-8")
    except (ValueError, TypeError, AttributeError, RecursionError):
        raise AgentContractError(ERROR) from None
