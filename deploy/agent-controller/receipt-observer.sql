-- INACTIVE FAKE-ONLY REVIEW PACKAGE. Trusted disposable installation only.
-- SEPARATE nonlogin definer and principal from clinical capture/reservation.
-- No runtime login, binding, epoch, grant, write command or I/O permit is made.
CREATE ROLE {owner} NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOREPLICATION NOBYPASSRLS;
CREATE SCHEMA {receipts} AUTHORIZATION {owner};
REVOKE ALL ON SCHEMA {receipts} FROM PUBLIC;

CREATE TABLE {receipts}.principal (
    login_oid oid PRIMARY KEY,
    login_name name NOT NULL UNIQUE,
    database_id uuid NOT NULL,
    epoch_id uuid NOT NULL,
    starts_at timestamptz NOT NULL,
    ends_at timestamptz NOT NULL,
    enabled boolean NOT NULL DEFAULT false,
    CHECK (ends_at > starts_at AND ends_at <= starts_at + interval '4 hours')
);
ALTER TABLE {receipts}.principal OWNER TO {owner};
REVOKE ALL ON {receipts}.principal FROM PUBLIC;
GRANT USAGE ON SCHEMA {product} TO {owner};
GRANT SELECT(id, mode, database_id, epoch_id), UPDATE(id)
    ON {product}.agent_admission_epoch TO {owner};
GRANT SELECT(tenant_id, id, actor_id, request_id, grant_id, operation_key,
             snapshot, config_digest, source_digest, created_at, deadline)
    ON {product}.agent_operation TO {owner};
GRANT SELECT(tenant_id, id, mode, approval_ref, starts_at, ends_at,
             case_limit, concurrency_limit, unit_limit, units_per_attempt)
    ON {product}.agent_execution_grant TO {owner};
GRANT SELECT(tenant_id, id, operation_id, attempt_number, submission_id, fence_id, submitted_at)
    ON {product}.agent_attempt TO {owner};

CREATE FUNCTION {receipts}.inventory_fake() RETURNS jsonb
LANGUAGE plpgsql VOLATILE SECURITY DEFINER PARALLEL UNSAFE
SET search_path = pg_catalog, pg_temp SET row_security = on SET lock_timeout = '2s'
AS $inventory$
DECLARE
    anchor record;
    principal record;
    entries jsonb;
    result jsonb;
    now_value timestamptz;
BEGIN
    -- All existing admission writers take this lock first. No clinical locks
    -- are needed for immutable checkpoint material; no mutable state is returned.
    SELECT e.mode, e.database_id, e.epoch_id INTO anchor
      FROM {product}.agent_admission_epoch AS e WHERE e.id = 1 FOR UPDATE OF e;
    IF NOT FOUND OR anchor.mode <> 'fake-only' THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'agent_admission_quarantined';
    END IF;
    SELECT p.* INTO principal FROM {receipts}.principal AS p
      JOIN pg_catalog.pg_roles AS r ON r.oid = p.login_oid AND r.rolname = p.login_name
      WHERE r.rolname = session_user AND r.rolcanlogin AND NOT r.rolsuper
        AND NOT r.rolcreatedb AND NOT r.rolcreaterole AND NOT r.rolreplication
        AND NOT r.rolbypassrls AND NOT r.rolinherit AND p.enabled
        AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_auth_members m WHERE m.member = r.oid)
      FOR SHARE OF p;
    IF NOT FOUND OR principal.database_id <> anchor.database_id
       OR principal.epoch_id <> anchor.epoch_id THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'agent_admission_quarantined';
    END IF;
    -- Epoch-wide, not caller/tenant/case-filtered: forgotten work anywhere in
    -- the epoch must quarantine admission everywhere. Never truncate to 30.
    IF (SELECT count(*) FROM
         (SELECT a.id FROM {product}.agent_attempt a LIMIT 31) bounded) > 30 THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'agent_admission_quarantined';
    END IF;
    SELECT coalesce(jsonb_agg(jsonb_build_object(
      'operation', jsonb_build_object(
        'tenant_id', o.tenant_id, 'id', o.id, 'actor_id', o.actor_id,
        'request_id', o.request_id, 'grant_id', o.grant_id,
        'operation_key', o.operation_key, 'snapshot', o.snapshot,
        'config_digest', o.config_digest, 'source_digest', o.source_digest,
        'created_at', o.created_at, 'deadline', o.deadline),
      'grant', jsonb_build_object(
        'tenant_id', g.tenant_id, 'id', g.id, 'mode', g.mode,
        'approval_ref', g.approval_ref, 'starts_at', g.starts_at, 'ends_at', g.ends_at,
        'case_limit', g.case_limit, 'concurrency_limit', g.concurrency_limit,
        'unit_limit', g.unit_limit, 'units_per_attempt', g.units_per_attempt),
      'attempt', jsonb_build_object(
        'tenant_id', a.tenant_id, 'id', a.id, 'operation_id', a.operation_id,
        'attempt_number', a.attempt_number, 'submission_id', a.submission_id,
        'fence_id', a.fence_id, 'submitted_at', a.submitted_at)
      ) ORDER BY a.submission_id), '[]'::jsonb) INTO entries
      FROM {product}.agent_attempt a
      LEFT JOIN {product}.agent_operation o
        ON o.tenant_id = a.tenant_id AND o.id = a.operation_id
      LEFT JOIN {product}.agent_execution_grant g
        ON g.tenant_id = o.tenant_id AND g.id = o.grant_id;
    result := jsonb_build_object('epoch', jsonb_build_object(
      'mode', anchor.mode, 'database_id', anchor.database_id, 'epoch_id', anchor.epoch_id),
      'entries', entries);
    now_value := clock_timestamp();
    IF NOT (principal.starts_at <= now_value AND now_value < principal.ends_at)
       OR octet_length(result::text) > 4194304 THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'agent_admission_quarantined';
    END IF;
    RETURN result;
END;
$inventory$;
ALTER FUNCTION {receipts}.inventory_fake() OWNER TO {owner};
REVOKE ALL ON FUNCTION {receipts}.inventory_fake() FROM PUBLIC;
