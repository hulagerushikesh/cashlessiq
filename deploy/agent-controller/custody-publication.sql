-- INACTIVE FAKE-ONLY extension after custody-submission.sql. Separate trusted
-- custody validates Python deterministic/citation contracts on this transaction.
-- No browser/clinical runtime receives these commands or a "validated" flag.
-- SQL alone does not prove Python validation or independent external history.
GRANT UPDATE(lease_until) ON {product}.agent_operation TO {owner};
GRANT SELECT(units_per_attempt, in_flight, reserved_units, consumed_units)
    ON {product}.agent_execution_grant TO {owner};
GRANT UPDATE(in_flight, reserved_units, consumed_units)
    ON {product}.agent_execution_grant TO {owner};
GRANT INSERT ON {product}.agent_comparison TO {owner};
-- No uncertain-unit/refund/grant creation, original deadline/snapshot/fence,
-- attempt update or human review/audit/outbox privilege is added.

CREATE FUNCTION {receipts}.publication_context_fake(p_request text, p_operation uuid,
    p_version integer, p_fence uuid, p_submission uuid) RETURNS jsonb
LANGUAGE plpgsql VOLATILE SECURITY DEFINER PARALLEL UNSAFE
SET search_path = pg_catalog, pg_temp SET row_security = on SET lock_timeout = '2s'
AS $context$
DECLARE
    context jsonb;
    attempt record;
BEGIN
    context := {receipts}._submission_context(p_request, p_operation, p_version, p_fence, 'submitting');
    SELECT a.* INTO attempt FROM {product}.agent_attempt a
      WHERE a.tenant_id = (context->>'tenant_id')::uuid AND a.operation_id = p_operation
        AND a.submission_id = p_submission AND a.fence_id = p_fence AND a.attempt_number = 1;
    IF NOT FOUND OR p_version >= 2147483647
       OR clock_timestamp() >= (context->>'deadline')::timestamptz THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'agent_admission_quarantined';
    END IF;
    -- Clinical projection stays within authenticated custody and these locks.
    RETURN jsonb_build_object('checkpoint', jsonb_build_object(
      'operation_id', p_operation, 'version', p_version, 'fence_id', p_fence,
      'attempt_id', attempt.id, 'submission_id', attempt.submission_id),
      'checked_at', clock_timestamp(), 'deadline', context->'deadline',
      'window_end', context->'window_end', 'clinical', context->'clinical');
END;
$context$;
ALTER FUNCTION {receipts}.publication_context_fake(text, uuid, integer, uuid, uuid) OWNER TO {owner};
REVOKE ALL ON FUNCTION {receipts}.publication_context_fake(text, uuid, integer, uuid, uuid) FROM PUBLIC;

CREATE FUNCTION {receipts}.heartbeat_submitted_fake(p_request text, p_operation uuid,
    p_version integer, p_fence uuid, p_submission uuid) RETURNS jsonb
LANGUAGE plpgsql VOLATILE SECURITY DEFINER PARALLEL UNSAFE
SET search_path = pg_catalog, pg_temp SET row_security = on SET lock_timeout = '2s'
AS $heartbeat$
DECLARE
    context jsonb;
    now_value timestamptz;
BEGIN
    context := {receipts}.publication_context_fake(
      p_request, p_operation, p_version, p_fence, p_submission);
    now_value := clock_timestamp();
    IF now_value >= (context->>'deadline')::timestamptz THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'agent_admission_quarantined';
    END IF;
    UPDATE {product}.agent_operation SET version = version + 1,
      lease_until = least(now_value + interval '30 seconds', (context->>'window_end')::timestamptz)
      WHERE tenant_id = (context->'clinical'->>'tenant_id')::uuid AND id = p_operation;
    RETURN jsonb_set(context->'checkpoint', '{{version}}', to_jsonb(p_version + 1));
END;
$heartbeat$;
ALTER FUNCTION {receipts}.heartbeat_submitted_fake(text, uuid, integer, uuid, uuid) OWNER TO {owner};
REVOKE ALL ON FUNCTION {receipts}.heartbeat_submitted_fake(text, uuid, integer, uuid, uuid) FROM PUBLIC;

CREATE FUNCTION {receipts}.publish_comparison_fake(p_request text, p_operation uuid,
    p_version integer, p_fence uuid, p_submission uuid, p_candidate jsonb) RETURNS jsonb
LANGUAGE plpgsql VOLATILE SECURITY DEFINER PARALLEL UNSAFE
SET search_path = pg_catalog, pg_temp SET row_security = on SET lock_timeout = '2s'
AS $publish$
DECLARE
    context jsonb;
    tenant uuid;
    operation record;
    allowance record;
    now_value timestamptz;
BEGIN
    -- Recheck after Python validation while retaining the SAME fresh locks.
    context := {receipts}.publication_context_fake(
      p_request, p_operation, p_version, p_fence, p_submission);
    tenant := (context->'clinical'->>'tenant_id')::uuid;
    SELECT o.* INTO operation FROM {product}.agent_operation o
      WHERE o.tenant_id = tenant AND o.id = p_operation;
    SELECT g.id, g.units_per_attempt, g.in_flight, g.reserved_units INTO allowance
      FROM {product}.agent_execution_grant g WHERE g.tenant_id = tenant AND g.id = operation.grant_id;
    now_value := clock_timestamp();
    -- Defense in depth; exact money/deterministic/owned-content citation checks
    -- are performed by trusted Python, not a caller's validation attestation.
    IF (jsonb_typeof(p_candidate) = 'object'
        AND octet_length(p_candidate::text) <= 128000
        AND p_candidate->'binding' = operation.snapshot->'binding'
        AND p_candidate->>'run_id' = p_operation::text
        AND allowance.in_flight >= 1 AND allowance.reserved_units >= allowance.units_per_attempt
        AND now_value < (context->>'deadline')::timestamptz) IS DISTINCT FROM true THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'agent_admission_quarantined';
    END IF;
    INSERT INTO {product}.agent_comparison
      (tenant_id, operation_id, attempt_id, candidate, published_at)
    VALUES (tenant, p_operation, (context->'checkpoint'->>'attempt_id')::uuid, p_candidate, now_value);
    UPDATE {product}.agent_execution_grant SET in_flight = in_flight - 1,
      reserved_units = reserved_units - allowance.units_per_attempt,
      consumed_units = consumed_units + allowance.units_per_attempt
      WHERE tenant_id = tenant AND id = allowance.id;
    UPDATE {product}.agent_operation SET state = 'published', version = version + 1
      WHERE tenant_id = tenant AND id = p_operation;
    RETURN jsonb_set(context->'checkpoint', '{{version}}', to_jsonb(p_version + 1));
END;
$publish$;
ALTER FUNCTION {receipts}.publish_comparison_fake(text, uuid, integer, uuid, uuid, jsonb) OWNER TO {owner};
REVOKE ALL ON FUNCTION {receipts}.publish_comparison_fake(text, uuid, integer, uuid, uuid, jsonb) FROM PUBLIC;
