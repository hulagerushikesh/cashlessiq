# Restricted fake reservation and lease commands

3 November 2026. Inactive disposable engineering package. Not a production
installer, independent admission verifier or provider submission capability.

## Authority and commands

[`reservation.sql`](../../deploy/agent-controller/reservation.sql) extends the
[capture capability](agent-controller-capture.md) in the same trusted installation
transaction. Its protected `reservation_scope` table defaults disabled and binds
one authenticated login/request to an exact fake grant, database/epoch IDs,
captured snapshot, stable operation key, configuration/source digests and timeout
of at most 120 seconds. The package creates no login, binding, scope row, grant or
epoch. The trusted disposable operator validates the snapshot and computes the
key through shared Python contracts using `FakeReservationApproval`; PostgreSQL
does not substitute its JSON serialization for canonical Python fingerprints.
No caller can supply a tenant, actor, grant, snapshot, digest, clock or epoch to
the runtime commands.

`reserve_fake(request, timeout)` locks the local epoch, protected binding/scope,
fresh clinical rows, allowance and prior operation, in that order. It compares
the exact owned projection to the staged snapshot, then verifies the fake grant's
key, mapping, window, case/concurrency and total unit limits. A new reservation
inserts one owned operation and increments admitted/in-flight/reserved allowance
atomically. Its deadline is bounded by the requested/operator maximum, original
120-second bound, grant end and principal end. Concurrent duplicates return the
same minimal receipt without changing the owner, grant, deadline or accounting.
Another grant cannot repurchase the same operation. Cross-mapping replacement
and unresolved prior work remain fenced under the clinical locks.

`lease_fake(request, operation, version, fence)` claims only a still-reserved
operation, or renews its current unexpired fence. It rereads fresh clinical scope,
the exact staged snapshot/grant and the original deadline under locks. Claims
require no active lease; heartbeats require the exact current version/fence.
Reclaiming an expired lease generates a new fence and retains the original
deadline. Neither path changes allowance or operates on submitted/terminal work.
The wall clock is checked after waiting for the allowance/operation locks.

The nonlogin definer gets only existing clinical capture privileges plus epoch
reads/row locking, grant reads and three accounting column updates, operation
reads/inserts and version/fence/lease column updates. It cannot create a grant,
update operation state/deadline/snapshot, refund via a command, change consumed or
uncertain accounting, write an attempt/comparison or finalize a human review.
The definer owns its private scope table, which remains trusted operator
authority; runtime receives no table privileges or membership in that role.
Only capture and the two public commands are executable by the test login.
The private context helper is not executable by runtime/PUBLIC. All functions
fix object resolution, RLS and a two-second lock timeout, with PUBLIC execution
revoked before commit. No dynamic SQL or object replacement is supplied.

[`ControllerReservation`](../../apps/api/src/ciq_api/agent_controller_reservation.py)
provides typed minimal receipts and fixed safe failures; errors suppress private
driver/SQL/clinical context. The service constructor selects a trusted engine and
restricted installation schema, never a browser/IPC selector. No route, worker,
executor or startup imports the client.

## Deliberate boundary before submission

These commands are **reservation-only fake engineering**. They do not replace
`FakeAgentLedger` or independently verify external receipt history. The local
epoch match catches a wrong binding; it does **not** detect an older same-epoch
backup missing a later submission. A reservation/lease receipt is never an I/O
permit, external issued marker, independent source observation or publication
authorization. The runtime has no attempt, comparison, refund, release,
reconciliation or grant-creation command. Held allowance stays held, including
after timeout, because no recovery/refund command is implemented here.

The [independent fake receipt observer](agent-receipt-observer.md) now prepares
a separate restricted history-reading identity, with no ticket or I/O permission.
Before checkpoint/issue/publication can be exposed, design and test an
independently authenticated custody/admission command path that cannot be bypassed
by directly invoking SQL as the runtime. Passing a caller-selected boolean or
digest saying "journal checked" would not establish that authority. Preserve
epoch-before-clinical/grant locking, full bounded history, external prepare before
local commit, single-use issued markers, no replay and conservative unknown cost.
Then run the successful clinical execution/concurrency and fourteen populated
encrypted recovery journeys through the restricted path. Existing owner-level
ledger/executor recovery tests do not establish that missing integration.

The private binding/scope tables remain outside the normal 22-table migration and
backup manifest. No deployed restore/rotation compatibility is claimed. Effective
PUBLIC/default grants and ownership need target-specific review before an exact
forward/revoke proposal. A trusted operator/database administrator can modify
staged authority; this package is not protection against that administrator or a
continuous privilege-drift detector.

## Verification

Offline checks cover malformed requests before connecting, bounded timeouts,
fixed schema selection, typed transitions, safe failures and strict disabled
operator staging. Dedicated CI uses the existing exact-repository/Linux/explicit
opt-in/fixed dummy PostgreSQL 17 guard, a new disposable database, unique schemas,
actual restricted password logins and owned cleanup. It checks successful held
allowance/leases, duplicate and concurrent reservations/claims, every allowance
limit, stale facts/review/policy, disabled/wrong epoch scope, expiry while waiting,
replacement fences, lease replay, transaction rollback and effective ACLs. No
local Docker, GCP VM, Snowflake source or provider is needed.

Revision `a5a0e87` passes [full product CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41582984895)
and [private preview CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41582984446).
All **50 new actual-login cases** pass alongside the 59 capture cases, existing
476 agent checks and fourteen encrypted recoveries. The recovery cases still use
the existing owner-connected ledger; restricted submission/recovery acceptance
remains outstanding. The **27 new offline cases** pass, with 391 combined offline
agent/contract/controller checks. Full regression passes 1,027 root, 2,038 API
(seventeen expected skips), 72 membership, 58 client, 26 browser, 15 source UI and
all eighteen MVP journeys. Catalog, transport isolation, process containment,
contracts/types/lint/build and owned cleanup pass. The private preview separately
passes eighteen journeys, encrypted 22-table restoration and both saved-workflow
browser reopenings, with owned cleanup. An earlier fixture tried rewriting an
immutable approval; the accepted fixtures instead create new grants and valid
historical rows without disabling any trigger. The superseded product run was
cancelled and cleaned up. No live install, paid build/run or local Docker startup
was performed. The GCP VM is verified TERMINATED with its 1,800-second STOP.
