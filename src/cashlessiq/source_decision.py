"""Offline validation of saved source decisions, not an HTTP or Snowflake adapter.

Reuse the canonical decision validator without importing the API or Snowflake.
Citation registries must come from independently verified request/product reads;
passing an arbitrary allowlist is not proof of database ownership or parity.
"""

import json
from collections.abc import Mapping, Sequence, Set
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from cashlessiq.decision_schema import validate_decision


class SourceDecisionError(ValueError):
    """Saved decision is missing, inconsistent or outside verified source context."""


@dataclass(frozen=True)
class DecisionObservation:
    """Comparison-only amounts; not a complete product case or parity verdict."""

    request_id: str
    outcome: str
    claimed_inr: int
    payable_inr: int | None
    amount_basis: str


def observe_saved_decision(
    row: Mapping[str, Any],
    *,
    request_id: str,
    tpa_id: str,
    product_id: str,
    estimated_total_inr: int,
    evidence: Sequence[Mapping[str, Any]],
    verified_record_ids: Set[str],
) -> DecisionObservation:
    """Validate one saved row and project amounts without calculating money.

    An uncomputed QUERY/REFER must have no financial lines and zero stored
    totals. Its claimed amount is the separately supplied estimate, and payable
    becomes None. Ambiguous partial calculations fail closed rather than being
    hidden. Stored SCHEMA_VALID is deliberately ignored. No raw clinical JSON
    or validation errors are included in the public exception message.
    """
    try:
        if type(estimated_total_inr) is not int or estimated_total_inr < 0:
            raise ValueError("Invalid supplied estimate")
        if row["request_id"] != request_id or row["tpa_id"] != tpa_id:
            raise ValueError("Source scope mismatch")
        decision = row["decision_json"]
        if isinstance(decision, str):
            decision = json.loads(decision, object_pairs_hook=_unique_keys)
        if not isinstance(decision, Mapping):
            raise ValueError("Missing decision object")
        validate_decision(decision)
        amounts = [decision["total_claimed_inr"], decision["total_payable_inr"]]
        for line in decision["lines"]:
            amounts.extend(line[field] for field in ("claimed_inr", "payable_inr", "deduction_inr"))
        if any(type(amount) is not int for amount in amounts):
            raise ValueError("Decision amounts must be integer rupees")
        if decision["request_id"] != request_id or row["outcome"] != decision["outcome"]:
            raise ValueError("Stored decision mismatch")
        # Snowflake NUMBER may be Decimal, but booleans/floats/strings are not money.
        stored_payable = row["payable_inr"]
        if type(stored_payable) not in (int, Decimal):
            raise ValueError("Invalid stored payable")
        if stored_payable != decision["total_payable_inr"]:
            raise ValueError("Stored payable mismatch")

        clauses = set()
        for reference in evidence:
            if (
                reference["request_id"] != request_id
                or reference["tpa_id"] != tpa_id
                or reference["product_id"] != product_id
                or not isinstance(reference["clause_id"], str)
                or not reference["clause_id"].strip()
                or reference["clause_id"] in clauses
            ):
                raise ValueError("Invalid evidence scope")
            clauses.add(reference["clause_id"])
        if not clauses:
            raise ValueError("Missing evidence coverage")
        for line in decision["lines"]:
            for citation in line["citations"]:
                registry = clauses if citation["type"] == "clause" else verified_record_ids
                if citation["id"] not in registry:
                    raise ValueError("Unresolved citation")

        uncomputed = decision["outcome"] in {"QUERY", "REFER"}
        if uncomputed:
            if decision["lines"] or decision["total_claimed_inr"] or stored_payable:
                raise ValueError("Ambiguous uncomputed decision")
        elif not decision["lines"]:
            raise ValueError("Approval without calculation")
        return DecisionObservation(
            request_id=request_id,
            outcome=decision["outcome"],
            claimed_inr=estimated_total_inr if uncomputed else decision["total_claimed_inr"],
            payable_inr=None if uncomputed else decision["total_payable_inr"],
            amount_basis="supplied_estimate" if uncomputed else "saved_calculation",
        )
    except Exception as exc:
        raise SourceDecisionError("Saved source decision unavailable or invalid") from exc


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result
