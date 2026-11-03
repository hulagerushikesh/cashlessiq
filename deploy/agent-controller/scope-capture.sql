-- INACTIVE DISPOSABLE REVIEW PACKAGE, not a migration/startup installer.
-- Named placeholders are psycopg Identifier values from the trusted CI harness.
-- No runtime login, credential or binding is created by this package.
CREATE ROLE {owner} NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOREPLICATION NOBYPASSRLS;
CREATE SCHEMA {capture} AUTHORIZATION {owner};
REVOKE ALL ON SCHEMA {capture} FROM PUBLIC;

CREATE TABLE {capture}.principal (
    login_oid oid PRIMARY KEY,
    login_name name NOT NULL UNIQUE,
    tenant_id uuid NOT NULL,
    actor_id uuid NOT NULL,
    request_ids text[] NOT NULL,
    starts_at timestamptz NOT NULL,
    ends_at timestamptz NOT NULL,
    enabled boolean NOT NULL DEFAULT false,
    CHECK (cardinality(request_ids) BETWEEN 1 AND 30),
    CHECK (ends_at > starts_at AND ends_at <= starts_at + interval '4 hours'),
    FOREIGN KEY (tenant_id, actor_id)
        REFERENCES {product}.tenant_membership(tenant_id, user_id)
);
ALTER TABLE {capture}.principal OWNER TO {owner};
REVOKE ALL ON {capture}.principal FROM PUBLIC;

-- Only columns needed for scope and row locking. The nonlogin definer is trusted;
-- the runtime gets NONE of these table or column grants.
GRANT USAGE ON SCHEMA {product} TO {owner};
GRANT SELECT(id, active), UPDATE(id) ON {product}.tenant TO {owner};
GRANT SELECT(id, active), UPDATE(id) ON {product}.app_user TO {owner};
GRANT SELECT(tenant_id, user_id, role, active), UPDATE(tenant_id)
    ON {product}.tenant_membership TO {owner};
GRANT SELECT(tenant_id, request_id, policy_id, inputs, record), UPDATE(tenant_id)
    ON {product}.submitted_case TO {owner};
GRANT SELECT(tenant_id, id, proposal), UPDATE(id)
    ON {product}.policy_version TO {owner};
GRANT SELECT(tenant_id, request_id, version, state, assignee_id), UPDATE(tenant_id)
    ON {product}.review_case TO {owner};
GRANT SELECT(tenant_id, request_id, revision, inputs, digest)
    ON {product}.case_input_revision TO {owner};
GRANT SELECT(tenant_id, subject_id, action) ON {product}.mvp_event TO {owner};

CREATE FUNCTION {capture}._capture_bound(p_login oid, p_request_id text) RETURNS jsonb
LANGUAGE plpgsql VOLATILE SECURITY DEFINER PARALLEL UNSAFE
SET search_path = pg_catalog, pg_temp
SET row_security = on
SET lock_timeout = '2s'
AS $capture$
DECLARE
    principal record;
    active_value boolean;
    member_value record;
    case_value record;
    policy_value record;
    review_value record;
    revision_value record;
    decision_value record;
