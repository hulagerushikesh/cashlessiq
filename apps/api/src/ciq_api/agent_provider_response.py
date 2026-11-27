"""Inactive decoder for complete non-streaming Cortex responses; no provider I/O.

The trusted transport must authenticate the response and supply the expected
provider run ID independently. Matching metadata is not authentication. These
clinical replies cannot authorize a continuation or publish a recommendation.
"""

import json
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, model_validator

from ciq_api.agent_client_tools import CapturedToolResults, resolve_captured_tool_calls
from ciq_api.agent_contracts import (
    AgentCandidate,
    AgentContext,
    AgentContractError,
    AgentInput,
    ImmutableContract,
    canonical_json,
    validate_candidate,
)
from ciq_api.agent_snapshot_tools import select_captured_snapshot

MAX_PROVIDER_RESPONSE_BYTES = 384_000
ERROR = "captured_provider_response_unavailable"
MessageID = Annotated[int, Field(strict=True, gt=0, le=2**63 - 1)]


class _Metadata(ImmutableContract):
    run_id: str = Field(min_length=1, max_length=200, repr=False)
    thread_id: MessageID | None = None
    user_message_id: MessageID | None = None
    assistant_message_id: MessageID | None = None
    # Retained as reported observations, never interpreted as billed cost or
    # permission. The complete raw-response byte bound also bounds this object.
    usage: dict | None = Field(default=None, repr=False)

    @model_validator(mode="after")
    def complete_cursor(self):
        ids = (self.thread_id, self.user_message_id, self.assistant_message_id)
        if any(i is not None for i in ids) and (
            any(i is None for i in ids) or self.user_message_id == self.assistant_message_id
        ):
            raise ValueError(ERROR)
        return self


class _Text(ImmutableContract):
    type: Literal["text"]
    text: str = Field(min_length=1, max_length=128_000, repr=False)


class _ThinkingBody(ImmutableContract):
    text: str = Field(max_length=64_000, repr=False)
    signature: str | None = Field(default=None, max_length=16_000, repr=False)


class _Thinking(ImmutableContract):
    type: Literal["thinking"]
    thinking: _ThinkingBody = Field(repr=False)


class _ToolContent(ImmutableContract):
    type: Literal["tool_use"]
    tool_use: dict = Field(repr=False)


Content = Annotated[_Text | _Thinking | _ToolContent, Field(discriminator="type")]


class _Response(ImmutableContract):
    role: Literal["assistant"]
    status: Literal["completed"]
    content: tuple[Content, ...] = Field(min_length=1, max_length=10, repr=False)
    metadata: _Metadata = Field(repr=False)
    warnings: tuple[dict, ...] = Field(default=(), max_length=0, repr=False)


class CapturedToolTurn(ImmutableContract):
    kind: Literal["tools"] = "tools"
    operation_id: UUID = Field(repr=False)
    provider_metadata_json: str = Field(repr=False)
    # Preserve the entire assistant content, including signed thinking, for a
    # future reviewed continuation. Never reconstruct history from final text.
    assistant_content_json: str = Field(repr=False)
    results: CapturedToolResults = Field(repr=False)


class CapturedFinalTurn(ImmutableContract):
    kind: Literal["candidate"] = "candidate"
    provider_metadata_json: str = Field(repr=False)
    candidate: AgentCandidate = Field(repr=False)


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(ERROR)
        result[key] = value
    return result


def _invalid_constant(_value):
    raise ValueError(ERROR)


def _parse_response(raw):
    """One strict aggregate parser shared by captured and synchronous profiles.

    Parsing does not authenticate a transport, authorize work or validate the
    clinical text. In particular, a run ID read here is an observed value.
    """
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_PROVIDER_RESPONSE_BYTES:
        raise ValueError(ERROR)
    value = json.loads(
        raw.decode("utf-8"), object_pairs_hook=_unique, parse_constant=_invalid_constant,
    )
    if len(canonical_json(value).encode("utf-8")) > MAX_PROVIDER_RESPONSE_BYTES:
        raise ValueError(ERROR)
    return value, _Response.model_validate(value)


def decode_captured_provider_response(
    snapshot: AgentInput, current: AgentContext, operation_id: UUID,
    expected_provider_run_id: str, raw: bytes, *, allow_client_tools: bool = True,
) -> CapturedToolTurn | CapturedFinalTurn:
    """Decode one authenticated-by-caller aggregate, not SSE or partial events.

    This deliberately narrow profile requires explicit completed status and run
    metadata, even though some documented examples omit them. Nonempty warnings,
    server tool observations, mixed text/tool output and unknown extensions fail
    closed. Thinking is preserved privately, never searched for a candidate.
    Provider run IDs are opaque and separate from the internal operation UUID.
    Every invocation requires freshly supplied clinical context. No retry occurs.
    The single-call profile passes allow_client_tools=False; any requested tool
    then fails before dispatch, without creating a continuation or tool results.
    """
    try:
        snapshot = select_captured_snapshot(snapshot, current)
        if (
            type(allow_client_tools) is not bool
            or type(operation_id) is not UUID or type(expected_provider_run_id) is not str
            or not 1 <= len(expected_provider_run_id) <= 200
        ):
            raise ValueError(ERROR)
        value, response = _parse_response(raw)
        if response.metadata.run_id != expected_provider_run_id:
            raise ValueError(ERROR)
        metadata = canonical_json(value["metadata"])
        calls = [c.tool_use for c in response.content if isinstance(c, _ToolContent)]
        texts = [c.text for c in response.content if isinstance(c, _Text)]
        if calls:
            if texts or not allow_client_tools:
                raise ValueError(ERROR)
            results = resolve_captured_tool_calls(
                snapshot, current, canonical_json(calls).encode("utf-8"),
            )
            return CapturedToolTurn(
                operation_id=operation_id, provider_metadata_json=metadata,
                assistant_content_json=canonical_json(value["content"]), results=results,
            )
        if len(texts) != 1:
            raise ValueError(ERROR)
        # No fence stripping, recursive JSON search, candidate repair or binding
        # synthesis. The provider itself must return the complete candidate.
        candidate = validate_candidate(snapshot, current, operation_id, texts[0].encode("utf-8"))
        return CapturedFinalTurn(provider_metadata_json=metadata, candidate=candidate)
    except (ValueError, TypeError, AttributeError, RecursionError):
        raise AgentContractError(ERROR) from None
