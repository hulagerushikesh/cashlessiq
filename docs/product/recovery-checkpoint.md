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
