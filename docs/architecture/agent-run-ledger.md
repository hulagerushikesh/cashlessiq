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
- `apps/api/tests/test_agent_ledger.py`: 90 PostgreSQL crash, authority,
  concurrency, accounting, retention and publication checks. Public CI supplies
  disposable PostgreSQL 17; no operator Mac containers are needed.
- `apps/api/tests/test_agent_ledger_recovery.py`: ten populated, encrypted
  snapshot/dump/restore checks on the explicit disposable CI PostgreSQL service.

## Implemented boundaries

The operation key binds tenant/request, input revision and digest, pinned
policy/product/rules/evidence versions, orchestration version and configuration/
source mapping digests. A separate application fence rejects changed config/source
digests for the same request while any nonexpired operation exists, including
terminal results. Unresolved submitting/unknown work also blocks new input
revisions under unchanged digests. Only expired, never-submitted work can change
mapping under a new exact fake grant. This fence runs at reservation and again
before the submission checkpoint under existing tenant/request locks; it is
not a new SQL uniqueness constraint or provider reconciliation path. Correlation,
browser command, grant and review assignment
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
Eighteen additional PostgreSQL cases cover cross-version replacements, concurrent
configuration admission, unresolved amendments and rechecking old reservations
at submission. Populated restore also rejects changed config/source attempts on
retained published results. The earlier 146 contract/golden tests and 122 offline
source-mapping checks remain separate. Fake outputs are
canonical fixtures, not evidence of actual Cortex parity.
The original restart faults reconstruct the ledger over new database sessions;
they do not kill PostgreSQL or a VM. Populated recovery is now separately tested
in ten CI cases: reserved, claimed, submitting, unknown, rejected, published,
superseded and expired states, plus two valid pre-submission recovery paths.
Current backups contain all 22 tables and nonempty grant/operation/attempt/
comparison tables. The shared read-only manifest and `pg_dump` use one exported
snapshot. The existing encrypted-transfer helper encrypts/decrypts through
separate disposable keyrings before `pg_restore` loads a newly created database.

Restored row/column hashes, stable attempt/submission IDs, private comparisons
and allowance totals match. Expired work cannot resubmit, unknown work retains
uncertain units/concurrency, changed grants cannot repurchase the same operation,
and repeated recovery is idempotent. Restored append-only/state/fake-only guards,
one-attempt uniqueness and exact operation/attempt foreign keys still reject
invalid mutations. Unsubmitted work within its original deadline may obtain its
first permit and publish once; restore does not reset the deadline. The source
schema remains unchanged and the temporary restored database is dropped.
The ordinary preview still covers encrypted full-volume restore/browser reopening
with empty agent tables; populated recovery uses a separate database on the
CI service. Neither suite proves crash-consistent provider execution, recovery
off-machine backup custody or actual provider behaviour. The new stale-backup
fake gate is described below.

In particular, restoring a backup taken *before* an actual submission can lose
that receipt. The [fake quarantine gate](agent-admission-quarantine.md) now denies that gap
using independently retained test receipts; live execution still needs reviewed
external custody and operator reconciliation. Do not interpret the populated checkpoint tests as
exactly-once remote execution across point-in-time rollback.

Recovery revision `ac48b19` passed the dedicated
[disposable PostgreSQL job](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41423257127/job/125203629399):
218 existing contract/ledger checks in 12.88 seconds, followed by all ten populated
recovery checks in 9.36 seconds. The shared probe remains self-contained for
execution inside the preview container. Ordinary API runs skip the CI-only
restore tests unless an explicit service ID is supplied; Linux/GitHub/repository,
exact container image, localhost database and generated restore-target checks
precede its mutations. No operator Mac Docker or GCP VM is started by this suite.

Source-mapping/replacement revision `3436411` also passes the
[dedicated disposable job](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41425980997/job/125212572250):
358 combined checks (146 contract, 122 mapping, 90 ledger) and ten populated
restores, including the changed-digest denial after recovery. Full product and
private-preview CI pass. The [executor boundary package](agent-executor-boundary.md)
records implemented fake process/restore gates and the remaining production
identity, privilege and custody work.

Before live integration, the remaining design in
[the durable-stage proposal](agent-run-ledger-design.md) still needs review:

- Separate clinical execution identity/process/database privileges and credential
  custody. Current same-database ownership is not production isolation.
- Governed request/policy/evidence transport and pinned tool/search mappings.
  The [source mapping preparation](agent-source-mapping.md) records the concrete
  identifier/version/normalization gaps. Local hashes do not create Snowflake
  permissions or source records.
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

Readiness and new backup manifests now require `0005_agent_admission`. Offline
package verification still recognizes historical `0003_mvp`/`0004_agent_ledger` manifests for
custody/decryption; recognizing an old package does not certify a current-schema
restore. Retained cost receipts are forward-only. Existing cloud images and
their retained database are not upgraded by source or CI changes.


## Inactive process integration — 2 November

The [fake executor seam](agent-executor-boundary.md) now uses the committed
submission permit for exactly one bounded child exchange. The permit includes
mapping/configuration hashes and the effective minimum of operation deadline,
claim lease and approval window. Publication checks those pins and rejects an
extended effective deadline; no route or worker calls this seam. Thirteen
additional PostgreSQL tests verify checkpoint visibility before process start,
private-only publication, malformed/invalid results, revocation/review drift,
child crashes/timeouts, conservative unknown recovery and no replay. The ninety
original ledger and ten populated recovery tests remain separate.

The stdlib fake artifact has no database credential, client package or network
in its disposable isolation test. The controller connection still owns its test
schema: these process checks do not establish controller database least
privilege. Direct grant-counter DML is not a safe runtime capability just because
identity/state guards exist; counters intentionally remain mutable for trusted
transactions today. The next database boundary must restrict runtime commands,
protect accounting and fresh scope locks, and deny direct human-workflow writes.
No production role/grant/SQL command function is provisioned by this batch.


## Default-closed fake admission — 2 November

Migration `0005_agent_admission` creates a fifth agent table without an anchor
row. The [fake gate and independent receipt adapter](agent-admission-quarantine.md)
are explicit disposable test capabilities; ordinary ledger construction cannot
admit or issue transport. All admission writers lock the anchor first and compare
local/external attempt history. Submission prepares external custody before local
commit; fake I/O requires a separately committed single-use issue marker and
fresh clinical validation. Restart does not reconstruct permission. The new
offline/PostgreSQL fault tests and four pre-checkpoint encrypted restores cover
missing, contradictory, closed and rolled-back local history. Status-only expiry
recovery remains available without opening admission. Production custody and
database least privilege remain required; no deployed database is migrated.
