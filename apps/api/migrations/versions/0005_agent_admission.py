"""Default-closed fake admission anchor; no epoch is provisioned by migration."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0005_agent_admission"
down_revision = "0004_agent_ledger"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "agent_admission_epoch",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("database_id", UUID, nullable=False),
        sa.Column("epoch_id", UUID, nullable=False),
        sa.CheckConstraint("id = 1 AND mode = 'fake-only'", name="ck_agent_epoch_fake_only"),
    )
    op.execute("""CREATE TRIGGER agent_admission_epoch_immutable
BEFORE UPDATE OR DELETE ON agent_admission_epoch
FOR EACH ROW EXECUTE FUNCTION review_audit_append_only()""")


def downgrade():
    raise RuntimeError("Admission history is forward-only; quarantine without deleting its anchor")
