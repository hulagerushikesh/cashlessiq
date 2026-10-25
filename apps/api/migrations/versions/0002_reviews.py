"""Transactional synthetic reviewer state, receipts, audit and outbox.

Revision ID: 0002_reviews. Roll back by disabling the feature, preserving history.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_reviews"
down_revision = "0001_identity"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "review_case",
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenant.id"), primary_key=True),
        sa.Column("request_id", sa.String(120), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(40), nullable=False),
        sa.Column("assignee_id", sa.Uuid()),
        sa.Column("final_payable_inr", sa.BigInteger()),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "assignee_id"],
            ["tenant_membership.tenant_id", "tenant_membership.user_id"],
        ),
        sa.CheckConstraint("version >= 0", name="ck_review_version"),
        sa.CheckConstraint(
            "state IN ('DRAFT_READY','IN_REVIEW','NEEDS_INFORMATION','REFERRED',"
            "'APPROVED','APPROVED_WITH_DEDUCTIONS')",
            name="ck_review_state",
        ),
    )
    op.create_table(
        "review_comment",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.String(120), nullable=False),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("visibility", sa.String(20), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "request_id"], ["review_case.tenant_id", "review_case.request_id"]
        ),
        sa.CheckConstraint(
            "visibility IN ('team','clinical')", name="ck_review_comment_visibility"
        ),
    )
    op.create_index("ix_review_comment_tenant_id", "review_comment", ["tenant_id"])
    op.create_table(
        "review_audit",
        sa.Column("event_id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.String(120), nullable=False),
        sa.Column("aggregate_version", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("actor_role", sa.String(40), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("command_id", sa.Uuid(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "request_id"], ["review_case.tenant_id", "review_case.request_id"]
        ),
        sa.UniqueConstraint(
            "tenant_id", "request_id", "aggregate_version", name="uq_review_audit_version"
        ),
    )
    op.create_index("ix_review_audit_tenant_id", "review_audit", ["tenant_id"])
    op.create_table(
        "review_command_receipt",
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenant.id"), primary_key=True),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("app_user.id"), primary_key=True),
        sa.Column("command_id", sa.Uuid(), primary_key=True),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response", postgresql.JSONB()),
    )
    op.create_table(
        "review_outbox",
        sa.Column("event_id", sa.Uuid(), sa.ForeignKey("review_audit.event_id"), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenant.id"), nullable=False),
        sa.Column("event", postgresql.JSONB(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_review_outbox_tenant_id", "review_outbox", ["tenant_id"])
    op.execute("""CREATE FUNCTION review_audit_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Review audit is append-only' USING ERRCODE='42501'; END; $$""")
    op.execute("""CREATE TRIGGER review_audit_immutable BEFORE UPDATE OR DELETE ON review_audit
FOR EACH ROW EXECUTE FUNCTION review_audit_append_only()""")


def downgrade():
    raise RuntimeError("Review history is forward-only; disable synthetic_workflows to roll back")
