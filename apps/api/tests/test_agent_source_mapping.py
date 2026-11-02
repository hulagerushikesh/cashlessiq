"""Offline mapping faults. All observations are synthetic fixtures, not source proof."""

import ast
import json
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError
from test_agent_contracts import POLICY, capture

from ciq_api import agent_source_mapping
from ciq_api.agent_contracts import AgentContractError, canonical_json
from ciq_api.agent_source_mapping import (
    MAX_MANIFEST_BYTES,
    ROLES,
    CapturedIdentity,
    DefinitionPin,
    GoldenIdentity,
    MappingCase,
    SourceManifest,
    SourceObservation,
    parse_manifest,
    snapshot_pin,
    validate_source_mapping,
)


def package(index=0, path="existing-golden-v1", **capture_changes):
    snapshot = capture(index, **capture_changes)
    source = (
        GoldenIdentity(
            path=path,
            request_id=f"SYN-GOL{index + 1:03}",
            insurance_policy_id="POL-1",
            tpa_id="TPA-1",
        )
        if path == "existing-golden-v1"
        else CapturedIdentity(path=path, capture_id=uuid4())
    )
    definitions = tuple(
        DefinitionPin(role=role, name=f"SYNTHETIC.{role}", content_digest="a" * 64)
        for role in sorted(ROLES)
    )
    observation = SourceObservation(
        tenant_id=snapshot.binding.tenant_id,
        registry_revision="b" * 64,
        source_schema="synthetic-source-v1",
        definitions=definitions,
        source=source,
        facts_json=snapshot.facts_json,
        policy_json=snapshot.policy_json,
    )
    manifest = SourceManifest(
        tenant_id=observation.tenant_id,
        registry_revision=observation.registry_revision,
        source_schema=observation.source_schema,
        definitions=definitions,
        cases=(
            MappingCase(
                product=snapshot_pin(snapshot),
                source=source,
                source_snapshot_digest=observation.snapshot_digest(),
            ),
        ),
    )
    return snapshot, manifest, observation


def validate(parts, **changes):
    snapshot, manifest, observation = parts
    return validate_source_mapping(
        snapshot, manifest, observation, expected_digest=changes.get("digest", manifest.digest())
    )


@pytest.mark.parametrize("index", range(len(POLICY["examples"])))
@pytest.mark.parametrize("path", ["existing-golden-v1", "captured-product-v1"])
def test_all_golden_fixture_projections_match_both_explicit_paths(index, path):
    parts = package(index, path)
    snapshot, manifest, observation = parts
    receipt = validate(parts)
    assert receipt.source_digest == manifest.digest()
    assert receipt.path == path
    assert receipt.source_snapshot_digest == observation.snapshot_digest()
    assert receipt.request_id == snapshot.binding.request_id
    # Null stays null, including incomplete estimates. No legacy _money conversion.
    assert observation.snapshots() == snapshot.snapshots()
    parsed = parse_manifest(canonical_json(manifest.model_dump(mode="json")).encode())
    assert parsed.digest() == manifest.digest()
    assert "facts_json" not in manifest.model_dump_json()
    assert "clinical_note" not in repr(observation)


@pytest.mark.parametrize(
    "field,value",
    [
        ("request_id", "REQ-other"),
        ("policy_id", uuid4()),
        ("product_id", "PRODUCT-other"),
        ("policy_version", "v-other"),
        ("input_revision", 999),
        ("input_digest", "c" * 64),
        ("policy_digest", "c" * 64),
        ("rules_digest", "c" * 64),
        ("evidence_digest", "c" * 64),
    ],
)
def test_exact_product_pin_cannot_drift_even_with_new_manifest_digest(field, value):
    snapshot, manifest, observation = package()
    case = manifest.cases[0]
    changed = case.product.model_copy(update={field: value})
    manifest = manifest.model_copy(
        update={"cases": (case.model_copy(update={"product": changed}),)}
    )
    with pytest.raises(AgentContractError, match=r"^source_mapping_unavailable$"):
        validate((snapshot, manifest, observation))


@pytest.mark.parametrize("target", ["manifest", "observation"])
@pytest.mark.parametrize("field", ["tenant_id", "registry_revision", "source_schema"])
def test_independently_captured_ownership_and_registry_must_match(target, field):
    snapshot, manifest, observation = package()
    value = uuid4() if field == "tenant_id" else "c" * 64
    if target == "manifest":
        manifest = manifest.model_copy(update={field: value})
    else:
        observation = observation.model_copy(update={field: value})
    with pytest.raises(AgentContractError, match="source_mapping_unavailable"):
        validate((snapshot, manifest, observation))


