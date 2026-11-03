-- INACTIVE FAKE-ONLY disposable extension after capture, reservation and observer.
-- {owner} is the RECEIPT definer, distinct from the clinical definer.
-- Only independently authenticated custody receives public command EXECUTE.
-- Its fixed trusted program checks external history while holding the epoch.
-- SQL alone cannot verify external custody; never grant these to the controller.
-- No login, binding, assignment, grant, epoch, I/O or production service is made.
CREATE TABLE {receipts}.submission_scope (
    login_oid oid NOT NULL REFERENCES {receipts}.principal(login_oid),
    request_id text NOT NULL CHECK (length(request_id) BETWEEN 1 AND 120),
    controller_oid oid NOT NULL,
    controller_name name NOT NULL,
    tenant_id uuid NOT NULL,
    actor_id uuid NOT NULL,
    operation_id uuid NOT NULL,
    enabled boolean NOT NULL DEFAULT false,
    PRIMARY KEY (login_oid, request_id),
    UNIQUE (tenant_id, operation_id)
);
ALTER TABLE {receipts}.submission_scope OWNER TO {owner};
REVOKE ALL ON {receipts}.submission_scope FROM PUBLIC;

-- Delegation is PRIVATE. It selects only an operator-pinned clinical principal,
-- never SET ROLE / SET SESSION AUTHORIZATION or a caller-selected actor/tenant.
GRANT USAGE ON SCHEMA {capture} TO {owner};
GRANT EXECUTE ON FUNCTION {capture}._reservation_context_for(oid, text) TO {owner};
GRANT SELECT ON {product}.agent_operation TO {owner};
GRANT SELECT(config_digest, source_digest, operation_keys)
    ON {product}.agent_execution_grant TO {owner};
GRANT UPDATE(id) ON {product}.agent_execution_grant TO {owner};
GRANT UPDATE(state, version) ON {product}.agent_operation TO {owner};
GRANT INSERT ON {product}.agent_attempt TO {owner};
-- No grant accounting, lease, deadline, snapshot, comparison or human writes.

CREATE FUNCTION {receipts}._submission_context(p_request text, p_operation uuid,
    p_version integer, p_fence uuid, p_state text) RETURNS jsonb
LANGUAGE plpgsql VOLATILE SECURITY DEFINER PARALLEL UNSAFE
SET search_path = pg_catalog, pg_temp SET row_security = on SET lock_timeout = '2s'
AS $context$
DECLARE
    assignment record;
    context jsonb;
    approval jsonb;
    allowance record;
    operation record;
    custody_end timestamptz;
    now_value timestamptz;
BEGIN
    -- Authenticates custody and locks epoch before bindings/clinical/grant/op.
    -- This SQL observation is NOT the independent external-journal comparison.
    PERFORM {receipts}.inventory_fake();
    SELECT s.* INTO assignment FROM {receipts}.submission_scope s
      JOIN pg_catalog.pg_roles r ON r.oid = s.login_oid AND r.rolname = session_user
      JOIN pg_catalog.pg_roles c ON c.oid = s.controller_oid AND c.rolname = s.controller_name
      WHERE s.request_id = p_request AND s.operation_id = p_operation AND s.enabled
      FOR SHARE OF s;
    IF NOT FOUND OR p_version IS NULL OR p_version < 0 OR p_fence IS NULL THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'agent_admission_quarantined';
    END IF;
    context := {capture}._reservation_context_for(assignment.controller_oid, p_request);
    approval := context->'approval';
    IF (context->>'tenant_id' = assignment.tenant_id::text
        AND context->>'actor_id' = assignment.actor_id::text) IS DISTINCT FROM true THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'agent_admission_quarantined';
    END IF;
    -- Original exact grant locator is operator authority, not a request field.
    SELECT g.id, g.mode, g.config_digest, g.source_digest, g.operation_keys,
           g.starts_at, g.ends_at INTO allowance FROM {product}.agent_execution_grant g
      WHERE g.tenant_id = assignment.tenant_id AND g.id = (approval->>'grant_id')::uuid
      FOR UPDATE OF g;
    IF NOT FOUND THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'agent_admission_quarantined';
    END IF;
    SELECT o.* INTO operation FROM {product}.agent_operation o
      WHERE o.tenant_id = assignment.tenant_id AND o.id = assignment.operation_id
      FOR UPDATE OF o;
    now_value := clock_timestamp();
    IF NOT FOUND OR (operation.actor_id = assignment.actor_id
        AND operation.request_id = p_request AND operation.state = p_state
        AND operation.version = p_version AND operation.fence_id = p_fence
        AND operation.grant_id = allowance.id
        AND operation.operation_key = approval->>'operation_key'
        AND operation.snapshot = approval->'snapshot'
        AND operation.config_digest = approval->>'config_digest'
        AND operation.source_digest = approval->>'source_digest'
        AND allowance.mode = 'fake-only'
        AND allowance.config_digest = operation.config_digest
        AND allowance.source_digest = operation.source_digest
        AND allowance.operation_keys ? operation.operation_key
        AND allowance.starts_at <= now_value AND now_value < allowance.ends_at
        AND now_value < (context->>'ends_at')::timestamptz
        AND operation.created_at <= now_value AND now_value < operation.deadline
        AND now_value < operation.lease_until) IS DISTINCT FROM true THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'agent_admission_quarantined';
    END IF;
    -- Recheck custody expiry after waiting for clinical/grant/operation locks.
    PERFORM {receipts}.inventory_fake();
    SELECT p.ends_at INTO custody_end FROM {receipts}.principal p
      JOIN pg_catalog.pg_roles r ON r.oid = p.login_oid AND r.rolname = session_user;
    RETURN jsonb_build_object('tenant_id', assignment.tenant_id,
      'deadline', least(operation.deadline, operation.lease_until, allowance.ends_at,
                       (context->>'ends_at')::timestamptz, custody_end));
