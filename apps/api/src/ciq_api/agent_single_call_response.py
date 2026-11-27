"""Inactive synchronous-response observations and final clinical validation.

The original custody must associate these bytes with its own issued exchange.
The provider ID is OBSERVED, never compared with a copy of itself as proof of
identity. These pure helpers cannot establish provenance or permit publication.
The captured decoder's independent expected-ID requirement is unchanged.
"""

import hashlib
from uuid import UUID

from pydantic import Field

from ciq_api.agent_contracts import (
    AgentCandidate,
    AgentContext,
    AgentContractError,
    AgentInput,
    Digest,
    ImmutableContract,
    validate_candidate,
)
from ciq_api.agent_provider_response import _parse_response
from ciq_api.agent_single_call_journal import ReportedTokenUsage
from ciq_api.agent_snapshot_tools import select_captured_snapshot

ERROR = "single_call_response_unavailable"


class SingleCallObservation(ImmutableContract):
    response_sha256: Digest = Field(repr=False)
    provider_run_id: str = Field(repr=False)
    reported_usage: ReportedTokenUsage


class SingleCallFinal(ImmutableContract):
    observation: SingleCallObservation = Field(repr=False)
    candidate: AgentCandidate = Field(repr=False)


def inspect_single_call_response(raw: bytes) -> SingleCallObservation:
    """Observe a strict completed aggregate, before judging its clinical text.

    Malformed/failed envelopes have no trusted accounting projection. A valid
    envelope with an invalid clinical answer can still be recorded as observed.
    No reviewed mapping exists for the provider's variable usage objects: both
    counts remain UNKNOWN, including reports that contain numeric zero. Do not
    infer free work or billed cost from those unverified fields.
    """
    try:
        _, response = _parse_response(raw)
        run_id = response.metadata.run_id
        if not all(32 <= ord(char) <= 126 for char in run_id):
            raise ValueError(ERROR)
        return SingleCallObservation(
            response_sha256=hashlib.sha256(raw).hexdigest(), provider_run_id=run_id,
            reported_usage=ReportedTokenUsage(input_tokens=None, output_tokens=None),
        )
    except Exception:
        raise AgentContractError(ERROR) from None


def decode_single_call_final(
    snapshot: AgentInput, current: AgentContext, operation_id: UUID, raw: bytes,
) -> SingleCallFinal:
    """Final-only candidate from caller-associated bytes; no continuation or I/O.

    This entry does not invent an expected provider ID. Custody must keep the
    original exchange private and retain its digest before calling this helper.
    Current context is a trusted caller assertion, not a database access check.
    """
    try:
        snapshot = select_captured_snapshot(snapshot, current)
        if type(operation_id) is not UUID:
            raise ValueError(ERROR)
        observation = inspect_single_call_response(raw)
        _, response = _parse_response(raw)
        # Never resolve a tool, including a tool mixed with a valid final text.
        if any(content.type == "tool_use" for content in response.content):
            raise ValueError(ERROR)
        texts = [content.text for content in response.content if content.type == "text"]
        if len(texts) != 1:
            raise ValueError(ERROR)
        candidate = validate_candidate(snapshot, current, operation_id, texts[0].encode("utf-8"))
        return SingleCallFinal(observation=observation, candidate=candidate)
    except Exception:
        raise AgentContractError(ERROR) from None
