# CashlessIQ product delivery checklist

Last updated: 21 October 2026
Current phase: **P2 / M2 — synthetic-only, read-only case workspace**

This is the current-status index. The migration plan defines sequence; phase
checklists contain verification evidence. Earlier entries in those checklists
are historical checkpoints, not the latest status. Hackathon submission is done;
demo-video work is not part of this product plan.

## Phase scoreboard

| Phase | Status | Exit gate |
| --- | --- | --- |
| P0 — product direction | Complete, approved | Scope, boundaries, initial policy and synthetic pilot decisions agreed |
| P1 / M0–M1 — foundation | Engineering complete; research deferred explicitly | Local authenticated stack and CI pass; five interviews still owed before customer rollout |
| P2 / M2 — read-only workspace | **In progress** | Governed source adapter and verified queue/case/member/decision/evidence views |
| P3 / M3 — reviewer commands | Not started | Assignment, comments, concurrency, transactional audit/outbox; full synthetic review |
| P4 / M4 — asynchronous assessment | Not started | Validated assessment survives worker restart and safe retry |
| P5 / M5 — ingestion and policy management | Not started | Secure ingestion; second supported policy onboarded through approval/regression gates |
| P6 / M6 — prototype retirement | Not started | Parallel reconciliation passes; no operational dependency on Streamlit/user credentials |

## Completed foundations

- [x] Approved Indian TPA / hybrid deployment / PostgreSQL / Next.js + FastAPI direction.
- [x] Frozen canonical decision contract and 30 golden rule results.
- [x] Local web/API/PostgreSQL stack, migrations, identity and tenant membership.
- [x] Authenticated API contracts and generated TypeScript types.
- [x] Three-role synthetic queue and case UI, responsive layouts and browser tests.
- [x] API isolation/revocation tests and no-Snowflake CI for the implemented slice.
- [x] Separate source-alpha identities and immutable TPA001/TPA003 ownership scopes.
- [x] Bounded metadata/history/decision/clause inspection code; unknown scopes do no I/O.
- [x] Pure-Python saved-decision/citation and member-history validators with offline tests.
- [x] Approved inspection grants independently verified: 13 direct USAGE/SELECT grants,
  no grant option, only RUSHIKESH2001 as grantee. PUBLIC caveat remains open.

## P2 remaining work — in order

### Current completion gates (latest summary)

The local application and bounded operator source checks are implemented. P2 is
**not complete**: the live product path is still disabled and must not reuse the
operator's credentials or raw-input API adapter.

| Remaining gate | What closes it |
| --- | --- |
| Worker security | Private mTLS/delegation, retained replay, package/network/mount and restricted DB composition/verified TLS tests pass; [lifecycle/configuration proposal](../architecture/p2-runtime-lifecycle.md) prepared, fixed connection factory, actual custody/clock controls and service wiring remain |
| Snowflake isolation | Exact tenant views/coherent validation query, six runtime identities, secret custody/rollback and relevant PUBLIC/MFA/live-definition gaps reviewed; separately approved provisioning and negative tests |
| Governed evidence display | Approve the financial-trace/clinical projection and verify calculation/citation presentation; current source contract intentionally returns summary/reference metadata only |
| Local live acceptance | Both tenants/all roles through authenticated API/UI; foreign/base-table denial, role revocation/downgrade, true missing states and source failure, with bounded spend/evidence |
| Final delivery verification | Full regression/browser/build/contract checks, separately authorised push, remote CI and P2 exit review |

No website deployment or P3 is included. User interviews/customer rollout and
real-data operational gates remain separate; synthetic-alpha permission does
not waive them. Detailed evidence and next actions are below.

1. [x] Complete Python reader authentication and bounded live source inspection.
2. [x] Compare all three cases against independent metadata/history expectations;
   validate available saved decisions and every citation; explicitly preserve
   absent recommendations under the approved gate revision below. Record discrepancies, never hide
   them with fixture fallback, fresh AI output or changed golden expectations.
   Live repository check passed on 19 October: GOL001 SAVED, GOL024/GOL027
   MISSING, no compared-field differences. This is summary/reference parity,
   not full calculation-trace or narrative-grounding/UI parity.
