"""Offline HTTP/projection controls; PostgreSQL authority is tested separately."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from single_call_fixtures import call_material
from test_agent_contracts import candidate, context

from ciq_api import agent_single_call_results as results

ACTOR = uuid4()


@pytest.fixture
def material():
    snapshot, _, _, _ = call_material()
    return record(snapshot), snapshot, context(snapshot)


def record(snapshot):
    now, op = datetime.now(UTC), uuid4()
    row = dict(operation_id=op, tenant_id=snapshot.binding.tenant_id, actor_id=ACTOR,
               request_id=snapshot.binding.request_id, phase="published",
               snapshot=snapshot.model_dump(mode="json"), checkpoint_at=now,
               deadline=now + timedelta(seconds=18), published_at=now + timedelta(seconds=1),
               candidate=candidate(snapshot, op))
    return row


def test_current_published_result_is_revalidated_and_only_clinical_view_is_returned(material):
    row, _, current = material
    view = results.single_call_result(row, current, ACTOR)
    assert view.state == "published" and view.comparison.payable_inr == 95000
    assert view.execution_profile == results.PROFILE
    assert not {"snapshot", "candidate", "pin", "observation", "actor_id", "tenant_id"} & (
        view.model_dump().keys())
    assert view.request_context is None  # Never offers a generic executor request.


@pytest.mark.parametrize("field", ["tenant_id", "actor_id", "request_id", "operation_id"])
def test_foreign_or_reassociated_records_are_redacted(material, field):
    row, _, current = material
    row[field] = "OTHER" if field == "request_id" else uuid4()
    view = results.single_call_result(row, current, ACTOR)
    assert view.state == "unavailable"
    assert view.operation_id is view.comparison is view.policy_version is None


@pytest.mark.parametrize("fault", ["amount", "citation", "explanation", "extra", "timestamps"])
def test_corrupt_saved_candidates_never_cross_http_projection(material, fault):
    row, _, current = material
    if fault == "amount":
        row["candidate"]["payable_inr"] = 1
    elif fault == "citation":
        row["candidate"]["citations"][0]["source_id"] = "PRIVATE FOREIGN EVIDENCE"
    elif fault == "explanation":
        row["candidate"]["explanation"] = "x" * 4001
    elif fault == "extra":
        row["private_plan"] = "PRIVATE RAW BODY"
    else:
        row["published_at"] = row["deadline"]
    view = results.single_call_result(row, current, ACTOR)
    assert view.state == "unavailable" and view.comparison is view.operation_id is None
    assert "PRIVATE" not in view.model_dump_json()


@pytest.mark.parametrize("fault", ["revision", "policy", "review", "tenant", "authorization"])
def test_current_scope_change_withholds_all_prior_metadata(material, fault):
    row, _, current = material
    if fault in {"revision", "policy", "review"}:
        key = {"revision": "input_revision", "policy": "policy_version",
               "review": "review_version"}[fault]
        value = "CHANGED" if fault == "policy" else getattr(current.binding, key) + 1
        current = current.model_copy(update={
            "binding": current.binding.model_copy(update={key: value}),
        })
    else:
        key = "tenant_active" if fault == "tenant" else "clinical_authorized"
        current = current.model_copy(update={key: False})
    view = results.single_call_result(row, current, ACTOR)
    assert view.state == "stale" and view.comparison is view.operation_id is None


@pytest.mark.parametrize("phase,expected", [("staged", "reserved"), ("checkpointed", "unknown")])
def test_unpublished_phase_is_not_remote_execution_proof(material, phase, expected):
    row, _, current = material
    row.update(phase=phase, published_at=None, candidate=None)
    if phase == "staged":
        row.update(checkpoint_at=None, deadline=None)
    view = results.single_call_result(row, current, ACTOR)
    assert view.state == expected and view.comparison is view.request_context is None


def test_published_advisory_can_be_read_after_execution_deadline(material):
    row, _, current = material
    for name in ("checkpoint_at", "published_at", "deadline"):
        row[name] -= timedelta(days=1)
    assert results.single_call_result(row, current, ACTOR).state == "published"


def test_config_never_enables_execution_or_reads_outside_synthetic_mode(settings):
    with pytest.raises(ValueError, match="require synthetic workflows"):
        type(settings).model_validate({**settings.model_dump(), "single_call_advisory_reads": True})


