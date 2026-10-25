"""Synthetic reviewer workflow persistence; immutable audit, transactional outbox."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ciq_api.models import Base


class ReviewCase(Base):
    __tablename__ = "review_case"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "assignee_id"],
            ["tenant_membership.tenant_id", "tenant_membership.user_id"],
        ),
        CheckConstraint("version >= 0", name="ck_review_version"),
        CheckConstraint(
            "state IN ('DRAFT_READY','IN_REVIEW','NEEDS_INFORMATION','REFERRED',"
            "'APPROVED','APPROVED_WITH_DEDUCTIONS')",
            name="ck_review_state",
        ),
    )
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenant.id"), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, default=0)
    state: Mapped[str] = mapped_column(String(40), default="DRAFT_READY")
    assignee_id: Mapped[UUID | None] = mapped_column(nullable=True)
    final_payable_inr: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReviewComment(Base):
    __tablename__ = "review_comment"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "request_id"], ["review_case.tenant_id", "review_case.request_id"]
        ),
        CheckConstraint("visibility IN ('team','clinical')", name="ck_review_comment_visibility"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(index=True)
    request_id: Mapped[str] = mapped_column(String(120))
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("app_user.id"))
    visibility: Mapped[str] = mapped_column(String(20))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReviewAudit(Base):
    __tablename__ = "review_audit"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "request_id", "aggregate_version", name="uq_review_audit_version"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "request_id"], ["review_case.tenant_id", "review_case.request_id"]
        ),
    )
    event_id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(index=True)
    request_id: Mapped[str] = mapped_column(String(120))
    aggregate_version: Mapped[int] = mapped_column(Integer)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("app_user.id"))
    actor_role: Mapped[str] = mapped_column(String(40))
    action: Mapped[str] = mapped_column(String(40))
    command_id: Mapped[UUID] = mapped_column()
    payload: Mapped[dict] = mapped_column(JSONB)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ReviewCommandReceipt(Base):
    __tablename__ = "review_command_receipt"
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenant.id"), primary_key=True)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("app_user.id"), primary_key=True)
    command_id: Mapped[UUID] = mapped_column(primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class ReviewOutbox(Base):
    __tablename__ = "review_outbox"
    event_id: Mapped[UUID] = mapped_column(ForeignKey("review_audit.event_id"), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenant.id"), index=True)
    event: Mapped[dict] = mapped_column(JSONB)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
