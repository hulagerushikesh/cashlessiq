-- INACTIVE review package after scope-capture.sql, NOT a migration/installer.
-- One owner-staged authorization per installation, disabled by default. No
-- login, approval, live credential, service, journal or provider call is created.
-- Only the separately authenticated TRUSTED CUSTODY program may execute public
-- commands. SQL cannot authenticate a provider response or run shared Python
-- clinical validation. Never grant these commands to an API/controller login.
CREATE ROLE {owner} NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOREPLICATION NOBYPASSRLS;
CREATE SCHEMA {calls} AUTHORIZATION {owner};
REVOKE ALL ON SCHEMA {calls} FROM PUBLIC;

CREATE TABLE {calls}.installation (
    slot integer PRIMARY KEY CHECK (slot = 1),
    database_oid oid NOT NULL,
    database_name name NOT NULL,
    database_id uuid NOT NULL,
    epoch_id uuid NOT NULL,
    enabled boolean NOT NULL DEFAULT false
);
CREATE TABLE {calls}.authorization (
    slot integer PRIMARY KEY REFERENCES {calls}.installation(slot) CHECK (slot = 1),
    operation_id uuid NOT NULL UNIQUE,
    custody_oid oid NOT NULL,
    custody_name name NOT NULL,
    clinical_oid oid NOT NULL,
    clinical_name name NOT NULL,
    tenant_id uuid NOT NULL,
    actor_id uuid NOT NULL,
    request_id text NOT NULL CHECK (length(request_id) BETWEEN 1 AND 120),
    -- Exact UTC-canonical ReviewedCallPin, checked and hashed by trusted Python
    -- inside the locked transaction. A matching hash alone is NOT owner consent.
    pin text NOT NULL CHECK (octet_length(pin) BETWEEN 1 AND 4096),
    pin_sha256 text NOT NULL CHECK (pin_sha256 ~ '^[a-f0-9]{{64}}$'),
    snapshot jsonb NOT NULL CHECK (jsonb_typeof(snapshot) = 'object'),
    config jsonb NOT NULL CHECK (jsonb_typeof(config) = 'object'),
    enabled boolean NOT NULL DEFAULT false,
    phase text NOT NULL DEFAULT 'staged' CHECK (phase IN ('staged','checkpointed','published')),
    checkpoint_at timestamptz,
    deadline timestamptz,
    published_at timestamptz,
    FOREIGN KEY (tenant_id, actor_id)
        REFERENCES {product}.tenant_membership(tenant_id, user_id),
    CHECK ((phase = 'staged' AND checkpoint_at IS NULL AND deadline IS NULL AND published_at IS NULL)
        OR (phase = 'checkpointed' AND checkpoint_at IS NOT NULL AND deadline > checkpoint_at
            AND published_at IS NULL)
        OR (phase = 'published' AND checkpoint_at IS NOT NULL AND deadline > checkpoint_at
            AND published_at >= checkpoint_at AND published_at < deadline))
);
CREATE TABLE {calls}.comparison (
    operation_id uuid PRIMARY KEY REFERENCES {calls}.authorization(operation_id),
    candidate jsonb NOT NULL CHECK (jsonb_typeof(candidate) = 'object'
        AND octet_length(candidate::text) <= 256000),
    observation jsonb NOT NULL CHECK (jsonb_typeof(observation) = 'object'
        AND octet_length(observation::text) <= 4096),
    created_at timestamptz NOT NULL
);
ALTER TABLE {calls}.installation OWNER TO {owner};
ALTER TABLE {calls}.authorization OWNER TO {owner};
ALTER TABLE {calls}.comparison OWNER TO {owner};
REVOKE ALL ON ALL TABLES IN SCHEMA {calls} FROM PUBLIC;

CREATE FUNCTION {calls}._forward_only() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $immutable$
BEGIN
    IF TG_OP <> 'UPDATE' OR (to_jsonb(NEW) - ARRAY['enabled','phase','checkpoint_at','deadline','published_at'])
        IS DISTINCT FROM (to_jsonb(OLD) - ARRAY['enabled','phase','checkpoint_at','deadline','published_at'])
       OR NOT ((NEW.phase = OLD.phase AND NEW.checkpoint_at IS NOT DISTINCT FROM OLD.checkpoint_at
                AND NEW.deadline IS NOT DISTINCT FROM OLD.deadline
                AND NEW.published_at IS NOT DISTINCT FROM OLD.published_at)
           OR (OLD.phase = 'staged' AND NEW.phase = 'checkpointed')
           OR (OLD.phase = 'checkpointed' AND NEW.phase = 'published'
               AND NEW.checkpoint_at = OLD.checkpoint_at AND NEW.deadline = OLD.deadline)) THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'single_call_unavailable';
    END IF;
    RETURN NEW;