3. [x] Establish the explicit shared-domain package boundary for the API.
4. [x] Implement and test the preliminary v2 repository adapter, including source
   failure, missing data, separate tenant ownership and condition disclosure.
   Default HTTP reads remain disabled; this is not full workspace parity.
5. [x] Review source identity/effective privileges with CoCo. Operator table
   grants and disabled secondary roles are not production tenant RLS; inherited
   PUBLIC capabilities are unresolved. No account-wide revocations are approved.
   CoCo report and policy-reference follow-up received; see
   [reconciled findings](source-access-findings.md). Review is complete, but
   remediation/service identity/isolation approval and implementation remain open.
   None of the eight source tables has a row-access policy; only CLINICAL_NOTE
   has the reported masking policy. No unattended/customer deployment is approved.
   CoCo subsequently reports the approved reader/empty-secondary user defaults
   applied with grants unchanged. The reader/NONE worksheet context is verified
   after explicit USE commands; automatic fresh-login context remains unverified.
   Next: [bounded MFA/PUBLIC/isolation follow-up](source-hardening-followup.md).
   Local follow-up independently confirmed stored defaults, zero enrolled MFA
   methods and 109 visible PUBLIC grants; CIQ_WH remained suspended at inspection.
   [Results/design proposal](source-hardening-results.md) records enforcement and
   dependency visibility gaps. No new service/views or PUBLIC changes applied.
   Subsequent owner passkey enrollment is independently verified: one PASSKEY,
   HAS_MFA true; stored defaults unchanged. This supersedes the zero-method
   observation. Effective policy enforcement and second interactive login remain
   unverified; administrative dependency review is still pending.
6. [ ] Opt in separate local source identities and exercise authenticated API/UI
   parity. Keep the existing mixed offline demo and public site unchanged.
   Presentation groundwork: the authenticated local `/source-preview` now renders
   fictional v2 fixtures for SAVED/MISSING, saved QUERY/REFER and source failure.
   It does not call `/v2/cases` or Snowflake, seed source tenants, or establish
   source parity. No source access has been activated. See the latest P2 checkpoint.
   The Evidence fixture now exercises searchable clause-reference metadata and
   page links; it does not retrieve PDF content or establish narrative grounding.
   The offline v2 HTTP-client boundary is implemented with exported-schema
   validation and 41 no-network tests. It is now exercised through gated
   `/source-cases` routes in an isolated contract-test stack: real API/PostgreSQL
   identity checks, fake source gateways, two tenants and all three roles.
   Fifteen browser integration tests pass; this is not live source parity.
   Normal local startup and production return 404 for these routes. No
   persistent source identities or live connections have been activated.
7. [ ] Run regression/API/PostgreSQL/browser/build/contract checks, obtain push
   authority, then verify remote CI. Review P2 exit evidence before starting P3.
   - [x] Full local regression, API/PostgreSQL, client, offline source integration,
     web build/typecheck/lint, domain-wheel and contract-drift checks rerun.
   - [ ] Push authority and remote CI for the resulting commits.
   - [ ] Live security/source acceptance and full financial-trace/evidence gates.

## Remaining P2 blockers (not website deployment)

- [x] Receive CoCo administrative follow-up report (28 metadata statements,
  owner-supplied; not independently rerun). Review found policy/count
  inconsistencies and unsafe proposed auth restrictions; receipt is not acceptance.
- [ ] Resolve effective MFA/PUBLIC dependency and live-definition gaps identified
  in the [corrected review-only proposal](p2-isolation-proposal.md).
- [ ] Review/approve the narrow service-authentication and database tenant/
  clinical-isolation implementation before provisioning anything.
