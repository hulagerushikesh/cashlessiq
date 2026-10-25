"""Durable jobs, synthetic ingestion, versioned policy and append-only governance."""

from alembic import op

revision = "0003_mvp"
down_revision = "0002_reviews"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE document_upload (
	id UUID NOT NULL,
	tenant_id UUID NOT NULL,
	actor_id UUID NOT NULL,
	command_id UUID NOT NULL,
	request_id VARCHAR(120) NOT NULL,
	digest VARCHAR(64) NOT NULL,
	content BYTEA NOT NULL,
	state VARCHAR(30) NOT NULL,
	extracted_text TEXT,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_upload_command UNIQUE (tenant_id, actor_id, command_id),
	FOREIGN KEY(tenant_id) REFERENCES tenant (id),
	FOREIGN KEY(actor_id) REFERENCES app_user (id)
)""")
    op.execute("""CREATE INDEX ix_document_upload_tenant_id ON document_upload (tenant_id)""")
    op.execute("""CREATE TABLE mvp_event (
	id UUID NOT NULL,
	tenant_id UUID NOT NULL,
	actor_id UUID NOT NULL,
	actor_role VARCHAR(40) NOT NULL,
	command_id UUID NOT NULL,
	action VARCHAR(40) NOT NULL,
	subject_id VARCHAR(120) NOT NULL,
	fingerprint VARCHAR(64) NOT NULL,
	payload JSONB NOT NULL,
	occurred_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_mvp_event_command UNIQUE (tenant_id, actor_id, command_id),
	FOREIGN KEY(tenant_id) REFERENCES tenant (id),
	FOREIGN KEY(actor_id) REFERENCES app_user (id)
)""")
    op.execute("""CREATE INDEX ix_mvp_event_tenant_id ON mvp_event (tenant_id)""")
    op.execute("""CREATE TABLE policy_version (
	id UUID NOT NULL,
	tenant_id UUID NOT NULL,
	product_id VARCHAR(80) NOT NULL,
	version VARCHAR(80) NOT NULL,
	author_id UUID NOT NULL,
	command_id UUID NOT NULL,
	fingerprint VARCHAR(64) NOT NULL,
	proposal JSONB NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_policy_version UNIQUE (tenant_id, product_id, version),
	CONSTRAINT uq_policy_command UNIQUE (tenant_id, author_id, command_id),
	FOREIGN KEY(tenant_id) REFERENCES tenant (id),
	FOREIGN KEY(author_id) REFERENCES app_user (id)
)""")
    op.execute("""CREATE INDEX ix_policy_version_tenant_id ON policy_version (tenant_id)""")
    op.execute("""CREATE TABLE work_job (
	id UUID NOT NULL,
	tenant_id UUID NOT NULL,
	actor_id UUID NOT NULL,
	kind VARCHAR(30) NOT NULL,
	subject_id VARCHAR(120) NOT NULL,
	payload JSONB NOT NULL,
	state VARCHAR(20) NOT NULL,
	attempts INTEGER NOT NULL,
	lease_id UUID,
	lease_until TIMESTAMP WITH TIME ZONE,
	available_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	result JSONB,
	error_code VARCHAR(40),
	PRIMARY KEY (id),
	FOREIGN KEY(tenant_id) REFERENCES tenant (id),
	FOREIGN KEY(actor_id) REFERENCES app_user (id)
)""")
    op.execute("""CREATE INDEX ix_work_job_tenant_id ON work_job (tenant_id)""")
    op.execute("""CREATE TABLE policy_active (
	tenant_id UUID NOT NULL,
	product_id VARCHAR(80) NOT NULL,
	version_id UUID NOT NULL,
	event_id UUID NOT NULL,
	PRIMARY KEY (tenant_id, product_id),
	FOREIGN KEY(tenant_id) REFERENCES tenant (id),
	FOREIGN KEY(version_id) REFERENCES policy_version (id),
	FOREIGN KEY(event_id) REFERENCES mvp_event (id)
)""")
    op.execute("""CREATE TABLE submitted_case (
	tenant_id UUID NOT NULL,
	request_id VARCHAR(120) NOT NULL,
	actor_id UUID NOT NULL,
	command_id UUID NOT NULL,
	fingerprint VARCHAR(64) NOT NULL,
	policy_id UUID NOT NULL,
	inputs JSONB NOT NULL,
	record JSONB,
	priority VARCHAR(20) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	due_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (tenant_id, request_id),
	CONSTRAINT uq_submission_command UNIQUE (tenant_id, actor_id, command_id),
	FOREIGN KEY(tenant_id) REFERENCES tenant (id),
	FOREIGN KEY(actor_id) REFERENCES app_user (id),
	FOREIGN KEY(policy_id) REFERENCES policy_version (id)
)""")
    op.execute("""CREATE TABLE analytics_event (
	event_id UUID NOT NULL,
	tenant_id UUID NOT NULL,
	event JSONB NOT NULL,
	PRIMARY KEY (event_id),
	FOREIGN KEY(event_id) REFERENCES review_audit (event_id),
	FOREIGN KEY(tenant_id) REFERENCES tenant (id)
)""")
    op.execute("""CREATE INDEX ix_analytics_event_tenant_id ON analytics_event (tenant_id)""")
    op.execute("""ALTER TABLE tenant_membership DROP CONSTRAINT ck_membership_role""")
    op.execute(
        """ALTER TABLE tenant_membership ADD CONSTRAINT ck_membership_role
CHECK (role IN ('processor','medical_officer','auditor',
'policy_analyst','policy_approver','operations_lead','tenant_admin'))"""
    )
    op.execute(
        """CREATE TRIGGER mvp_event_immutable
BEFORE UPDATE OR DELETE ON mvp_event
FOR EACH ROW EXECUTE FUNCTION review_audit_append_only()"""
    )
    op.execute(
        """CREATE TRIGGER policy_version_immutable
BEFORE UPDATE OR DELETE ON policy_version
FOR EACH ROW EXECUTE FUNCTION review_audit_append_only()"""
    )
    op.execute(
        """CREATE TRIGGER analytics_event_immutable
BEFORE UPDATE OR DELETE ON analytics_event
FOR EACH ROW EXECUTE FUNCTION review_audit_append_only()"""
    )

    op.execute("""CREATE TABLE case_input_revision (
	tenant_id UUID NOT NULL,
	request_id VARCHAR(120) NOT NULL,
	revision INTEGER NOT NULL,
	actor_id UUID NOT NULL,
	inputs JSONB NOT NULL,
	digest VARCHAR(64) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (tenant_id, request_id, revision),
	FOREIGN KEY(tenant_id, request_id) REFERENCES submitted_case (tenant_id, request_id),
	FOREIGN KEY(actor_id) REFERENCES app_user (id)
);
CREATE TRIGGER case_input_revision_immutable
BEFORE UPDATE OR DELETE ON case_input_revision
FOR EACH ROW EXECUTE FUNCTION review_audit_append_only()""")


def downgrade():
    raise RuntimeError("MVP history is forward-only; disable synthetic_workflows to roll back")
