# Product P2 — read-only case workspace

Status: In progress — synthetic-only alpha  
Last updated: 19 October 2026

## Latest checkpoint — authenticated inspection

### Loopback mutually authenticated worker transport — latest

Both broker -> read relay and read relay -> validator now pass real mTLS tests,
using temporary test PKI and fake source inputs. Certificate chain/validity/EKU,
server IP SAN, leaf pin and URI identity are checked; transport-derived peer
identity cannot be replaced by a header. Fixed scoped operations and assertion/
membership/replay checks remain in force. No ordinary source/HTTP startup change.

278 API/PostgreSQL and 145 root tests pass; lint/format/whitespace checks pass.
23 transport tests cover positive/negative handshakes, protocol rejection,
identity spoofing, replay and safe errors. No Snowflake/AI, real credentials,
grants, provisioning, push, deployment or P3. Temporary listeners/certificates
are cleaned up. Separate worker packaging, remote membership, secret/CA/replay
lifecycle and live Snowflake isolation remain open; see
[transport limits](../architecture/p2-worker-transport.md).

### Offline delegated read/validation path — latest checkpoint

The authenticated broker can select a fixed read relay and tenant validator
using separate broker-signed audience/operation-bound capabilities. Scope and
parent nonce binding prevent child swaps/widening. Each hop rechecks membership,
expiry and replay; validators expose only scoped summaries. The peer identity
used in tests is explicitly fake; no network/mTLS or credential isolation is
claimed. This is not a complete queue/detail worker or full financial-trace view.

255 API/PostgreSQL tests and 145 root tests pass, with root/API lint, API formatting
and whitespace checks green. All source/HTTP startup and v2 contracts are unchanged.
No Snowflake/AI use, grants, credentials persisted, provisioning, push, deployment
or P3. See the current [five P2 completion gates](progress.md#p2-remaining-work--in-order)
and [worker checklist](p2-worker-boundary-checklist.md). Earlier counts below are
historical checkpoints, not current totals.

### Approved design: first offline worker-boundary slice — 19 October

Rushikesh approved the local validation design, including two additional tenant
validators. Implemented explicit RS256 internal assertions, strict fixed scope,
30-second expiry, bounded concurrent replay ledger, fresh injected membership
checks before reads/delivery and a summary-only canonical validator handler.
34 new fake-source/no-network tests pass; all 179 API/PostgreSQL tests pass.
All 145 root regression tests and root/API Ruff checks pass; API format and git
whitespace checks pass. See [remaining boundary work](p2-worker-boundary-checklist.md):
peer transport/delegation, restart-safe replay, actual membership/routing adapters,
worker packaging/secret custody and coherent source SQL are not complete.
No public routes/contracts, Snowflake/AI calls, secrets, provisioning, live source
activation, website deployment, push or P3. Existing local services were unchanged.

### Local validation boundary designed — 19 October

Prepared the [worker/credential design](../architecture/p2-validation-boundary.md):
four tenant/disclosure readers and two additional tenant validators, trusted
broker, asymmetric internal assertions/private peer authentication, isolated
secret custody, coherent-input validation prerequisite, failure/revocation and
rollback gates. This is proposed design, not implemented authentication or
provisioned identities. Current raw-inspection API composition is explicitly
not the isolated runtime. Exact design approval precedes offline implementation
and SQL review. Documentation checks only; no runtime tests, Snowflake/AI calls,
worker startup, secrets, push, deployment or P3.

### Approved metadata preflight report reconciled — 19 October

Owner approved the bounded read-only execution and supplied CoCo's report:
21 attempted statements including one failure; no mutations/data reads/AI
reported. Compared all eight column inventories with repository DDL and recorded
the DECISION nullability-count discrepancy, missing query IDs/time evidence,
policy-scope uncertainty and inherited-role inspection gaps in the
[reconciliation](p2-isolation-preflight-results.md). No independent Snowflake
rerun or full isolation/MFA acceptance. Next is validation-host/credential-boundary
design before the exact implementation package. Documentation checks only;
runtime tests not rerun, no push/deploy or P3.

### Architecture approved; metadata preflight prepared — 19 October

Rushikesh explicitly approved the [isolation architecture](p2-isolation-proposal.md).
Prepared the [24-statement/five-minute metadata preflight](p2-isolation-preflight.md)
and a short CoCo prompt. Execution is not approved or performed by this checkpoint.
Hosting/credential custody, exact implementation, provisioning and functional
acceptance remain separate gates. No Snowflake/AI calls, runtime changes, push or
deployment. Documentation whitespace checks only; runtime suites not rerun.

### Corrected isolation implementation proposal — 19 October

Received the owner's full CoCo follow-up (28 metadata statements reported, no
mutations). Reconciled it with repository contracts and official authentication/
row-access documentation. Proposed auth allowlists/client spelling, categorical
MFA claims, unsupported RAP limitation, PUBLIC safety claims and role counts
cannot be accepted as supplied. No report SQL was executed.

