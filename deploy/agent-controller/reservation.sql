-- INACTIVE FAKE-ONLY DISPOSABLE REVIEW PACKAGE; install after scope-capture.sql
-- in the SAME transaction. Identifiers are supplied by the trusted CI harness.
-- No login, binding, approval row, epoch, grant or submission authority is created.
-- These commands can only HOLD allowance and maintain an unsubmitted lease.
-- They cannot checkpoint, issue, publish, refund, reconcile or reset anything.
CREATE TABLE {capture}.reservation_scope (
    login_oid oid NOT NULL REFERENCES {capture}.principal(login_oid),
    request_id text NOT NULL CHECK (length(request_id) BETWEEN 1 AND 120),
    grant_id uuid NOT NULL,
    database_id uuid NOT NULL,
    epoch_id uuid NOT NULL,
    operation_key text NOT NULL CHECK (operation_key ~ '^[a-f0-9]{{64}}$'),
    config_digest text NOT NULL CHECK (config_digest ~ '^[a-f0-9]{{64}}$'),
    source_digest text NOT NULL CHECK (source_digest ~ '^[a-f0-9]{{64}}$'),
    snapshot jsonb NOT NULL CHECK (jsonb_typeof(snapshot) = 'object'),
    timeout_seconds integer NOT NULL CHECK (timeout_seconds BETWEEN 1 AND 120),
    enabled boolean NOT NULL DEFAULT false,
    PRIMARY KEY (login_oid, request_id)
);
ALTER TABLE {capture}.reservation_scope OWNER TO {owner};
REVOKE ALL ON {capture}.reservation_scope FROM PUBLIC;

GRANT SELECT(id, mode, database_id, epoch_id), UPDATE(id)
    ON {product}.agent_admission_epoch TO {owner};
GRANT SELECT ON {product}.agent_execution_grant TO {owner};
GRANT UPDATE(admitted, in_flight, reserved_units)
    ON {product}.agent_execution_grant TO {owner};
GRANT SELECT, INSERT ON {product}.agent_operation TO {owner};
GRANT UPDATE(version, fence_id, lease_until) ON {product}.agent_operation TO {owner};

-- Private helper: never grant EXECUTE to runtime. No caller-supplied tenant,
-- actor, grant, snapshot, hash, clock or epoch becomes authority.
CREATE FUNCTION {capture}._reservation_context_for(p_login oid, p_request_id text) RETURNS jsonb
LANGUAGE plpgsql VOLATILE SECURITY DEFINER PARALLEL UNSAFE
SET search_path = pg_catalog, pg_temp SET row_security = on SET lock_timeout = '2s'
AS $context$
DECLARE
    anchor record;
    principal record;
    approval record;
    observed jsonb;
    binding jsonb;
BEGIN
    -- Serialize before clinical/grant/operation locks, like fake admission.
    -- Matching this local anchor is NOT independent receipt-history verification.
    SELECT e.mode, e.database_id, e.epoch_id INTO anchor
      FROM {product}.agent_admission_epoch AS e WHERE e.id = 1 FOR UPDATE OF e;
    IF NOT FOUND OR anchor.mode <> 'fake-only' THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'reservation_unavailable';
    END IF;
    SELECT p.* INTO principal FROM {capture}.principal AS p
      JOIN pg_catalog.pg_roles AS r ON r.oid = p.login_oid AND r.rolname = p.login_name
      WHERE r.oid = p_login AND r.rolcanlogin AND NOT r.rolsuper
        AND NOT r.rolcreatedb AND NOT r.rolcreaterole AND NOT r.rolreplication
        AND NOT r.rolbypassrls AND NOT r.rolinherit AND p.enabled
        AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_auth_members m WHERE m.member = r.oid)
      FOR SHARE OF p;
    IF NOT FOUND OR p_request_id IS NULL OR length(p_request_id) NOT BETWEEN 1 AND 120
       OR (p_request_id = ANY(principal.request_ids)) IS DISTINCT FROM true THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'reservation_unavailable';
    END IF;
    SELECT s.* INTO approval FROM {capture}.reservation_scope AS s
      WHERE s.login_oid = principal.login_oid AND s.request_id = p_request_id
        AND s.enabled FOR SHARE OF s;
    IF NOT FOUND OR approval.database_id <> anchor.database_id
       OR approval.epoch_id <> anchor.epoch_id THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'reservation_unavailable';
    END IF;
    observed := {capture}._capture_bound(p_login, p_request_id);
    binding := approval.snapshot->'binding';
    -- The trusted operator validates/canonicalizes the exact snapshot and key
    -- with shared Python contracts BEFORE staging this disabled approval row.
    -- Compare JSON values; never hash PostgreSQL's different JSON serialization.
    IF (binding->>'tenant_id' = principal.tenant_id::text
        AND binding->>'request_id' = p_request_id
        AND binding->>'policy_id' = observed->>'policy_id'
        AND binding->'input_revision' = observed->'input_revision'
        AND binding->'review_version' = observed->'review_version'
        AND binding->>'input_digest' = observed->>'revision_digest'
        AND observed->'record_input_digest' = observed->'revision_digest'
        AND observed->'record_rules_digest' = binding->'rules_digest'
        AND observed->'record_policy_version' = binding->'policy_version'
        AND observed->'facts' = observed->'revision_inputs'
        AND observed->'facts' = (approval.snapshot->>'facts_json')::jsonb
        AND observed->'policy' = (approval.snapshot->>'policy_json')::jsonb
       ) IS DISTINCT FROM true THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'reservation_unavailable';
    END IF;
    RETURN jsonb_build_object(
      'tenant_id', principal.tenant_id, 'actor_id', principal.actor_id,
      'ends_at', principal.ends_at, 'approval', to_jsonb(approval));
