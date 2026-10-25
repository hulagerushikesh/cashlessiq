"""Bounded synthetic ingestion and data-driven policy contracts."""

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import Field, StrictBool, StrictInt, model_validator

from ciq_api.contracts import Contract

Money = StrictInt


class CostInput(Contract):
    item: str = Field(min_length=1, max_length=120)
    claimed_inr: Money = Field(ge=0, le=100_000_000)


class ConditionInput(Contract):
    icd10_code: str = Field(max_length=30)
    condition_name: str = Field(max_length=120)
    first_diagnosed_on: date
    declared_at_proposal: StrictBool


class AssessmentInput(Contract):
    member_reference: str = Field(min_length=1, max_length=80, pattern=r"^SYN-[A-Za-z0-9-]+$")
    sum_insured_inr: Money = Field(ge=1, le=100_000_000)
    si_remaining_inr: Money = Field(ge=0, le=100_000_000)
    inception_date: date
    continuous_cover_since: date
    diagnosis: str | None = Field(default=None, max_length=500)
    icd10_code: str | None = Field(default=None, max_length=30)
    procedure: str | None = Field(default=None, max_length=500)
    is_emergency: StrictBool | None = None
    admission_date: date | None = None
    planned_los_days: StrictInt | None = Field(default=None, ge=1, le=365)
    room_category: str | None = Field(default=None, max_length=80)
    room_rent_per_day_inr: Money | None = Field(default=None, ge=0, le=100_000_000)
    icu_days: StrictInt | None = Field(default=0, ge=0, le=365)
    cost_breakup: list[CostInput] = Field(default_factory=list, max_length=50)
    estimated_total_inr: Money | None = Field(default=None, ge=0, le=100_000_000)
    clinical_note: str | None = Field(default=None, max_length=2000)
    declared_conditions: list[ConditionInput] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def coherent(self):
        if self.si_remaining_inr > self.sum_insured_inr:
            raise ValueError("Remaining cover exceeds sum insured")
        if (
            self.admission_date
            and max(self.inception_date, self.continuous_cover_since) > self.admission_date
        ):
            raise ValueError("Cover cannot start after admission")
        if self.cost_breakup and self.estimated_total_inr != sum(
            c.claimed_inr for c in self.cost_breakup
        ):
            raise ValueError("Cost lines must equal the estimated total")
        if self.cost_breakup and self.planned_los_days is None:
            raise ValueError("Length of stay is required for a calculation")
        if self.planned_los_days and self.icu_days and self.icu_days > self.planned_los_days:
            raise ValueError("ICU days exceed planned stay")
        return self


class RequestSubmission(Contract):
    command_id: UUID
    product_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    synthetic_data: Literal[True]
    priority: Literal["normal", "urgent"] = "normal"
    facts: AssessmentInput


class RuleInput(Contract):
    rule_id: str = Field(min_length=1, max_length=80)
    rule_type: Literal[
        "ROOM_RENT_CAP",
        "ICU_CAP",
        "PROPORTIONATE_DEDUCTION",
        "PROCEDURE_SUBLIMIT",
        "WAITING_PED",
        "WAITING_SPECIFIC",
        "WAITING_INITIAL",
        "EXCLUSION",
        "COPAY",
    ]
    clause_id: str = Field(min_length=1, max_length=80)
    params: dict

    @model_validator(mode="after")
    def supported_parameters(self):
        layouts = {
            "ROOM_RENT_CAP": {"pct_of_si": "pct", "max_inr_per_day": "money"},
            "ICU_CAP": {"pct_of_si": "pct", "max_inr_per_day": "money"},
            "PROPORTIONATE_DEDUCTION": {"applies_to": "list", "exempt_items": "list"},
            "PROCEDURE_SUBLIMIT": {
                "procedure": "text",
                "pct_of_si": "pct",
                "max_inr": "money",
                "basis": "basis",
            },
            "WAITING_PED": {"months": "duration"},
            "WAITING_SPECIFIC": {
                "months": "duration",
                "conditions": "list",
                "accident_exempt": "bool",
            },
            "WAITING_INITIAL": {"days": "duration", "accident_exempt": "bool"},
            "EXCLUSION": {"condition": "text"},
            "COPAY": {"pct": "pct"},
        }
        layout = layouts[self.rule_type]
        if set(self.params) != set(layout):
            raise ValueError("Unsupported or missing rule parameters")
        for key, kind in layout.items():
            value = self.params[key]
            if kind in {"pct", "money", "duration"}:
                maximum = {"pct": 100, "money": 100_000_000, "duration": 3650}[kind]
                valid = type(value) is int and 0 <= value <= maximum
            elif kind == "bool":
                valid = type(value) is bool
            elif kind == "list":
                valid = (
                    isinstance(value, list)
                    and 0 < len(value) <= 30
                    and all(type(v) is str and 0 < len(v) <= 120 for v in value)
                )
            elif kind == "basis":
                valid = value == "per_eye_per_policy_year"
            else:
                valid = type(value) is str and 0 < len(value) <= 120
            if not valid:
                raise ValueError("Rule parameter type or bound is unsupported")
        return self