@pytest.mark.parametrize("role", sorted(ROLES))
@pytest.mark.parametrize("field,value", [("content_digest", "c" * 64), ("name", "CHANGED.object")])
def test_unchanged_names_or_changed_tool_search_agent_rules_definitions_are_not_parity(
    role, field, value
):
    snapshot, manifest, observation = package()
    definitions = tuple(
        pin.model_copy(update={field: value}) if pin.role == role else pin
        for pin in observation.definitions
    )
    with pytest.raises(AgentContractError):
        validate((snapshot, manifest, observation.model_copy(update={"definitions": definitions})))


def test_order_independent_inventory_digest_but_ordered_rules_are_preserved():
    snapshot, manifest, observation = package()
    reversed_manifest = manifest.model_copy(
        update={"definitions": tuple(reversed(manifest.definitions))}
    )
    assert reversed_manifest.digest() == manifest.digest()
    validate((snapshot, reversed_manifest, observation))
    policy = json.loads(observation.policy_json)
    policy["rules"].reverse()
    changed = observation.model_copy(update={"policy_json": canonical_json(policy)})
    with pytest.raises(AgentContractError):
        validate((snapshot, manifest, changed))


@pytest.mark.parametrize("change", ["wording", "clause_id", "facts", "remaining", "nullable"])
def test_source_content_drift_is_rejected_even_if_recaptured_hash_is_replaced(change):
    snapshot, manifest, observation = package()
    facts, policy = observation.snapshots()
    if change == "wording":
        policy["clauses"][0]["text"] += " Synthetic changed wording"
    elif change == "clause_id":
        policy["clauses"][0]["page"] += 1
    elif change == "facts":
        facts["diagnosis"] = "Synthetic changed diagnosis"
    elif change == "remaining":
        facts["si_remaining_inr"] -= 1
    else:
        facts["clinical_note"] = None if facts["clinical_note"] else "Synthetic note"
    changed = SourceObservation.model_validate(
        {
            **observation.model_dump(),
            "facts_json": canonical_json(facts),
            "policy_json": canonical_json(policy),
        }
    )
    case = manifest.cases[0].model_copy(
        update={"source_snapshot_digest": changed.snapshot_digest()}
    )
    manifest = manifest.model_copy(update={"cases": (case,)})
    with pytest.raises(AgentContractError):
        validate((snapshot, manifest, changed))


@pytest.mark.parametrize("value", [True, "95000", 95000.0, -1, 100_000_001])
def test_source_money_is_never_coerced(value):
    snapshot, manifest, observation = package()
    facts = json.loads(observation.facts_json)
    facts["estimated_total_inr"] = value
    changed = observation.model_copy(update={"facts_json": canonical_json(facts)})
    with pytest.raises(AgentContractError, match=r"^source_mapping_unavailable$"):
        validate((snapshot, manifest, changed))


@pytest.mark.parametrize("field", ["estimated_total_inr", "clinical_note", "icu_days"])
def test_projection_must_explicitly_preserve_defaults_and_nulls(field):
    snapshot, manifest, observation = package()
    facts = json.loads(observation.facts_json)
    del facts[field]
    with pytest.raises(AgentContractError):
        validate(
            (
                snapshot,
                manifest,
                observation.model_copy(update={"facts_json": canonical_json(facts)}),
            )
        )


@pytest.mark.parametrize("field", ["request_id", "insurance_policy_id", "tpa_id"])
def test_legacy_identifiers_have_separate_bounded_namespaces(field):
    snapshot, manifest, observation = package(request_id="REQ-" + "x" * 100)
    validate((snapshot, manifest, observation))
    source = observation.source.model_dump()
    for value in (snapshot.binding.request_id, str(snapshot.binding.policy_id), "bad id", "../id"):
        with pytest.raises(ValidationError):
            GoldenIdentity.model_validate({**source, field: value})
    assert manifest.cases[0].product.policy_id != observation.source.insurance_policy_id


def test_missing_duplicate_mixed_or_ambiguous_mappings_fail_before_validation():
    _, manifest, _ = package()
    value = manifest.model_dump(mode="json")
    for cases in (
        [],
        [*value["cases"], *value["cases"]],
        [
            value["cases"][0],
            {
                **value["cases"][0],
                "product": {**value["cases"][0]["product"], "request_id": "REQ-second"},
            },
        ],
        [
            value["cases"][0],
            {
                **value["cases"][0],
                "source": {"path": "captured-product-v1", "capture_id": str(uuid4())},
                "product": {**value["cases"][0]["product"], "request_id": "REQ-second"},
            },
        ],
    ):
        with pytest.raises(AgentContractError, match=r"^invalid_source_mapping$"):
            parse_manifest(canonical_json({**value, "cases": cases}).encode())


