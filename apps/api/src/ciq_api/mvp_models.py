"""Durable local MVP data. All reads and mutations bind the authenticated tenant."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ciq_api.models import Base


class SubmittedCase(Base):
    __tablename__ = "submitted_case"
    __table_args__ = (
        UniqueConstraint("tenant_id", "actor_id", "command_id", name="uq_submission_command"),
    )
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenant.id"), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("app_user.id"))
    command_id: Mapped[UUID] = mapped_column()
    fingerprint: Mapped[str] = mapped_column(String(64))
    policy_id: Mapped[UUID] = mapped_column(ForeignKey("policy_version.id"))
    inputs: Mapped[dict] = mapped_column(JSONB)
    record: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    priority: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WorkJob(Base):
    __tablename__ = "work_job"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenant.id"), index=True)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("app_user.id"))
    kind: Mapped[str] = mapped_column(String(30))
    subject_id: Mapped[str] = mapped_column(String(120))
    payload: Mapped[dict] = mapped_column(JSONB)
    state: Mapped[str] = mapped_column(String(20), default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    lease_id: Mapped[UUID | None] = mapped_column(nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(40), nullable=True)


class DocumentUpload(Base):
    __tablename__ = "document_upload"
    __table_args__ = (
        UniqueConstraint("tenant_id", "actor_id", "command_id", name="uq_upload_command"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenant.id"), index=True)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("app_user.id"))
    command_id: Mapped[UUID] = mapped_column()
    request_id: Mapped[str] = mapped_column(String(120))
    digest: Mapped[str] = mapped_column(String(64))
    content: Mapped[bytes] = mapped_column(LargeBinary)
    state: Mapped[str] = mapped_column(String(30), default="quarantined")
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PolicyVersion(Base):
    __tablename__ = "policy_version"
    __table_args__ = (
        UniqueConstraint("tenant_id", "product_id", "version", name="uq_policy_version"),
        UniqueConstraint("tenant_id", "author_id", "command_id", name="uq_policy_command"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenant.id"), index=True)
    product_id: Mapped[str] = mapped_column(String(80))
    version: Mapped[str] = mapped_column(String(80))
    author_id: Mapped[UUID] = mapped_column(ForeignKey("app_user.id"))
    command_id: Mapped[UUID] = mapped_column()
    fingerprint: Mapped[str] = mapped_column(String(64))
    proposal: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PolicyActive(Base):
    __tablename__ = "policy_active"
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenant.id"), primary_key=True)
    product_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    version_id: Mapped[UUID] = mapped_column(ForeignKey("policy_version.id"))
    event_id: Mapped[UUID] = mapped_column(ForeignKey("mvp_event.id"))


class MvpEvent(Base):
    __tablename__ = "mvp_event"
    __table_args__ = (
        UniqueConstraint("tenant_id", "actor_id", "command_id", name="uq_mvp_event_command"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenant.id"), index=True)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("app_user.id"))
    actor_role: Mapped[str] = mapped_column(String(40))
    command_id: Mapped[UUID] = mapped_column()
    action: Mapped[str] = mapped_column(String(40))
    subject_id: Mapped[str] = mapped_column(String(120))
    fingerprint: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSONB)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AnalyticsEvent(Base):
    __tablename__ = "analytics_event"
    event_id: Mapped[UUID] = mapped_column(ForeignKey("review_audit.event_id"), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenant.id"), index=True)
    event: Mapped[dict] = mapped_column(JSONB)


class CaseInputRevision(Base):
    __tablename__ = "case_input_revision"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "request_id"], ["submitted_case.tenant_id", "submitted_case.request_id"]
        ),
    )
    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    request_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("app_user.id"))
    inputs: Mapped[dict] = mapped_column(JSONB)
    digest: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
