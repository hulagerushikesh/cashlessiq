"""Inactive source-mapping coherence checks; no source I/O or execution authority.

A trusted preflight must independently capture observations and verify ownership,
privileges and definitions. Matching caller-supplied hashes does not do that.
ValidatedMapping is a local validation receipt, never a submission permit.
"""

import json
from typing import Annotated, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, model_validator

from ciq_api.agent_contracts import (
    AgentContractError,
    AgentInput,
    AgentPolicySnapshot,
    Digest,
    ImmutableContract,
    Label,
    Revision,
    canonical_json,
)
from ciq_api.assessment import fingerprint
from ciq_api.mvp_contracts import AssessmentInput

MAX_MANIFEST_BYTES = 128_000
SourceId = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,20}$")]
ObjectName = Annotated[str, Field(pattern=r"^[A-Za-z0-9_.-]{1,200}$")]
ROLES = frozenset(
    {"agent", "case_tool", "waiting_tool", "payable_tool", "sla_tool", "clause_search", "rules"}
)


class MappingContract(ImmutableContract):
    model_config = ConfigDict(
        extra="forbid", frozen=True, hide_input_in_errors=True, revalidate_instances="always"
    )


class SnapshotPin(MappingContract):
    """Computation identity; review version/correlation remain publication fences."""

    request_id: Label
    policy_id: UUID
    product_id: Label
    policy_version: Label
    input_revision: Revision
    input_digest: Digest
    policy_digest: Digest
    rules_digest: Digest
    evidence_digest: Digest


class GoldenIdentity(MappingContract):
    path: Literal["existing-golden-v1"]
    # Distinct namespaces: none of these are a product policy-version UUID.
    request_id: SourceId
    insurance_policy_id: SourceId
    tpa_id: SourceId


class CapturedIdentity(MappingContract):
    path: Literal["captured-product-v1"]
    # A capture handle, not a legacy lookup key or proof of a supported transport.
    capture_id: UUID


SourceIdentity = Annotated[GoldenIdentity | CapturedIdentity, Field(discriminator="path")]


class DefinitionPin(MappingContract):
    role: Literal[
        "agent", "case_tool", "waiting_tool", "payable_tool", "sla_tool", "clause_search", "rules"
    ]
    name: ObjectName
    content_digest: Digest


def _definitions(pins):
    if len(pins) != len(ROLES) or {p.role for p in pins} != ROLES:
        raise ValueError("invalid_definition_set")
    # Canonical ordering makes inventory order irrelevant; duplicates never win.
    return tuple(sorted(pins, key=lambda p: p.role))


class MappingCase(MappingContract):
    product: SnapshotPin
    source: SourceIdentity
    source_snapshot_digest: Digest


class SourceManifest(MappingContract):
    schema_version: Literal["source-mapping-v1"] = "source-mapping-v1"
    input_schema: Literal["agent-input-v1"] = "agent-input-v1"
    normalization: Literal["canonical-inr-integer-null-v1"] = "canonical-inr-integer-null-v1"
    tenant_id: UUID
    registry_revision: Digest
    source_schema: ObjectName
    definitions: tuple[DefinitionPin, ...] = Field(min_length=7, max_length=7)
    cases: tuple[MappingCase, ...] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def coherent(self):
        _definitions(self.definitions)
        requests = [case.product.request_id for case in self.cases]
        # A legacy request is globally identified by its request key, not by a
        # caller's claimed policy/TPA. Changing that claim cannot create a second
        # source case or make an ambiguous alias acceptable.
        sources = [
            case.source.request_id
            if isinstance(case.source, GoldenIdentity)
            else str(case.source.capture_id)
            for case in self.cases
        ]
        if len(set(requests)) != len(requests) or len(set(sources)) != len(sources):
            raise ValueError("ambiguous_mapping")
        if len({case.source.path for case in self.cases}) != 1:
            raise ValueError("mixed_input_paths")
        return self

    def digest(self) -> str:
        value = self.model_dump(mode="json")
        value["definitions"] = [p.model_dump(mode="json") for p in _definitions(self.definitions)]
        value["cases"] = sorted(value["cases"], key=lambda c: c["product"]["request_id"])
        return fingerprint(value)


