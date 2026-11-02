# Inactive fake admission quarantine

2 November 2026. Implemented only for disposable synthetic engineering. No API,
worker, service startup or deployed configuration enables this path. A fake
approval reference, epoch or receipt does not authorize a live provider call.

## Default and custody

Migration `0005_agent_admission` creates an append-only, fake-only singleton
anchor **without a row**. `FakeAgentLedger(engine)` refuses reservation, claim,
heartbeat, submission and publication. Capture and explicit fake-grant creation
remain test/operator helpers; neither grants transport permission. Status-only
expiry recovery stays available and retains submitted uncertainty. It releases
never-submitted reservation units only when independent history is verified;
unverified/contradictory custody retains even an expired reservation. That
reservation status is not transport permission.

Only the explicit `FakeAdmissionGate.provision_empty_for_tests` helper can
bootstrap a test epoch. It checks for no prior operations/attempts or accounted
units and refuses an existing anchor. It creates a new private directory and
SQLite file outside the product PostgreSQL backup, with separately pinned random
database/epoch identities. It never overwrites an existing directory. Failed
partial provisioning leaves unusable custody; it does not repair or reset it.
Neither migration, restore, startup nor a caller-supplied command provisions an
epoch automatically.

The fixed-file fake adapter uses SQLite FULL synchronous transactions, bounded
storage and a one-second lock wait. Reopen requires the existing private regular
file, matching owner and epoch, and an active identity. Missing, malformed,
oversized, public or symlink custody fails with `agent_admission_quarantined`.
The journal stores only tenant/request/operation/submission identifiers, an exact
immutable checkpoint digest and prepared/issued status. Its digest covers the
attempt, actor, captured-snapshot hash, source/configuration, original deadline,
grant identity, approval-reference hash, window and allowance. Timestamps are
canonical UTC instants, independent of the database session time zone. No raw facts,
policy wording, response, credentials or connection parameters are stored there.
Quarantine tracebacks suppress underlying file/SQLite failure details.
Identifiers/hashes still require private custody.

This is **a fake durable adapter, not selected production custody**. Same-host
files do not survive host loss, prevent their owner from altering SQLite/schema,
or authenticate an independent operator. Restoring/rolling back both stores can
erase both histories; local hashes cannot detect that. Live custody must be
separately retained, access controlled and reviewed before use. No service or
paid storage has been selected/provisioned.

## Ordering and conservative failure

All admission methods first lock the singleton anchor, then acquire the existing
clinical/grant/operation locks. They compare the complete bounded local attempt
inventory with independent receipts. Missing, extra or changed receipt identity
blocks the entire epoch, including another case/new grant. The fake epoch holds
at most thirty receipts. There is no pruning/refund or automatic new-epoch path.

1. Submission validates fresh membership, review, mapping, fence and deadlines.
2. It flushes the sole local attempt inside the PostgreSQL transaction, then
   commits the independent **prepared** receipt before committing PostgreSQL.
3. Only the originating coordinator instance retains ephemeral permission to
   issue this exact newly committed permit. Restart never reconstructs it.
4. Immediately before fake child I/O, a fresh transaction rechecks custody,
   clinical scope, exact permit, state/version, lease and approval window. It
   atomically changes the independent receipt from prepared to **issued**.
5. After that durable marker, the bounded fake executor rechecks its remaining
   local budget, starts at most one child and publishes through fresh validation.

The two stores are deliberately **not atomic**. If external prepare commits but
PostgreSQL rolls back, the orphan external receipt quarantines admission. If
PostgreSQL commits but the coordinator exits before issue, restarting cannot
obtain its ephemeral permission. If issue commits but the caller exits, times
out or fails before child startup, it still cannot reissue. Expired submitted
work becomes unknown and keeps concurrency/uncertain allowance. An expired
reservation also keeps its allowance if independent history cannot be verified:
a restored database may have forgotten the submitted attempt. Lost external
custody cannot be recreated from a restored database. A terminal external
quarantine has no clear/reopen API. There is no automatic reconciliation,
resubmission or refund because a process/lookup failed.

An old backup can restore matching anchor IDs and plausible old grant counters
while omitting a later attempt. The separately retained receipt then disagrees
with local history and denies every new admission. A normal restored constructor
also defaults closed. CI's existing post-checkpoint restore cases explicitly
supply their retained fake authority as a test attestation; that is not automatic
production restore approval. Before any real restore, an operator must close
admission externally and reconcile independently retained execution history.

## Verification and remaining boundaries

Offline checks cover journal persistence across abrupt process exits, concurrent
prepare/issue, exact identity drift, private file validation, lost/corrupt custody,
terminal quarantine and bounds. Disposable PostgreSQL checks cover default denial,
bootstrap refusal, immutable anchors, external/local commit gaps, fresh revocation,
no permit rehydration and conservative unknown recovery. Actual child tests observe
the independently committed issued marker before startup.

Four additional encrypted dump/restore cases take a backup **before** a later
checkpoint, issue, publication or terminal quarantine. They restore all 22 tables
into a separate disposable database and prove the forgotten attempt cannot be
repurchased or replaced by a new epoch. The original ten populated recoveries
continue to cover retained receipts, guarded valid first submission and expiry.
Revision `93abcdd` passes [product CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41459570300)
and [preview CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41459570298):
27 offline journal/UTC checks, 22 PostgreSQL admission cases, the existing 427
agent checks and all fourteen populated encrypted recoveries. Full product,
transport containment/cleanup, browser and 22-table preview recovery pass. See the
[delivery status](../product/delivery-status.md) for counts.

The controller still has an owner-level test connection. This gate does not
prevent arbitrary database owners from resetting counters or bypassing code.
Narrow runtime database commands/principals, independently captured source
provenance, production secret/receipt custody and supported bounded provider
semantics remain pre-live work. No claim of exactly-once remote execution,
actual provider usage limits or protection against a privileged host operator.
See the [executor boundary](agent-executor-boundary.md).
