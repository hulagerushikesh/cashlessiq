"""Inactive agent comparison contract. No transport, routes, credentials or persistence.

All values are clinical/internal. Trusted context must come from locked product
records and authorization, never from a browser or an agent response. Hashes bind
snapshots; they do not establish ownership, approval or authenticity.
"""

import json
from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

from ciq_api.assessment import CalculationPolicy, calculate_rules, fingerprint
from ciq_api.contracts import Outcome
from ciq_api.mvp_contracts import AssessmentInput, ClauseInput, PolicyProposal

Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Label = Annotated[str, Field(min_length=1, max_length=120)]
Money = Annotated[int, Field(strict=True, ge=0, le=100_000_000)]
Revision = Annotated[int, Field(strict=True, ge=0)]
MAX_RESPONSE_BYTES = 128_000


class AgentContractError(ValueError):
    """Safe fixed error; do not log response bodies or Pydantic input errors."""


class ImmutableContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class AgentBinding(ImmutableContract):
    schema_version: Annotated[int, Field(strict=True, ge=1, le=1)] = 1
    orchestration_version: Literal["inactive-comparison-v1"] = "inactive-comparison-v1"
    tenant_id: UUID
    request_id: Label
    policy_id: UUID
    product_id: Label
    policy_version: Label
    input_revision: Revision
    review_version: Revision
    input_digest: Digest
    rules_digest: Digest
    policy_digest: Digest
    evidence_digest: Digest
    correlation_id: UUID


class EvidenceReference(ImmutableContract):
    kind: Literal["clause", "record"]
    source_id: Label
    source_digest: Digest


class AgentPolicySnapshot(CalculationPolicy):
    """Selected policy projection; never includes unrelated regression examples."""

    effective_from: date
    effective_to: date | None
    wording_document_id: UUID | None
    clauses: list[ClauseInput] = Field(min_length=1, max_length=40)

    @model_validator(mode="after")
    def coherent_policy(self):
        ids = {c.clause_id for c in self.clauses}
        singleton = [r.rule_type for r in self.rules if r.rule_type != "WAITING_SPECIFIC"]
        if (
            (self.effective_to and self.effective_to < self.effective_from)
            or len(ids) != len(self.clauses)
            or any(r.clause_id not in ids for r in self.rules)
            or len({r.rule_id for r in self.rules}) != len(self.rules)
            or len(singleton) != len(set(singleton))
        ):
            raise ValueError("Invalid selected policy projection")
        return self


class AgentInput(ImmutableContract):
    binding: AgentBinding
    # Canonical JSON strings prevent mutation of nested clinical lists/dicts.
    facts_json: str = Field(max_length=64_000, repr=False)
    policy_json: str = Field(max_length=1_000_000, repr=False)

    @model_validator(mode="after")
    def coherent_snapshot(self):
        facts, policy = self.snapshots()
        b = self.binding
        if (
            self.facts_json != canonical_json(facts)
            or self.policy_json != canonical_json(policy)
            or b.product_id != policy["product_id"]
            or b.policy_version != policy["version"]
            or b.input_digest != fingerprint(facts)
            or b.rules_digest != fingerprint(policy["rules"])
            or b.policy_digest != fingerprint(policy)
            or b.evidence_digest != fingerprint(self.evidence_payload())
        ):
            raise AgentContractError("snapshot_mismatch")
        return self

    def snapshots(self):
        facts = AssessmentInput.model_validate_json(self.facts_json).model_dump(mode="json")
        policy = AgentPolicySnapshot.model_validate_json(self.policy_json).model_dump(mode="json")
        return facts, policy

    def evidence_payload(self):
        facts, policy = self.snapshots()
        return {
            "policy_id": str(self.binding.policy_id),
            "clauses": policy["clauses"],
            "request_id": self.binding.request_id,
            "facts": facts,
        }

    def evidence(self) -> tuple[EvidenceReference, ...]:
        facts, policy = self.snapshots()
        return (
            EvidenceReference(
                kind="record", source_id=self.binding.request_id, source_digest=fingerprint(facts)
            ),
            *(
                EvidenceReference(
                    kind="clause", source_id=c["clause_id"], source_digest=fingerprint(c)
                )
                for c in policy["clauses"]
            ),
        )


