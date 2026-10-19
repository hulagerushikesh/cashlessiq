"""V2 synthetic source reads; distinct from v1 frozen demonstration snapshots."""

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, HttpUrl, model_validator

from ciq_api.contracts import Contract, Outcome

INR = Annotated[int, Field(strict=True, ge=0)]


class MissingSourceRecommendation(Contract):
    state: Literal["MISSING"] = "MISSING"


class SavedSourceRecommendation(Contract):
    state: Literal["SAVED"] = "SAVED"
    outcome: Outcome
    claimed_inr: INR
    payable_inr: INR | None
    amount_basis: Literal["saved_calculation", "supplied_estimate"]

    @model_validator(mode="after")
    def consistent_availability(self):
        uncomputed = self.outcome in {"QUERY", "REFER"}
        if uncomputed != (self.payable_inr is None):
            raise ValueError("Inconsistent saved recommendation")
        if self.amount_basis != ("supplied_estimate" if uncomputed else "saved_calculation"):
            raise ValueError("Inconsistent amount provenance")
        return self


SourceRecommendation = Annotated[
    MissingSourceRecommendation | SavedSourceRecommendation, Field(discriminator="state")
]


class SourceCaseSummary(Contract):
    request_id: str
    policy_id: str
    product_id: str
    product_name: str
    policy_version: str
    continuous_cover_since: date
    admission_date: date
    estimated_total_inr: INR


class SourceCaseQueue(Contract):
    schema_version: Literal[2] = 2
    data_mode: Literal["synthetic_source"] = "synthetic_source"
    tenant_id: UUID
    # Metadata-only queue: absence is not inferred without a decision read.
    recommendations_loaded: Literal[False] = False
    items: list[SourceCaseSummary]
    total: int
    page: int
    page_size: int


class SourceCondition(Contract):
    icd10_code: str
    condition_name: str
    first_diagnosed_on: date
    declared_at_proposal: bool


class SourceMemberHistory(Contract):
    member_id: str
    sum_insured_inr: INR
    cumulative_bonus_inr: INR
    status: str
    claim_count: INR
    total_paid_inr: INR
    last_admission_date: date | None
    conditions_visible: bool
    conditions: list[SourceCondition] | None


class SourceClauseReference(Contract):
    clause_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    page: int = Field(strict=True, ge=1)
    source_url: HttpUrl


class SourceCaseDetail(Contract):
    schema_version: Literal[2] = 2
    data_mode: Literal["synthetic_source"] = "synthetic_source"
    tenant_id: UUID
    case: SourceCaseSummary
    member_history: SourceMemberHistory
    recommendation: SourceRecommendation
    evidence_kind: Literal["product_clause_register"] = "product_clause_register"
    evidence: list[SourceClauseReference]
