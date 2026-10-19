# Product P2 — read-only case workspace

Status: In progress — synthetic-only alpha  
Last updated: 19 October 2026

## Latest checkpoint — authenticated inspection

### CoCo source-access review received — 19 October

Rushikesh supplied the metadata-only security report and policy-reference
follow-up. All 13 direct reader grants match; PUBLIC and human-admin identity
risks remain. None of the eight source tables has a row-access or projection
policy. Only PREAUTH_FACTS.CLINICAL_NOTE has MASK_CLINICAL_TEXT, which intentionally
permits medical/admin role hierarchies. An active admin secondary hierarchy can
therefore authorise clear text; a primary reader role alone is not sufficient.
The fixed metadata query does not select this column. No clinical unmasking test
was performed here. See [findings and qualifications](source-access-findings.md)
for OAuth/default-role caveats and the proposed remediation sequence.

The review gate is documented, not the remediation/production-isolation gate.
Default-user changes, MFA, PUBLIC impact review and service provisioning require
their respective approvals/workflows. No Snowflake call or change accompanied
this documentation increment; source HTTP remains disabled by default. P2 stays
open, with financial/evidence display and authenticated UI parity outstanding.

### Live v2 repository check — 19 October

The actual SourceCaseRepository now passes a bounded live check through both
Snowflake gateways, not just independently tested diagnostic inputs. One
CIQ_PRODUCT_READER connection had secondary roles disabled and checked the
primary role before reads. Two tenant queues and three details used five
metadata SELECTs and twelve inspection SELECTs. Expected queue ownership was
exactly TPA001/GOL001 and TPA003/GOL024,GOL027.

All seven metadata comparisons and every independent member/history field
(including conditions) matched for all three cases. GOL001's saved recommendation
freshly validated against scoped citations with an empty record-ID allowlist;
outcome/claimed/payable matched the frozen baseline. GOL024/GOL027 were MISSING
with no invented recommendation fields. Each case returned 35 scoped clause
references. Only IDs, states, counts and difference-field lists were printed;
no raw clinical payload or credentials were logged. Comparison fixtures were
not used as runtime fallback. The process exited successfully.

This establishes preliminary repository summary/reference parity under the
approved missing-state revision. It does not establish full financial trace,
narrative grounding, authenticated API/browser parity, production identity/RLS
or resolved PUBLIC privileges. No source writes, AI, grants, persistent seeds
or deployment ran; P2 stays open and P3 has not started.
Final reader-role SHOW confirmed CIQ_WH SUSPENDED with zero started clusters,
running or queued queries; X-Small/60-second auto-suspend were unchanged. No
incremental dollar amount or current trial balance is claimed.

### V2 source read adapter — 19 October

The preliminary `SourceCaseRepository` now composes the bounded metadata and
inspection gateways with the installed domain validators. It rechecks TPA,
request/product/policy/member references against the inspected synthetic scope,
enforces coverage/uniqueness, validates evidence references and saved decisions,
and never falls back to demo snapshots. Unknown/unowned requests do no source
I/O. Record citations fail closed until independently governed record lookup
exists; an ID copied from a citation is not considered verification.

New authenticated `/v2/cases` routes expose a metadata-only queue and a separate
detail summary with validated member/claim history, role-restricted conditions,
SAVED/MISSING recommendation and product-clause register. No clinical prose,
raw JSON or calculation text is returned in this slice. Authenticated source
reads are 503 by default; an injected local/test repository is required and
staging/production injection is rejected. No operator connection is constructed
at startup. This is not a production service identity or full UI/view parity.

Verification: 145 root and 145 API/PostgreSQL tests pass, including 44 new source
repository/HTTP tests. Root/API lint, API formatting and whitespace checks pass.
OpenAPI and browser types were regenerated; every pre-existing path/component
schema remains unchanged and web typecheck passes. No frozen fixtures/schema or
policy rules changed. Browser/UI and remote CI were not rerun for this backend
increment. No Snowflake calls, source writes, AI or public/private deployment.
The updated API Docker image builds and its non-root OpenAPI/import smoke passes
with networking disabled. Local PostgreSQL was stopped after the isolated test
suite; its volume was retained.

Remaining P2 work includes a reviewed live adapter check, safe calculation-trace
and citation presentation, source identity hardening and separate-tenant UI
integration. The two integration exits remain open; P3 is not started.

### Shared-domain packaging boundary — 19 October

