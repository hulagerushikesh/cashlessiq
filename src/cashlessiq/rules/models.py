"""Typed, Snowflake-independent domain objects for deterministic decisions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Any


class Outcome(StrEnum):
    """Permitted recommendations; a machine-generated denial is impossible."""

    APPROVE = "APPROVE"
    APPROVE_WITH_DEDUCTIONS = "APPROVE_WITH_DEDUCTIONS"
    QUERY = "QUERY"
    REFER = "REFER"


class CitationType(StrEnum):
    """Evidence source types accepted by the decision contract."""

    CLAUSE = "clause"
    RECORD = "record"


class SlaState(StrEnum):
    """SLA traffic-light states."""

    GREEN = "GREEN"
    AMBER = "AMBER"
    RED = "RED"


@dataclass(frozen=True, slots=True)
class Policy:
    """Policy inputs needed by the pure rules core."""

    policy_id: str
    member_id: str
    product_id: str
    tpa_id: str
    sum_insured_inr: int
    inception_date: date
    continuous_cover_since: date
    cumulative_bonus_inr: int = 0
    status: str = "ACTIVE"


@dataclass(frozen=True, slots=True)
class Rule:
    """A data-driven policy rule linked to its source clause."""

    rule_id: str
    product_id: str
    rule_type: str
    params: dict[str, Any]
    clause_id: str


@dataclass(frozen=True, slots=True)
class CostItem:
    """One extracted cost component in integer rupees."""

    item: str
    claimed_inr: int


@dataclass(frozen=True, slots=True)
class PreAuthFacts:
    """Structured facts extracted from a synthetic pre-authorisation request."""

    request_id: str
    diagnosis: str | None
    icd10_code: str | None
    procedure: str | None
    is_emergency: bool | None
    admission_date: date | None
    planned_los_days: int | None
    room_category: str | None
    room_rent_per_day_inr: int | None
    icu_days: int | None
    cost_breakup: tuple[CostItem, ...]
    estimated_total_inr: int | None
    clinical_note: str | None
    missing_fields: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Citation:
    """A traceable policy clause or table record reference."""

    type: CitationType
    id: str


@dataclass(frozen=True, slots=True)
class DecisionLine:
    """One fully evidenced payable calculation line."""

    item: str
    claimed_inr: int
    payable_inr: int
    deduction_inr: int
    reason: str
    calc: str
    citations: tuple[Citation, ...]


@dataclass(frozen=True, slots=True)
class SlaStatus:
    """Deterministic status of the one-hour pre-authorisation clock."""

    elapsed_min: int
    state: SlaState
    received_at: datetime | None = None
    remaining_min: int | None = None


@dataclass(frozen=True, slots=True)
class Decision:
    """Validated recommendation returned to a human reviewer."""

    request_id: str
    outcome: Outcome
    total_claimed_inr: int
    total_payable_inr: int
    lines: tuple[DecisionLine, ...]
    queries: tuple[str, ...]
    refer_reasons: tuple[str, ...]
    summary: str
    sla: SlaStatus
    metadata: dict[str, Any] = field(default_factory=dict)