END;
$context$;
ALTER FUNCTION {receipts}._submission_context(text, uuid, integer, uuid, text) OWNER TO {owner};
REVOKE ALL ON FUNCTION {receipts}._submission_context(text, uuid, integer, uuid, text) FROM PUBLIC;

CREATE FUNCTION {receipts}.checkpoint_fake(p_request text, p_operation uuid,
    p_version integer, p_fence uuid) RETURNS jsonb
LANGUAGE plpgsql VOLATILE SECURITY DEFINER PARALLEL UNSAFE
SET search_path = pg_catalog, pg_temp SET row_security = on SET lock_timeout = '2s'
AS $checkpoint$
DECLARE
    context jsonb;
    tenant uuid;
    attempt record;
BEGIN
    context := {receipts}._submission_context(p_request, p_operation, p_version, p_fence, 'reserved');
    tenant := (context->>'tenant_id')::uuid;
    IF EXISTS (SELECT 1 FROM {product}.agent_attempt a
               WHERE a.tenant_id = tenant AND a.operation_id = p_operation)
       OR EXISTS (SELECT 1 FROM {product}.agent_operation o
          JOIN {product}.agent_operation current_op
            ON current_op.tenant_id = tenant AND current_op.id = p_operation
          WHERE o.tenant_id = tenant AND o.request_id = p_request AND o.id <> p_operation
            AND o.state <> 'expired' AND (o.config_digest <> current_op.config_digest
               OR o.source_digest <> current_op.source_digest
               OR o.state IN ('submitting', 'unknown')))
       OR clock_timestamp() >= (context->>'deadline')::timestamptz THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'agent_admission_quarantined';
    END IF;
    INSERT INTO {product}.agent_attempt
      (tenant_id, id, operation_id, attempt_number, submission_id, fence_id, submitted_at)
    VALUES (tenant, gen_random_uuid(), p_operation, 1, gen_random_uuid(), p_fence, clock_timestamp())
    RETURNING * INTO attempt;
    UPDATE {product}.agent_operation SET state = 'submitting', version = version + 1
      WHERE tenant_id = tenant AND id = p_operation;
    RETURN jsonb_build_object('operation_id', p_operation, 'version', p_version + 1,
      'fence_id', p_fence, 'attempt_id', attempt.id, 'submission_id', attempt.submission_id);
END;
$checkpoint$;
ALTER FUNCTION {receipts}.checkpoint_fake(text, uuid, integer, uuid) OWNER TO {owner};
REVOKE ALL ON FUNCTION {receipts}.checkpoint_fake(text, uuid, integer, uuid) FROM PUBLIC;

-- Revalidate the committed checkpoint. No SQL ticket or local issued flag exists;
-- independently retained external issue is committed by custody before any I/O.
CREATE FUNCTION {receipts}.issue_fake(p_request text, p_operation uuid,
    p_version integer, p_fence uuid, p_submission uuid) RETURNS jsonb
LANGUAGE plpgsql VOLATILE SECURITY DEFINER PARALLEL UNSAFE
SET search_path = pg_catalog, pg_temp SET row_security = on SET lock_timeout = '2s'
AS $issue$
DECLARE
    context jsonb;
    attempt record;
BEGIN
    context := {receipts}._submission_context(p_request, p_operation, p_version, p_fence, 'submitting');
    SELECT a.* INTO attempt FROM {product}.agent_attempt a
      WHERE a.tenant_id = (context->>'tenant_id')::uuid AND a.operation_id = p_operation
        AND a.submission_id = p_submission AND a.fence_id = p_fence AND a.attempt_number = 1;
    IF NOT FOUND OR clock_timestamp() >= (context->>'deadline')::timestamptz THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'agent_admission_quarantined';
    END IF;
    -- Internal custody projection, never an IPC/browser permission. The trusted
    -- coordinator consumes external issue and dispatches within this budget.
    RETURN jsonb_build_object('checkpoint', jsonb_build_object(
      'operation_id', p_operation, 'version', p_version, 'fence_id', p_fence,
      'attempt_id', attempt.id, 'submission_id', attempt.submission_id),
      'checked_at', clock_timestamp(), 'deadline', context->'deadline');
END;
$issue$;
ALTER FUNCTION {receipts}.issue_fake(text, uuid, integer, uuid, uuid) OWNER TO {owner};
REVOKE ALL ON FUNCTION {receipts}.issue_fake(text, uuid, integer, uuid, uuid) FROM PUBLIC;