The owner approved preparation of a [review-only implementation proposal](p2-isolation-proposal.md).
It defines two tenant/disclosure classes, explicit ownership/column boundaries,
a still-unimplemented trusted canonical-validation boundary, separate human
authentication recovery planning and ordered approval/negative-test packets.
The proposal does not approve provisioning, new credentials, source activation,
PUBLIC revocation, account login changes or website deployment. P2 remains open.
Documentation-only change: no code/contract behaviour changed; no Snowflake/AI
calls, functional isolation tests or regression-suite rerun are claimed.

### Offline authenticated source API-to-UI integration — 19 October

The new `/source-cases` queue/detail routes consume the validated v2 client and
existing source presentation. They require local environment, local auth and
`CIQ_SOURCE_UI_MODE=contract_test`; normal startup is unchanged/404. They also
return 404 in production mode even if that flag is set. Every test page labels
its fake gateways and placeholder references. There is no live-source flag,
credential injection, automatic source login or reviewer write capability.

`make product-test-source-ui` builds Next, then temporarily starts a loopback
test API (8003) and built web (3003). The API uses real JWT verification and real
PostgreSQL membership resolution in a random isolated schema; only its source
gateways are fake, reused from the API unit tests. Persistent source identities
are not seeded. Test tokens use a public test-only key that is never installed
in the ordinary stack. The harness refuses non-loopback/non-test database URLs.

All 15 integration tests pass: both tenants/all roles, saved vs MISSING fidelity,
condition visibility, no raw decision prose in HTML, known foreign-ID 404s even
with spoofed headers, anonymous/expired sessions, filters/empty queue, mobile
layout, page links and a test-only injected HTTP 503 outage. The outage fixture
tests transport handling, not a live Snowflake outage. Desktop screenshot was
visually inspected. Source financial line/clinical prose and narrative-grounding
parity remain out of scope of the current summary contract, not completed.

Root regression 145 and API/PostgreSQL 145 pass. Client 41, typecheck, lint,
production build, isolated domain-wheel and contract-drift checks pass. CI now
includes the offline source integration target; remote CI has not run. Test
output directories are separated to avoid suite artifacts clobbering each other.
The first medical browser assertion needed a list-item locator; fixed and rerun.
All 23 normal-stack browser regressions pass, including the source-route
default-off checks. Local web container rebuilt and healthy; no test flag set.

Shutdown testing exposed Uvicorn's signal replay bypassing outer cleanup. The
test-only server restores signal handlers without replay so cleanup executes.
Three explicitly identified leftover test schemas were checked and removed;
their fixtures are reproducible. A subsequent full run leaves zero test schemas
and zero source-alpha tenants in the persistent sandbox. SIGKILL/power-loss
cleanup is not guaranteed; do not use broad schema-deletion commands.

No Snowflake usage, source writes/grants, public deployment or push. Website
deployment is explicitly excluded by the owner. P2 remains open for CoCo security
follow-up, approved service/tenant/clinical isolation, governed trace projection,
live browser parity and remote CI; P3 is not started.

