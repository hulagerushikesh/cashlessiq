"""Strict JSON contract and semantic validation for agent decisions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from jsonschema import Draft202012Validator

OUTCOMES = ("APPROVE", "APPROVE_WITH_DEDUCTIONS", "QUERY", "REFER")

DECISION_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "CashlessIQ decision",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "request_id",
        "outcome",
        "total_claimed_inr",
        "total_payable_inr",
        "lines",
        "queries",
        "refer_reasons",
        "summary",
        "sla",
    ],
    "properties": {
        "request_id": {"type": "string", "pattern": "^[A-Z][A-Z0-9_-]{2,19}$"},
        "outcome": {"enum": list(OUTCOMES)},
        "total_claimed_inr": {"type": "integer", "minimum": 0},
        "total_payable_inr": {"type": "integer", "minimum": 0},
        "lines": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "item",
                    "claimed_inr",
                    "payable_inr",
                    "deduction_inr",
                    "reason",
                    "calc",
                    "citations",
                ],
                "properties": {
                    "item": {"type": "string", "minLength": 1},
                    "claimed_inr": {"type": "integer", "minimum": 0},
                    "payable_inr": {"type": "integer", "minimum": 0},
                    "deduction_inr": {"type": "integer", "minimum": 0},
                    "reason": {"type": "string", "minLength": 1},
                    "calc": {"type": "string", "minLength": 1},
                    "citations": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["type", "id"],
                            "properties": {
                                "type": {"enum": ["clause", "record"]},
                                "id": {"type": "string", "minLength": 1},
                            },
                        },
                    },
                },
            },
        },
        "queries": {"type": "array", "items": {"type": "string", "minLength": 1}},
        "refer_reasons": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
        },
        "summary": {"type": "string", "minLength": 1},
        "sla": {
            "type": "object",
            "additionalProperties": False,
            "required": ["elapsed_min", "state"],
            "properties": {
                "elapsed_min": {"type": "integer", "minimum": 0},
                "state": {"enum": ["GREEN", "AMBER", "RED"]},
            },
        },
    },
}


class DecisionValidationError(ValueError):
    """Raised when agent output violates the JSON or arithmetic contract."""


def validate_decision(decision: Mapping[str, Any]) -> None:
    """Validate structure, conditional fields, and deterministic totals.

    Raises:
        DecisionValidationError: with all discovered validation failures.
    """

    errors = [
        f"{'.'.join(str(part) for part in error.absolute_path) or '$'}: {error.message}"
        for error in sorted(
            Draft202012Validator(DECISION_SCHEMA).iter_errors(decision),
            key=lambda error: list(error.absolute_path),
        )
    ]
    if errors:
        raise DecisionValidationError("; ".join(errors))

    outcome = decision["outcome"]
    if outcome == "QUERY" and not decision["queries"]:
        errors.append("queries: QUERY requires at least one query")
    if outcome == "REFER" and not decision["refer_reasons"]:
        errors.append("refer_reasons: REFER requires at least one reason")

    lines = decision["lines"]
    claimed_total = sum(line["claimed_inr"] for line in lines)
    payable_total = sum(line["payable_inr"] for line in lines)
    if decision["total_claimed_inr"] != claimed_total:
        errors.append("total_claimed_inr must equal the sum of line claimed_inr")
    if decision["total_payable_inr"] != payable_total:
        errors.append("total_payable_inr must equal the sum of line payable_inr")

    for index, line in enumerate(lines):
        expected_deduction = line["claimed_inr"] - line["payable_inr"]
        if line["payable_inr"] > line["claimed_inr"]:
            errors.append(f"lines.{index}.payable_inr cannot exceed claimed_inr")
        if line["deduction_inr"] != expected_deduction:
            errors.append(
                f"lines.{index}.deduction_inr must equal claimed_inr minus payable_inr"
            )

    if errors:
        raise DecisionValidationError("; ".join(errors))
