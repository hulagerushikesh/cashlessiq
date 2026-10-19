# CashlessIQ product delivery checklist

Last updated: 19 October 2026  
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
7. [ ] Run regression/API/PostgreSQL/browser/build/contract checks, obtain push
   authority, then verify remote CI. Review P2 exit evidence before starting P3.

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
  its owner/clinical-access tests remain open. The fixture preview is explicitly
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

## Spend guardrails

Planning baseline: $205 credit balance reported by Rushikesh, **not a fresh
billing measurement**; retain $50 reserve. Necessary bounded reads are approved.
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
