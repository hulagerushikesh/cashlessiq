"""Availability is not a financial outcome or a source-error fallback."""

from copy import deepcopy
from dataclasses import FrozenInstanceError, asdict

import pytest

from cashlessiq.source_decision import SourceDecisionError
from cashlessiq.source_recommendation import (
    MissingRecommendation,
    SavedRecommendation,
    observe_source_recommendation,
)


@pytest.fixture
def inputs():
    return {
        "rows": [],
        "request_id": "GOL024",
        "tpa_id": "TPA003",
        "product_id": "AS_NIA_V02_2425",
        "estimated_total_inr": 80_000,
        "evidence": [],
        "verified_record_ids": frozenset(),
    }


def test_missing_has_estimate_but_no_fabricated_recommendation(inputs):
    before = deepcopy(inputs)
    result = observe_source_recommendation(**inputs)
    assert isinstance(result, MissingRecommendation)
    assert asdict(result) == {
        "request_id": "GOL024",
        "tpa_id": "TPA003",
        "product_id": "AS_NIA_V02_2425",
        "supplied_estimate_inr": 80_000,
        "state": "MISSING",
    }
    assert not hasattr(result, "decision")
    assert not hasattr(result, "outcome")
    assert not hasattr(result, "payable_inr")
    assert inputs == before
    with pytest.raises(FrozenInstanceError):
        result.state = "SAVED"


@pytest.mark.parametrize("outcome,estimate", [("QUERY", 90_000), ("REFER", 80_000)])
def test_saved_query_and_refer_are_not_missing(inputs, outcome, estimate):
    inputs["estimated_total_inr"] = estimate
    inputs["evidence"] = [{
        "request_id": inputs["request_id"],
        "tpa_id": inputs["tpa_id"],
        "product_id": inputs["product_id"],
        "clause_id": "PED",
    }]
    decision = {
        "request_id": inputs["request_id"],
        "outcome": outcome,
        "total_claimed_inr": 0,
        "total_payable_inr": 0,
        "lines": [],
        "queries": ["Missing breakup"] if outcome == "QUERY" else [],
        "refer_reasons": ["PED review"] if outcome == "REFER" else [],
        "summary": "Synthetic test",
        "sla": {"elapsed_min": 0, "state": "GREEN"},
    }
    inputs["rows"] = [{
        "request_id": inputs["request_id"],
        "tpa_id": inputs["tpa_id"],
        "outcome": outcome,
        "payable_inr": 0,
        "decision_json": decision,
    }]
    result = observe_source_recommendation(**inputs)
    assert isinstance(result, SavedRecommendation)
    assert result.state == "SAVED"
    assert result.decision.outcome == outcome
    assert result.decision.claimed_inr == estimate
    assert result.decision.payable_inr is None


def test_saved_approval_validates_citations_without_fallback(inputs):
    inputs["evidence"] = [{
        "request_id": inputs["request_id"], "tpa_id": inputs["tpa_id"],
        "product_id": inputs["product_id"], "clause_id": "COPAY",
    }]
    inputs["rows"] = [{
        "request_id": inputs["request_id"], "tpa_id": inputs["tpa_id"],
        "outcome": "APPROVE_WITH_DEDUCTIONS", "payable_inr": 76_000,
        "decision_json": {
            "request_id": inputs["request_id"], "outcome": "APPROVE_WITH_DEDUCTIONS",
            "total_claimed_inr": 80_000, "total_payable_inr": 76_000,
            "lines": [{
                "item": "Treatment", "claimed_inr": 80_000, "payable_inr": 76_000,
                "deduction_inr": 4_000, "reason": "Saved co-pay", "calc": "Saved trace",
                "citations": [{"type": "clause", "id": "COPAY"}],
            }],
            "queries": [], "refer_reasons": [], "summary": "Synthetic test",
            "sla": {"elapsed_min": 0, "state": "GREEN"},
        },
    }]
    before = deepcopy(inputs)
    result = observe_source_recommendation(**inputs)
    assert isinstance(result, SavedRecommendation)
    assert result.decision.payable_inr == 76_000
    assert inputs == before
    inputs["rows"][0]["decision_json"]["lines"][0]["citations"][0]["id"] = "FOREIGN"
    with pytest.raises(SourceDecisionError):
        observe_source_recommendation(**inputs)


@pytest.mark.parametrize("rows", [None, {}, "", [{}], [{}, {}]])
def test_bad_or_ambiguous_rows_never_become_missing(inputs, rows):
    inputs["rows"] = rows
    with pytest.raises(SourceDecisionError):
        observe_source_recommendation(**inputs)


@pytest.mark.parametrize("field,value", [
    ("request_id", ""), ("tpa_id", " "), ("product_id", None),
    ("estimated_total_inr", True), ("estimated_total_inr", -1),
    ("estimated_total_inr", 80_000.0),
])
def test_missing_still_requires_valid_context(inputs, field, value):
    inputs[field] = value
    with pytest.raises(SourceDecisionError):
        observe_source_recommendation(**inputs)