def canonical_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def capture_input(
    *,
    tenant_id,
    request_id,
    policy_id,
    input_revision,
    review_version,
    correlation_id,
    facts,
    policy,
) -> AgentInput:
    """Capture server-owned inputs only; approval/authorization is checked separately."""
    facts = AssessmentInput.model_validate(facts).model_dump(mode="json")
    policy = PolicyProposal.model_validate(policy).model_dump(
        mode="json",
        include={
            "product_id",
            "version",
            "effective_from",
            "effective_to",
            "wording_document_id",
            "clauses",
            "rules",
        },
    )
    return AgentInput(
        binding=AgentBinding(
            tenant_id=tenant_id,
            request_id=request_id,
            policy_id=policy_id,
            product_id=policy["product_id"],
            policy_version=policy["version"],
            input_revision=input_revision,
            review_version=review_version,
            input_digest=fingerprint(facts),
            rules_digest=fingerprint(policy["rules"]),
            policy_digest=fingerprint(policy),
            evidence_digest=fingerprint(
                {
                    "policy_id": str(policy_id),
                    "clauses": policy["clauses"],
                    "request_id": request_id,
                    "facts": facts,
                }
            ),
            correlation_id=correlation_id,
        ),
        facts_json=canonical_json(facts),
        policy_json=canonical_json(policy),
    )


class AgentContext(ImmutableContract):
    """Current server-owned scope; re-read under a future publication transaction."""

    binding: AgentBinding
    tenant_active: StrictBool
    policy_approved: StrictBool
    clinical_authorized: StrictBool
    review_open: StrictBool


def require_current(snapshot: AgentInput, current: AgentContext) -> None:
    if not all(
        (
            current.tenant_active,
            current.policy_approved,
            current.clinical_authorized,
            current.review_open,
        )
    ):
        raise AgentContractError("scope_unavailable")
    if snapshot.binding != current.binding:
        raise AgentContractError("stale_or_wrong_scope")


class AgentLine(ImmutableContract):
    item: Label
    claimed_inr: Money
    payable_inr: Money
    deduction_inr: Money
    citations: tuple[EvidenceReference, ...] = Field(min_length=1, max_length=40)


class AgentCandidate(ImmutableContract):
    binding: AgentBinding
    run_id: UUID
    outcome: Outcome
    claimed_inr: Money | None
    payable_inr: Money | None
    lines: tuple[AgentLine, ...] = Field(max_length=50)
    citations: tuple[EvidenceReference, ...] = Field(min_length=1, max_length=41)
    # Unverified explanation, restricted to the clinical boundary and human review.
    explanation: str = Field(min_length=1, max_length=4000, repr=False)


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate_key")
        value[key] = item
    return value


def parse_candidate(raw: bytes) -> AgentCandidate:
    """One bounded JSON object, with no coercion of money or ignored fields."""
    try:
        if type(raw) is not bytes or len(raw) > MAX_RESPONSE_BYTES:
            raise ValueError("response_bound")
        value = json.loads(raw, object_pairs_hook=_unique_object)
        return AgentCandidate.model_validate(value)
    except (ValueError, TypeError, RecursionError):
        raise AgentContractError("invalid_agent_response") from None


def validate_candidate(
    snapshot: AgentInput, current: AgentContext, run_id: UUID, raw: bytes
) -> AgentCandidate:
    """Validate a comparison candidate; this does not publish or finalize a review."""
    require_current(snapshot, current)
    candidate = parse_candidate(raw)
    if candidate.binding != snapshot.binding or candidate.run_id != run_id:
        raise AgentContractError("response_binding_mismatch")
    facts, policy = snapshot.snapshots()
    expected = calculate_rules(
        snapshot.binding.request_id,
        facts,
        {k: policy[k] for k in ("product_id", "version", "rules")},
    )
    if (
        candidate.outcome != expected["outcome"]
        or candidate.claimed_inr != expected["claimed_inr"]
        or candidate.payable_inr != expected["payable_inr"]
    ):
        raise AgentContractError("deterministic_mismatch")
    evidence = {(ref.kind, ref.source_id): ref for ref in snapshot.evidence()}

    def exact_citations(refs, required):
        keys = [(ref.kind, ref.source_id) for ref in refs]
        if len(set(keys)) != len(keys) or set(keys) != set(required):
            raise AgentContractError("citation_mismatch")
        if any(evidence.get(key) != ref for key, ref in zip(keys, refs, strict=True)):
            raise AgentContractError("citation_version_mismatch")

    exact_citations(
        candidate.citations,
        [
            ("record", snapshot.binding.request_id),
            *(("clause", cid) for cid in expected["clause_ids"]),
        ],
    )
    expected_lines = expected["payable"]["lines"] if expected["payable"] else ()
    if len(candidate.lines) != len(expected_lines):
        raise AgentContractError("line_mismatch")
    for line, original in zip(candidate.lines, expected_lines, strict=True):
        if any(
            getattr(line, k) != original[k]
            for k in ("item", "claimed_inr", "payable_inr", "deduction_inr")
        ):
            raise AgentContractError("line_mismatch")
        exact_citations(line.citations, [(c["type"], c["id"]) for c in original["citations"]])
    return candidate