- [ ] Approve a governed financial-trace/clinical projection and verify the
  calculation/citation display; the current v2 contract deliberately omits prose.
- [ ] Bounded live API/UI parity after those security gates, then review P2 exit.

Rushikesh approved the corrected architecture on 19 October. It separates tenant
projections, clinical validation, service authentication and human login changes.
The [bounded metadata preflight](p2-isolation-preflight.md) was separately approved;
CoCo reports 21 attempts with no changes/data reads/AI. Its column inventory was
compared with repository DDL; [report limitations](p2-isolation-preflight-results.md)
include missing query IDs/time evidence, policy scope and inherited-role checks.
No independent rerun or isolation acceptance is claimed. Validation hosting and
credential custody must be settled before the implementation package. Architecture
approval is not provisioning approval. No new SQL, credentials, source activation
or account changes.

Next design prepared: [local validation/credential boundary](../architecture/p2-validation-boundary.md).
It proposes four read workers plus two tenant validators, with no Snowflake
credentials in the API. Rushikesh approved the design including the two extra
validator identities. First [offline boundary slice](p2-worker-boundary-checklist.md)
is implemented: asymmetric assertions, fresh injected membership/replay guards
and canonical summary-only validator handler, with 34 new tests. Peer transport,
delegation, restart-safe replay, packaging/secret custody and live SQL/isolation
remain open. Nothing is provisioned or live; P2 remains open.

Next offline increment adds a token-verifying summary broker, fresh PostgreSQL
membership adapter, internal-user UUID subjects and immutable tenant/disclosure
routing. Broker delivery rechecks session/membership and validates response
scope. Seventeen additional disposable-database/fake-source tests pass; latest
API total is **196**, root regression **145**, with Ruff/format/whitespace checks
passing. This in-process summary composition is not the read-worker delegation
or authenticated transport implementation. No HTTP startup integration, live
source access, persistent identities, push or website deployment was added.

The website must remain unchanged per Rushikesh's latest instruction. Completing
offline tests does not waive these gates or authorise P3, public deployment,
new grants, account-wide restrictions or reuse of human OAuth in a server.

## Gates that remain open

- [ ] Five target-user interviews and reconciliation of workflow findings.
- [ ] Customer identity/SSO deployment, real-data privacy/security/residency gates.
- [ ] Pilot integration format and owner-agreed quality/latency thresholds.
- [ ] Production service authentication and database-enforced tenant isolation.
- [ ] Backup/restore, incident response and operational launch readiness.

These are not waived by synthetic-alpha permission. No real patient data,
customer rollout, autonomous denial or unsupported executable rule activation.
Policy activation continues to require explicit human approval.

## Verification and delivery checkpoint

- Latest offline integration checkpoint: root **145**, API/PostgreSQL **145**,
  client **41**, source API-to-UI **15**, normal browser **23** tests pass. Typecheck/lint/production
  build, isolated domain wheel and contract regeneration without drift pass.
  The test stack uses loopback ports 8003/3003 and a disposable PostgreSQL schema;
  no source-alpha tenants were seeded into the persistent sandbox. Graceful
  shutdown cleanup was verified after fixing Uvicorn signal replay; the three
  earlier disposable test schemas were removed explicitly, and the latest run
  leaves zero. Fixtures can recreate them; no sandbox volume/data was removed.
  Production-mode source routes return 404 even with the contract-test flag set.
  The normal local stack also verifies both source routes return 404; its web
  container was rebuilt and is healthy without enabling the contract-test flag.
  No Snowflake/AI, grants, push, remote CI or website deployment ran.

- Latest client increment: **41 no-network client tests pass**; client/web
  typecheck and lint pass, as does the web production build. No source route
  was enabled or connected. Canonical API/domain and database behaviour are
  unchanged; their Python suites were not rerun for this increment.
  Local web Docker rebuild/readiness and all **22 browser regressions** pass
  with the new locked client dependencies. No remote CI run is claimed.

