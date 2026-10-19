# P2 bounded Snowflake source gateway

Status: offline-tested gateway; not enabled in the API. 19 October 2026.

The legacy schema identifies TPA ownership through CORE.POLICY.TPA_ID, not a
product tenant UUID. Never guess that mapping or accept it from browser headers.
The operator must verify ownership before configuring a server-side mapping.
The current gateway permits only GOL001, GOL024, and GOL027 and returns source
metadata, not decisions or clinical narrative. It does not synthesize missing
rows, compute money, rerun extraction, or execute an agent.

Existing CIQ_AUDITOR inherits CIQ_APP_USER, which has APP INSERT/UPDATE grants.
Do not reuse it as a read-only product credential. The proposed dedicated role
in sql/64_product_reader.sql has no inherited runtime role or AI privilege.
Table-level SELECT is still NOT tenant RLS. A customer deployment requires
tenant-scoped secure views, validated mapping and service authentication;
this gateway is only a synthetic operator spike.

## Next live verification

1. Complete local browser authentication: `snow connection test -c cashlessiq`.
2. Run the existing explicit cost snapshot before billable integration. Confirm
   CIQ_WH is X-Small/60s auto-suspend and all container pools/search stay suspended.
3. Ask CoCo to review and apply the reader SQL and exact operator grant:

   > Review sql/64_product_reader.sql. Inspect CURRENT_USER(), existing grants
   > and role hierarchy first. Create the dedicated role idempotently and grant
   > it only to this local operator, not PUBLIC or application users. Confirm
   > it inherits no CIQ_APP_USER/admin role and has only the specified source
   > SELECT plus database/schema/warehouse USAGE. Do not change existing app
   > grants, run agents/extraction, or wake Streamlit. Inspect the ownership of
   > GOL001/GOL024/GOL027 through PREAUTH_REQUEST -> POLICY and report the exact
   > TPA_ID for each. Do not assume all three belong to the same TPA.

4. With a verified synthetic mapping only, run the bounded read from repo root:

   ```sh
   uv run --project apps/api --extra snowflake python -m ciq_api.snowflake_reads \
     --tenant-id 00000000-0000-0000-0000-000000000001 \
     --verified-tpa-id <verified-synthetic-TPA_ID>
   ```

   Expected: JSON count and IDs for approved cases owned by that TPA (0–3).
   An empty result is not parity success. Missing grants/authentication produce
   a generic error, never connector details in API responses or CLI output.
5. Compare request/policy/product/version, dates and supplied integer estimates
   with frozen case fixtures. Record differences; never overwrite frozen traces
   with live agent output or silently fall back if the source fails.
6. Check end-state resources after the bounded session. Allow CIQ_WH auto-suspend;
   don't suspend shared workloads or wake the authenticated Streamlit app.

Only after the ownership and parity evidence passes should the repository use
this gateway. Live evidence/decision mapping remains separate P2 work. The HTTP
API and UI deliberately continue to show their existing synthetic snapshots.
No production environment, policy activation, or reviewer write is enabled.

The connector is an optional API extra, not a default runtime dependency. Tests
use fake connections, assert bound parameters/row caps, prevent cross-tenant
results, reject duplicates/unapproved IDs, and verify connection cleanup.
Connections use an explicit role, warehouse, query tag, 30-second statement
timeout, and 15-second queue timeout. No ACCOUNTADMIN fallback exists.

Connector behavior follows Snowflake's official
[connection configuration](https://docs.snowflake.com/en/developer-guide/python-connector/python-connector-connect)
and [parameter binding](https://docs.snowflake.com/en/developer-guide/python-connector/python-connector-example)
documentation. No credentials belong in this document or committed env files.
