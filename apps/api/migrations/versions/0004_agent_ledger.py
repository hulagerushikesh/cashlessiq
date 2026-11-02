"""Inactive fake-only admission/submission ledger; no execution is enabled."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0004_agent_ledger"
down_revision = "0003_mvp"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "agent_execution_grant",
        sa.Column("tenant_id", UUID, primary_key=True),
        sa.Column("id", UUID, primary_key=True),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("approval_ref", sa.String(120), nullable=False),
        sa.Column("operation_keys", JSONB, nullable=False),
        sa.Column("config_digest", sa.String(64), nullable=False),
        sa.Column("source_digest", sa.String(64), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        *[
            sa.Column(n, sa.Integer, nullable=False)
            for n in (
                "case_limit",
                "concurrency_limit",
                "units_per_attempt",
                "unit_limit",
                "admitted",
                "in_flight",
                "reserved_units",
                "consumed_units",
                "uncertain_units",
            )
        ],
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.CheckConstraint("mode = 'fake-only'", name="ck_agent_grant_fake_only"),
        sa.CheckConstraint("ends_at > starts_at", name="ck_agent_grant_window"),
        sa.CheckConstraint(
            "case_limit BETWEEN 1 AND 30 AND concurrency_limit BETWEEN 1 AND case_limit "
            "AND units_per_attempt BETWEEN 1 AND 1000000 "
            "AND unit_limit BETWEEN units_per_attempt AND 30000000",
            name="ck_agent_grant_limits",
        ),
        sa.CheckConstraint(
            "admitted BETWEEN 0 AND case_limit AND in_flight BETWEEN 0 AND admitted "
            "AND reserved_units >= 0 AND consumed_units >= 0 AND uncertain_units >= 0 "
            "AND reserved_units + consumed_units + uncertain_units <= unit_limit",
            name="ck_agent_grant_accounting",
        ),
    )
    op.create_table(
        "agent_operation",
        sa.Column("tenant_id", UUID, primary_key=True),
        sa.Column("id", UUID, primary_key=True),
        sa.Column("request_id", sa.String(120), nullable=False),
        sa.Column("actor_id", UUID, nullable=False),
        sa.Column("grant_id", UUID, nullable=False),
        *[
            sa.Column(n, sa.String(64), nullable=False)
            for n in (
                "operation_key",
                "config_digest",
                "source_digest",
            )
        ],
        sa.Column("snapshot", JSONB, nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fence_id", UUID, nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id", "request_id"],
            ["submitted_case.tenant_id", "submitted_case.request_id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "actor_id"],
            ["tenant_membership.tenant_id", "tenant_membership.user_id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "grant_id"],
            ["agent_execution_grant.tenant_id", "agent_execution_grant.id"],
        ),
        sa.UniqueConstraint("tenant_id", "operation_key", name="uq_agent_operation_key"),
        sa.CheckConstraint(
            "state IN ('reserved','submitting','unknown','rejected',"
            "'published','superseded','expired')",
            name="ck_agent_operation_state",
        ),
        sa.CheckConstraint("version >= 0", name="ck_agent_operation_version"),
        sa.CheckConstraint(
            "deadline > created_at AND deadline <= created_at + interval '120 seconds'",
            name="ck_agent_operation_deadline",
        ),
        sa.CheckConstraint(
            "(fence_id IS NULL) = (lease_until IS NULL) AND "
            "(lease_until IS NULL OR lease_until <= deadline)",
            name="ck_agent_operation_lease",
        ),
    )
    op.create_table(
        "agent_attempt",
        sa.Column("tenant_id", UUID, primary_key=True),
        sa.Column("id", UUID, primary_key=True),
        sa.Column("operation_id", UUID, nullable=False),
        sa.Column("attempt_number", sa.Integer, nullable=False),
        sa.Column("submission_id", UUID, nullable=False),
        sa.Column("fence_id", UUID, nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "operation_id"], ["agent_operation.tenant_id", "agent_operation.id"]
        ),
        sa.UniqueConstraint("tenant_id", "operation_id", name="uq_agent_single_attempt"),
        sa.UniqueConstraint("submission_id", name="uq_agent_submission_id"),
        sa.UniqueConstraint("tenant_id", "operation_id", "id", name="uq_agent_attempt_owner"),
        sa.CheckConstraint("attempt_number = 1", name="ck_agent_one_attempt"),
    )
    op.create_table(
        "agent_comparison",
        sa.Column("tenant_id", UUID, primary_key=True),
        sa.Column("operation_id", UUID, primary_key=True),
        sa.Column("attempt_id", UUID, nullable=False),
        sa.Column("candidate", JSONB, nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "operation_id"], ["agent_operation.tenant_id", "agent_operation.id"]
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "operation_id", "attempt_id"],
            ["agent_attempt.tenant_id", "agent_attempt.operation_id", "agent_attempt.id"],
        ),
    )
    for table in ("agent_attempt", "agent_comparison"):
        op.execute(f"""CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table}
FOR EACH ROW EXECUTE FUNCTION review_audit_append_only()""")
    # Receipts cannot be deleted to buy a replacement. Identity and approved limits
    # cannot be rebound while normal counters/state/leases remain mutable.
    for table, fields in (
        (
            "agent_execution_grant",
            "tenant_id,id,mode,approval_ref,operation_keys,config_digest,"
            "source_digest,starts_at,ends_at,case_limit,concurrency_limit,units_per_attempt,unit_limit",
        ),
        (
            "agent_operation",
            "tenant_id,id,request_id,actor_id,grant_id,operation_key,config_digest,"
            "source_digest,snapshot,created_at,deadline",
        ),
    ):
        old = ",".join(f"OLD.{field}" for field in fields.split(","))
        new = ",".join(f"NEW.{field}" for field in fields.split(","))
        op.execute(f"""CREATE FUNCTION {table}_identity_guard() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Agent receipt retained'; END IF;
  IF ROW({old}) IS DISTINCT FROM ROW({new}) THEN
    RAISE EXCEPTION 'Agent identity immutable';
  END IF;
  RETURN NEW;
END; $$ LANGUAGE plpgsql;
CREATE TRIGGER {table}_identity BEFORE UPDATE OR DELETE ON {table}
FOR EACH ROW EXECUTE FUNCTION {table}_identity_guard()""")
    op.execute("""CREATE FUNCTION agent_operation_transition_guard() RETURNS trigger AS $$
BEGIN
  IF NEW.version <> OLD.version + 1 OR NOT (
    (OLD.state = 'reserved' AND NEW.state IN ('reserved','submitting','expired')) OR
    (OLD.state = 'submitting' AND NEW.state IN
      ('submitting','unknown','rejected','published','superseded'))
  ) THEN RAISE EXCEPTION 'Agent transition forbidden'; END IF;
  RETURN NEW;
END; $$ LANGUAGE plpgsql;
CREATE TRIGGER agent_operation_transition BEFORE UPDATE ON agent_operation
FOR EACH ROW EXECUTE FUNCTION agent_operation_transition_guard()""")


def downgrade():
    raise RuntimeError("Agent cost receipts are retained; the inactive stage cannot be reset")