END;
$context$;
ALTER FUNCTION {capture}._reservation_context_for(oid, text) OWNER TO {owner};
REVOKE ALL ON FUNCTION {capture}._reservation_context_for(oid, text) FROM PUBLIC;

CREATE FUNCTION {capture}._reservation_context(p_request_id text) RETURNS jsonb
LANGUAGE sql VOLATILE SECURITY DEFINER PARALLEL UNSAFE
SET search_path = pg_catalog, pg_temp SET row_security = on SET lock_timeout = '2s'
AS $wrapper$
    SELECT {capture}._reservation_context_for(
      (SELECT oid FROM pg_catalog.pg_roles WHERE rolname = session_user), p_request_id);
$wrapper$;
ALTER FUNCTION {capture}._reservation_context(text) OWNER TO {owner};
REVOKE ALL ON FUNCTION {capture}._reservation_context(text) FROM PUBLIC;

CREATE FUNCTION {capture}.reserve_fake(p_request_id text, p_timeout integer) RETURNS jsonb
LANGUAGE plpgsql VOLATILE SECURITY DEFINER PARALLEL UNSAFE
SET search_path = pg_catalog, pg_temp SET row_security = on SET lock_timeout = '2s'
AS $reserve$
DECLARE
    context jsonb;
    approval jsonb;
    tenant uuid;
    actor uuid;
    allowance record;
    operation record;
    now_value timestamptz;
    deadline_value timestamptz;
BEGIN
    IF p_timeout IS NULL OR p_timeout NOT BETWEEN 1 AND 120 THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'reservation_unavailable';
    END IF;
    context := {capture}._reservation_context(p_request_id);
    approval := context->'approval';
    tenant := (context->>'tenant_id')::uuid;
    actor := (context->>'actor_id')::uuid;
    IF p_timeout > (approval->>'timeout_seconds')::integer THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'reservation_unavailable';
    END IF;
    SELECT g.* INTO allowance FROM {product}.agent_execution_grant AS g
      WHERE g.tenant_id = tenant AND g.id = (approval->>'grant_id')::uuid FOR UPDATE OF g;
    IF NOT FOUND OR allowance.mode <> 'fake-only'
       OR allowance.config_digest <> approval->>'config_digest'
       OR allowance.source_digest <> approval->>'source_digest'
       OR (allowance.operation_keys ? (approval->>'operation_key')) IS DISTINCT FROM true THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'reservation_unavailable';
    END IF;
    SELECT o.* INTO operation FROM {product}.agent_operation AS o
      WHERE o.tenant_id = tenant AND o.operation_key = approval->>'operation_key'
      FOR UPDATE OF o;
    IF FOUND THEN
        -- Another grant/correlation cannot repurchase this computation. Never
        -- expose another actor's receipt or change the original deadline/owner.
        IF operation.actor_id <> actor OR operation.request_id <> p_request_id
           OR clock_timestamp() >= (context->>'ends_at')::timestamptz THEN
            RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'reservation_unavailable';
        END IF;
        RETURN jsonb_build_object('operation_id', operation.id,
          'state', operation.state, 'version', operation.version);
    END IF;
    -- Same cross-mapping and unresolved-attempt fence as the owning fake ledger.
    IF EXISTS (SELECT 1 FROM {product}.agent_operation AS o
      WHERE o.tenant_id = tenant AND o.request_id = p_request_id AND o.state <> 'expired'
        AND (o.config_digest <> approval->>'config_digest'
          OR o.source_digest <> approval->>'source_digest'
          OR o.state IN ('submitting', 'unknown'))) THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'reservation_unavailable';
    END IF;
    now_value := clock_timestamp();
    deadline_value := least(now_value + make_interval(secs => p_timeout), allowance.ends_at,
                           (context->>'ends_at')::timestamptz);
    IF NOT (allowance.starts_at <= now_value AND now_value < deadline_value)
       OR allowance.admitted >= allowance.case_limit
       OR allowance.in_flight >= allowance.concurrency_limit
       OR allowance.reserved_units + allowance.consumed_units + allowance.uncertain_units
          + allowance.units_per_attempt > allowance.unit_limit THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'reservation_unavailable';
    END IF;
    INSERT INTO {product}.agent_operation
      (tenant_id, id, request_id, actor_id, grant_id, operation_key, config_digest,
       source_digest, snapshot, state, version, created_at, deadline, fence_id, lease_until)
    VALUES (tenant, gen_random_uuid(), p_request_id, actor, allowance.id,
      approval->>'operation_key', approval->>'config_digest', approval->>'source_digest',
      approval->'snapshot', 'reserved', 0, now_value, deadline_value, NULL, NULL)
    RETURNING * INTO operation;
    UPDATE {product}.agent_execution_grant SET admitted = admitted + 1,
      in_flight = in_flight + 1, reserved_units = reserved_units + allowance.units_per_attempt
      WHERE tenant_id = tenant AND id = allowance.id;
    RETURN jsonb_build_object('operation_id', operation.id,
      'state', operation.state, 'version', operation.version);