The API now declares a locked local dependency on `cashlessiq-domain`, whose
only direct runtime dependency is jsonschema. An allowlisted wheel bridge builds
the four canonical schema/source-observation modules under `cashlessiq_domain`;
no source implementation is duplicated, no `sys.path` edits are used, and the
rules/procedure/legacy application tree is not moved. The API uses the distinct
namespace; do not exchange class instances across old/new namespaces. See the
[package boundary](../../packages/domain/README.md) for build limits.

The wheel check verifies canonical byte identity, the frozen decision schema,
isolated imports and missing/invalid-state behavior without Snowflake, Streamlit,
FastAPI or the legacy cashlessiq package installed. It is now a CI step. Explicit
cache keys cover canonical source files outside the package directory. The API
Dockerfile preserves the dependency layout and copies only those required files.

Verification: 145 root tests, 101 full API/PostgreSQL tests, root/API lint and API
format checks pass. The API image builds and runs its non-root import/OpenAPI/
missing-state smoke with networking disabled. Product OpenAPI regenerates with
no drift; frozen schema, snapshots and golden results are unchanged. PostgreSQL
was started locally for isolated schemas and stopped afterward, volume retained.
No source reads, grants, AI, deployment, reviewer writes or policy changes ran.
Browser/UI and remote CI have not been rerun for this packaging increment.

Next: versioned source-read contract and repository integration tests, preserving
explicit missing recommendations and separate owner scopes. P2 exits remain
open; no P3 work is started.

### Approved follow-up: explicit missing state

Rushikesh approved “Approve explicit missing-recommendation state” on 19 October.
P2's source parity gate now requires faithfully preserving absent recommendations
for GOL024/GOL027, not copying the frozen QUERY/REFER outcomes into live views.
The original all-three-saved-decision comparison is not claimed as passed.

`cashlessiq.source_recommendation` now provides immutable SAVED/MISSING
observations after a successful owner-scoped inspection. Missing contains only
request/TPA/product context and the supplied estimate. A present row still goes
through the canonical saved-decision and scoped-citation validator. Invalid,
ambiguous or failed reads do not become missing, and no money is computed.
Fifteen offline tests cover absence, saved approval/QUERY/REFER, unresolved
citations, malformed rows and invalid context. Existing v1 API/UI and the frozen
decision schema remain unchanged; versioned source-read integration is next.
No new Snowflake calls, grants, backfill, policy activation or reviewer writes.
Verification: 139 root tests and root lint pass; git whitespace checks pass.
API/browser suites were not rerun for this domain-only increment.

The subsequent unbuffered Python operator check authenticated successfully as
CIQ_PRODUCT_READER. One connection, secondary roles disabled, two bounded
metadata reads and twelve inspection SELECTs covered exactly the three allowed
cases. No AI, extraction, grants, source writes or Streamlit startup occurred.

| Case | Verified owner | Independent history comparison | Latest saved decision | Product clause references |
| --- | --- | --- | --- | --- |
| GOL001 | TPA001 | Matches all expected fields | Present; fresh canonical validation and clause resolution pass; outcome/claimed/payable match snapshot | 35 |
| GOL024 | TPA003 | Matches all expected fields | **Missing** | 35 |
| GOL027 | TPA003 | Matches all expected fields | **Missing** | 35 |

GOL001 validated without any record-ID allowlist: no record citation was
invented. The other two cases cannot pass saved-decision parity because no
saved rows exist. Reference counts do not prove narrative grounding or clause
text retrieval. No source data was created or golden expectations changed to
hide this gap. Earlier authentication-failure/grant-pending notes below describe
historical checkpoints, superseded by this inspection.

Post-session SHOW confirmed CIQ_WH SUSPENDED, zero started clusters and zero
running/queued queries; X-Small/60-second auto-suspend remained unchanged.
Exact incremental dollars and the remaining trial balance were not measured.

P2 remains open. The follow-up approval above resolves the missing-source scope
choice in favor of an explicit missing state, not source backfill. Do not run a fresh agent,
create reviewer decisions or silently reuse snapshots as live data. The governed
repository adapter, service-identity review and API/UI parity remain outstanding.
P3 has not started. See the [current progress checklist](progress.md).

Checkpoint tests: 124 root regressions and root lint pass; 39 targeted
metadata/inspection boundary tests pass. The full API rerun had 54 passes and
44 database-setup errors because Docker was unavailable. After starting Docker,
the active environment had no cached stack images; the fresh image-download
attempt was cancelled before containers started. Full API/PostgreSQL/browser
verification remains pending; no database volume was deleted.

## Authority and limits

Rushikesh approved the P1 research-gate deferral on 19 October. Five target-user
interviews remain outstanding; defaults are hypotheses, not validated findings.
This exception permits synthetic-only P2 work, not real patient data, production
deployment, policy activation, or reviewer writes.

