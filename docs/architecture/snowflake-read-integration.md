# P2 bounded Snowflake source gateway

Status: bounded live source reads verified; not enabled in the API. 19 October 2026.

## Restricted-role follow-up — 19 October

After CoCo applied the role and exact operator grant, local SHOW checks confirmed
the eight direct USAGE/SELECT grants, no grant options, no inherited account
role in that direct grant list, and RUSHIKESH2001 as its single grantee.
The Python gateway connected explicitly as CIQ_PRODUCT_READER and returned:

- TPA001: GOL001 only (one record).
- TPA003: GOL024 and GOL027 only (two records).

These were separate operator probes using explicit UUID/TPA arguments, NOT
persisted application tenant mappings or changes to API fixtures/memberships.
The TPA003 probe passed after the gateway was hardened to run
`USE SECONDARY ROLES NONE` before source reads. The earlier TPA001 probe used
the explicit primary reader role but preceded this hardening. Unit tests assert
the session command runs first and prevents reads if rejected.

**Effective privileges caveat:** CoCo's "no AI privileges" conclusion described
direct grants only. Live PUBLIC grants include USE AI FUNCTIONS and
SNOWFLAKE.CORTEX_USER, as well as SNOWFLAKE_LEARNING_ROLE and compute-pool usage.
Every account role inherits PUBLIC, so this is NOT an effectively AI-disabled
or account-wide read-only identity. The operator also has direct grants on its
personal workspace/schema. Do not claim that disabling secondary roles removes
PUBLIC or all user grants. The gateway itself executes only fixed session/SELECT
statements and no AI calls; it is still an operator-only synthetic spike.
No PUBLIC/user grants were revoked or changed. Production service identity and
account-wide privilege hardening require a separately reviewed plan with CoCo
to avoid breaking the existing app and interactive tools.

Sources: [secondary-role control](https://docs.snowflake.com/en/sql-reference/sql/use-secondary-roles),
[default Cortex access](https://docs.snowflake.com/en/user-guide/snowflake-cortex/opting-out),
[pending direct-user-grant behavior](https://docs.snowflake.com/en/release-notes/bcr-bundles/2026_08/bcr-2438).

Verification: 62 root tests and 46 API/PostgreSQL/gateway tests pass (108 total),
plus API Ruff and whitespace checks. No policy/rule changes or reviewer writes.
End-state inspection confirmed both container pools and search indexing/serving
still suspended. CIQ_WH had zero running/queued queries, was explicitly suspended
after the source checks, and the final SHOW confirmed zero clusters/SUSPENDED.

## Live inspection — 19 October

Local OAuth succeeded. A bounded diagnostic SELECT under CIQ_ADMIN (not the
product reader) returned exactly three records. These seven source fields match
the packaged snapshots: request ID, policy ID, product name, policy version,
continuous-cover date, admission date, and supplied estimate/claimed amount.
This is metadata parity only, not decision, evidence, clinical, or member parity.

| Request | Policy | Source TPA | Product |
| --- | --- | --- | --- |
| GOL001 | POL0001 | TPA001 | AS_NIA_V02_2425 |
| GOL024 | POL0024 | TPA003 | AS_NIA_V02_2425 |
| GOL027 | POL0027 | TPA003 | AS_NIA_V02_2425 |

The offline alpha intentionally groups three golden examples in a demo tenant;
that grouping is NOT evidence of a single customer/TPA's ownership. Do not map
the existing sandbox tenant to both TPAs or relabel source ownership. Before
live UI integration, separate tenant mappings and their membership/fixtures must
be explicitly designed and tested. Keep the offline demo unchanged meanwhile.

`SHOW ROLES LIKE 'CIQ_PRODUCT_READER'` returned no rows. No reader role or grant
was applied in this session: interactive grant review remains with CoCo. The
gateway itself has NOT yet been verified under a restricted live role. Next:
CoCo reviews the script and grants that role to the authenticated operator
RUSHIKESH2001 only, then the operator can verify each source TPA separately.
Do not use an admin connection as a fallback to claim gateway verification.

The pre-session resource check found all four warehouses and both container
pools suspended; search indexing and serving were suspended. CIQ_RM reported
2.15 of 10 monthly warehouse credits used. Billing history shows $0.12 warehouse
usage on 18 October; this is neither this session's cost nor a live trial balance.
No agent, extraction, ingestion, or Streamlit startup was performed.
CIQ_WH was activated by these reads, then explicitly suspended with no running
or queued queries; the final SHOW confirmed SUSPENDED with zero clusters.

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