END;
$reserve$;
ALTER FUNCTION {capture}.reserve_fake(text, integer) OWNER TO {owner};
REVOKE ALL ON FUNCTION {capture}.reserve_fake(text, integer) FROM PUBLIC;

-- Claim only a reserved operation, or extend its current unexpired fence.
-- Neither path can extend the original deadline or operate on a submitted run.
CREATE FUNCTION {capture}.lease_fake(p_request_id text, p_operation uuid,
    p_version integer, p_fence uuid) RETURNS jsonb
LANGUAGE plpgsql VOLATILE SECURITY DEFINER PARALLEL UNSAFE
SET search_path = pg_catalog, pg_temp SET row_security = on SET lock_timeout = '2s'
AS $lease$
DECLARE
    context jsonb;
    approval jsonb;
    tenant uuid;
    allowance record;
    operation record;
    now_value timestamptz;
    fence uuid;
BEGIN
    IF p_operation IS NULL OR p_version IS NULL OR p_version < 0 THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'reservation_unavailable';
    END IF;
    context := {capture}._reservation_context(p_request_id);
    approval := context->'approval';
    tenant := (context->>'tenant_id')::uuid;
    -- Immutable locator only. Mutable state/owner are rechecked under locks.
    SELECT o.grant_id INTO operation FROM {product}.agent_operation AS o
      WHERE o.tenant_id = tenant AND o.id = p_operation;
    IF NOT FOUND THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'reservation_unavailable';
    END IF;
    SELECT g.* INTO allowance FROM {product}.agent_execution_grant AS g
      WHERE g.tenant_id = tenant AND g.id = operation.grant_id FOR UPDATE OF g;
    SELECT o.* INTO operation FROM {product}.agent_operation AS o
      WHERE o.tenant_id = tenant AND o.id = p_operation FOR UPDATE OF o;
    now_value := clock_timestamp();
    IF (operation.actor_id::text = context->>'actor_id'
        AND operation.request_id = p_request_id AND operation.state = 'reserved'
        AND operation.grant_id::text = approval->>'grant_id'
        AND operation.version = p_version
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
       ) IS DISTINCT FROM true THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'reservation_unavailable';
    END IF;
    IF p_fence IS NULL THEN
        IF operation.lease_until IS NOT NULL AND now_value < operation.lease_until THEN
            RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'reservation_unavailable';
        END IF;
        fence := gen_random_uuid();
    ELSE
        IF (operation.fence_id = p_fence AND now_value < operation.lease_until)
           IS DISTINCT FROM true THEN
            RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'reservation_unavailable';
        END IF;
        fence := p_fence;
    END IF;
    UPDATE {product}.agent_operation SET fence_id = fence, version = version + 1,
      lease_until = least(now_value + interval '30 seconds', deadline, allowance.ends_at,
                         (context->>'ends_at')::timestamptz)
      WHERE tenant_id = tenant AND id = p_operation RETURNING * INTO operation;
    RETURN jsonb_build_object('operation_id', operation.id, 'state', operation.state,
      'version', operation.version, 'fence_id', operation.fence_id);
END;
$lease$;
ALTER FUNCTION {capture}.lease_fake(text, uuid, integer, uuid) OWNER TO {owner};
REVOKE ALL ON FUNCTION {capture}.lease_fake(text, uuid, integer, uuid) FROM PUBLIC;
