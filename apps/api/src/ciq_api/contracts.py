"""Versioned API responses; generated browser types derive from these models."""

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthResponse(Contract):
    status: Literal["ok", "ready", "unavailable"]


class UserView(Contract):
    id: UUID
    display_name: str


class TenantView(Contract):
    id: UUID
    name: str


class MeResponse(Contract):
    schema_version: Literal[1] = 1
    user: UserView
    tenant: TenantView
    role: Literal[
        "processor",
        "medical_officer",
        "auditor",
        "policy_analyst",
        "policy_approver",
        "operations_lead",
        "tenant_admin",
    ]
    capabilities: list[str]
    identity_mode: Literal["local", "oidc"]


class LocalSessionRequest(Contract):
    profile: Literal[
        "processor",
        "medical_officer",
        "auditor",
        "policy_analyst",
        "policy_approver",
        "operations_lead",
        "tenant_admin",
    ]


class TokenResponse(Contract):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


Outcome = Literal["APPROVE", "APPROVE_WITH_DEDUCTIONS", "QUERY", "REFER"]


class CaseSummary(Contract):
    request_id: str
    member_reference: str
    outcome: Outcome
    workflow_state: Literal["DRAFT_READY"] = "DRAFT_READY"
    admission_date: date
    claimed_inr: int
    payable_inr: int | None


class CaseQueue(Contract):
    schema_version: Literal[1] = 1
    data_mode: Literal["synthetic_snapshot"] = "synthetic_snapshot"
    items: list[CaseSummary]
    total: int
    page: int
    page_size: int


class Citation(Contract):
    type: Literal["clause", "record"]
    id: str


class CalculationLine(Contract):
    item: str
    claimed_inr: int
    payable_inr: int
    deduction_inr: int
    reason: str
    calc: str
    citations: list[Citation]


class PolicyCheck(Contract):
    rule_id: str
    clause_id: str
    rule_type: str
    applies: bool
    months_elapsed: int | None
    months_required: int | None
    reason: str


class PolicyEvidence(Contract):
    clause_id: str
    title: str
    page: int
    source_url: str


class CaseDetail(CaseSummary):
    schema_version: Literal[1] = 1
    data_mode: Literal["synthetic_snapshot"] = "synthetic_snapshot"
    baseline_commit: str
    policy_id: str
    product_name: str
    policy_version: str
    continuous_cover_since: date
    diagnosis: str | None = None
    procedure: str | None = None
    clinical_note: str | None = None
    clinical_visible: bool = False
    lines: list[CalculationLine]
    checks: list[PolicyCheck]
    queries: list[str]
    refer_reasons: list[str]
    evidence: list[PolicyEvidence]
