# Private pre-expiry recovery checkpoint

This is a partial, synthetic operator checkpoint, **not a Snowflake database
backup**, production activation, or P2 exit. It preserves committed numbered
SQL, seeded generator/goldens, canonical domain code, source adapter code,
dependency locks, tests and product/security documentation in `rebuild.tar`.
It excludes the submission video, local credentials, environment files and
untracked files. The archive includes existing committed synthetic fixtures;
it does not replace them with live source observations.

## Bounded capture

From the repository root, with the existing `cashlessiq` CLI profile authenticated:

```sh
mkdir -p output
uv run python scripts/recovery_checkpoint.py output/recovery-20261021 --capture
uv run python scripts/recovery_checkpoint.py output/recovery-20261021 --verify-only
```

The destination must not already exist. Its parent must exist. New directories
are mode 0700 and files mode 0600. Keep the ignored directory private; do not
upload or commit the archive. Hashes detect accidental corruption, not malicious
replacement of both the artifact and manifest. Preserve them together on trusted
private storage; there is no encrypted backup/off-device durability claim.

Capture runs exactly one CLI invocation, no retry, maximum 180 seconds client
wait. Session statement/queue timeouts are 30/15 seconds. Eleven explicit SQL
statements: session timeout/tag configuration; five queries each followed by a
query-ID lookup. Three queries read source tables, only for GOL001/TPA001 and
GOL024/GOL027/TPA003, capped at four rows and refusing anything other than the
three expected pairs. Context must be reader/NONE; the CLI selects those roles
explicitly before SQL. No account security changes or source writes.

The captures contain metadata, saved-row counts, clause-reference counts and
warehouse state. No raw clinical notes, conditions, decision payloads, clause
text, demographics, extraction, agents, search or Streamlit. These are separate
statements, **not a coherent snapshot**. Saved-row counts are not canonical
decision validation, and zero rows do not by themselves validate runtime MISSING.
Reader-visible monitor null does not override the owner's admin confirmation.

Errors are generic; raw CLI stdout/stderr is never printed or saved. On failure
an incomplete directory can remain, with no success manifest; inspect the cause
before any retry, using a new destination. Killing the client does not guarantee
instant server cancellation; server timeouts provide a separate bound. CLI login
may require owner interaction. Connection setup statements are CLI-managed and
not counted as the eleven explicit SQL statements.

No exact dollar/credit cost is measured. Warehouse reads may resume CIQ_WH;
after capture independently check `SHOW WAREHOUSES LIKE 'CIQ_WH'` under the reader
and confirm its 60-second auto-suspend. Do not mutate the monitor or shared
resources. No larger batch until cost/expiry and existing security gates permit it.

## Offline replay/rebuild

`--verify-only` performs no Snowflake/network calls. It checks hashes, safe
archive entries, retained evidence scope and query IDs. It is an integrity and
metadata replay check, not a full database restore. After verification, extract
the trusted archive into a **new private empty directory**, never over a working
checkout. Use Python 3.11 and the frozen `uv.lock`. Run the canonical schema/rules
and source history/recommendation unit tests there with Snowflake disconnected.

Do not execute setup/teardown SQL automatically during recovery: account features,
roles, grants, clinical masking, human onboarding approvals, runtime credentials
and exact tenant isolation need review on the eventual target. New funded access
is not assumed. Future raw recovery inputs/live definitions require a separately
reviewed bounded disclosure scope; this checkpoint intentionally cannot restore
all historical decisions, source documents, account definitions or grants.

## Completed checkpoint — 21 October 2026

Tool/rebuild revision: `d81838f`. Private ignored bundle:
`output/recovery-20261021` (not pushed). Eleven explicit statements completed in
25.062 seconds; exactly three bounded source SELECTs. No raw source payloads,
AI, writes, grants, deployment or runtime activation. Saved-row counts remain
2/0/0 for GOL001/GOL024/GOL027; each case has 35 clause references.

Captured query IDs, in query order (context, metadata, saved counts, clause counts,
warehouse):

- `01c7df9b-0009-4ef4-0002-055a005694aa`
- `01c7df9b-0009-a597-0002-055a00574262`
- `01c7df9b-0009-4832-0002-055a005732f6`
- `01c7df9b-0009-4843-0002-055a00575182`
- `01c7df9b-0009-4ef4-0002-055a005694ae`

Offline manifest/evidence/archive verification passed. The verified archive was
extracted into a new mode-0700 temporary directory; imports were confirmed from
that restored `src` tree, not the working checkout. **127 canonical schema/rules/
source-decision/history/recommendation tests passed**, using the already installed
Python 3.11 environment without any Snowflake call or dependency installation.
This is not a clean-machine dependency install, complete application rebuild,
new-account restore or validation of fresh raw saved decisions.

Full working-tree root regression: **155 passed**, including ten checkpoint
tests; targeted lint/format and whitespace passed. No API/browser/container/remote
CI rerun for this operator-tool increment. The first metadata-only follow-up
found STARTED/idle; the subsequent follow-up confirmed **SUSPENDED**, zero started
clusters/running/queued. Total thirteen explicit SQL statements including those
two follow-ups; follow-up query IDs were not collected. Exact incremental cost,
remaining USD balance and expiry time remain unverified.

The temporary restored tree and private bundle remain local. No encrypted or
off-device copy has been made. Full raw recovery/live definitions and all existing
P2 isolation/credential/clinical-projection/live API/UI gates remain open.
