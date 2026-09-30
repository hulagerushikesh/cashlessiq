"""Contract tests for Cortex Agent decision output."""

from copy import deepcopy

import pytest

from cashlessiq.decision_schema import DecisionValidationError, validate_decision


@pytest.fixture
def valid_decision() -> dict:
    """Return a schema-valid, arithmetically consistent example."""

    return {
        "request_id": "PAR-0007",
        "outcome": "APPROVE_WITH_DEDUCTIONS",
        "total_claimed_inr": 32_000,
        "total_payable_inr": 20_000,
        "lines": [
            {
                "item": "Room rent (4 days)",
                "claimed_inr": 32_000,
                "payable_inr": 20_000,
                "deduction_inr": 12_000,
                "reason": "Room rent exceeds the policy cap.",
                "calc": "5000 x 4 = 20000",
                "citations": [
                    {"type": "clause", "id": "ASP-RGI-V1-4.1"},
                    {"type": "record", "id": "CORE.POLICY:POL-000123"},
                ],
            }
        ],
        "queries": [],
        "refer_reasons": [],
        "summary": "The request is payable with a room-rent deduction.",
        "sla": {"elapsed_min": 12, "state": "GREEN"},
    }


def test_valid_example(valid_decision: dict) -> None:
    validate_decision(valid_decision)


def test_generated_request_id_is_valid(valid_decision: dict) -> None:
    valid_decision["request_id"] = "GOL001"
    validate_decision(valid_decision)


def test_missing_citation_is_rejected(valid_decision: dict) -> None:
    invalid = deepcopy(valid_decision)
    invalid["lines"][0]["citations"] = []
    with pytest.raises(DecisionValidationError, match="citations"):
        validate_decision(invalid)


def test_bad_total_is_rejected(valid_decision: dict) -> None:
    invalid = deepcopy(valid_decision)
    invalid["total_payable_inr"] = 19_999
    with pytest.raises(DecisionValidationError, match="total_payable_inr"):
        validate_decision(invalid)


def test_query_requires_queries(valid_decision: dict) -> None:
    invalid = deepcopy(valid_decision)
    invalid["outcome"] = "QUERY"
    with pytest.raises(DecisionValidationError, match="QUERY requires"):
        validate_decision(invalid)


def test_refer_requires_reasons(valid_decision: dict) -> None:
    invalid = deepcopy(valid_decision)
    invalid["outcome"] = "REFER"
    with pytest.raises(DecisionValidationError, match="REFER requires"):
        validate_decision(invalid)


def test_deny_is_rejected(valid_decision: dict) -> None:
    invalid = deepcopy(valid_decision)
    invalid["outcome"] = "DENY"
    with pytest.raises(DecisionValidationError, match="outcome"):
        validate_decision(invalid)
