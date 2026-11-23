"""Clinical response projection: no database, worker, receipt or paid execution."""

from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from test_agent_contracts import NOW, candidate, capture, context

from ciq_api.agent_results import result_view


def fixture(index=0):
    snapshot = capture(index)
    actor = uuid4()
    operation = SimpleNamespace(
        id=uuid4(),
        tenant_id=snapshot.binding.tenant_id,
        request_id=snapshot.binding.request_id,
        actor_id=actor,
        snapshot=snapshot.model_dump(mode="json"),
        state="published",
        created_at=NOW,
        deadline=NOW + timedelta(seconds=120),
    )
    comparison = SimpleNamespace(
        tenant_id=operation.tenant_id,
        operation_id=operation.id,
        candidate=candidate(snapshot, operation.id),
        published_at=NOW + timedelta(seconds=1),
    )
    return operation, comparison, context(snapshot), actor


@pytest.mark.parametrize("index", range(30))
def test_golden_comparisons_keep_exact_money_nulls_and_evidence(index):
    op, comparison, current, actor = fixture(index)
    view = result_view(op, comparison, current, actor)
    assert view.state == "published"
    data = view.model_dump(mode="json")
    assert data["comparison"] == {
        k: v for k, v in comparison.candidate.items() if k not in {"binding", "run_id"}
    }
    assert set(data) == {
        "mode",
        "state",
        "operation_id",
        "created_at",
        "deadline",
        "published_at",
        "policy_version",
        "input_revision",
        "review_version",
        "comparison",
        "request_context",
        "request_job_id",
    }
    assert data["request_context"] is None and data["request_job_id"] is None
    assert data["mode"] == "synthetic-only"


@pytest.mark.parametrize(
    "field,value",
    [
        ("input_revision", 99),
        ("review_version", 99),
        ("policy_version", "changed"),
        ("policy_id", uuid4()),
        ("tenant_id", uuid4()),
        ("request_id", "OTHER"),
        ("input_digest", "0" * 64),
        ("rules_digest", "0" * 64),
        ("policy_digest", "0" * 64),
        ("evidence_digest", "0" * 64),
    ],
)
def test_changed_binding_never_reveals_old_candidate(field, value):
    op, comparison, current, actor = fixture()
    current = current.model_copy(
        update={"binding": current.binding.model_copy(update={field: value})}
    )
    result = result_view(op, comparison, current, actor)
    assert result.state in {"stale", "unavailable"}
    assert result.comparison is result.operation_id is result.policy_version is None


@pytest.mark.parametrize(
    "state",
    [
        "reserved",
        "submitting",
        "unknown",
        "rejected",
        "superseded",
        "expired",
    ],
)
def test_nonpublished_state_cannot_reveal_even_a_stored_candidate(state):
    op, comparison, current, actor = fixture()
    op.state = state
    result = result_view(op, comparison, current, actor)
    assert result.state == state
    assert result.comparison is result.published_at is None


@pytest.mark.parametrize(
    "fault",
    [
        "wrong_actor",
        "missing_result",
        "wrong_result_tenant",
        "wrong_result_operation",
        "malformed_snapshot",
        "wrong_run",
        "invalid_money",
        "citation_drift",
        "extra_field",
    ],
)
def test_invalid_private_storage_is_a_safe_empty_response(fault):
    op, comparison, current, actor = fixture()
    if fault == "wrong_actor":
        actor = uuid4()
    elif fault == "missing_result":
        comparison = None
    elif fault == "wrong_result_tenant":
        comparison.tenant_id = uuid4()
    elif fault == "wrong_result_operation":
        comparison.operation_id = uuid4()
    elif fault == "malformed_snapshot":
        op.snapshot = {"facts_json": "PRIVATE CANARY"}
    elif fault == "wrong_run":
        comparison.candidate["run_id"] = str(uuid4())
    elif fault == "invalid_money":
        comparison.candidate["payable_inr"] = True
    elif fault == "citation_drift":
        comparison.candidate["citations"][0]["source_digest"] = "0" * 64
    else:
        comparison.candidate["PRIVATE CANARY"] = "PRIVATE CANARY"
    result = result_view(op, comparison, current, actor)
    assert result.state == "unavailable"
    assert result.comparison is result.operation_id is None
    assert "PRIVATE CANARY" not in result.model_dump_json()


def test_correlation_changes_alone_do_not_invalidate_provenance():
    op, comparison, current, actor = fixture()
    current = current.model_copy(
        update={"binding": current.binding.model_copy(update={"correlation_id": uuid4()})}
    )
    assert result_view(op, comparison, current, actor).state == "published"


def test_not_requested_is_distinct_from_failed_or_successful_execution():
    _, _, current, actor = fixture()
    result = result_view(None, None, current, actor)
    assert result.state == "not_requested"
    assert result.comparison is result.operation_id is None
