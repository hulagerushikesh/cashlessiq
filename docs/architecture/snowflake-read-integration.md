# P2 bounded Snowflake source gateway

Status: bounded live source reads verified; not enabled in the API. 19 October 2026.

## Latest inspection result — 19 October

The approved 13 direct reader privileges have now been independently verified,
and the bounded Python inspection authenticated successfully. History validation
matches the independent seed-42 constants for all three cases. GOL001's saved
decision passes fresh canonical validation, clause-reference resolution and
outcome/amount comparison. GOL024 and GOL027 have **no saved decisions**; each
case has 35 scoped product-clause references, which alone are not decision or
narrative-evidence parity. No fixture fallback or source backfill was performed.

The read session closed, and a final SHOW confirmed CIQ_WH SUSPENDED with zero
running/queued queries and zero started clusters. No AI or Streamlit was started.
Remaining balance is not inferred from this check. PUBLIC inheritance and the
operator-only identity limitations below still apply.

These findings supersede the historical pending-auth/grant notes below, not the
remaining integration gates. Resolve the missing-recommendation contract before
building the adapter; do not fabricate source recommendations or begin P3.
See [current product progress](../product/progress.md).

## Offline member-history expectations — 19 October

`cashlessiq.source_history` now validates and copies scoped policy/member
references, sum insured/bonus, policy status, claim count, total paid, latest
admission and conditions into immutable comparison observations. It rejects
missing/mismatched identifiers, malformed or non-integer amounts/counts,
inconsistent empty-claim aggregates, timestamps in date fields, non-boolean
declarations, duplicate conditions and more than 20 conditions. Zero prior
claims and an empty condition list are legitimate, not fabricated coverage.
It does not calculate remaining cover, waiting periods, PED eligibility or
decision amounts. Conditions remain restricted clinical history with no HTTP
exposure; a separate role-based disclosure policy is still required.

Explicit constants in `tests/fixtures/migration/member_history.json` record
seed-42 core observations, independently of UI/rule-result snapshots:

| Request | Policy/member | Prior claims | Paid INR | Latest admission | Conditions |
| --- | --- | --- | --- | --- | --- |
| GOL001 | POL0001 / MEM0001 | 1 | 86,400 | 2025-11-14 | 0 |
| GOL024 | POL0024 / MEM0024 | 0 | 0 | none | 4, including declared E11.6 |
| GOL027 | POL0027 / MEM0027 | 0 | 0 | none | 2 |

These are synthetic source expectations, not live parity evidence or patient
facts. A regression test independently runs core generation in memory and
compares these constants; it writes no CSV/PDF and reads no local generated
output. No demographic facts or output files are committed. The generator is
unchanged. This increment adds 32 tests; all 124 root tests and root lint pass.
API/UI/contracts are unchanged and their suites were not rerun.

The offline history and null-payable preparation is complete. Next is the CoCo
review of proposed SQL 65, followed by separately approved minimum grants and
a bounded live comparison using these validators. Do not claim P2 integration
success from offline tests, nor import root-domain code into the API by changing
`sys.path`. Live parity, shared-domain packaging, service identity and the
repository integration exit criteria remain open. No Snowflake calls, grants,
deployment, source writes or persistent local seed changes ran in this step.

## Offline saved-decision validation — 19 October

`cashlessiq.source_decision.observe_saved_decision` now reuses the existing
canonical JSON/arithmetic validator in the domain package, with no API,
Snowflake, or framework imports. It checks row/JSON request and outcome,
stored payable consistency, integer rupees, and each line citation against a
request/TPA/product-scoped clause registry or independently verified record IDs.
The stored `SCHEMA_VALID` flag is not trusted. Duplicate JSON keys, missing
evidence coverage, foreign references, empty approvals and ambiguous partial
QUERY/REFER calculations fail closed with a generic error message.

For an uncomputed QUERY/REFER (empty lines and zero saved totals), the comparison
observation copies the separately supplied estimate and exposes payable as null.
For approvals it copies saved calculation totals. It never recomputes money or
substitutes fixtures. Tests explicitly cover the 90,000 QUERY and 80,000 REFER
estimate semantics, not live decisions. The returned immutable observation is
not a case model or parity verdict. It does not invent calculation checks,
clause text, clinical history or SLA state.

This is an offline operator building block only, with 30 new tests (92 root
tests total). It is deliberately not imported into the separately packaged API;
future HTTP integration needs an explicit shared-domain dependency boundary.
The supplied citation registries are assertions, not ownership discovery: the
live operator must independently verify them. QUERY/REFER JSON has no line
citations, so this does not prove its narrative is supported by policy evidence.
Typed member/history validation, independent history expectations, live parity,
CoCo grant review and service-identity hardening remain pending. No Snowflake
queries, grants, source writes, deployment or persistent seeds ran in this step.

## Pending parity-input inspection — 19 October

`source_inspection.py` now prepares four fixed, parameterized diagnostic SELECTs
for one allowlisted request and its verified TPA per call. It uses the same
immutable ownership scopes, disables secondary roles first, and closes the
connection on success/failure. Unknown/cross-owner cases perform no I/O.

| Input | Bound | Purpose and limitation |
| --- | --- | --- |
| Policy/member reference + claims aggregate | 1 row | Same claim count/paid total/latest admission as legacy member summary; no demographics |
| Declared conditions | 20 rows | Restricted clinical history; no current offline member-history baseline exists |
| Latest saved decision | 1 row | Deterministic creation-time/ID ordering; empty stays empty, stored validation flag is not trusted as fresh validation |
| Product clause references | 100 rows | Heading/page/source URL registry for that policy product; not retrieved text or proof every citation resolves |