### Offline web-to-v2 client boundary — 19 October

Added typed source queue/detail HTTP readers, checked against the exported
OpenAPI response schemas (Ajv/format validation, no coercion/removal/defaults).
They reject wrong tenant/request, unsafe integers, unexpected fields, clinical
visibility mismatches and inconsistent saved outcome/payable provenance.
401/403/detail-404 are distinct from unavailable; malformed/failed reads never
become MISSING, an empty queue or a demo fallback. Five-second abort signals,
redirect rejection and bounded query inputs are exercised without network I/O.
API canonical Python validation remains authoritative; client checks do not
establish database isolation or compute eligibility/money.

All 41 client tests pass with injected fetch only, no servers/credentials/browser
needed. Root typecheck and lint now include the client package/tests, and CI
runs `npm run test:client`. Web build passes. No API schema or Python domain/API
code changed, so those suites were not rerun. No source helper is imported by a
UI route, source identity seeded, source repository activated, Snowflake/AI
invoked or public deployment made. P2 integration/security gates remain open;
P3 is not started. See the integration architecture for caller requirements.
Local web Docker rebuild is healthy; all 22 browser regressions also pass with
the locked dependencies. Remote CI remains unverified until an approved push.

### Searchable clause register — 19 October

The v2 presentation now has an ID/title text filter, visible reference counts,
clear control and a distinct zero-match message that makes no coverage inference.
PDF links preserve each recorded page and announce new-tab navigation. The
register remains explicitly metadata, not retrieved quotations, evidence ranking
or proof of narrative grounding. No money or eligibility calculation was added.

The authenticated local preview's Evidence state supplies three fictional UI-*
references; its Example.org PDF links are labelled placeholders, not real policy
documents. No GOL fixture/source fact was changed. All 22 browser tests pass,
including three new filter/link/mobile tests; typecheck, lint, production build
and whitespace checks pass. Desktop screenshot visually inspected. Browser tests
inspect placeholder link attributes without requesting those documents.

The local web container was rebuilt and is healthy. Public hosting is unchanged.
No Snowflake reads/spend, AI, grants, source identities or live adapter activation.
Python/API suites were not rerun for this frontend-only change. P2 source UI/API
parity, full trace, effective-privilege and service-isolation gates remain open;
P3 has not started. Remote CI is not verified for this increment.

### V2 presentation groundwork — 19 October

Added a typed SourceCaseView consuming the generated v2 contract, without any
source fetch or money computation. SAVED, MISSING and unavailable presentation
remain distinct; saved QUERY/REFER show uncalculated payable rather than zero.
Member/history values are displayed as recorded, conditions follow visibility,
and the clause register is labelled reference metadata, not retrieved quotations.
No calculation trace, clinical narrative or grounding claim was added.

An authenticated `/source-preview` route is available only in local/local-auth
mode, linked from local workspace navigation. Its clearly labelled fictional
UI-* fixtures are not GOL/source records; all roles see the same nonclinical
examples. This is presentation testing, not an identity, source parity or
medical-disclosure test. The normal case queue and public demo are unchanged.
The route returns 404 in production-mode verification. A desktop screenshot
was visually inspected and mobile overflow is covered by browser tests.

Verification: all 19 browser tests pass (seven new preview tests plus the
existing 12 workspace/case tests), web typecheck/lint/production build and git
whitespace checks pass. The initial browser executable was absent; Chromium
was installed before rerunning. Accessible link names and a named failure alert
were corrected during testing. API/PostgreSQL and Python suites were not rerun
for this presentation-only increment; remote CI has not run on this commit.

No source adapter was injected, source tenants seeded, Snowflake/AI invoked,
grants changed or public deployment performed. Source UI/API parity and the
security/financial-trace gates remain open; P3 is not started.

### Passkey enrollment verified — 19 October

