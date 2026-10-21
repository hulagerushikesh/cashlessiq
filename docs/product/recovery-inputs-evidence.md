# Private synthetic replay inputs — captured evidence

21 October 2026. Owner's “go next” after the specific private-export approval
request accepted the [bounded scope](recovery-export-scope.md). No public
disclosure, runtime activation, grants, AI or deployment was included.

## Completed

- Offline exporter and 20 negative/control tests implemented before live reads.
- Root regression: **175 passed**; targeted Ruff lint/format and diff checks pass.
- Capture revision: `465979108dfbd8f9c57918d880e029077c942e05`.
- Stage A: GOL001/TPA001, five source SELECTs, 15 explicit statements,
  **12.698 seconds** including CLI execution/authentication.
- Stage B: GOL024 and GOL027/TPA003, nine source SELECTs, 23 explicit statements,
  **9.136 seconds**. Only started after A validated and persisted successfully.
- Both stages independently passed offline canonical replay after capture.
- One final metadata-only warehouse SHOW confirmed **SUSPENDED**, zero started
  clusters/running/queued: **39 explicit statements total**, 14 source SELECTs.
  The final SHOW's query ID was not collected; stage query IDs are retained below.
- GOL001: **SAVED**, canonical schema/arithmetic/stored totals and independent
  clause citations validated; record-ID registry remains empty/fail-closed.
- GOL024/GOL027: **MISSING**, only after successful complete owner-scoped reads.
  No recommendation was invented, copied from fixtures or generated.

The private ignored directories are `output/replay-inputs-20261021-a` and
`output/replay-inputs-20261021-b`. Each contains `inputs.json` and a SHA-256
`manifest.json`; directories are 0700 and files 0600. Raw inputs/conditions and
clinical decision prose are intentionally not committed or reproduced here.
Stage B records Stage A's input hash. Inputs include exact SQL/projection hashes,
code revision, capture time, elapsed duration, query IDs and derived observations.
No failed raw responses were saved. No off-device or encrypted backup is claimed.

Commands (offline unless `--capture-stage` is explicitly supplied):

```sh
uv run pytest
uv run ruff check scripts/recovery_inputs.py tests/test_recovery_inputs.py
uv run python scripts/recovery_inputs.py output/replay-inputs-20261021-a
uv run python scripts/recovery_inputs.py output/replay-inputs-20261021-b
```

Do not recapture/overwrite these destinations or automatically retry a failure.
Use the captured code revision if future SQL projections change. The offline
replay path has no connector dependency; the tests forbid subprocess/network
capture during verification. Both stdout and stderr are byte-bounded while
receiving live CLI results; timeout/overflow kills and reaps the local child.
A killed CLI is not proof of immediate server cancellation. Fixed server
statement/queue timeouts remain 30/15 seconds; batches are bounded, not coherent
transactions or a server-wide dollar limiter.

## Retained query IDs

Only metadata/provenance identifiers are listed here; source payloads stay private.

Stage A, context → metadata → member → conditions → decision → evidence → warehouse:

```text
01c7dfa4-0009-4ef4-0002-055a005694c6
01c7dfa4-0009-4ef4-0002-055a005694ca
01c7dfa4-0009-4832-0002-055a00573312
01c7dfa4-0009-4843-0002-055a0057518e
01c7dfa4-0009-a461-0002-055a0056f42e
01c7dfa4-0009-4832-0002-055a00573316
01c7dfa4-0009-4ef4-0002-055a005694d2
```

Stage B, context → metadata → four GOL024 reads → four GOL027 reads → warehouse:

```text
01c7dfa4-0009-4843-0002-055a00575196
01c7dfa4-0009-4843-0002-055a0057519e
01c7dfa4-0009-a461-0002-055a0056f436
01c7dfa4-0009-4832-0002-055a00573322
01c7dfa4-0009-4832-0002-055a00573326
01c7dfa4-0009-4832-0002-055a0057332a
01c7dfa4-0009-a461-0002-055a0056f43e
01c7dfa4-0009-4ef4-0002-055a005694ea
01c7dfa4-0009-4832-0002-055a00573332
01c7dfa5-0009-4832-0002-055a0057333a
01c7dfa5-0009-4832-0002-055a0057333e
```

## Limits / remaining work

This is three-case restricted synthetic evidence, not a full source backup,
fresh rules recomputation, clinical extraction archive, or production security
acceptance. Only the latest GOL001 decision was selected, not its complete history.
Separate queries do not establish snapshot coherence or tenant RLS. Live policy
rules, documents, DDL, PUBLIC/effective grants, runtime service identities, and
auth/API/UI acceptance remain outside this capture and retain their own gates.
The historical backend suite was not rerun for this standalone operator tool.
P2 stays open; no P3, website deployment, runtime startup or push occurred.
Exact remaining dollars, expiry and incremental costs remain unverified. Do not
buy credits or consume the balance simply because expiry is approaching.
