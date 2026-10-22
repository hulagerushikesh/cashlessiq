# Inactive supervisor acceptance

22 October 2026. Owner explicitly approved implementation with **fake processes
and disposable state only**. This is not service-wiring, provisioning, spend or
deployment approval. Implements the modeled behavior in
[the operational control contract](p2-operational-control-design.md).

## Implemented slice

`apps/api/src/ciq_api/offline_supervisor.py` is a standalone, inactive model.
It has no executable, filesystem, network, process-launch, credential or database
implementation. Construction calls no adapters. Application startup, HTTP routes,
worker/membership manifests and default activation refusals are unchanged.

- Exact eight-role inventory, seven distinct authority-state identifiers,
  one generation and individual artifact/configuration fingerprints.
- Explicit one-use external-approval interface and verification before launch.
  The test adapter is disposable in-memory state, **not a durable authority**.
- STOPPED / VERIFYING / STARTING / READY / DRAINING / FENCED transitions; all
  eight acknowledgements bind attempt, generation, fingerprint and process
  incarnation. Stale/duplicate acknowledgements cannot advance the barrier.
- Own a returned process handle before inspecting its fallible incarnation.
  Partial launch failure cleans up known handles and remains fenced, because a
  raising launcher might hide an allocation. Unknown stop retains ownership.
- Mandatory numeric budgets, immediate capacity rejection/no waiting queue,
  immutable operation receipts, exclusive deadlines, strict elapsed-domain,
  rollback/gap/overflow rejection and another sample after approval callbacks.
- Retire delivery before cancellation or shutdown. Late/duplicate/forged/old-
  attempt receipts cannot deliver or release a slot twice. Uncertain cancellation
  fences the run; a known successful cancellation can retire an expired operation.
  Slow cancellation rechecks other deadlines. Observed cancellation/cleanup
  grace overrun fences even if an adapter claims successful termination.
- Cleanup still attempts every owned handle when clock sampling fails. Repeated
  stop never clears a fence. Recovery requires confirmed owned termination, an
  external retirement approval, a new generation and seven disjoint new state
  identifiers, then a separate fresh start approval and readiness barrier.
- No ledger initialization/repair/deletion, nonce refund, assessment retry,
  translation to MISSING, token/source-payload audit or raw adapter diagnostics.
  Audit is an explicitly bounded metadata ring; not a durable incident log.

## Verification and limits

Tests use fake handles, clock samples, readiness, approval and delivery adapters.
The recovery test creates a disposable operator evidence file and confirms its
bytes remain unchanged. No real guard file or secret is opened by the controller.
Root boundary tests confirm no application-main import, no worker/membership
packaging and only standard-library imports without I/O adapters.

The model requires **serialized, non-reentrant calls**. It is not a concurrent
server, scheduler, watchdog or process supervisor. A successful fake `stop` is
not OS termination evidence; a readiness receipt is not cryptographic attestation.
Elapsed samples are injected, not proof of suspend-aware host clocks. There is no
automatic polling thread: deadlines are checked when a method is called. A blocked
callback cannot be interrupted. Late observation/denial is **not a hard execution
or delivery deadline**, nor can this model recall a callback already invoked.

The approval interface only models external one-use/current-generation/retirement
decisions. It does not implement durable crash/restore fencing, key rotation or
retirement verification. Replacement-controller denial is tested using the same
fake external authority, not a claim that memory survives machine replacement.
Fingerprint checks validate identifiers, not real artifact/mount/key bytes.
Existing cryptographic guard and container acceptance remain separate evidence.

Fixture nanosecond budgets are deliberately tiny, **not deployment defaults**.
Normal startup remains unavailable. No real adapter or deployment wiring is added
until the operational package is selected, reviewed and separately approved.

## Reproduce offline

```sh
uv run --project apps/api pytest apps/api/tests/test_offline_supervisor.py
make product-test
uv run pytest -o addopts='' -q
uv run ruff check .
git diff --check
```

Verified: **105 focused supervisor tests; full API/PostgreSQL 1,003; root 203**.
Ruff, changed-Python formatting and whitespace checks pass. Both isolated
non-editable worker/membership canonical-package checks and default startup
refusals pass. Existing intentional invalid-model serializer warning remains in
one backend negative test. Real container topology, frontend/browser/build and
contract generation were not rerun locally in this internal-only batch.

Remote product CI for `8b2ab24` is confirmed successful: run `39785213296`,
checked on 23 October. This does not prove actual process containment or custody.
This milestone does not itself close P2 or raise its rough completion estimate.
See [release blockers](../product/deployment-readiness.md).
