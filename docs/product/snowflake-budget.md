# Snowflake development budget

Last updated: 21 October 2026

## Spending envelope

Latest owner update: **30 hours until expiry**; the most recent supplied balance
remains **$195**, not independently refreshed. There is **no
budget for purchasing credits afterward**. Prioritize useful source evidence
and recovery material now, not only after offline worker work finishes. This
supersedes the earlier $203/four-day and $205/18-day estimates and the calendar
schedule below. The exact
expiry timestamp and balance have not been independently verified. Use relative
Day 1/Day 2 rather than infer a new expiry date from the older document date.
Necessary product-related Snowflake spend is authorised; exact service-user,
credential, grant and live-activation packages still need separate approval.
Do not upgrade the account or incur out-of-pocket charges.
Aim to retain useful evidence before expiry, not to consume the entire balance.

The owner explicitly requested live testing now rather than postponing all
source work behind offline infrastructure. The next bounded operator acceptance
has passed: one source statement per stage over the same three permitted cases,
canonical validation in memory, redacted reports only. See
[single-statement results](single-statement-source-evidence.md). No new runtime
credentials, grants, AI budget or deployment was authorized or performed.

| Use | Maximum USD |
| --- | ---: |
| Day 1: inventory, bounded source verification and evidence capture | 60 |
| Day 2: reviewed isolation/local parity tests, only if their gates pass | 45 |
| Synthetic evidence/recovery exports and restore checks | 25 |
| Retry allowance after failure review | 15 |
| Reserve | 50 |
| Total | 195 |

These are ceilings rather than forecasts or configured Snowflake budgets.
Pause bulk AI work when measured daily usage exceeds $10. Stop ordinary work
at $50 remaining and report before allocating the reserve. Because billing
views lag, restrict test batch size independently of historical spending.

## Priority two-day sprint — latest owner instruction

**First priority today:** confirm the exact trial expiry/balance and resource
state, using the account UI if billing history cannot establish them. Preserve
existing useful evidence before doing more offline infrastructure work. Capture
available project definitions and a redacted object/grant inventory; preserve
canonical expected summaries and a bounded, private synthetic recovery fixture
only where existing read authority and disclosure scope permit it. Exclude
credentials/tokens and unnecessary clinical text; never commit raw export files
by default. Local schema/generator/golden files already provide the starting
rebuild path. An export is not proof that a new Snowflake account can be restored
for free or that it will have the same features/grants.

Proposed first execution batches: at most **12 metadata statements/five minutes**
for targeted project inventory, then at most **20 source SELECTs/ten minutes**
over the three known synthetic cases. These are new planning caps, not a reuse
of the spent administrative preflight allowance. Review the exact statements and
required role before execution; no account-wide scan, implicit admin escalation,
new grants or AI. Stop on unexpected access/ownership differences and review
before retry. Capture query IDs, statement counts, elapsed time, permitted
outputs and final resource state. Billing lag means these caps cannot enforce
an exact dollar ceiling.

**Rest of Day 1:** finish remaining offline prerequisites without Snowflake spend.
Prepare
the exact tenant-view, six runtime-principal, key-custody and rollback package
for CoCo review. Obtain that package's separate approval before provisioning.
Only after approval, run bounded ownership/base-table/foreign-tenant denial and
coherent-input tests against the three existing synthetic cases. Start with one
case and expand only after it passes. Record query IDs, statement counts, elapsed
time, results and cost visibility limitations. No account-wide PUBLIC/auth changes.

**Day 2, before expiry:** if Day 1 security gates pass, exercise local authenticated API/UI
parity for both tenants and all three roles; verify revocation/downgrade, masked
or forbidden fields, unavailable input and true MISSING states. Preserve GOL001
SAVED and GOL024/GOL027 MISSING without backfill or agent calls. Export a bounded
synthetic recovery bundle: reviewed definitions, redacted grants/config inventory,
permitted fixtures, canonical expected summaries, query/test evidence and restore
instructions. Exclude credentials, tokens and unnecessary clinical payloads.
Test replay/restore locally with Snowflake disabled, then verify project resources
are suspended. No website deployment or P3.

If isolation/credential approval or offline prerequisites remain incomplete,
switch to already-authorised operator-only bounded inspection and recovery
exports; label them supervised evidence, not isolated API/UI acceptance. Do not
activate the existing raw API adapter as a shortcut or buy compute to bypass a
security gate. The sprint can finish with P2 still open and credits unspent.

The $145 usable envelope is a ceiling, not a spending target or a billing-enforced
hard stop. Each functional test batch still needs a statement/time/credit cap;
USD forecasts must use observed account pricing, never a guessed universal rate.
No AI/extraction/search/Streamlit budget is allocated in this sprint. Keep the
$50 reserve unless the owner separately reallocates it. Remaining trial days
provide contingency, not an instruction to schedule unattended work.

## After-expiry operating mode

21 October checkpoint: owner-supplied ACCOUNTADMIN/NONE evidence confirms
CIQ_RM attached to CIQ_WH, 10 monthly warehouse credits, 2.27 used, notification
50/75% and suspend 90%. Reader-visible null was incomplete visibility, not a
missing monitor. A subsequent local bounded three-case metadata/presence capture
ran without AI or raw clinical data; see [source evidence](snowflake-expiry-source-evidence.md).
Incremental cost/current trial balance and exact expiry were not measured.

- Keep the public static demo and local synthetic fixture development independent
  of Snowflake. Test domain/API/UI and disposable PostgreSQL locally; this is not
  a replacement for live Snowflake isolation acceptance.
- Keep live source routes disabled. Connection failure/expired access remains
  unavailable, never fabricated SAVED/MISSING results or an unlabeled demo fallback.