After Rushikesh enrolled a passkey, a local reader OAuth connection executed
three bounded metadata/session statements. SHOW MFA METHODS reports one PASSKEY;
DESCRIBE USER reports HAS_MFA true, reader default and empty secondary defaults.
No factor identifiers/secrets were logged. Connection closed; no source reads,
AI, writes or app startup. Enrollment passes. Second interactive passkey login
and effective authentication-policy enforcement are not established by OAuth.
Administrative enforcement/PUBLIC dependency review remains the next security
gate; no service provisioning or source HTTP/UI activation is authorised.

### Local hardening follow-up — 19 October

Two reader/NONE OAuth connections executed nine bounded metadata/session
statements; no case data, writes, AI or apps. Stored reader/empty defaults were
independently confirmed. SHOW MFA METHODS returned zero methods; HAS_MFA false.
Authentication-policy listing returned no rows under reader visibility, not proof
of absent enforcement. PUBLIC had 109 visible direct grant rows; the first
100-row cap was exceeded and a bounded retry completed within 1,001 rows.
CIQ_WH was SUSPENDED with zero started clusters/running/queued on inspection.
Both connections closed. No fresh balance or exact cost claim is made.

See [results, impact matrix and isolation proposal](source-hardening-results.md).
Owner MFA setup and administrative policy/dependency visibility remain open.
No service provisioning, PUBLIC revocation or source HTTP activation ran. P2
remains open, P3 not started; automatic fresh-login defaults remain unverified.

### Approved operator defaults and worksheet context — 19 October

CoCo reports DEFAULT_ROLE changed from ACCOUNTADMIN to CIQ_PRODUCT_READER and
DEFAULT_SECONDARY_ROLES from ALL to empty for RUSHIKESH2001, with all existing
grants unchanged. Rushikesh's first supplied worksheet still used ACCOUNTADMIN;
the later screenshot after both USE commands shows the reader and empty
secondary roles. Explicit worksheet context passes; unmodified fresh-login
defaults remain unverified. No clinical masking behaviour was tested with data.

See the [change record](operator-defaults-change.md) and next
[read-only hardening packet](source-hardening-followup.md). MFA enrollment and
enforcement, PUBLIC dependency impact and tenant-isolation implementation are
still open; no additional grants/policies/credentials or service provisioning
are authorised. No Snowflake calls or compute were used to prepare this packet.
P2 remains open; P3 has not started.

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

## Offline broker authorization checkpoint — 19 October

The approved worker design now has a local, unmounted summary broker and fresh
PostgreSQL membership adapter. Issuer-qualified application identity resolves to
an internal UUID; tenant/disclosure routing is fixed server configuration. Both
validator and broker check current membership before delivery; revoked users,
tenants, memberships, changed roles and expired requests fail closed. The
existing v2 HTTP/public UI/source configuration is unchanged.

Verification: 196 API tests, 145 root tests, root/API Ruff, API formatting and
whitespace checks pass. Seventeen new tests use disposable local PostgreSQL
schemas and fake source inputs. No Snowflake/AI, new credentials, provisioning,
push, website deployment or P3. Read-worker delegation, authenticated transport,
restart-safe replay and live isolation remain open; see the
[worker boundary checklist](p2-worker-boundary-checklist.md).

## Offline shared replay checkpoint — 19 October

An optional injected SQLite ledger now atomically consumes hashed assertion
nonces across same-host processes and retains rejection after authority restart.
No token/source payload is stored. Missing, corrupt, locked or full stores deny
without an in-memory fallback; expiry is checked again after storage consumption.
Default process-local replay and all HTTP/source startup configuration remain
unchanged. Same retained file, trusted host, stable clock and fixed namespace
capacity are prerequisites; deletion/rollback, network filesystems and separate
hosts are not covered. Packaging and lifecycle review remain activation gates.

Verification: 207 API/PostgreSQL tests and 145 root tests pass, with 11 new replay
tests including spawned processes. Root/API lint, API formatting and whitespace
checks pass. No Snowflake/AI calls, credentials, grants, push, website deployment
or P3. Next: offline read-worker delegation and authenticated peer transport.
