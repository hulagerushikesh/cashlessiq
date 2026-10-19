"""Offline, scoped member-history observations; no policy eligibility calculation."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any


class SourceHistoryError(ValueError):
    """History is missing, malformed or outside the verified source context."""


@dataclass(frozen=True)
class ConditionObservation:
    icd10_code: str
    condition_name: str
    first_diagnosed_on: date
    declared_at_proposal: bool


@dataclass(frozen=True)
class MemberHistoryObservation:
    request_id: str
    tpa_id: str
    policy_id: str
    member_id: str
    sum_insured_inr: int
    cumulative_bonus_inr: int
    status: str
    claim_count: int
    total_paid_inr: int
    last_admission_date: date | None
    conditions: tuple[ConditionObservation, ...]


def observe_member_history(
    member: Mapping[str, Any],
    conditions: Sequence[Mapping[str, Any]],
    *,
    request_id: str,
    tpa_id: str,
    policy_id: str,
    member_id: str,
) -> MemberHistoryObservation:
    """Copy validated source facts without deriving remaining cover or PED status.

    Expected identifiers must be independently verified, not taken from the row
    being checked. These restricted observations must not be logged or exposed
    through HTTP without a separate role-based disclosure policy.
    """
    try:
        expected = {
            "request_id": request_id,
            "tpa_id": tpa_id,
            "policy_id": policy_id,
            "member_id": member_id,
        }
        if any(_text(value) != member[key] for key, value in expected.items()):
            raise ValueError("History scope mismatch")
        count = _integer(member["claim_count"])
        paid = _integer(member["total_paid_inr"])
        last = member["last_admission_date"]
        last = None if last is None else _date(last)
        if (count == 0 and (paid != 0 or last is not None)) or (count > 0 and last is None):
            raise ValueError("Inconsistent aggregate")
        if len(conditions) > 20:
            raise ValueError("History bound exceeded")
        observations = []
        seen = set()
        for row in conditions:
            if row["request_id"] != request_id or row["tpa_id"] != tpa_id:
                raise ValueError("Condition scope mismatch")
            code = _text(row["icd10_code"])
            if code in seen or type(row["declared_at_proposal"]) is not bool:
                raise ValueError("Duplicate or malformed condition")
            seen.add(code)
            observations.append(
                ConditionObservation(
                    code,
                    _text(row["condition_name"]),
                    _date(row["first_diagnosed_on"]),
                    row["declared_at_proposal"],
                )
            )
        return MemberHistoryObservation(
            request_id,
            tpa_id,
            policy_id,
            member_id,
            _integer(member["sum_insured_inr"]),
            _integer(member["cumulative_bonus_inr"]),
            _text(member["status"]),
            count,
            paid,
            last,
            tuple(sorted(observations, key=lambda item: item.icd10_code)),
        )
    except Exception as exc:
        raise SourceHistoryError("Source member history unavailable or invalid") from exc


def _integer(value: Any) -> int:
    if type(value) not in (int, Decimal):
        raise ValueError("Expected integer source number")
    if isinstance(value, Decimal) and (not value.is_finite() or value != value.to_integral_value()):
        raise ValueError("Expected finite integer")
    if value < 0:
        raise ValueError("Negative source number")
    return int(value)


def _text(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Expected nonempty string")
    return value


def _date(value: Any) -> date:
    if type(value) is date:
        return value
    if isinstance(value, str) and len(value) == 10:
        return date.fromisoformat(value)
    raise ValueError("Expected date, not timestamp")
