# Inactive fake-only agent ledger

2 November 2026. The PostgreSQL ledger is implemented and exercised with a fake
gateway. **It cannot admit a live execution grant.** No route, embedded worker,
provider SDK, credentials or Snowflake write is connected to it. The existing
deployed GCP images still use the earlier deterministic workflow and schema.

Implementation:

- `apps/api/src/ciq_api/agent_ledger.py`: short transaction boundaries and trusted
  scope capture; `FakeAgentLedger` is an engineering seam, not a live executor.
- `apps/api/src/ciq_api/agent_ledger_models.py` and migration
  `0004_agent_ledger`: four owned grant/operation/attempt/comparison tables.
- `apps/api/tests/test_agent_ledger.py`: 72 PostgreSQL crash, authority,
  concurrency, accounting, retention and publication checks. Public CI supplies
  disposable PostgreSQL 17; no operator Mac containers are needed.

## Implemented boundaries

The operation key binds tenant/request, input revision and digest, pinned
policy/product/rules/evidence versions, orchestration version and configuration/
source mapping digests. Correlation, browser command, grant and review assignment
versions cannot create another operation. The captured review version remains a
publication fence; a result is never silently rebound to a later review.

Fresh locked tenant, user, medical-officer membership, owned request, pinned
policy and open review establish authority before claim, submission and
publication. Inputs must match the latest append-only revision and existing
assessment digest. Policy approval must remain valid; the request must be
unassigned or assigned to that officer. Tenant-first locking matches current
MVP writers, then grant and operation locks serialize admission/accounting.
The submission transition also compares the captured state/version/fence.

Grants are immutable **fake-only** allowlists of exact operation keys and pinned
configuration hashes, with case/concurrency/unit limits and a fixed window.
Units are synthetic conservative admission counters, not currency, provider
usage measurements or a billing cap. Reservation and allowance updates commit
atomically. Each operation has at most one attempt, enforced by PostgreSQL.

A worker gets a 30-second renewable lease within an immutable deadline of at
most 120 seconds and the grant window. `begin_submission` commits the attempt's
stable submission ID and `submitting` state before returning a permit to the
test fake gateway. Only one concurrent caller wins. A crashed caller cannot
claim another submission, including the conservative gap where it died before
actually making its fake call.

Expired pre-submission operations release reserved units/concurrency, but retain
their operation key and admitted-case receipt. Expired submitted operations
become `unknown`, retain all uncertain units **and a concurrency slot**, and
never automatically return to a callable state. Recovery is status-only, takes
grant/operation locks without later acquiring workflow locks, and can account
for an abandoned operation after its user's capability was revoked. It neither
contacts a provider nor concludes that work or billing stopped.

Valid output is checked against the captured contract inside the final locked
transaction. The private comparison row and operation/accounting change commit
together. Retried local publication is idempotent; a storage failure rolls back
both. Stale inputs/review versions cannot publish; invalid output is rejected
without storing its raw body. No result changes `SubmittedCase.record`, a human
decision, review version, general audit, analytics or outbox. There is no API
that exposes these private comparisons to any role.

Composite foreign keys bind operations to owned requests/memberships/grants and
comparisons to the exact owned operation's attempt. Unique keys and append-only
triggers preserve receipts. Immutable operation/grant identity and limits, state
transition guards and version checks prevent resetting a terminal operation or
deleting a result to enable a replacement invocation through this seam.

## Verified faults and remaining work

The database tests cover concurrent duplicate enqueue, claim, submission and
publication; distinct cases competing for case/concurrency/unit allowances;
restarts before and after submission; unknown completion; lost fences and
heartbeat/deadline boundaries; revocation/unapproved policy/final review;
amendments; invalid/oversized outputs; publication rollback; cross-tenant and
wrong-operation references; immutable receipts and accounting constraints.
The earlier 146 contract/golden tests remain separate. Fake outputs are
canonical fixtures, not evidence of actual Cortex parity.
The restart faults reconstruct the ledger over new database sessions; they do
not kill PostgreSQL or a VM. The preview recovery suite exercises the new
schema with empty agent tables. A populated agent-ledger backup/restore and
post-restore no-resubmission probe remains an explicit pre-live acceptance item.

Before live integration, the remaining design in
[the durable-stage proposal](agent-run-ledger-design.md) still needs review:

- Separate clinical execution identity/process/database privileges and credential
  custody. Current same-database ownership is not production isolation.
- Governed request/policy/evidence transport and pinned tool/search mappings.
  Local evidence hashes do not create Snowflake permissions or source records.
- A provider adapter with supported remote-run checkpoint/lookup, bounded
  transport/poll timeouts, usage observations and explicit uncertain-run
  reconciliation. This seam intentionally cannot recover by resubmitting or
  release uncertain allowances. It has no remote cancellation guarantee.
- A reviewed shorter remote budget plus transport/validation margin, or an
  explicit contract change. The retained 120-second remote budget cannot simply
  fit inside the existing 120-second overall ceiling.
- Separately approved live case/configuration/window/attempt/spend limits,
  bounded golden comparisons, clinical display/retention policy and human
  acceptance. Live grants require a new reviewed migration/path; changing a
  configuration flag does not activate them.

Readiness and new backup manifests now require `0004_agent_ledger`. Offline
package verification still recognizes historical `0003_mvp` manifests for
custody/decryption; recognizing an old package does not certify a current-schema
restore. Retained cost receipts are forward-only. Existing cloud images and
their retained database are not upgraded by source or CI changes.