class ClauseInput(Contract):
    clause_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=10000)
    page: StrictInt = Field(ge=1, le=2000)


class RegressionExample(Contract):
    name: str = Field(min_length=1, max_length=80)
    facts: AssessmentInput
    expected_outcome: Literal["APPROVE", "APPROVE_WITH_DEDUCTIONS", "QUERY", "REFER"]
    expected_payable_inr: Money | None = Field(default=None, ge=0, le=100_000_000)


class PolicyProposal(Contract):
    command_id: UUID
    product_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    version: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    effective_from: date
    effective_to: date | None = None
    reason: str = Field(min_length=1, max_length=2000)
    wording_document_id: UUID | None = None
    clauses: list[ClauseInput] = Field(min_length=1, max_length=40)
    rules: list[RuleInput] = Field(min_length=1, max_length=30)
    examples: list[RegressionExample] = Field(min_length=3, max_length=50)

    @model_validator(mode="after")
    def complete(self):
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("Invalid effective dates")
        clauses = {c.clause_id for c in self.clauses}
        if len(clauses) != len(self.clauses) or any(r.clause_id not in clauses for r in self.rules):
            raise ValueError("Every rule needs one unique versioned clause")
        if len({r.rule_id for r in self.rules}) != len(self.rules):
            raise ValueError("Duplicate rule IDs")
        # The core selects a single payable rule of each type. Reject ambiguous
        # configurations instead of silently choosing the first.
        singleton = [r.rule_type for r in self.rules if r.rule_type != "WAITING_SPECIFIC"]
        if len(set(singleton)) != len(singleton):
            raise ValueError("Duplicate singleton rule type")
        if not {"QUERY", "REFER"}.issubset(e.expected_outcome for e in self.examples) or not any(
            e.expected_outcome.startswith("APPROVE") for e in self.examples
        ):
            raise ValueError("Regression needs query, referral and calculated examples")
        return self


class PolicyAction(Contract):
    command_id: UUID
    expected_activation: UUID | None = None
    reason: str = Field(min_length=1, max_length=2000)
    action: Literal["approve", "reject", "activate"]


class RetryCommand(Contract):
    command_id: UUID
    reason: str = Field(min_length=1, max_length=2000)


class Amendment(RetryCommand):
    expected_version: StrictInt = Field(ge=0, le=2**31 - 1)
    facts: AssessmentInput


class MembershipCommand(RetryCommand):
    expected_role: Literal[
        "processor",
        "medical_officer",
        "auditor",
        "policy_analyst",
        "policy_approver",
        "operations_lead",
        "tenant_admin",
    ]
    role: Literal[
        "processor",
        "medical_officer",
        "auditor",
        "policy_analyst",
        "policy_approver",
        "operations_lead",
        "tenant_admin",
    ]
    expected_active: StrictBool
    active: StrictBool