BEGIN
    -- PRIVATE helper. Only trusted definer functions may select a pinned login.
    -- Do not trust current_user (the definer) or caller-controlled GUCs.
    -- Pin both name AND OID, so a dropped/recreated/renamed login loses scope.
    SELECT p.* INTO principal FROM {capture}.principal AS p
    JOIN pg_catalog.pg_roles AS r ON r.oid = p.login_oid AND r.rolname = p.login_name
    WHERE r.oid = p_login AND r.rolcanlogin AND NOT r.rolsuper
      AND NOT r.rolcreatedb AND NOT r.rolcreaterole AND NOT r.rolreplication
      AND NOT r.rolbypassrls AND NOT r.rolinherit AND p.enabled
      AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_auth_members m WHERE m.member = r.oid)
    FOR SHARE OF p;
    IF NOT FOUND OR p_request_id IS NULL OR length(p_request_id) NOT BETWEEN 1 AND 120
       OR (p_request_id = ANY(principal.request_ids)) IS DISTINCT FROM true THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'scope_unavailable';
    END IF;

    -- Same tenant/user/membership/case/policy/review ordering as MVP writers.
    SELECT t.active INTO active_value FROM {product}.tenant AS t
      WHERE t.id = principal.tenant_id FOR UPDATE OF t;
    IF active_value IS DISTINCT FROM true THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'scope_unavailable';
    END IF;
    SELECT u.active INTO active_value FROM {product}.app_user AS u
      WHERE u.id = principal.actor_id FOR UPDATE OF u;
    IF active_value IS DISTINCT FROM true THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'scope_unavailable';
    END IF;
    SELECT m.active, m.role INTO member_value FROM {product}.tenant_membership AS m
      WHERE m.tenant_id = principal.tenant_id AND m.user_id = principal.actor_id
      FOR UPDATE OF m;
    IF NOT FOUND OR NOT member_value.active OR member_value.role <> 'medical_officer' THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'scope_unavailable';
    END IF;
    SELECT c.policy_id, c.inputs, c.record INTO case_value FROM {product}.submitted_case AS c
      WHERE c.tenant_id = principal.tenant_id AND c.request_id = p_request_id FOR UPDATE OF c;
    IF NOT FOUND OR case_value.record IS NULL THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'scope_unavailable';
    END IF;
    SELECT p.proposal INTO policy_value FROM {product}.policy_version AS p
      WHERE p.tenant_id = principal.tenant_id AND p.id = case_value.policy_id FOR UPDATE OF p;
    IF NOT FOUND THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'scope_unavailable';
    END IF;
    SELECT r.version, r.state, r.assignee_id INTO review_value FROM {product}.review_case AS r
      WHERE r.tenant_id = principal.tenant_id AND r.request_id = p_request_id FOR UPDATE OF r;
    IF NOT FOUND OR review_value.state NOT IN ('DRAFT_READY', 'IN_REVIEW')
       OR (review_value.assignee_id IS NOT NULL AND review_value.assignee_id <> principal.actor_id)
    THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'scope_unavailable';
    END IF;
    SELECT v.revision, v.inputs, v.digest INTO revision_value
      FROM {product}.case_input_revision AS v
      WHERE v.tenant_id = principal.tenant_id AND v.request_id = p_request_id
      ORDER BY v.revision DESC LIMIT 1;
    IF NOT FOUND THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'scope_unavailable';
    END IF;
    SELECT bool_or(e.action = 'policy_approve') AS approved,
           bool_or(e.action = 'policy_reject') AS rejected INTO decision_value
      FROM {product}.mvp_event AS e WHERE e.tenant_id = principal.tenant_id
      AND e.subject_id = case_value.policy_id::text
      AND e.action IN ('policy_approve', 'policy_reject');
    -- Recheck real wall clock AFTER waiting for clinical locks. A capture
    -- obtained after approval expiry must not return any clinical projection.
    IF decision_value.approved IS DISTINCT FROM true OR decision_value.rejected
       OR NOT (principal.starts_at <= clock_timestamp() AND clock_timestamp() < principal.ends_at)
    THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'scope_unavailable';
    END IF;
    RETURN jsonb_build_object(
      'tenant_id', principal.tenant_id, 'request_id', p_request_id,
      'policy_id', case_value.policy_id,
      'facts', case_value.inputs, 'revision_inputs', revision_value.inputs,
      'revision_digest', revision_value.digest, 'input_revision', revision_value.revision,
      'review_version', review_value.version,
      'record_input_digest', case_value.record->'input_digest',
      'record_policy_version', case_value.record->'policy_version',
      'record_rules_digest', case_value.record->'rules_digest',
      'policy', jsonb_build_object(
        'product_id', policy_value.proposal->'product_id',
        'version', policy_value.proposal->'version',
        'effective_from', policy_value.proposal->'effective_from',
        'effective_to', policy_value.proposal->'effective_to',
        'wording_document_id', policy_value.proposal->'wording_document_id',
        'clauses', policy_value.proposal->'clauses', 'rules', policy_value.proposal->'rules')
    );
END;
$capture$;
ALTER FUNCTION {capture}._capture_bound(oid, text) OWNER TO {owner};
REVOKE ALL ON FUNCTION {capture}._capture_bound(oid, text) FROM PUBLIC;

-- Runtime wrapper has no principal selector. Delegation is granted separately
-- only to the custody definer, whose own protected assignment selects that OID.
CREATE FUNCTION {capture}.capture(p_request_id text) RETURNS jsonb
LANGUAGE sql VOLATILE SECURITY DEFINER PARALLEL UNSAFE
SET search_path = pg_catalog, pg_temp SET row_security = on SET lock_timeout = '2s'
AS $wrapper$
    SELECT {capture}._capture_bound(
      (SELECT oid FROM pg_catalog.pg_roles WHERE rolname = session_user), p_request_id);
$wrapper$;
ALTER FUNCTION {capture}.capture(text) OWNER TO {owner};
REVOKE ALL ON FUNCTION {capture}.capture(text) FROM PUBLIC;
