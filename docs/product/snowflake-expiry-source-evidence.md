# Pre-expiry source metadata evidence — 21 October 2026

Scope: supervised synthetic operator reads, not activated API/UI or isolated
service access. The owner-supplied ACCOUNTADMIN report resolved the apparent
monitor discrepancy: CIQ_RM exists and is attached. No monitor repair was made.

The local CLI authenticated explicitly as CIQ_PRODUCT_READER with secondary
roles NONE. Five statements completed: context SELECT, bounded case metadata,
bounded saved-row counts, bounded clause-reference counts, warehouse SHOW.
Only three statements read source tables; each restricts the three known
request/TPA pairs and limits returned groups/records to four. No raw decision,
clinical note, condition, demographics or clause text was selected/exported.
No agent, extraction, search, Streamlit, source writes or grants were invoked.

## Captured source observations

Common product: `AS_NIA_V02_2425`, version `V02 2024-25`, Arogya Sanjeevani
Policy, The New India Assurance Co. Ltd. All admission dates: 2026-10-02.

| Request | TPA | Policy | Continuous cover since | Supplied estimate INR | Saved rows | Clause refs |
| --- | --- | --- | --- | ---: | ---: | ---: |
| GOL001 | TPA001 | POL0001 | 2023-01-01 | 100000 | 2 | 35 |
| GOL024 | TPA003 | POL0024 | 2026-01-01 | 80000 | 0 | 35 |
| GOL027 | TPA003 | POL0027 | 2023-01-01 | 90000 | 0 | 35 |

Amounts are copied supplied integer estimates, not computed payables. GOL001's
two saved rows are historical observations; the count query does not choose or
validate a latest decision. No new SAVED/schema/citation/arithmetic validation
pass is claimed. Zero rows corroborate the approved missing-recommendation
scope, but are not a replacement for full owned-context validation in runtime.
Clause counts do not establish distinct registry coverage or narrative grounding.

These three queries are separate statements, **not a coherent decision/input
snapshot**. This result does not close the coherent-query, tenant service,
financial trace, clinical disclosure or live API/UI gates. No source data was
substituted into existing demo fixtures, and the normal routes remain disabled.

An offline assertion check compared the captured request ID, policy ID, product
name/version, cover/admission dates and supplied estimate with the existing
packaged snapshots: all seven fields match for all three cases. Snapshot outcome
and payable fields were deliberately not compared or substituted for absent live
decisions. No fixture file was changed.

## Execution evidence and limits

The final warehouse SHOW returned STARTED, one cluster, zero running/queued
queries, X-Small and 60-second auto-suspend. These reads resumed the previously
suspended warehouse; a subsequent metadata-only end-state check is required.
The resumed timestamp returned was `2026-10-21T00:12:18.510000-07:00`.
The reader still reports `resource_monitor=null`; this is visibility-limited and
does not overturn the owner-supplied administrative attachment confirmation.

The subsequent one-statement metadata-only end-state check completed and found
CIQ_WH **SUSPENDED**, zero started clusters and zero running/queued queries.
Auto-suspend recovered the idle warehouse without an administrative mutation.
Total for this source checkpoint including that check: six statements, three
source SELECTs. No further source query or resource change was made.

CLI `JSON_EXT` returned rows but no query IDs or per-statement timing in this
invocation. No exact IDs, server execution times or incremental dollars can be
reported from this output. The batch completed within ten minutes; no explicit
per-query timeout was set by this CLI invocation, unlike the canonical Python
gateway. Future repeatable capture must set session statement/queue timeouts
and collect `cursor.sfqid` directly without leaking credentials or raw payloads.

This committed file is deliberately a small synthetic metadata report, **not a
database backup**. Definitions, validated raw recovery inputs and a local replay/
restore check still need a bounded capture tool and private artifact handling.
No raw data bundle, new service credentials, paid upgrade, deployment or P3.
