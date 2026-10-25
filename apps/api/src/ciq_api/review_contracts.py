"""Version-three operational workflow, separate from frozen v1/v2 recommendations."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, StrictInt

from ciq_api.contracts import Contract, UserView

ReviewState = Literal[
    "DRAFT_READY",
    "IN_REVIEW",
    "NEEDS_INFORMATION",
    "REFERRED",
    "APPROVED",
    "APPROVED_WITH_DEDUCTIONS",
]
ReviewAction = Literal[
    "assign", "comment", "query", "refer", "approve", "approve_with_deductions", "reopen", "resume"
]


class ReviewCommand(Contract):
    command_id: UUID
    expected_version: StrictInt = Field(ge=0, le=2**31 - 1)
    action: ReviewAction
    assignee_id: UUID | None = None
    note: str = Field(default="", max_length=2000)
    visibility: Literal["team", "clinical"] = "team"
    payable_inr: StrictInt | None = Field(default=None, ge=0, le=2**53 - 1)


class ReviewCommentView(Contract):
    id: UUID
    actor: UserView
    visibility: Literal["team", "clinical"]
    body: str
    created_at: datetime


class ReviewAuditView(Contract):
    event_id: UUID
    aggregate_version: int
    actor: UserView
    actor_role: str
    action: ReviewAction | Literal["amend"]
    occurred_at: datetime
    payload: dict


class ReviewView(Contract):
    schema_version: Literal[3] = 3
    data_mode: Literal["synthetic_workflow"] = "synthetic_workflow"
    request_id: str
    version: int
    state: ReviewState
    assignee: UserView | None
    final_payable_inr: int | None
    comments: list[ReviewCommentView]
    clinical_notes_restricted: bool
    audit: list[ReviewAuditView]
    history_page: int = 1
    history_page_size: int = 50
    audit_total: int = 0
    comments_total: int = 0


class ReviewPeople(Contract):
    items: list[UserView]


class ReviewReceipt(Contract):
    schema_version: Literal[3] = 3
    request_id: str
    version: int
    state: ReviewState
    event_id: UUID
