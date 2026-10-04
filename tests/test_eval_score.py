"""Unit tests for deterministic golden-case scoring."""

from eval.run_eval import score


def test_score_matches_outcome_amount_and_citations() -> None:
    decision = {
        "outcome": "APPROVE_WITH_DEDUCTIONS",
        "total_payable_inr": 95_000,
        "lines": [
            {
                "citations": [
                    {"type": "clause", "id": "NIA-4.1-A"},
                    {"type": "clause", "id": "NIA-9.5"},
                ]
            }
        ],
    }
    case = {
        "expected_outcome": "APPROVE_WITH_DEDUCTIONS",
        "expected_payable_inr": 95_000,
        "expected_clause_ids": ["NIA-4.1-A", "NIA-9.5"],
    }
    assert score(decision, case) == {
        "actual_outcome": "APPROVE_WITH_DEDUCTIONS",
        "actual_payable_inr": 95_000,
        "outcome_match": True,
        "amount_match": True,
        "citation_recall": 1.0,
    }


def test_score_treats_null_expected_amount_as_not_applicable() -> None:
    decision = {"outcome": "QUERY", "total_payable_inr": 0, "lines": []}
    case = {
        "expected_outcome": "QUERY",
        "expected_payable_inr": None,
        "expected_clause_ids": ["NIA-4.1-A"],
    }
    result = score(decision, case)
    assert result["amount_match"] is True
    assert result["citation_recall"] == 0.0
