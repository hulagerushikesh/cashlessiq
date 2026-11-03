# Independent fake receipt observation

3 November 2026. Inactive disposable engineering only. No service, principal,
credential, role binding, source call or deployed schema change is activated.

## Selected next boundary

The custody verifier must obtain its own database history. A runtime-supplied
inventory, boolean or checkpoint digest cannot attest that a restored database
has not forgotten a later submission. The selected first step is a **separate
restricted receipt-observer login**, distinct from the clinical controller and
transport, with a no-argument history command. The observer compares that history
with separately retained fake custody while the database epoch remains locked.

The [SQL review package](../../deploy/agent-controller/receipt-observer.sql)
creates a separate nonlogin, nonadministrative definer and private schema. Its
protected registry pins login OID **and** name, database/epoch UUIDs and a window
of at most four hours; rows default disabled. No login or binding is created.
The runtime is granted no direct table/column access. Trusted disposable setup
explicitly grants only schema usage and `inventory_fake()` execution.

The command locks the singleton fake epoch first, then the registry entry. It
authenticates `session_user`, rejects administrative/inheriting roles and any role
membership, checks the exact epoch pin, and rechecks wall time after the history
query. A dropped/recreated or renamed login does not inherit authority. Missing,
disabled, future or expired bindings fail with a fixed quarantine error. Function
resolution is fixed to `pg_catalog, pg_temp`, RLS stays on, lock waits are bounded
at two seconds and PUBLIC execute is revoked within trusted installation.

The observer is deliberately **epoch-wide**, including historical work outside a
clinical controller's current case allowlist. Filtering by active tenant, user or
case could conceal forgotten work. It needs no current clinical membership and
cannot capture new clinical rows. It reads at most thirty immutable attempts and
the exact operation/grant fields needed for the existing checkpoint preimage;
31 attempts deny the entire observation, rather than returning a truncated view.
The returned inventory is bounded at four MiB in SQL and Python. Missing joins,
wrong types/epoch, duplicate case/operation/submission identities, extra fields,
naive timestamps or malformed material fail closed.

The historical operation snapshot and approval reference are sensitive and are
available **only to this trusted custody identity**, never returned by a browser,
controller command or transport IPC. They are needed to recompute the existing
Python canonical fingerprints. PostgreSQL JSON text hashing is not substituted.
No full source record, policy examples, candidate, general audit body, accounting
counters, mutable workflow state or credentials are projected. The definer has
only selected history-column reads and the minimum epoch-column UPDATE needed
for row locking; no operation/attempt/grant/comparison or human-workflow writes.
The private registry remains trusted operator authority, not protection against
its owner/database administrator or continuous privilege drift.

[`FakeReceiptVerifier`](../../apps/api/src/ciq_api/agent_receipt_verifier.py) uses
one trusted engine/schema and the already pinned journal. Its no-argument
`check()` compares the complete inventory inside the same database transaction,
including the independent SQLite transaction, and returns **None**. Shared
`checkpoint_from_material` preserves the exact owner-ledger canonical preimage,
including UTC instant normalization. Driver/SQL/validation/custody failures
suppress underlying private context. No inventory or epoch can be supplied to
`check()`, and no path/identity/file can be selected through IPC.

## This observation is not admission

A successful check is a point-in-time observation. It is **not** a ticket,
checkpoint, issue marker, refund, publication authorization or I/O permit. No
checkpoint/issue API or writable ticket table has been created, and no existing
controller/executor/startup path imports the observer. Existing owner-ledger
execution and the fourteen encrypted recoveries still use their prior path.

The next execution design must keep the custody identity in control of admission
and submission transactions, rather than returning an attestation for the
clinical runtime to present later. Only the independently authenticated custody
coordinator may receive future checkpoint/issue command capabilities; clinical
runtime must be denied those functions even when calling SQL directly. The
existing clinical commands bind `session_user`; a future coordinator must not
impersonate that login or accept caller-selected principal/tenant IDs as authority.
A protected operator binding and authenticated peer must authorize its exact
operation, clinical actor and scope before any future write command. Epoch-wide
history-read authority alone must not confer epoch-wide clinical execution.
The coordinator must hold epoch-before-clinical/grant/operation locks, observe full
history itself, commit external prepare before local checkpoint commit, retain
only original-process ephemeral issue permission and commit the single-use
external issued marker before child I/O. Restart cannot reconstruct that
permission. A rollbackable local ticket or cached successful observation cannot
replace these requirements, since an old restore can resurrect it.

The later [fake custody extension](agent-custody-submission.md) prepares
restricted checkpoint/issue commands on a custody-owned transaction. This observer
itself selects/installs no authenticated IPC/OS launcher, writable coordinator
capability or production custody service. The same-host private
SQLite journal remains fake-only, without protection from its owner, host loss or
rollback of both stores. There is no reset, automatic reconciliation or refund.
Missing, closed or contradictory custody conservatively denies observation.
The scope/registry tables remain outside the normal 22-table backup manifest;
no deployed restore, revocation or rotation compatibility is claimed.

## Verification

Offline checks cover full prepared/issued/empty comparison, exact epoch pins,
canonical timezone equivalence, malformed/oversized/duplicate projections,
missing/contradictory custody, fixed safe errors, transaction closure and no
transferable result. The opted-in disposable PostgreSQL CI suite uses real
separate password logins and owned database/schema/role cleanup. It checks
positive historical observation, effective PUBLIC/inherited ACLs and definer
metadata, controller/observer separation, role/binding denials, prepared/local
rollback gaps, bounded inventory, expiry while waiting and retention of the epoch
lock across external checking. No local Docker or paid environment is required.

Revision `499a6c7` passes [full product CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41612481036)
and [private preview CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41612481048).
All **37 new actual-login cases** pass alongside the prior 109 restricted capture/
reservation cases, 476 agent checks and fourteen encrypted recoveries. The new
**30 offline checks** pass in a combined 421-check offline agent/controller suite.
Full regression passes 1,027 root, 2,068 API (eighteen expected skips), 72 membership,
58 client, 26 browser, 15 source UI and all eighteen MVP journeys. Catalog,
transport isolation, process containment, contracts/types/lint/build and owned
cleanup pass. Preview separately passes eighteen journeys, encrypted 22-table
restoration and both saved-workflow browser reopenings with owned cleanup. The
fourteen agent recovery cases still use their prior owner-connected path; they
do not establish restricted submission/recovery integration. No API/worker/startup
imports the observer. No deployed role, binding, image, migration or source was
changed. GCP remains verified TERMINATED with its existing 1,800-second STOP;
no paid build/run, Snowflake call or local Docker startup was performed.
