"""Offline saved-decision boundary tests; no connector or fixture substitution."""

import json
from copy import deepcopy
from decimal import Decimal

import pytest

from cashlessiq.source_decision import SourceDecisionError, observe_saved_decision


@pytest.fixture
def inputs():
    decision = {
        "request_id": "GOL001",
        "outcome": "APPROVE_WITH_DEDUCTIONS",
        "total_claimed_inr": 100_000,
        "total_payable_inr": 95_000,
        "lines": [
            {
                "item": "Treatment",
                "claimed_inr": 100_000,
                "payable_inr": 95_000,
                "deduction_inr": 5_000,
                "reason": "Policy co-pay",
                "calc": "Saved calculation",
                "citations": [
                    {"type": "clause", "id": "COPAY"},
                    {"type": "record", "id": "CORE.POLICY:POL0001"},
                ],
            }
        ],
        "queries": [],
        "refer_reasons": [],
        "summary": "Synthetic test only",
        "sla": {"elapsed_min": 0, "state": "GREEN"},
    }
    return {
        "row": {
            "request_id": "GOL001",
            "tpa_id": "TPA001",
            "outcome": decision["outcome"],
            "payable_inr": Decimal(95_000),
            "schema_valid": False,
            "decision_json": decision,
        },
        "request_id": "GOL001",
        "tpa_id": "TPA001",
        "product_id": "PRODUCT1",
        "estimated_total_inr": 110_000,
        "evidence": [
            {
                "request_id": "GOL001",
                "tpa_id": "TPA001",
                "product_id": "PRODUCT1",
                "clause_id": "COPAY",
            }
        ],
        "verified_record_ids": frozenset({"CORE.POLICY:POL0001"}),
    }


@pytest.mark.parametrize("encoded", [False, True])
def test_approval_copies_saved_amounts_and_revalidates(inputs, encoded):
    original = deepcopy(inputs)
    if encoded:
        inputs["row"]["decision_json"] = json.dumps(inputs["row"]["decision_json"])
    result = observe_saved_decision(**inputs)
    assert (result.claimed_inr, result.payable_inr) == (100_000, 95_000)
    assert result.amount_basis == "saved_calculation"
    if not encoded:
        assert inputs == original


@pytest.mark.parametrize("outcome,estimate", [("QUERY", 90_000), ("REFER", 80_000)])
def test_uncomputed_uses_supplied_estimate_not_zero_payable(inputs, outcome, estimate):
    inputs["estimated_total_inr"] = estimate
    decision = inputs["row"]["decision_json"]
    decision.update(
        outcome=outcome,
        lines=[],
        total_claimed_inr=0,
        total_payable_inr=0,
        queries=["Missing breakup"] if outcome == "QUERY" else [],
        refer_reasons=["PED review"] if outcome == "REFER" else [],
    )
    inputs["row"].update(outcome=outcome, payable_inr=0)
    result = observe_saved_decision(**inputs)
    assert result.claimed_inr == estimate
    assert result.payable_inr is None
    assert result.amount_basis == "supplied_estimate"


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "wrong_request",
        "wrong_owner",
        "json_request",
        "outcome",
        "payable",
        "bad_total",
        "no_citation",
        "unknown_clause",
        "unknown_record",
        "foreign_product",
        "foreign_evidence_owner",
        "foreign_evidence_request",
        "duplicate_clause",
        "empty_evidence",
        "float_money",
        "bool_money",
        "float_stored",
        "bad_estimate",
        "deny",
        "duplicate_json",
        "invalid_json",
        "partial_query",
        "empty_approval",
        "query_without_question",
        "refer_without_reason",
    ],
)
def test_rejects_inconsistent_or_unresolved_source(inputs, fault):
    row = inputs["row"]
    decision = row["decision_json"]
    line = decision["lines"][0]
    if fault == "missing":
        inputs["row"] = {}
    elif fault == "wrong_request":
        row["request_id"] = "GOL024"
    elif fault == "wrong_owner":
        row["tpa_id"] = "TPA003"
    elif fault == "json_request":
        decision["request_id"] = "GOL024"
    elif fault == "outcome":
        row["outcome"] = "APPROVE"
    elif fault == "payable":
        row["payable_inr"] = 1
    elif fault == "bad_total":
        decision["total_payable_inr"] = 1
    elif fault == "no_citation":
        line["citations"] = []
    elif fault == "unknown_clause":
        line["citations"][0]["id"] = "FOREIGN"
    elif fault == "unknown_record":
        inputs["verified_record_ids"] = frozenset()
    elif fault.startswith("foreign_"):
        field = {
            "foreign_product": "product_id",
            "foreign_evidence_owner": "tpa_id",
            "foreign_evidence_request": "request_id",
        }[fault]
        inputs["evidence"][0][field] = "FOREIGN"
    elif fault == "duplicate_clause":
        inputs["evidence"] *= 2
    elif fault == "empty_evidence":
        inputs["evidence"] = []
    elif fault == "float_money":
        line["claimed_inr"] = 100_000.0
    elif fault == "bool_money":
        decision["total_claimed_inr"] = True
    elif fault == "float_stored":
        row["payable_inr"] = 95_000.0
    elif fault == "bad_estimate":
        inputs["estimated_total_inr"] = True
    elif fault == "deny":
        decision["outcome"] = row["outcome"] = "DENY"
    elif fault == "duplicate_json":
        row["decision_json"] = '{"request_id":"GOL001","request_id":"GOL024"}'
    elif fault == "invalid_json":
        row["decision_json"] = "not json"
    elif fault == "partial_query":
        decision.update(outcome="QUERY", queries=["Review"])
        row["outcome"] = "QUERY"
    elif fault == "empty_approval":
        decision.update(lines=[], total_claimed_inr=0, total_payable_inr=0)
        row["payable_inr"] = 0
    elif fault in {"query_without_question", "refer_without_reason"}:
        decision["outcome"] = row["outcome"] = (
            "QUERY" if fault == "query_without_question" else "REFER"
        )
    with pytest.raises(
        SourceDecisionError, match=r"^Saved source decision unavailable or invalid$"
    ):
        observe_saved_decision(**inputs)