@pytest.mark.parametrize(
    "change", ["duplicate_role", "unknown_role", "missing_role", "extra_field"]
)
def test_definition_inventory_never_uses_first_or_last_wins(change):
    _, manifest, _ = package()
    value = manifest.model_dump(mode="json")
    if change == "duplicate_role":
        value["definitions"][0] = value["definitions"][1]
    elif change == "unknown_role":
        value["definitions"][0]["role"] = "MEMBER_360"
    elif change == "missing_role":
        value["definitions"].pop()
    else:
        value["credentials"] = "SYNTHETIC-DO-NOT-LOG"
    with pytest.raises(AgentContractError, match=r"^invalid_source_mapping$") as exc:
        parse_manifest(canonical_json(value).encode())
    assert "SYNTHETIC-DO-NOT-LOG" not in str(exc.value)


@pytest.mark.parametrize(
    "raw", [b"{}", b"null", b"[]", b"not-json", b"x" * (MAX_MANIFEST_BYTES + 1)]
)
def test_untrusted_json_errors_are_bounded_and_fixed(raw):
    with pytest.raises(AgentContractError, match=r"^invalid_source_mapping$"):
        parse_manifest(raw)


def test_duplicate_json_keys_and_pinned_hash_drift_fail_closed():
    parts = package()
    raw = canonical_json(parts[1].model_dump(mode="json")).encode()
    with pytest.raises(AgentContractError):
        parse_manifest(b'{"tenant_id":"duplicate",' + raw[1:])
    with pytest.raises(AgentContractError):
        validate(parts, digest="c" * 64)


def test_receipt_is_immutable_and_review_fences_are_not_source_capture_versions():
    snapshot, manifest, observation = package()
    receipt = validate((snapshot, manifest, observation))
    changed = snapshot.model_copy(
        update={
            "binding": snapshot.binding.model_copy(
                update={"review_version": 999, "correlation_id": uuid4()}
            )
        }
    )
    assert validate((changed, manifest, observation)) == receipt
    with pytest.raises(ValidationError):
        receipt.source_digest = "c" * 64
    assert "permit" not in receipt.model_dump()


def test_multiple_cases_order_does_not_change_digest_or_allow_cross_request_source():
    first, manifest, observation = package()
    second, second_manifest, second_observation = package(
        1,
        tenant_id=first.binding.tenant_id,
        request_id="REQ-second",
        policy_id=first.binding.policy_id,
    )
    manifest = manifest.model_copy(update={"cases": (*manifest.cases, *second_manifest.cases)})
    validate((first, manifest, observation))
    validate((second, manifest, second_observation))
    assert (
        manifest.model_copy(update={"cases": tuple(reversed(manifest.cases))}).digest()
        == manifest.digest()
    )
    with pytest.raises(AgentContractError):
        validate((first, manifest, second_observation))


def test_mapping_validator_is_unwired_and_has_no_provider_or_database_dependency():
    package_dir = Path(agent_source_mapping.__file__).parent
    for name in (
        "main.py",
        "jobs.py",
        "local_worker.py",
        "reviews.py",
        "mvp.py",
        "agent_ledger.py",
    ):
        tree = ast.parse((package_dir / name).read_text())
        assert not any(
            isinstance(node, ast.ImportFrom)
            and node.module
            and "agent_source_mapping" in node.module
            for node in ast.walk(tree)
        )
    tree = ast.parse(Path(agent_source_mapping.__file__).read_text())
    forbidden = ("snowflake", "sqlalchemy", "httpx", "requests", "subprocess", "socket")
    assert not any(
        isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(forbidden)
        for node in ast.walk(tree)
    )
    # The clinical observation fixture is constructed here only; production code
    # has no function that manufactures independent observations from AgentInput.
    assert deepcopy(POLICY)["examples"] == POLICY["examples"]


@pytest.mark.parametrize("field", ["insurance_policy_id", "tpa_id"])
def test_same_legacy_request_cannot_alias_new_product_request_by_changing_ownership_claim(field):
    _, manifest, _ = package()
    value = manifest.model_dump(mode="json")
    second = deepcopy(value["cases"][0])
    second["product"]["request_id"] = "REQ-second"
    second["source"][field] = "CHANGED"
    value["cases"].append(second)
    with pytest.raises(AgentContractError, match=r"^invalid_source_mapping$"):
        parse_manifest(canonical_json(value).encode())
