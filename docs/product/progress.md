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
2. [ ] Compare all three cases against independent metadata/history expectations;
   validate available saved decisions and every citation; explicitly preserve
   absent recommendations under the approved gate revision below. Record discrepancies, never hide
   them with fixture fallback, fresh AI output or changed golden expectations.
3. [ ] Establish the explicit shared-domain package boundary for the API.
4. [ ] Implement and test the repository adapter, including source failure,
   missing data, separate tenant ownership and role-based clinical disclosure.
5. [ ] Review source identity/effective privileges with CoCo. Operator table
   grants and disabled secondary roles are not production tenant RLS; inherited
   PUBLIC capabilities are unresolved. No account-wide revocations are approved.
6. [ ] Opt in separate local source identities and exercise authenticated API/UI
   parity. Keep the existing mixed offline demo and public site unchanged.
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

- Root regression: **139 passed** after the missing-state increment (15 new tests);
  root lint and git whitespace checks pass.
- Targeted metadata/inspection boundary suite: **39 passed** this checkpoint.
- API suite: **98 passed** at the earlier inspection-query increment. This
  checkpoint's full rerun produced 54 passes and 44 database-setup errors because
  Docker was stopped; it is not a passing integration run. Docker was started,
  but its active environment had no cached images/containers/volumes. A fresh
  stack build began downloading images and was cancelled before any containers
  started. No volume was deleted. Full API/PostgreSQL/UI verification is pending.
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
- [ ] Explicit shared-domain package boundary and versioned source-read API.
- [ ] UI distinguishes no saved recommendation from QUERY/REFER, source error
  and zero payable; end-to-end coverage with separate source-alpha tenants.

The existing v1 API requires an outcome, so it is unchanged. The new observation
is not wired into HTTP/UI and is not itself proof of source parity. No source
writes, AI calls, deployment or historical decision-schema changes are needed.

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
