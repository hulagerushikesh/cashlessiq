"""Inactive Cortex client-tool codec. No SDK, network, database or execution loop.

Only a trusted future transport may supply the current response's tool-use list.
This module cannot authenticate that response, bind remote conversation history,
approve another billed turn, or publish a candidate. Replies remain clinical.
"""

import json
from typing import Annotated, Literal

from pydantic import Field, StrictBool

from ciq_api.agent_contracts import (
    AgentBinding,
    AgentContext,
    AgentContractError,
    AgentInput,
    ImmutableContract,
    canonical_json,
)
from ciq_api.agent_snapshot_tools import (
    assess_captured_case,
    read_captured_case,
    read_captured_clause,
    select_captured_snapshot,
)

MAX_CALL_BYTES = 16_000
MAX_RESULT_BYTES = 128_000
MAX_CALLS = 8
ERROR = "captured_client_tools_unavailable"


class _ToolUse(ImmutableContract):
    tool_use_id: Annotated[str, Field(min_length=1, max_length=120)]
    type: Literal["generic"]
    name: Literal["ciq_read_case", "ciq_assess_case", "ciq_read_clause"]
    input: dict = Field(repr=False)
    client_side_execute: StrictBool
    # Permission-bearing requests need a separate approval flow. None is
    # implemented here; even empty permission objects are deliberately denied.


class CapturedToolResults(ImmutableContract):
    """Local observations, neither a remote result nor permission to send it."""

    schema_version: Literal["captured-client-tools-v1"] = "captured-client-tools-v1"
    binding: AgentBinding = Field(repr=False)
    content_json: str = Field(repr=False)


def captured_tool_definitions() -> list[dict]:
    """Fresh inline generic specs; intentionally no server-side tool_resources.

    No tenant, request, policy, SQL, URL, command or credential selector is
    accepted from a model. The trusted captured snapshot selects all records.
    """
    tools = []
    for name, description, properties, required in (
        ("ciq_read_case", "Read selected captured request facts and record evidence.", {}, []),
        ("ciq_assess_case", "Calculate the selected request using its pinned rules.", {}, []),
        (
            "ciq_read_clause", "Read an exact clause from the selected captured policy.",
            {"clause_id": {"type": "string", "minLength": 1, "maxLength": 80}}, ["clause_id"],
        ),
    ):
        tools.append({"tool_spec": {
            "type": "generic", "name": name, "description": description,
            "input_schema": {
                "type": "object", "properties": properties, "required": required,
                "additionalProperties": False,
            },
        }})
    return tools


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(ERROR)
        result[key] = value
    return result


def _invalid_constant(_value):
    raise ValueError(ERROR)


def resolve_captured_tool_calls(
    snapshot: AgentInput, current: AgentContext, raw: bytes,
) -> CapturedToolResults:
    """Resolve one bounded, complete JSON tool-use array, preserving call order.

    The input is the tool-use list, NOT SSE events, assistant prose or an entire
    REST response. The future trusted transport must establish the original run,
    parent message, current clinical authority and continuation budget itself.
    No partial batch, error-shaped success, fallback lookup or automatic retry.
    """
    try:
        snapshot = select_captured_snapshot(snapshot, current)
        if type(raw) is not bytes or not 0 < len(raw) <= MAX_CALL_BYTES:
            raise ValueError(ERROR)
        # The provider wire format is UTF-8. Do not accept UTF-16/32 autodetection.
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_unique, parse_constant=_invalid_constant,
        )
        if type(value) is not list or not 1 <= len(value) <= MAX_CALLS:
            raise ValueError(ERROR)
        calls = [_ToolUse.model_validate(call) for call in value]
        if len({call.tool_use_id for call in calls}) != len(calls):
            raise ValueError(ERROR)
        for call in calls:
            if call.client_side_execute is not True:
                raise ValueError(ERROR)
            if call.name == "ciq_read_clause":
                clause_id = call.input.get("clause_id")
                if (
                    set(call.input) != {"clause_id"} or type(clause_id) is not str
                    or not 1 <= len(clause_id) <= 80
                ):
                    raise ValueError(ERROR)
            elif call.input:
                raise ValueError(ERROR)

        content = []
        for call in calls:
            if call.name == "ciq_read_case":
                reply = read_captured_case(snapshot, current)
            elif call.name == "ciq_assess_case":
                reply = assess_captured_case(snapshot, current)
            else:
                reply = read_captured_clause(snapshot, current, call.input["clause_id"])
            content.append({"type": "tool_result", "tool_result": {
                "tool_use_id": call.tool_use_id, "type": "generic", "name": call.name,
                "status": "success", "content": [{
                    "type": "json", "json": {
                        "schema_version": reply.schema_version, "tool": reply.tool,
                        "origin": reply.origin, "binding": reply.binding.model_dump(mode="json"),
                        "payload": json.loads(reply.payload_json),
                    },
                }],
            }})
            # Bound the entire encoded batch, including binding/evidence/framing.
            if len(canonical_json(content).encode("utf-8")) > MAX_RESULT_BYTES:
                raise ValueError(ERROR)
        return CapturedToolResults(binding=snapshot.binding, content_json=canonical_json(content))
    except (ValueError, TypeError, AttributeError, RecursionError):
        # Pydantic/JSON errors and tool arguments may contain clinical values.
        raise AgentContractError(ERROR) from None