- Latest presentation increment: **22 browser tests pass**, web typecheck/lint
  and production build pass. Local-only fixture route returns 404 in production
  mode in the prior checkpoint; its environment/auth guards are unchanged.
  Clause filter/title/ID matching, reset, page-link attributes and mobile layout
  are now covered. Desktop screenshot visually inspected. This tests presentation,
  not real source API/UI or service isolation.
  Python/API suites were not rerun for this frontend-only increment.

- Root regression: **145 passed** after domain-packaging regressions; root/API
  lint, API formatting and git whitespace checks pass.
- Targeted metadata/inspection boundary suite: **39 passed** this checkpoint.
- API/PostgreSQL suite: **145 passed** after the v2 source-adapter increment,
  including 44 new repository/HTTP tests. This supersedes the earlier unavailable-Docker
  test attempt. Local PostgreSQL was started for disposable test schemas, then
  stopped with its data volume retained. No volume was deleted.
- Isolated domain wheel: byte identity with all four canonical modules, frozen
  schema and missing/invalid-state smoke pass without the legacy package,
  Snowflake, Streamlit or FastAPI installed. API Docker build and non-root image
  smoke pass with network disabled for the smoke. The normal image has no
  Snowflake/Streamlit runtime dependency. API OpenAPI regenerated with no drift.
- Generated v2 OpenAPI/TypeScript contracts and web typecheck pass. All previous
  paths and component schemas are unchanged. New source routes authenticate but
  return 503 unless a repository is injected explicitly in local/test. No default
  connection, source UI/login or staging/production activation is enabled.
- Updated API Docker build and network-disabled non-root v2 schema smoke pass.
- Browser/UI and remote CI have not been rerun for this backend increment.
- Remote CI: last verified passing `d3623da`; newer local commits are not covered
  by that run. Recheck the branch before reporting an ahead count or pushing.
- Python source authentication now completed. All three independent history
  comparisons pass. GOL001's saved decision validates and matches the snapshot;
  GOL024/GOL027 have no saved decision rows, so full decision parity is open.
- All three cases have 35 scoped product-clause references. Counts are not proof
  of narrative grounding or retrieved clause text. No source backfill/AI ran.
- Final warehouse check: CIQ_WH SUSPENDED, zero clusters/running/queued queries.
- Public demo and authenticated Streamlit remain separate from the local product
  alpha. Product source integration has not been deployed.
- Preserve the untracked submission video; do not include it in product commits.

### Approved missing-recommendation scope revision — 19 October

Rushikesh approved an explicit missing-recommendation state rather than source
backfill. P2 must faithfully show an absent recommendation for GOL024/GOL027;
it must not reproduce the demo QUERY/REFER as live decisions. This revises the
original expectation of three matching saved decisions, not the remaining
source, isolation, clinical-disclosure or UI integration gates.

- [x] Pure-Python immutable SAVED/MISSING source observations and offline tests.
- [x] Missing state has only validated context and the supplied estimate; no
  invented outcome/payable/calculation/query/referral. Invalid saved rows and
  ambiguous reads remain errors, never missing-state fallback.
- [x] Explicit shared-domain package boundary (`cashlessiq-domain`).
- [x] Versioned source-read API with tested opt-in adapter; v1 is unchanged.
- [ ] UI distinguishes no saved recommendation from QUERY/REFER, source error
  and zero payable; end-to-end coverage with separate source-alpha tenants.
  Local fixture presentation is implemented; real source-alpha integration and
  its live owner/clinical-access tests remain open. The isolated real-HTTP fake-
  gateway integration now tests both tenant scopes and all three roles, not
  Snowflake enforcement or live parity. The fixture preview is explicitly
  labelled, authenticated and unavailable outside local/local-auth mode.

The existing v1 API requires an outcome, so it is unchanged. The v2 adapter uses
the new observation, but HTTP reads stay disabled by default and the UI is not
integrated. The first source view omits raw clinical prose and calculation text;
full financial trace/citation display remains open. Live repository verification
subsequently passed as recorded below. No source writes, AI calls, deployment or
historical schema changes ran.

