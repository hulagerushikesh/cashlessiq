-- INACTIVE fake-only extension after custody publication. Trusted custody only.
-- No runtime installation, role, binding, epoch, grant or retry is created.
GRANT SELECT(uncertain_units), UPDATE(uncertain_units)
    ON {product}.agent_execution_grant TO {owner};
-- Other selected counters/state updates come from the earlier packages.

CREATE FUNCTION {receipts}._recover_fake(p_request text, p_operation uuid,
    p_refund boolean) RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER PARALLEL UNSAFE
SET search_path = pg_catalog, pg_temp SET row_security = on SET lock_timeout = '2s'
AS $recover$
DECLARE
    anchor record;
    principal record;
    assignment record;
    operation record;
    allowance record;
    locator uuid;
    now_value timestamptz;
    next_state text;
    has_attempt boolean;
BEGIN
    -- Epoch FIRST, then protected custody bindings, grant and operation. Never
    -- acquire clinical locks in status recovery, including after grant/op locks.
    SELECT e.mode, e.database_id, e.epoch_id INTO anchor
      FROM {product}.agent_admission_epoch e WHERE e.id=1 FOR UPDATE OF e;
    IF NOT FOUND OR anchor.mode <> 'fake-only' THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'agent_admission_quarantined';
    END IF;
    SELECT p.* INTO principal FROM {receipts}.principal p
      JOIN pg_catalog.pg_roles r ON r.oid=p.login_oid AND r.rolname=p.login_name
      WHERE r.rolname=session_user AND r.rolcanlogin AND NOT r.rolsuper
        AND NOT r.rolcreatedb AND NOT r.rolcreaterole AND NOT r.rolreplication
        AND NOT r.rolbypassrls AND NOT r.rolinherit AND p.enabled
        AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_auth_members m WHERE m.member=r.oid)
      FOR SHARE OF p;
    IF NOT FOUND OR principal.database_id <> anchor.database_id
       OR principal.epoch_id <> anchor.epoch_id THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'agent_admission_quarantined';
    END IF;
    SELECT s.* INTO assignment FROM {receipts}.submission_scope s
      WHERE s.login_oid=principal.login_oid AND s.request_id=p_request
        AND s.operation_id=p_operation AND s.enabled FOR SHARE OF s;
    IF NOT FOUND THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'agent_admission_quarantined';
    END IF;
    -- Immutable locator read before grant lock; recheck exact identity under op
    -- lock. This uses no clinical principal, membership, policy or review row.
    SELECT o.grant_id INTO locator FROM {product}.agent_operation o
      WHERE o.tenant_id=assignment.tenant_id AND o.id=p_operation;
    SELECT g.id, g.mode, g.units_per_attempt, g.in_flight, g.reserved_units
      INTO allowance FROM {product}.agent_execution_grant g
      WHERE g.tenant_id=assignment.tenant_id AND g.id=locator FOR UPDATE OF g;
    IF NOT FOUND OR allowance.mode <> 'fake-only' THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'agent_admission_quarantined';
    END IF;
    SELECT o.* INTO operation FROM {product}.agent_operation o
      WHERE o.tenant_id=assignment.tenant_id AND o.id=p_operation FOR UPDATE OF o;
    now_value := clock_timestamp();
    IF NOT FOUND OR (operation.grant_id=allowance.id AND operation.actor_id=assignment.actor_id
        AND operation.request_id=p_request
        AND principal.starts_at <= now_value AND now_value < principal.ends_at)
        IS DISTINCT FROM true THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'agent_admission_quarantined';
    END IF;
    SELECT EXISTS(SELECT 1 FROM {product}.agent_attempt a
      WHERE a.tenant_id=assignment.tenant_id AND a.operation_id=p_operation) INTO has_attempt;
    IF operation.state='submitting' AND has_attempt AND operation.lease_until IS NOT NULL
       AND now_value >= least(operation.lease_until, operation.deadline) THEN
        next_state := 'unknown';
    ELSIF p_refund IS TRUE AND operation.state='reserved' AND NOT has_attempt
       AND now_value >= operation.deadline THEN
        next_state := 'expired';
    ELSE
        RETURN;
    END IF;
    IF operation.version >= 2147483647 OR allowance.in_flight < 1
       OR allowance.reserved_units < allowance.units_per_attempt THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'agent_admission_quarantined';
    END IF;
    UPDATE {product}.agent_execution_grant
      SET reserved_units=reserved_units-allowance.units_per_attempt,
          uncertain_units=uncertain_units + CASE WHEN next_state='unknown'
            THEN allowance.units_per_attempt ELSE 0 END,
          in_flight=in_flight - CASE WHEN next_state='expired' THEN 1 ELSE 0 END
      WHERE tenant_id=assignment.tenant_id AND id=allowance.id;
    UPDATE {product}.agent_operation SET state=next_state, version=version+1
      WHERE tenant_id=assignment.tenant_id AND id=p_operation;
END;
$recover$;
ALTER FUNCTION {receipts}._recover_fake(text, uuid, boolean) OWNER TO {owner};
REVOKE ALL ON FUNCTION {receipts}._recover_fake(text, uuid, boolean) FROM PUBLIC;

CREATE FUNCTION {receipts}.recover_submitted_fake(p_request text, p_operation uuid) RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER PARALLEL UNSAFE
SET search_path = pg_catalog, pg_temp SET row_security = on SET lock_timeout = '2s'
AS $status$
BEGIN
    -- Missing/closed external custody can never authorize a reserved refund.
    PERFORM {receipts}._recover_fake(p_request, p_operation, false);
END;
$status$;
ALTER FUNCTION {receipts}.recover_submitted_fake(text, uuid) OWNER TO {owner};
REVOKE ALL ON FUNCTION {receipts}.recover_submitted_fake(text, uuid) FROM PUBLIC;

CREATE FUNCTION {receipts}.recover_verified_fake(p_request text, p_operation uuid) RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER PARALLEL UNSAFE
SET search_path = pg_catalog, pg_temp SET row_security = on SET lock_timeout = '2s'
AS $verified$
BEGIN
    -- Trusted custody has independently compared ALL external history on THIS
    -- epoch transaction. SQL alone cannot validate SQLite; no public bool flag
    -- or caller-supplied history is accepted. Runtime receives neither command.
    PERFORM {receipts}.inventory_fake();
    PERFORM {receipts}._recover_fake(p_request, p_operation, true);
END;
$verified$;
ALTER FUNCTION {receipts}.recover_verified_fake(text, uuid) OWNER TO {owner};
REVOKE ALL ON FUNCTION {receipts}.recover_verified_fake(text, uuid) FROM PUBLIC;