class SourceObservation(MappingContract):
    """Clinical, trusted preflight projection; never log or expose to processors.

    facts/policy must be independently captured and normalized under the reviewed
    mapping, not copied from AgentInput to manufacture apparent source parity.
    Extra raw-source custody and authorization are outside this offline contract.
    """

    tenant_id: UUID
    registry_revision: Digest
    source_schema: ObjectName
    definitions: tuple[DefinitionPin, ...] = Field(min_length=7, max_length=7)
    source: SourceIdentity
    facts_json: str = Field(max_length=64_000, repr=False)
    policy_json: str = Field(max_length=1_000_000, repr=False)

    @model_validator(mode="after")
    def coherent(self):
        _definitions(self.definitions)
        facts, policy = self.snapshots()
        if self.facts_json != canonical_json(facts) or self.policy_json != canonical_json(policy):
            raise ValueError("noncanonical_source_projection")
        return self

    def snapshots(self):
        facts = AssessmentInput.model_validate_json(self.facts_json).model_dump(mode="json")
        policy = AgentPolicySnapshot.model_validate_json(self.policy_json).model_dump(mode="json")
        return facts, policy

    def snapshot_digest(self) -> str:
        facts, policy = self.snapshots()
        return fingerprint(
            {
                "projection": "source-projection-v1",
                "tenant_id": str(self.tenant_id),
                "registry_revision": self.registry_revision,
                "source_schema": self.source_schema,
                "source": self.source.model_dump(mode="json"),
                "facts": facts,
                "policy": policy,
            }
        )


class ValidatedMapping(MappingContract):
    """Coherence receipt only; not an access grant, spend approval or I/O permit."""

    tenant_id: UUID
    request_id: Label
    source_digest: Digest
    source_snapshot_digest: Digest
    path: Literal["existing-golden-v1", "captured-product-v1"]


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_key")
        result[key] = value
    return result


def parse_manifest(raw: bytes) -> SourceManifest:
    """One bounded JSON manifest with no duplicate keys or ignored fields."""
    try:
        if type(raw) is not bytes or len(raw) > MAX_MANIFEST_BYTES:
            raise ValueError("manifest_bound")
        return SourceManifest.model_validate(json.loads(raw, object_pairs_hook=_unique_object))
    except (ValueError, TypeError, RecursionError):
        raise AgentContractError("invalid_source_mapping") from None


def snapshot_pin(snapshot: AgentInput) -> SnapshotPin:
    return SnapshotPin.model_validate(
        snapshot.binding.model_dump(mode="json", include=set(SnapshotPin.model_fields))
    )


def validate_source_mapping(
    snapshot: AgentInput,
    manifest: SourceManifest,
    observation: SourceObservation,
    *,
    expected_digest: str,
) -> ValidatedMapping:
    """Fail closed on drift. All arguments must come from trusted server custody.

    No live path calls this yet. The expected digest must be separately pinned by
    a reviewed admission, not calculated from an untrusted incoming manifest.
    """
    try:
        # Revalidate even model_copy/model_construct objects; nested lists in the
        # older AgentInput are rechecked through its canonical JSON contract.
        snapshot = AgentInput.model_validate(snapshot.model_dump(mode="json"))
        manifest = SourceManifest.model_validate(manifest)
        observation = SourceObservation.model_validate(observation)
        pin = snapshot_pin(snapshot)
        matches = [case for case in manifest.cases if case.product.request_id == pin.request_id]
        if (
            expected_digest != manifest.digest()
            or manifest.tenant_id != snapshot.binding.tenant_id
            or observation.tenant_id != manifest.tenant_id
            or observation.registry_revision != manifest.registry_revision
            or observation.source_schema != manifest.source_schema
            or _definitions(observation.definitions) != _definitions(manifest.definitions)
            or len(matches) != 1
        ):
            raise ValueError("mapping_mismatch")
        case = matches[0]
        facts, policy = observation.snapshots()
        if (
            case.product != pin
            or case.source != observation.source
            or case.source_snapshot_digest != observation.snapshot_digest()
            or (facts, policy) != snapshot.snapshots()
        ):
            raise ValueError("source_snapshot_mismatch")
        return ValidatedMapping(
            tenant_id=manifest.tenant_id,
            request_id=pin.request_id,
            source_digest=manifest.digest(),
            source_snapshot_digest=case.source_snapshot_digest,
            path=case.source.path,
        )
    except (ValueError, TypeError, RecursionError):
        raise AgentContractError("source_mapping_unavailable") from None