### Live repository verification — 19 October

One operator connection explicitly used CIQ_PRODUCT_READER with secondary roles
disabled. The actual repository composed the metadata and inspection gateways;
two queue reads and three detail reads made five bounded metadata SELECTs and
twelve bounded inspection SELECTs. All three cases matched the frozen seven-field
metadata baseline and independent member/history constants, including conditions.
The frozen files were comparison inputs only, never source fallback.

GOL001's saved recommendation passed fresh canonical/citation validation and
matched outcome/claimed/payable. GOL024/GOL027 returned only the approved MISSING
state, without invented outcome/payable. Each detail contained 35 validated,
scoped clause-register references; this does not prove retrieved text/narrative
grounding. No source writes, AI, grants, persistent identity seeds, HTTP/UI
activation or deployment ran. This check exercises the repository directly,
not authenticated browser parity. Source identity/PUBLIC and UI gates remain open.
Final SHOW under the reader role confirmed CIQ_WH SUSPENDED, zero started
clusters/running/queued queries, X-Small and 60-second auto-suspend unchanged.
Incremental dollars and current trial balance were not measured.

## Latest offline increment — restart-aware replay

- [x] Optional same-host atomic replay ledger and authority integration, not
  imported into startup. Eleven new tests cover concurrent spawned processes,
  retained consumption after restart, shared capacity, expiry and fail-closed
  missing/corrupt/locked/full storage. No raw tokens or source payloads persisted.
- [x] 207 API/PostgreSQL tests, 145 root tests, root/API lint and API formatting
  pass. Existing local stack only; test schemas/files are disposable.
- [ ] Read-worker delegation, authenticated private peer transport, lifecycle/
  secret mounts, exact Snowflake isolation package and live acceptance remain.
  The replay candidate requires retained shared local state and lifecycle review;
  it is not distributed-host or deployed isolation. Default replay is unchanged.

No Snowflake/AI use, source activation, new credentials/grants, push or deployment.
The two-day credit plan is committed; actual balance/expiry remain unverified.

### Subsequent offline delegation increment

Broker-authenticated requests can now take a fixed read-relay -> tenant-validator
path in disposable tests. The broker signs separate audience/operation-bound
parent/summary capabilities with identical subject, tenant, disclosure, case and
lifetime, plus a parent nonce binding. Readers hold no signing key and forward
the enclosed summary capability unchanged. Reader and validator independently
consume replay guards and check fresh membership; broker checks again on delivery.

The endpoint checks a fixed reader/disclosure pairing against **injected fake
peer context**, not real TLS authentication. Real transport, remote membership,
packaging and credential isolation remain open. This relay returns summary only,
not a complete queue/detail read worker or approved financial-trace projection.
All HTTP startup, source/UI activation and public v2 contracts remain unchanged.

Latest verification: **255 API/PostgreSQL tests and 145 root tests** pass; root/API
lint, API formatting and whitespace checks pass. The increment adds 32 delegation
tests and reruns 16 existing broker scenarios through the delegated path. Web/
browser/build/remote CI were not rerun for these internal-only changes. No
Snowflake/AI calls, keys saved to disk, grants, provisioning, push or deployment.

## Latest transport checkpoint

The two local worker hops now have an explicitly constructed mTLS transport
candidate: required client certificates, explicit CA, IP SAN verification,
certificate pins/URI identities and certificate-derived peer context. Twenty-three
real loopback TLS tests pass, including both-hop composition, missing/foreign/
untrusted/expired/wrong-purpose credentials, spoofed headers, malformed requests,
replay and generic failure handling. Temporary test PKI is deleted by fixtures.

Latest backend total: **278 API/PostgreSQL tests**, plus **145 root tests**, with
root/API lint, API formatting and whitespace checks passing. Web/browser/build/
remote CI were not rerun for this internal-only increment. No Snowflake/AI calls,
real credentials, grants, source activation, ordinary startup, push or deployment.

