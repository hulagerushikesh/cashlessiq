"""Inactive fake-only agent ledger. Clinical data; no route or worker registers it."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ciq_api.models import Base


class AgentAdmissionEpoch(Base):
    """No default row: a restored database alone cannot enable fake transport."""

    __tablename__ = "agent_admission_epoch"
    __table_args__ = (
        CheckConstraint("id = 1 AND mode = 'fake-only'", name="ck_agent_epoch_fake_only"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mode: Mapped[str] = mapped_column(String(20))
    database_id: Mapped[UUID] = mapped_column()
    epoch_id: Mapped[UUID] = mapped_column()


class AgentExecutionGrant(Base):
    __tablename__ = "agent_execution_grant"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        CheckConstraint("mode = 'fake-only'", name="ck_agent_grant_fake_only"),
        CheckConstraint("ends_at > starts_at", name="ck_agent_grant_window"),
        CheckConstraint(
            "case_limit BETWEEN 1 AND 30 AND concurrency_limit BETWEEN 1 AND case_limit "
            "AND units_per_attempt BETWEEN 1 AND 1000000 "
            "AND unit_limit BETWEEN units_per_attempt AND 30000000",
            name="ck_agent_grant_limits",
        ),
        CheckConstraint(
            "admitted BETWEEN 0 AND case_limit AND in_flight BETWEEN 0 AND admitted "
            "AND reserved_units >= 0 AND consumed_units >= 0 AND uncertain_units >= 0 "
            "AND reserved_units + consumed_units + uncertain_units <= unit_limit",
            name="ck_agent_grant_accounting",
        ),
    )
    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    id: Mapped[UUID] = mapped_column(primary_key=True)
    mode: Mapped[str] = mapped_column(String(20))
    approval_ref: Mapped[str] = mapped_column(String(120))
    operation_keys: Mapped[list] = mapped_column(JSONB)
    config_digest: Mapped[str] = mapped_column(String(64))
    source_digest: Mapped[str] = mapped_column(String(64))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    case_limit: Mapped[int] = mapped_column(Integer)
    concurrency_limit: Mapped[int] = mapped_column(Integer)
    units_per_attempt: Mapped[int] = mapped_column(Integer)
    unit_limit: Mapped[int] = mapped_column(Integer)
    admitted: Mapped[int] = mapped_column(Integer, default=0)
    in_flight: Mapped[int] = mapped_column(Integer, default=0)
    reserved_units: Mapped[int] = mapped_column(Integer, default=0)
    consumed_units: Mapped[int] = mapped_column(Integer, default=0)
    uncertain_units: Mapped[int] = mapped_column(Integer, default=0)


class AgentOperation(Base):
    __tablename__ = "agent_operation"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "request_id"],
            ["submitted_case.tenant_id", "submitted_case.request_id"],
        ),
        ForeignKeyConstraint(
            ["tenant_id", "actor_id"],
            ["tenant_membership.tenant_id", "tenant_membership.user_id"],
        ),
        ForeignKeyConstraint(
            ["tenant_id", "grant_id"],
            ["agent_execution_grant.tenant_id", "agent_execution_grant.id"],
        ),
        UniqueConstraint("tenant_id", "operation_key", name="uq_agent_operation_key"),
        CheckConstraint(
            "state IN ('reserved','submitting','unknown','rejected',"
            "'published','superseded','expired')",
            name="ck_agent_operation_state",
        ),
        CheckConstraint("version >= 0", name="ck_agent_operation_version"),
        CheckConstraint(
            "deadline > created_at AND deadline <= created_at + interval '120 seconds'",
            name="ck_agent_operation_deadline",
        ),
        CheckConstraint(
            "(fence_id IS NULL) = (lease_until IS NULL) AND "
            "(lease_until IS NULL OR lease_until <= deadline)",
            name="ck_agent_operation_lease",
        ),
    )
    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    id: Mapped[UUID] = mapped_column(primary_key=True)
    request_id: Mapped[str] = mapped_column(String(120))
    actor_id: Mapped[UUID] = mapped_column()
    grant_id: Mapped[UUID] = mapped_column()
    operation_key: Mapped[str] = mapped_column(String(64))
    config_digest: Mapped[str] = mapped_column(String(64))
    source_digest: Mapped[str] = mapped_column(String(64))
    snapshot: Mapped[dict] = mapped_column(JSONB)
    state: Mapped[str] = mapped_column(String(20))
    version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fence_id: Mapped[UUID | None] = mapped_column(nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentAttempt(Base):
    """Immutable submission checkpoint; absence of a result does not mean no cost."""

    __tablename__ = "agent_attempt"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "operation_id"], ["agent_operation.tenant_id", "agent_operation.id"]
        ),
        UniqueConstraint("tenant_id", "operation_id", name="uq_agent_single_attempt"),
        UniqueConstraint("submission_id", name="uq_agent_submission_id"),
        UniqueConstraint("tenant_id", "operation_id", "id", name="uq_agent_attempt_owner"),
        CheckConstraint("attempt_number = 1", name="ck_agent_one_attempt"),
    )
    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    id: Mapped[UUID] = mapped_column(primary_key=True)
    operation_id: Mapped[UUID] = mapped_column()
    attempt_number: Mapped[int] = mapped_column(Integer)
    submission_id: Mapped[UUID] = mapped_column()
    fence_id: Mapped[UUID] = mapped_column()
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AgentComparison(Base):
    """Private validated comparison, never a reviewer decision or general audit body."""

    __tablename__ = "agent_comparison"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "operation_id"], ["agent_operation.tenant_id", "agent_operation.id"]
        ),
        ForeignKeyConstraint(
            ["tenant_id", "operation_id", "attempt_id"],
            ["agent_attempt.tenant_id", "agent_attempt.operation_id", "agent_attempt.id"],
        ),
    )
    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    operation_id: Mapped[UUID] = mapped_column(primary_key=True)
    attempt_id: Mapped[UUID] = mapped_column()
    candidate: Mapped[dict] = mapped_column(JSONB)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
