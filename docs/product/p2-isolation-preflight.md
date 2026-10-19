# P2 isolation: bounded metadata preflight

Date: 19 October 2026. Status: prepared, **not executed**.
Architecture: [approved proposal](p2-isolation-proposal.md).

## Purpose and approval boundary

Reconcile live column definitions and effective-policy/PUBLIC inventory gaps
before preparing implementation SQL. Architecture approval does not authorise
this execution. Ask the owner to approve this bounded metadata plan first.
CoCo performs the approved inspection; no automatic local Snowflake invocation.

Hard limits: 24 Snowflake statements and five minutes after starting inspection,
whichever comes first. Every attempted statement, including session context and
failed checks, counts; no automatic retries or cap extension. No warehouse
resume, source-row SELECT, warehouse-backed history, AI invocation, app startup
or account/object mutation. These bounds are not a measured dollar guarantee.
Use existing administrative access only where needed for metadata visibility;
do not change stored defaults or create credentials. Do not print tokens,
passwords, factor identifiers, connection configuration or raw clinical values.

## Inspection budget

| Area | Maximum statements | Evidence requested |
| --- | --- | --- |
| Session context | 2 | Actual user/role/secondary-role context; distinguish explicit context from fresh-login defaults |
| Eight table definitions | 8 | One supported metadata description per source table; explicit columns/types/nullability, no rows |
| Human authentication | 6 | Visible account/user policy attachment and relevant policy metadata; missing visibility stays unknown |
| PUBLIC reconciliation | 4 | Current direct grant inventory and bounded targeted inherited-role inspection; reconcile 12 listed database roles versus earlier summary of 11 |
| Existing governance definitions | 2 | Relevant masking/ownership metadata, only where available without compute; do not scan all objects |
| Reserve | 2 | Resolve one concrete definition/visibility gap; no functional tests |

Source tables: CORE.POLICY, CORE.POLICY_PRODUCT, CORE.CLAIM,
CORE.MEMBER_CONDITION, DOCS.PREAUTH_REQUEST, DOCS.PREAUTH_FACTS,
DOCS.POLICY_CLAUSE and APP.DECISION, all in CASHLESSIQ.

Capture only relevant metadata excerpts and query IDs, not full dumps. Compare
definitions with repository SQL and adapter fields before drafting projections.
If repository files are unavailable in Snowsight, explicitly report that limit;
do not claim a comparison or recreate missing files from memory. An authorised
metadata description is not permission to read source rows or call GET_DDL on
unrelated objects. If supported syntax or compute requirements are uncertain,
skip and report the exact question for review rather than improvising.

Metadata cannot prove ownership uniqueness, cross-tenant denial, actual login
compatibility, clinical disclosure, dependency safety or an unused PUBLIC grant.
Those require separately approved functional tests. Do not label privileges
safe to revoke or claim MFA enforcement merely from enrollment/absent policies.

## Short CoCo prompt (only after execution approval)

```text
CashlessIQ P2: architecture approved, provisioning NOT approved. Run only the
bounded metadata preflight: max 24 attempted Snowflake statements / 5 minutes.
No mutations, credentials, source-row reads, warehouse resume, history scans,
AI, app startup or functional tests. Use existing authorised metadata access.

Budget: session context 2; DESCRIBE the 8 CASHLESSIQ source tables 8;
effective user/account authentication metadata 6; PUBLIC direct inventory and
targeted inherited roles 4; existing masking/ownership metadata 2; reserve 2.
Tables: CORE.{POLICY,POLICY_PRODUCT,CLAIM,MEMBER_CONDITION},
DOCS.{PREAUTH_REQUEST,PREAUTH_FACTS,POLICY_CLAUSE}, APP.DECISION.
Inspect columns/types/nullability, no rows. Reconcile 12 listed PUBLIC database
roles versus earlier summary of 11. Unknown policy visibility stays unknown.
Do not claim metadata proves isolation, MFA enforcement or safe revocations.
Stop any check needing compute/uncertain syntax; no retries beyond the cap.
Do not expose secrets, factor IDs or raw clinical data. Do not create missing
repo files from memory. Return <=60 lines: statement count/query IDs, relevant
column drift, policy/PUBLIC corrections, unknowns and proposed next review.
No automatic implementation. Attach longer evidence as text, not chat dumps.
```

## After the report

- [ ] Reconcile evidence with repository definitions; record uncertainties.
- [ ] Select validation hosting/invocation and isolated secret custody explicitly.
  Prefer local-only isolated workers for the next synthetic acceptance design;
  this is a candidate, not approval to create identities or start services.
- [ ] Prepare exact numbered SQL/object/grant/rollback package for review.
- [ ] Obtain separate provisioning and bounded functional-test approvals.

The current API/UI remains disabled for live source use. No website deployment,
push, P3, PUBLIC revocations or login-policy rollout follows automatically.