This closes loopback peer authentication, not deployed isolation. Remote
membership, separate packaging/mounts, CA/signing-key custody/rotation, replay
lifecycle and exact Snowflake/live acceptance gates remain. See the
[transport checkpoint](../architecture/p2-worker-transport.md). Next: authoritative
remote membership and worker packaging preparation; do not give workers general
operational DB credentials or activate human OAuth as a shortcut.

## Latest membership checkpoint

The narrow authoritative membership service/client now passes loopback mTLS tests
without giving workers general DB credentials. Certificate identity pins the
tenant; UUID/nonce-bound responses contain only the fresh current role or null.
Revocation, lookup outages and medical downgrade deny before delivery. Both tenant
scopes/all roles compose with fake source inputs; no source endpoint was activated.

Latest verification: **312 API/PostgreSQL tests**, **145 root tests**, root/API
lint, API formatting and whitespace checks. Web/browser/build/remote CI not rerun
for this internal-only change. No Snowflake spend, real credentials, grants, push,
ordinary startup or deployment. See [evidence/limits](../architecture/p2-worker-membership.md).

Next: separate worker/membership packaging, private network and mount-isolation
tests, then reviewed secret/replay lifecycle and exact Snowflake package. P2 is
not complete; the live product path and public website remain unchanged.

## Latest packaging checkpoint

A separate minimal worker artifact now builds without API startup, DB modules or
Snowflake connector. The default image refuses activation. An explicit test-only
image passed eight-container/14-private-network checks: permitted edges work;
forbidden peers fail by hostname/direct IP; non-root/read-only/dummy-secret mount
boundaries hold. All disposable resources were cleaned up; normal local stack and
website are untouched. See [packaging evidence/limits](../architecture/p2-worker-packaging.md).

312 API/PostgreSQL and 145 root tests remain green. No Snowflake/AI, real keys,
service provisioning, live source activation, push or deployment. Deployment is
paused again at the owner's request. Next: actual container mTLS using temporary
PKI, trusted membership-service packaging/DB policy and secret/replay lifecycle.
The topology probes are not application handlers; P2 remains incomplete.

## Latest private-container transport checkpoint — 21 October

Four disposable containers now exercise the canonical delegated relay/validator
and remote membership adapters over exact private IPs with pinned temporary mTLS
identities. The synthetic SAVED summary is correct; replay, wrong identity,
cross-tenant/direct-hop access and revoked/unavailable membership deny. Per-role
read-only test key mounts hold; the eight-container topology/package smoke also
passes. See [scope/evidence/limits](../architecture/p2-worker-container-mtls.md).

342 API/PostgreSQL and 145 root tests pass; lint/format/whitespace pass and public
OpenAPI is unchanged. Disposable resources are removed. No website/normal startup,
Snowflake/AI use, real keys/grants, push or P3. This supersedes the container-mTLS
next action above, not the broader live-acceptance gates. Next: retained replay
volume/restart lifecycle using disposable keys, then trusted membership-service
packaging and narrow DB access review. P2 remains in progress.

## Latest retained replay checkpoint — 21 October

The disposable private-mTLS harness now has an explicit retained-volume variant.
Both validator and reader container restarts reject their original consumed
capabilities while still unexpired; fresh capabilities succeed afterward. Exact
per-authority mounts, file ownership/modes, hash/expiry-only contents and refused
reinitialization are checked. Missing state denies requests and listener startup
without recreating the file or falling back to memory. All test volumes are
removed after the run. See [evidence/limits](../architecture/p2-worker-replay-lifecycle.md).

342 backend and 145 root tests remain green. No production code/API/startup,
real credentials, Snowflake/AI, push, deployment or P3 changes. This closes the
offline container restart test, **not** production replay/key recovery policy.
Next: separately packaged trusted membership service and narrow DB policy, using
bounded disposable tests; retain the remaining P2 live/isolation/evidence gates.