END;
$immutable$;
ALTER FUNCTION {calls}._forward_only() OWNER TO {owner};
REVOKE ALL ON FUNCTION {calls}._forward_only() FROM PUBLIC;
CREATE TRIGGER authorization_forward_only BEFORE UPDATE OR DELETE ON {calls}.authorization
    FOR EACH ROW EXECUTE FUNCTION {calls}._forward_only();

GRANT USAGE ON SCHEMA {capture} TO {owner};
GRANT EXECUTE ON FUNCTION {capture}._capture_bound(oid, text) TO {owner};
GRANT SELECT(login_oid, login_name, tenant_id, actor_id, ends_at)
    ON {capture}.principal TO {owner};

CREATE FUNCTION {calls}._context(p_operation uuid, p_phase text) RETURNS jsonb
LANGUAGE plpgsql VOLATILE SECURITY DEFINER PARALLEL UNSAFE
SET search_path = pg_catalog, pg_temp SET row_security = on SET lock_timeout = '2s'
AS $context$
DECLARE
    installation record;
    authorization record;
    clinical_end timestamptz;
    clinical jsonb;
    pin_value jsonb;
    now_value timestamptz;
    end_value timestamptz;
BEGIN
    -- Fixed installation -> authorization -> clinical principal/product locks.
    -- Database name AND OID prevent casually reusing a restored/renamed clone.
    -- They do not detect rollback in the SAME database: independent retention
    -- and a reviewed restore/quarantine procedure remain mandatory.
    SELECT i.* INTO installation FROM {calls}.installation i
      JOIN pg_catalog.pg_database d ON d.oid = i.database_oid AND d.datname = i.database_name
      WHERE i.slot = 1 AND i.enabled AND d.datname = current_database() FOR SHARE OF i;
    IF NOT FOUND THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'single_call_unavailable';
    END IF;
    SELECT a.* INTO authorization FROM {calls}.authorization a
      JOIN pg_catalog.pg_roles r ON r.oid = a.custody_oid AND r.rolname = a.custody_name
      JOIN pg_catalog.pg_roles c ON c.oid = a.clinical_oid AND c.rolname = a.clinical_name
      WHERE a.slot = 1 AND a.operation_id = p_operation AND a.enabled AND a.phase = p_phase
        AND a.custody_oid <> a.clinical_oid
        AND r.rolname = session_user AND r.rolcanlogin AND NOT r.rolinherit
        AND NOT (r.rolsuper OR r.rolcreatedb OR r.rolcreaterole OR r.rolreplication OR r.rolbypassrls)
        AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_auth_members m WHERE m.member = r.oid)
      FOR UPDATE OF a;
    IF NOT FOUND THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'single_call_unavailable';
    END IF;
    pin_value := authorization.pin::jsonb;
    IF (pin_value->>'protocol' = 'prepared-single-provider-call-v1'
        AND pin_value->>'database_id' = installation.database_id::text
        AND pin_value->>'epoch_id' = installation.epoch_id::text
        AND pin_value->>'operation_id' = p_operation::text
        AND authorization.snapshot->'binding'->>'tenant_id' = authorization.tenant_id::text
        AND authorization.snapshot->'binding'->>'request_id' = authorization.request_id)
        IS DISTINCT FROM true THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'single_call_unavailable';
    END IF;
    -- Private delegation, never caller-selected identity or SET ROLE. This locks
    -- and checks the clinical principal, tenant, active user/membership, current
    -- case/policy/review and policy decisions with the existing scope function.
    clinical := {capture}._capture_bound(authorization.clinical_oid, authorization.request_id);
    SELECT p.ends_at INTO clinical_end FROM {capture}.principal p
      WHERE p.login_oid = authorization.clinical_oid AND p.login_name = authorization.clinical_name
        AND p.tenant_id = authorization.tenant_id AND p.actor_id = authorization.actor_id;
    now_value := clock_timestamp();
    end_value := least((pin_value->>'ends_at')::timestamptz, clinical_end,
                      coalesce(authorization.deadline, now_value + interval '18 seconds'));
    IF clinical_end IS NULL OR (clinical->>'tenant_id' = authorization.tenant_id::text
        AND (pin_value->>'starts_at')::timestamptz <= now_value AND now_value < end_value
        AND ((pin_value->>'ends_at')::timestamptz > (pin_value->>'starts_at')::timestamptz)
        AND ((pin_value->>'ends_at')::timestamptz <=
             (pin_value->>'starts_at')::timestamptz + interval '4 hours')) IS DISTINCT FROM true
       OR (p_phase = 'staged' AND end_value < now_value + interval '18 seconds') THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'single_call_unavailable';
    END IF;
    RETURN jsonb_build_object('operation_id', p_operation, 'pin', authorization.pin,
      'pin_sha256', authorization.pin_sha256, 'snapshot', authorization.snapshot,
      'config', authorization.config, 'clinical', clinical,
      'checked_at', now_value, 'deadline', end_value);
