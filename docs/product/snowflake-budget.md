# Snowflake development budget

Last updated: 18 October 2026

## Spending envelope

Rushikesh reports $205 remaining and 19 days of account availability. This is
the planning baseline, not a balance independently verified from billing SQL.
Do not upgrade the account or incur out-of-pocket charges.

| Use | Maximum USD |
| --- | ---: |
| Checks and existing service overhead | 20 |
| Backend integration tests | 35 |
| Agent and extraction evaluations | 65 |
| Final validation and demonstrations | 35 |
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

1. Days 1–6: local P1 contracts, application foundation, identity and tests.
2. Days 7–12: integration only after P1 exits; reuse existing extraction/indexes.
3. Days 13–16: evaluate three cases, then ten; run 30 only after small batches pass.
4. Days 17–19: validate the completed slice and export reproducibility evidence.

Dates do not override phase exit criteria. An unfinished phase stays unfinished.
Keep local development and the public demo independent of live AI calls.

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
