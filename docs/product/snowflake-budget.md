# Snowflake development budget

Last updated: 19 October 2026

## Spending envelope

Rushikesh reconfirmed $205 remaining and 18 days of account availability on
19 October, and authorised necessary Snowflake usage for product work. This is
the planning baseline, not a balance independently verified from billing SQL.
Do not upgrade the account or incur out-of-pocket charges.
The planning expiry is approximately 6 November 2026; the exact account expiry
and timezone must be confirmed from the account before relying on that date.
Aim to retain useful evidence before expiry, not to consume the entire balance.

| Use | Maximum USD |
| --- | ---: |
| Checks and existing service overhead | 20 |
| Backend integration tests | 35 |
| Agent and extraction evaluations | 65 |
| Product validation and reproducibility exports | 35 |
| Reserve | 50 |
| Total | 205 |

These are ceilings rather than forecasts or configured Snowflake budgets.
Pause bulk AI work when measured daily usage exceeds $10. Stop ordinary work
at $50 remaining and report before allocating the reserve. Because billing
views lag, restrict test batch size independently of historical spending.

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