END;
$context$;
ALTER FUNCTION {calls}._context(uuid, text) OWNER TO {owner};
REVOKE ALL ON FUNCTION {calls}._context(uuid, text) FROM PUBLIC;

CREATE FUNCTION {calls}.checkpoint(p_operation uuid) RETURNS jsonb
LANGUAGE plpgsql VOLATILE SECURITY DEFINER PARALLEL UNSAFE
SET search_path = pg_catalog, pg_temp SET row_security = on SET lock_timeout = '2s'
AS $checkpoint$
DECLARE context jsonb;
BEGIN
    context := {calls}._context(p_operation, 'staged');
    UPDATE {calls}.authorization SET phase = 'checkpointed',
        checkpoint_at = (context->>'checked_at')::timestamptz,
        deadline = (context->>'deadline')::timestamptz WHERE operation_id = p_operation;
    RETURN context;
END;
$checkpoint$;
ALTER FUNCTION {calls}.checkpoint(uuid) OWNER TO {owner};
REVOKE ALL ON FUNCTION {calls}.checkpoint(uuid) FROM PUBLIC;

CREATE FUNCTION {calls}.publication_context(p_operation uuid) RETURNS jsonb
LANGUAGE sql VOLATILE SECURITY DEFINER PARALLEL UNSAFE
SET search_path = pg_catalog, pg_temp SET row_security = on SET lock_timeout = '2s'
AS $publication$
    SELECT {calls}._context(p_operation, 'checkpointed');
$publication$;
ALTER FUNCTION {calls}.publication_context(uuid) OWNER TO {owner};
REVOKE ALL ON FUNCTION {calls}.publication_context(uuid) FROM PUBLIC;

CREATE FUNCTION {calls}.publish(p_operation uuid, p_candidate jsonb, p_observation jsonb)
RETURNS void LANGUAGE plpgsql VOLATILE SECURITY DEFINER PARALLEL UNSAFE
SET search_path = pg_catalog, pg_temp SET row_security = on SET lock_timeout = '2s'
AS $publish$
DECLARE context jsonb; now_value timestamptz;
BEGIN
    context := {calls}._context(p_operation, 'checkpointed');
    IF (jsonb_typeof(p_candidate) = 'object' AND jsonb_typeof(p_observation) = 'object'
        AND p_candidate->'binding' = context->'snapshot'->'binding'
        AND p_candidate->>'run_id' = p_operation::text
        AND p_observation->>'response_sha256' ~ '^[a-f0-9]{{64}}$'
        AND jsonb_typeof(p_observation->'provider_run_id') = 'string'
        AND octet_length(p_observation->>'provider_run_id') BETWEEN 1 AND 200
        AND p_observation->'reported_usage' =
          '{{"origin":"unverified-provider-report-v1","input_tokens":null,"output_tokens":null}}'::jsonb)
        IS DISTINCT FROM true THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'single_call_unavailable';
    END IF;
    now_value := clock_timestamp();
    IF now_value < (context->>'checked_at')::timestamptz
       OR now_value >= (context->>'deadline')::timestamptz THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'single_call_unavailable';
    END IF;
    INSERT INTO {calls}.comparison VALUES (p_operation, p_candidate, p_observation, now_value);
    UPDATE {calls}.authorization SET phase = 'published', published_at = now_value
        WHERE operation_id = p_operation;
END;
$publish$;
ALTER FUNCTION {calls}.publish(uuid, jsonb, jsonb) OWNER TO {owner};
REVOKE ALL ON FUNCTION {calls}.publish(uuid, jsonb, jsonb) FROM PUBLIC;