Multi-row reads use one overflow sentinel; overflow, duplicate keys, missing
policy context, ambiguous columns, and ownership mismatches fail closed. Empty
conditions can be legitimate. Empty decision/evidence must be reported as
missing coverage, never substituted with frozen fixtures. Returned rows are
diagnostic inputs, **not validated API models or a parity pass**. Conditions and
decision JSON are restricted clinical data: do not log/export them casually.
There is deliberately no CLI or HTTP registration for this inspector yet.

No Snowflake call, grant application, or persistent local provisioning ran for
this increment. Existing reader grants cannot execute all these queries.
`sql/65_product_inspection_reader.sql` proposes only APP schema USAGE and SELECT
on CLAIM, MEMBER_CONDITION, DECISION and POLICY_CLAUSE. It is excluded from
automatic setup and requires CoCo review; full MEMBER demographics/stages,
review actions, AI, writes, future-table grants and PUBLIC revocations are not
requested. Table-level access remains an operator synthetic spike, not RLS.

Next operator step (not executed): give CoCo the actual contents of that SQL
file, not just its local path, and this prompt:

> Review the attached SQL and current live object definitions for this P2
> synthetic-only inspection. Do not execute grants yet. Confirm the existing
> CIQ_PRODUCT_READER role and its single operator RUSHIKESH2001; inspect effective
> PUBLIC/user/secondary-role privileges. Confirm exactly which of the five
> proposed grants are needed by the four SELECTs in source_inspection.py. No
> AI, extraction, policy activation, reviewer writes, Streamlit startup, or
> account-wide privilege changes. Report the review for approval first.

After review/application, a separately bounded operator run must validate live
rows, saved decision JSON with the existing canonical validator, request/product
ownership of every citation, and snapshot differences. Legacy QUERY/REFER rows
store numeric zero while the product contract uses null for an uncomputed
payable; this needs an explicit adapter test, not a blind JSON copy. Member
history needs its own expected observations because the frozen UI snapshots
do not include history. Only then build the repository adapter; P2 remains open.

## Current increment — separate application identity fixtures

The optional local seed now defines distinct application tenant UUIDs ending
`0101` (TPA001) and `0103` (TPA003), each with three separate synthetic role
users and exactly one membership per user. `source_alpha_scopes()` provides an
explicit immutable mapping for these fixtures, not a default HTTP connection.
Normal startup, old demo identities, fixture ownership, and contracts are
unchanged. The seed is opt-in, local-identity-only, transactional and idempotent;
it does not restore revoked access or override database-owned roles.

Only isolated PostgreSQL test schemas were provisioned during this increment;
the persistent local stack was not seeded with these extra identities. See
[local opt-in instructions](local-development.md#optional-p2-source-identity-fixtures).
Tests verify all six identities, cross-TPA/demo rejection, no snapshot fallback,
revocation, collision rollback, and absence of automatic bootstrap access.
No Snowflake grants, queries, services, or policy rules were changed.

Remaining P2 work: member/decision/evidence parity and a reviewed service
identity/read adapter before source-case UI/login is enabled. Application
mapping is not Snowflake RLS and does not resolve PUBLIC privileges.

## Current increment — source ownership guards

`SyntheticSourceScopes` now validates an immutable, explicit operator binding
before the gateway can connect. It accepts only the inspected synthetic owners:
TPA001 -> GOL001 and TPA003 -> GOL024/GOL027. Each TPA must have a distinct UUID;
duplicate TPA bindings, unknown TPAs, malformed tenant keys, and the existing
mixed-ownership offline demo tenant are rejected. No default binding exists.
The query binds only the selected owner's IDs, with unused fixed SQL slots
bound to NULL. Returned IDs are checked against that owner-specific allowlist,
even if the returned TPA field looks correct. Unknown tenants perform no I/O.

This is configuration validation, NOT tenant provisioning, membership approval,
Snowflake row-access policy, or production authorization. No tenant/membership
records were created, no fixture ownership was rewritten, and HTTP remains
offline. The inspected ownership manifest is limited to these three synthetic
requests; do not extend it to customer data or treat it as live ownership discovery.

Verification: 62 root tests and 58 API/PostgreSQL/gateway tests passed (120 total),
with Ruff clean. This increment made no Snowflake calls or grant changes and
consumed no Snowflake compute/AI credits. Earlier live reads below preceded
these new guards; no live re-verification of this version is claimed.

Next within P2: verify member, decision and evidence reads with reviewed minimum
grants before HTTP integration. The later identity-fixture increment above
defines separate synthetic application mappings. Keep the PUBLIC-privilege caveat open; the
operator credential is not a production service identity. Do not return frozen
offline financial traces as if they were a live source decision.

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

## Earlier live verification procedure (completed for metadata only)

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

The CLI now rejects the actual seeded offline demo UUID
`00000000-0000-4000-8000-000000000001`. The example operator UUID above does not
create an application tenant or membership and must not be presented as one.

The connector is an optional API extra, not a default runtime dependency. Tests
use fake connections, assert bound parameters/row caps, prevent cross-tenant
results, reject duplicates/unapproved IDs, and verify connection cleanup.
Connections use an explicit role, warehouse, query tag, 30-second statement
timeout, and 15-second queue timeout. No ACCOUNTADMIN fallback exists.

Connector behavior follows Snowflake's official
[connection configuration](https://docs.snowflake.com/en/developer-guide/python-connector/python-connector-connect)
and [parameter binding](https://docs.snowflake.com/en/developer-guide/python-connector/python-connector-example)
documentation. No credentials belong in this document or committed env files.
