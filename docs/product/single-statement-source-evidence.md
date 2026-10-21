# Bounded single-statement source acceptance

21 October 2026. The owner reports **30 hours of trial access remaining** and
requests useful live product tests before expiry, without purchasing credits.
This increment prioritizes operator-only source acceptance over more offline
clock work. Existing service-identity, host/custody, provisioning and deployment
gates are not waived. Actual trial balance/expiry still need current UI evidence.

## Scope and controls

`scripts/test_source_statement.py` combines the exact already permitted metadata,
member/history, condition, latest decision and clause-reference projections with
explicit object keys and UNION ALL. It performs one source statement per stage,
not five/nine independently timed reads. No wildcard export, new source fields,
POLICY_RULE reads, DDL, grants, AI, search, extraction or Streamlit. The original
scope remains GOL001/TPA001 followed only on success by GOL024/GOL027/TPA003.

The use of null-preserving objects follows Snowflake's
[OBJECT_CONSTRUCT_KEEP_NULL](https://docs.snowflake.com/en/sql-reference/functions/object_construct_keep_null)
contract. One statement avoids the multi-statement read window under documented
[READ COMMITTED semantics](https://docs.snowflake.com/en/sql-reference/transactions).
This is an engineering inference for these ordinary tables, not a concurrent
mutation experiment, cross-stage snapshot or service-identity isolation proof.

Each stage has five explicit statements: timeout/tag session settings, context,
one bounded source SELECT, its LAST_QUERY_ID lookup, warehouse SHOW. Explicit
CIQ_PRODUCT_READER / secondary NONE / CIQ_WH; 30/15-second statement/queue limits;
180-second client deadline and 2 MiB combined stdout/stderr cap, no retry.
Killing the CLI does not establish immediate server cancellation. The source
branches retain overflow sentinel limits; canonical validation rejects excess,
foreign/duplicate/incomplete rows, bad arithmetic/citations and unexpected SAVED
or MISSING. Missing fields/errors never become a fabricated missing decision.

Before capture the original private export must still pass offline replay.
Stage B additionally requires a private successful current-SQL Stage A report
and matching manifest. No automatic Stage B call. This is operator tooling,
not connected to HTTP, normal startup or worker source credentials.

Unlike the earlier recovery export, raw clinical/decision inputs are validated
in memory only, not persisted or printed. New ignored 0700 directories / 0600
files retain only redacted SAVED/MISSING statuses, hashes, query ID, SQL hash,
code revision, timing and warehouse state. These reports are not replay backups;
the earlier private input bundles provide replay. Checksums are integrity checks,
not malicious-state or off-device/encrypted custody guarantees.

## Execution

Run A once, inspect success, then B once. Never overwrite or blindly retry.

```sh
uv run python -m scripts.test_source_statement output/statement-20261021-a --capture-stage A
uv run python -m scripts.test_source_statement output/statement-20261021-b --capture-stage B --prior-stage-a output/statement-20261021-a
```

The two preliminary context/warehouse statements already succeeded with reader /
NONE and CIQ_WH SUSPENDED. Live acceptance results will be recorded below only
after execution. Up to two final metadata-only warehouse checks are allowed;
including the preliminary pair the total bound is **14 explicit statements,
two source statements**. No dollar-cost or trial-balance claim from these caps.

## Remaining gates

Exact governed views, six runtime principals and approvals, PUBLIC/effective
privileges, enforced custody/clock/recovery/lifecycle controls, financial/clinical
display and authenticated API/UI acceptance remain open. This test alone does
not activate the raw adapter, complete P2, authorize P3 or deploy the website.

## Executed results

Code revision `a5a028e2ffc7b04c713ef66cb8de0dea6f342b65`. Both stages passed
without a retry; original private A/B captures also passed offline replay first.

| Stage | Cases / canonical result | CLI elapsed | Source query ID |
| --- | --- | ---: | --- |
| A | GOL001 SAVED | 8.792 s | `01c7e12e-0009-ac27-0002-055a0057b022` |
| B | GOL024 / GOL027 MISSING | 6.348 s | `01c7e12e-0009-a843-0002-055a0057a09a` |

The SAVED result passed existing schema/arithmetic/stored amount/outcome and
independent clause-citation validation, ignoring the stored schema flag as proof.
Record-ID evidence remains an empty fail-closed registry. MISSING follows
successful complete scoped reads, not a failure or demo substitution. No fresh
rules recomputation, financial-trace display or clinical disclosure acceptance.

Each result is one source statement containing bounded subqueries, not one
table read or proof of concurrent-writer behavior. Separate A/B stages are not
a shared snapshot. Reports remain private in ignored `output/statement-20261021-a`
and `output/statement-20261021-b`; no raw inputs were persisted by this tool.

**18 new offline tests; full root suite 193 passing**, repository Ruff,
changed-file formatting and whitespace checks pass. Backend/browser/build,
containers and remote CI were not rerun for this operator-only increment.
Both immediate warehouse observations were STARTED/idle pending auto-suspend;
the independent final state check is recorded separately below. Current exact
USD balance/expiry and incremental cost remain unmeasured; no paid purchase.

The first independent follow-up SHOW still reported STARTED with zero running/
queued queries. No administrative suspension or account changes were made;
a second bounded metadata-only check follows the idle auto-suspend interval.

The second and final independent SHOW confirmed **SUSPENDED**, zero started
clusters/running/queued. Total: **14 explicit statements, two source statements**;
connection setup is CLI-managed and separate. Follow-up SHOW query IDs were not
captured. No further source reads, explicit suspension or account mutation.

A new private offline rebuild archive at
`output/rebuild-offline-source-a5a028e` preserves committed revision `a1fbd77`
(including the acceptance tool and initial result documentation). Its integrity
verification passed, without a Snowflake call. The name identifies the tested
tool revision, not the archive HEAD. It is a code checkpoint, not a fresh source
export, complete DB restore or encrypted/off-device backup. Existing raw replay
bundles remain local/private. The original unrelated submission video is untouched.
