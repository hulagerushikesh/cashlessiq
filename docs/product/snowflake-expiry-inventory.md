# Pre-expiry bounded inventory — 21 October 2026

Status: live operator metadata checkpoint, not product isolation acceptance.
Eight statements completed successfully using the local `cashlessiq` connection,
explicit `CIQ_PRODUCT_READER`, secondary roles `NONE` and `CIQ_WH`. No role
escalation, account/object changes, source-row SELECTs or application startup.
The only SELECT returned session identity/context, not source records.

## Results

- Actual primary role: CIQ_PRODUCT_READER. Actual secondary roles: empty.
  Account CA31605, region GCP_ME_CENTRAL2. Local authentication succeeded.
- CIQ_WH: SUSPENDED, zero started clusters, zero running/queued queries,
  X-Small, 60-second auto-suspend. Query acceleration remains enabled.
- Both visible system CPU/GPU compute pools: SUSPENDED, zero active/idle/target
  nodes. These are role-visible results, not an account-wide effective audit.
- `SHOW CORTEX SEARCH SERVICES IN SCHEMA CASHLESSIQ.DOCS` returned no rows.
  **This does not establish that CLAUSE_SEARCH was deleted or is suspended**;
  the reader has no direct search-service privilege. No search query was made.
- Reader direct grants remain exactly 13: four schema/database USAGE grants,
  warehouse USAGE and eight table SELECT grants; no direct grant option. This
  does not resolve PUBLIC/inherited privileges or service identity isolation.
- Eight visible tables are present. SHOW-reported row counts are metadata, not
  independent source integrity checks or an exported recovery fixture:

| Schema | Table | Reported rows |
| --- | --- | ---: |
| CORE | POLICY_PRODUCT | 1 |
| CORE | POLICY | 500 |
| CORE | MEMBER_CONDITION | 800 |
| CORE | CLAIM | 300 |
| DOCS | POLICY_CLAUSE | 35 |
| DOCS | PREAUTH_REQUEST | 50 |
| DOCS | PREAUTH_FACTS | 50 |
| APP | DECISION | 11 |

## Discrepancy: monitor attachment not confirmed

The reader's SHOW WAREHOUSES result contains the string `null` in
`resource_monitor`, unlike the historical administrative baseline recording
CIQ_RM. Do not infer either a removed monitor or a confirmed attachment from
this role-limited checkpoint. Snowflake describes this field as the explicitly
assigned monitor in [SHOW WAREHOUSES](https://docs.snowflake.com/en/sql-reference/sql/show-warehouses);
[monitor inspection](https://docs.snowflake.com/en/user-guide/resource-monitors)
requires suitable privileges. No monitor/grant change was attempted.

Pause the next source-read/export batch pending a targeted administrative
confirmation; do not run the broader cost-snapshot script or grant the reader
extra privileges to work around visibility. Suggested owner/CoCo prompt:

> Read-only check only, using your existing authorized administrative context.
> Run SHOW WAREHOUSES LIKE 'CIQ_WH' and SHOW RESOURCE MONITORS LIKE 'CIQ_RM'.
> Maximum two metadata statements, two minutes. Return query IDs and confirm
> CIQ_WH's explicit monitor, current suspended state and CIQ_RM assignment/quota/
> triggers. If either is invisible or absent, report that; do not repair it.
> No source data reads, grants, changes, AI, warehouse resume or app startup.

This is a requested new bounded check, not an assertion that it has run or an
authorization to change account objects. If a change is needed, review its exact
scope separately. Also ask the owner to confirm exact trial expiry/balance in
the account UI; $195/two days remains owner-reported, not independently verified.

## Owner-supplied CoCo follow-up

The owner supplied the requested two-statement result: CIQ_WH remains suspended,
`resource_monitor=null`, X-Small/single-cluster/60-second auto-suspend, query
acceleration enabled with maximum scale factor 8. CIQ_RM returned no rows.
CoCo reports completion under two minutes and no changes, but no query IDs.
Its execution role was not supplied; the report itself recommends checking as
ACCOUNTADMIN. This repeats the attachment observation but does not settle monitor
existence/visibility. Do not record this as an ACCOUNTADMIN verification.

Next requested check is explicitly administrative, still read-only: use
ACCOUNTADMIN with secondary roles NONE; return actual current role/secondary
roles, SHOW WAREHOUSES LIKE 'CIQ_WH' and SHOW RESOURCE MONITORS LIKE 'CIQ_RM'.
Maximum three inspection statements plus the two session role-setting commands,
two minutes; no data reads, changes, AI or warehouse resume. Return query IDs if
the tool exposes them; never invent them. If the administrative role cannot be
used, stop and report that rather than creating grants. This follow-up requires
the owner/CoCo administrative context; it has not run here. Actual remediation
needs a separately approved exact package. Source-read/export batch stays paused.

## Statement ledger and limitations

### Administrative discrepancy resolved — owner-supplied follow-up

The owner subsequently supplied explicit ACCOUNTADMIN/NONE results: CIQ_RM
**exists and is attached to CIQ_WH**. The previous reader output was incomplete
visibility, not evidence of a missing attachment. No repair is needed; the
source-read pause for this discrepancy is lifted. This administrative result
is attributed to CoCo, not independently rerun locally, and has no supplied
query IDs. CIQ_WH was suspended with no running clusters/queued work.

CIQ_RM reports a 10-credit monthly warehouse quota, 2.27 used and 7.73 remaining;
notification triggers at 50/75%, suspend at 90%, no immediate-suspend trigger
and no named notify users. The monthly period began 29 September. Notification
delivery is not established by these results. No monitor or recipient change is
authorized here. Warehouse credits are not the $195 trial balance; this monitor
does not establish an all-service dollar cap. Exact trial expiry remains open.

Executed in this order:

1. SELECT current user/role/secondary roles/account/region.
2. SHOW WAREHOUSES LIKE 'CIQ_WH'.
3. SHOW COMPUTE POOLS.
4. SHOW CORTEX SEARCH SERVICES IN SCHEMA CASHLESSIQ.DOCS.
5. SHOW GRANTS TO ROLE CIQ_PRODUCT_READER.
6. SHOW TABLES IN SCHEMA CASHLESSIQ.CORE.
7. SHOW TABLES IN SCHEMA CASHLESSIQ.DOCS.
8. SHOW TABLES IN SCHEMA CASHLESSIQ.APP.

The CLI used JSON output; query IDs and server execution timestamps were not
included in the captured result. Do not claim complete query-ID/timing evidence.
The interactive invocation completed within the planned five-minute window;
no precise server duration or incremental USD cost was measured. The last
warehouse observation was statement 2, not a separate end-state check. These
statements did not request warehouse compute or resume a project resource; no
resource was explicitly suspended or changed afterward. A suspended warehouse
is not proof of a zero-cost account. No billing history query was run.

Remaining work: resolve the monitor discrepancy, preserve permitted definitions
and bounded synthetic validation/recovery evidence, verify offline recovery,
and continue the P2 isolation/evidence/live-UI gates. No paid upgrade, real
credential provisioning, deployment, P3 or push. The source export batch has
**not** run; no backup or source parity claim follows from table visibility.
