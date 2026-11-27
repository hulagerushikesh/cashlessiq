"""Inactive clinical tools over a captured product snapshot; no source/provider I/O.

These replies are tool observations, never provider candidates or source parity.
The trusted caller supplies freshly authorized context for each read. Nothing in
this module discovers membership, approves policy, schedules work or grants I/O.
"""

from typing import Literal

from pydantic import Field

from ciq_api.agent_contracts import (
    AgentBinding,
    AgentContext,
    AgentContractError,
    AgentInput,
    ImmutableContract,
    canonical_json,
    require_current,
)
from ciq_api.assessment import calculate_rules

ERROR = "snapshot_tools_unavailable"


class SnapshotToolReply(ImmutableContract):
    """Clinical/internal canonical payload; do not expose in logs or general UI."""

    schema_version: Literal["captured-tools-v1"] = "captured-tools-v1"
    tool: Literal["case", "assessment", "clause"]
    origin: Literal["captured-product-snapshot", "shared-deterministic-rules"]
    binding: AgentBinding = Field(repr=False)
    payload_json: str = Field(repr=False)


def select_captured_snapshot(snapshot: AgentInput, current: AgentContext) -> AgentInput:
    """Revalidate trusted capture/context values; this does not obtain authority."""
    try:
        if type(snapshot) is not AgentInput or type(current) is not AgentContext:
            raise ValueError(ERROR)
        # Recheck canonical content/hashes and strict scope flags, including
        # model_copy/model_construct values that bypass Pydantic validation.
        # Serialization warnings can contain private values; validation below
        # still rejects invalid types without emitting those diagnostics.
        snapshot = AgentInput.model_validate(snapshot.model_dump(mode="json", warnings=False))
        current = AgentContext.model_validate(current.model_dump(mode="json", warnings=False))
        require_current(snapshot, current)
        return snapshot
    except (ValueError, TypeError, AttributeError, RecursionError):
        raise AgentContractError(ERROR) from None


def read_captured_case(snapshot: AgentInput, current: AgentContext) -> SnapshotToolReply:
    """Read only the selected request facts, preserving strict money and nulls.

    No legacy request/policy ID is inferred, no history is enriched, and supplied
    remaining cover is not recomputed from other claims or today's date.
    """
    snapshot = select_captured_snapshot(snapshot, current)
    facts, _ = snapshot.snapshots()
    return SnapshotToolReply(
        tool="case",
        origin="captured-product-snapshot",
        binding=snapshot.binding,
        payload_json=canonical_json({
            "facts": facts,
            "evidence": snapshot.evidence()[0].model_dump(mode="json"),
        }),
    )


def assess_captured_case(snapshot: AgentInput, current: AgentContext) -> SnapshotToolReply:
    """Run the shared rules on the selected, ordered policy and captured facts.

    This is a deterministic observation, not generated reasoning or an agent
    outcome. A future provider must return its own separately validated response.
    """
    snapshot = select_captured_snapshot(snapshot, current)
    facts, policy = snapshot.snapshots()
    try:
        result = calculate_rules(
            snapshot.binding.request_id,
            facts,
            {key: policy[key] for key in ("product_id", "version", "rules")},
        )
        evidence = {(ref.kind, ref.source_id): ref for ref in snapshot.evidence()}
        keys = [
            ("record", snapshot.binding.request_id),
            *(("clause", clause_id) for clause_id in result["clause_ids"]),
        ]
        payload = canonical_json({
            "assessment": result,
            "evidence": [evidence[key].model_dump(mode="json") for key in keys],
        })
    except (ValueError, TypeError, KeyError, RecursionError):
        raise AgentContractError(ERROR) from None
    return SnapshotToolReply(
        tool="assessment", origin="shared-deterministic-rules",
        binding=snapshot.binding, payload_json=payload,
    )


def read_captured_clause(
    snapshot: AgentInput, current: AgentContext, clause_id: str
) -> SnapshotToolReply:
    """Resolve an exact owned clause, without search, fallback or source lookup.

    The content hash covers the complete selected clause projection. Clause ID
    equality in another policy or account cannot establish evidence ownership.
    """
    snapshot = select_captured_snapshot(snapshot, current)
    _, policy = snapshot.snapshots()
    if type(clause_id) is not str:
        raise AgentContractError(ERROR)
    matches = [clause for clause in policy["clauses"] if clause["clause_id"] == clause_id]
    if len(matches) != 1:
        raise AgentContractError(ERROR)
    reference = next(
        ref for ref in snapshot.evidence() if ref.kind == "clause" and ref.source_id == clause_id
    )
    return SnapshotToolReply(
        tool="clause",
        origin="captured-product-snapshot",
        binding=snapshot.binding,
        payload_json=canonical_json({
            "clause": matches[0], "evidence": reference.model_dump(mode="json"),
        }),
    )