- Retain reproducible numbered SQL, seeded generator, permitted synthetic fixture
  bundle, exact dependency locks, query evidence and remaining-gate checklist.
  Verify the recovery fixture can be validated locally with Snowflake disconnected.
- Do not upgrade, attach a payment method, buy credits, migrate to another paid
  service or assume another free trial. Further live work needs funded access
  from a separately agreed source; otherwise its gates remain explicitly open.
- Check resource state before expiry; suspend only project resources activated
  by our sessions after checking for other workloads. Do not delete source data
  or tear down shared objects merely because credits expire.

Remaining balance is owner-reported, not independently checked on 21 October.
No Snowflake call or spend was made to update this plan. Expiry does not require
using the reserve or override credential/security/phase approval gates.

## Live baseline checked on 18 October

- Local `cashlessiq` connection authenticated successfully.
- Its defaults are ACCOUNTADMIN and COMPUTE_WH. Pass explicit project role and
  CIQ_WH for development; use administrative access only for account inspection.
- All four visible warehouses were suspended.
- CIQ_WH is X-Small with 60-second auto-suspend and CIQ_RM attached.
- CIQ_RM shows a 10-credit monthly quota, 2.13 used, alerts at 50/75%, and suspend
  at 90%. These are warehouse credits, not dollars or total-account limits.
- Both visible compute pools were suspended with zero active nodes.
- CLAUSE_SEARCH indexing and serving were suspended; 35 rows are indexed and
  auto-suspend is 1,800 seconds.
- Query acceleration is enabled on CIQ_WH. Do not enable or scale additional
  compute; revisit acceleration before heavier integration queries.

Currency history returned these recent container-service costs:

| Billing date as returned | USD |
| --- | ---: |
| 14 October | 7.52 |
| 15 October | 12.89 |
| 16 October | 12.92 |
| 17 October | 7.69 |
| Total | 41.02 |

These are account-level Snowpark Container Services charges; this snapshot does
not attribute them to a particular app or prove why the pool stayed active.
The pool was already suspended at inspection. Avoid opening the authenticated
Streamlit app during local development because it can wake container compute.

## Working schedule and gates

### 19 October follow-up inspection

Authentication succeeded. Initial SHOW results again found all four warehouses,
both container pools, and CLAUSE_SEARCH indexing/serving suspended. CIQ_RM showed
2.15/10 monthly warehouse credits used. Currency history now includes $0.12 of
warehouse usage on 18 October; this does not measure the current session or
independently establish the remaining trial balance. A bounded three-case
metadata SELECT used CIQ_WH; no AI, extraction, search, or Streamlit was started.
No resource size or grants were changed. The $205 planning baseline and $50
reserve remain unchanged pending a live balance from the account UI.
End-state check found CIQ_WH started with zero running/queued queries after our
reads. Because it had been suspended before this session and was activated by
these checks, it was explicitly suspended and confirmed SUSPENDED/zero clusters.

After CoCo created the reader role, two bounded gateway probes read one TPA001
case and two TPA003 cases with no AI calls. Grant inspection also found inherited
PUBLIC Cortex privileges; no account-wide revocations were attempted. Both pools
and search remained suspended. CIQ_WH was again suspended and confirmed with
zero running/queued queries and zero clusters after the probes. Exact incremental
cost remains subject to billing lag; no new dollar balance is inferred.

The following is the superseded original schedule, retained for history only:

1. 19–22 October: finish remote CI for the local alpha, inspect spend/state, and
   implement bounded P2 Snowflake reads behind the repository interface. Reuse
   existing synthetic data and extraction/index outputs; do not wake Streamlit.
2. 23–28 October: after P2 exits, verify the next approved product slice against
   the existing governed objects. Do not resume AI/extraction merely to spend
   credits or skip reviewer-command/worker prerequisites to fit the calendar.
3. 29 October–2 November: if the assessment slice is ready, evaluate three cases,
   then ten; run 30 only after smaller batches pass. Otherwise spend only on
   relevant read parity and deterministic integration checks.
4. 3–5 November: export synthetic fixtures, schema/object definitions, evaluation
   evidence, and recovery instructions. Verify local development still works
   without the expiring account. Do not leave paid services running for expiry.

Dates do not override phase exit criteria. An unfinished phase stays unfinished.
Keep local development and the public demo independent of live AI calls.
The five interviews were explicitly deferred for a synthetic-only alpha on
19 October. This permits P2 integration using existing synthetic records, not
real-data ingestion or production deployment. The $50 reserve is still held;
report before reallocating it, even near expiry.

## Session procedure

1. Inspect account usage and existing object state before integration sessions.
2. Use CIQ_WH, bounded query timeouts, selected synthetic requests, and explicit
   roles. Do not recreate search services, reload all data, or rerun extraction
   as part of frontend/API tests.
3. Record measured cost before expanding a batch. Keep retries bounded and
   retain successful extraction and tool outputs.
4. Verify warehouse, search indexing/serving, and container-pool state after work.
   Suspend only project resources that the session activated; shared resources
   require checking other workloads first.
5. Use the public demo for UI review. Open Streamlit only for a specific test.

Reproducible read-only inspection:

```sh
snow sql -c cashlessiq -f sql/06_cost_snapshot.sql
```

This inspection itself may briefly resume CIQ_WH. Its 60-second auto-suspend
remains in force. Warehouse resource monitors exclude serverless/AI costs.
Account metering can lag about three hours; currency usage can lag up to 72
hours. Do not infer an exact current trial balance or universal USD/credit rate.

Sources: [resource monitors](https://docs.snowflake.com/en/user-guide/resource-monitors),
[metering](https://docs.snowflake.com/en/sql-reference/account-usage/metering_daily_history),
[currency history](https://docs.snowflake.com/en/sql-reference/organization-usage/usage_in_currency_daily).