## First slice: local synthetic case reads

- [x] Authenticated, tenant-scoped queue and detail contracts.
- [x] Repository boundary with deterministic synthetic snapshots and provenance.
- [x] Queue filtering, pagination, empty and failure states implemented.
- [x] Case, synthetic member context, calculation trace, and evidence references.
- [x] Clinical narrative restricted by role; no patient identifiers.
- [x] No reviewer mutation or upload endpoints/actions.
- [x] API isolation/revocation tests, browser walkthroughs, mobile checks.
- [x] Existing golden results and generated contracts remain consistent locally.
- [x] Remote CI passes for the new case slice after push.

## Local verification

Remote confirmation: [CI run 39198298419](https://github.com/hulagerushikesh/cashlessiq/actions/runs/39198298419)
passed on 19 October for `d3623da`, including regression, snapshot/contract drift,
lint, type/build, Docker, API/PostgreSQL, and browser checks.

On 19 October: 62 existing/contract regression tests, 36 API/PostgreSQL tests,
and 12 browser tests passed (110 total). Ruff, web lint, TypeScript, Next.js
production build, and Docker startup passed. Desktop and 390px mobile layouts
were visually inspected. The browser suite covers the three roles, all three
case journeys, filter/empty state, missing case, anonymous access, and overflow.

Data consists of GOL001, GOL024, and GOL027 copied from the frozen baseline
`6406d74`. Snapshot regeneration is checked for drift in CI. Financial traces
are copied, never recomputed by the web or API. Query/referral payable is null,
not zero. Policy evidence contains registered source references, not retrieved
clause text. Live member history, SLA clocks, and assignment are not simulated.

The API strips diagnosis, procedure, and submitted clinical note for processors
and auditors. Financial line labels and rule explanations remain visible; this
is not a complete clinical-data masking policy for real data. Synthetic reads
are disabled outside local/test environments. No data ingestion path exists.

## Later P2 integration — not required for first local slice

19 October increment: an optional, bounded source gateway and dedicated reader
role SQL are prepared with nine offline tests. Unknown tenants make no network
call; queries bind the server-owned TPA mapping and allowlist three golden IDs.
The existing auditor role is not reused because it inherits runtime writes.
Local authentication did not complete during this increment, so no live parity
or cost measurement is claimed. The gateway is not wired to HTTP/UI yet. See
[operator steps](../architecture/snowflake-read-integration.md).

Increment verification: 62 root tests and 45 API/PostgreSQL/gateway tests passed;
API Ruff and git whitespace checks passed. OAuth connection test timed out before
authentication; no source SQL, grants, warehouse activation or AI call ran.

Subsequent authenticated inspection on 19 October: bounded source metadata
parity passed for all three cases under CIQ_ADMIN. Live ownership is TPA001 for
GOL001 and TPA003 for GOL024/GOL027; the offline demo grouping must not become a
cross-TPA live tenant mapping. Dedicated CIQ_PRODUCT_READER does not yet exist;
its CoCo grant review, restricted-role verification, explicit tenant mapping,
and remaining member/decision/evidence parity are still outstanding. No grants
or source-data mutations were applied. This does not complete P2.

After CoCo applied the reader grants, direct grants and single grantee were
independently confirmed. Bounded Python gateway reads returned GOL001 for
TPA001 and GOL024/GOL027 for TPA003. Secondary roles are now explicitly disabled
before reads; tests fail closed if that command fails. 62 root and 46 API tests
pass. PUBLIC still grants Cortex/AI access, so the identity is not effectively
AI-disabled despite having no direct AI grants. No account-wide revocations
were made. This remains an operator spike, not tenant-RLS or full P2 completion.

- [ ] Governed Snowflake read adapter behind the repository interface.
- [ ] Approved economical integration verification and view parity.

Next local increment: immutable operator source scopes now require separate
UUID bindings for TPA001 and TPA003, reject the mixed offline demo tenant, and
bind/validate request IDs against their inspected owner rather than a global
allowlist. Invalid mappings fail before any connection; unknown tenants do no
I/O. No tenant/membership provisioning or HTTP integration was introduced.
62 root and 58 API/PostgreSQL/gateway tests pass (120 total); Ruff passes.
No Snowflake calls, grant changes, policy activation, or reviewer writes ran.
These guards were tested offline; the new query bindings have not been live
re-verified. Member/decision/evidence parity and service-identity hardening
remain outstanding. The two integration exit boxes remain unchecked.

Full M2/P2 is not complete until the integration criteria are met. The first
slice must work without Snowflake calls or AI spend. Do not start M3/P3 reviewer
commands as part of this work.

## Separate source-identity preparation — 19 October

- [x] Fixed, disjoint synthetic tenant mappings for TPA001 and TPA003.
- [x] Optional local-only seed with three distinct role users per source tenant.
- [x] Real PostgreSQL tests for identity/membership isolation, immediate revocation,
  idempotency, preserved database roles, and collision rollback.
- [x] Default demo startup and existing contracts remain unchanged; no snapshot
  fallback or automatic source-profile bootstrap login.

The new tenants were created only in isolated test schemas. Opt-in setup for
the persistent local stack is documented, not executed. No Snowflake calls or
credits were needed. These identity fixtures do not complete the two integration
exit criteria above, grant customer access, or permit P3 reviewer writes.

Verification: 62 root and 71 API/PostgreSQL tests passed (133 total). API Ruff
check/format and `uv run make lint` passed, as did git whitespace checks.
Plain `make lint` selected a system Python without Ruff; running it through
the project's uv environment resolves that tooling issue. No web contracts or
UI changed; browser/build checks were not rerun for this identity-only increment.

## Parity-input preparation — 19 October

### Approved inspection grants — 19 October

Rushikesh approved the four net-new inspection grants after CoCo's review.
CoCo applied them, and an independent local `SHOW GRANTS` check confirmed 13
direct privileges: five USAGE grants (warehouse, database, three schemas) and
eight table SELECT grants, all without grant option. The only grantee remains
user RUSHIKESH2001. No role-membership or PUBLIC changes were made.
POLICY_CLAUSE SELECT was already present and was not a net-new grant.

Preflight confirmed CIQ_WH X-Small, auto-suspend 60 seconds, SUSPENDED with
zero running/queued queries, and both container pools SUSPENDED with zero
active nodes. These SHOW checks do not establish source-data parity or a live
credit balance. PUBLIC inheritance remains unresolved; this is an operator
synthetic-data identity, not a production service identity. P2 integration
exits remain open. No AI calls, reviewer writes or app deployment were made.

The subsequent Python operator probe did not complete its first connection and
was stopped after approximately 90 seconds with no source results. CLI auth
success does not establish Python-connector authentication. No live history,
saved-decision or evidence parity is claimed. Root regression tests (124) and
lint passed; API/UI suites were not rerun for this documentation-only change.

- [x] Operator-only bounded member/claim, condition, latest-decision and
  product-clause inspection queries, with request/TPA ownership guards.
- [x] Proposed minimum extra reader grants saved separately for CoCo review;
  no grants executed and no automatic CLI/API/startup integration.
- [ ] Live inspection and canonical saved-decision/citation validation.
- [x] Explicit offline member-history expectations and QUERY/REFER null-payable adapter.

19 October follow-up: the offline null-payable adapter is implemented in the
domain package, reusing canonical decision validation and checking stored-row
consistency and scoped citation registries. Thirty no-network tests cover
valid saved calculations, uncomputed QUERY/REFER, invalid arithmetic, missing
and cross-owner/product citations, duplicate JSON keys and ambiguous partial
calculations. All 92 root tests and root lint pass. Member-history expectations
remain pending, so the combined checkbox above stays open. This does not claim
live saved-decision or citation parity and is not registered in the API/CLI.
API/UI and contracts are unchanged; their suites were not rerun in this step.
No Snowflake usage or grant changes; P2 remains open and P3 is not started.

Subsequent history increment: immutable domain observations now validate member,
policy/TPA/request identity, claim aggregates, dates and bounded conditions.
Explicit seed-42 history constants for all three cases are checked against
in-memory core generation independently of UI snapshots; no generator output
files are changed. All 124 root tests and lint pass (32 new history tests).
This closes only the offline preparation checkbox, not live history or decision
parity. CoCo review of SQL 65 and its minimum-grant approval are next, before a
bounded live comparison. No Snowflake spend, grants, API/UI changes, deployments
or reviewer writes. P2's two integration exits remain unchecked.

The diagnostic reader does not establish parity or return product read models.
No Snowflake usage, AI calls or reviewer writes were needed for this preparation.
The two P2 integration exit boxes remain unchecked.

Verification: 62 root and 98 API/PostgreSQL tests pass (160 total), including
27 new no-network inspection tests. Root/API Ruff and API format checks pass;
git whitespace checks pass. No web/API contracts changed, so browser/build
checks were not rerun. The proposed SQL remains unexecuted and must be reviewed
against live object definitions by CoCo before use.