## Latest membership package checkpoint — 21 October

Separate locked membership wheel and narrow DB adapter are implemented locally.
The adapter uses only role/ID/active columns in a fresh schema-qualified read-only
transaction with statement/lock timeouts. Artifact checks exclude API/auth/broker/
models/Snowflake and default startup refuses activation. Twenty new disposable-
schema/mocked tests pass; backend **362**, root **145**. See
[DB boundary and review proposal](../architecture/p2-membership-db-boundary.md).

This is not dedicated-principal privilege or container DB isolation acceptance:
tests use the existing local test admin connection. No persistent role/grant,
credential, source activation, Snowflake/AI, deployment or P3. Next: separately
package the membership container and verify column-grant/DB-network denial in a
disposable environment; exact production provisioning stays separately gated.
No push or remote CI is claimed.

## Latest membership container/DB checkpoint — 21 October

The membership image and disposable PostgreSQL restricted-principal test pass.
Real point lookup succeeds; 18 forbidden reads/writes/DDL/admin/function actions
fail by grants even in read-write transactions. Committed role downgrade and
user/tenant/membership deactivation are observed; required-grant revocation and
DB outage deny without missing-state fallback. Private pair networks and exact
per-service read-only secret mounts exclude DB drivers/credentials/reachability
from reader/validator containers. Default membership image refuses startup and
excludes its probe. All test resources/data/credentials are discarded; normal DB
and website unchanged. See [scope/evidence/limits](../architecture/p2-membership-container-db.md).

This is a disposable mirrored schema, not production grant acceptance. DB TLS,
real secret custody and actual mTLS-server/DB composition remain open. Next:
compose pinned membership transport with the restricted DB lookup, then continue
the remaining P2 security/source/evidence gates. No Snowflake/AI, persistent
provisioning, deployment, push or P3.

## Latest lifecycle/configuration review — 21 October

The [runtime lifecycle proposal](../architecture/p2-runtime-lifecycle.md) now
specifies the next offline fixed DB factory, material-by-service ownership,
maintenance-window rotation and lost-replay-state recovery. It identifies a
remaining clock-jump/rollback hazard: expiry pruning plus later backward time is
not protected by the current ledger. Trusted clock enforcement/recovery must be
implemented and negatively tested before activation; no automatic protection is
claimed. Stop-and-restart rotation matches the current single-key/static-pin
implementation; hot reload and zero-downtime renewal are not assumed.

Next bounded implementation: strict membership-only connection configuration and
fixed verified-TLS factory, with dummy inputs, no startup wiring and no real
secrets or network calls. Then reuse disposable DB acceptance and combine it with
retained replay. Exact encrypted secret-store/delivery and production readiness
remain separate review/approval gates. This is a documentation checkpoint only;
prior test counts are unchanged, not rerun. No Snowflake/AI, spend, provisioning,
deployment, push or P3.

## Spend guardrails

Latest planning baseline: **$203 remaining and four days until expiry**, reported
by Rushikesh, not independently verified. Concentrate useful Snowflake work into
the next two days using the [revised sprint budget](snowflake-budget.md): maximum
$153 ordinary work plus $50 reserve. This supersedes earlier $205/18-day estimates.
Necessary bounded reads are approved; service/credential/grant packages and live
activation retain their separate exact approval gates.
Do not upgrade or incur out-of-pocket charges. Do not start agents, extraction,
search or Streamlit just to use expiring credits. Confirm exact expiry and
balance before larger batches; historical billing lags.

## References

- [Migration sequence](../architecture/migration-plan.md)
- [P0 decisions](phase-p0-checklist.md)
- [P1 evidence and research deferral](phase-p1-checklist.md)
- [P2 evidence](phase-p2-checklist.md)
- [Snowflake integration](../architecture/snowflake-read-integration.md)
- [Budget](snowflake-budget.md)
