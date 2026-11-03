# Original-custody restricted fake exchange

3 November 2026. Inactive disposable engineering only. No route, worker, startup,
service listener, provider, live credential or deployed schema is activated.

## Exact path

The [custody coordinator](../../apps/api/src/ciq_api/agent_custody_submission.py)
now accepts an optional exact `BoundedFakeProcess` instance at trusted construction.
Its command is fixed harness configuration. There is no callable factory, later
transport attachment or public command/credential/tenant/actor selector. A browser
or clinical peer is not given this object or the separate custody DB connection.
There is no service endpoint; same-process trusted construction does not prove
authenticated IPC peers or production secret/process isolation. The existing
bounded process clears inherited environment/FDs and reaps its owned group, but
this same-UID local test is not an OS/file/network sandbox. Separate container
isolation remains a distinct CI probe, not deployed custody acceptance.

After confirmed `prepare()`, the original instance can call **either** `issue()`
(sacrifice dispatch) **or** `dispatch()` (one fake exchange). Both return None.
A stage lock serializes pending-state removal before any DB work, including two
threads calling the same object. A new coordinator cannot reconstruct permission
from the committed checkpoint or independently retained issued receipt. There is
no reusable "checked" flag, local ticket, receipt IPC handoff or automatic retry.

`dispatch()` independently observes the entire bounded epoch and checks retained
history on one custody connection/epoch transaction. The existing protected
`issue_fake` command rechecks exact assignment, clinical identity/membership,
current policy/review/input, staged snapshot/configuration/source/grant,
operation version/fence, original deadline and lease. Its internal projection now
includes the exact checkpoint plus DB `checked_at` and effective deadline, bounded
by operation deadline, lease, grant and **both clinical and custody principal
windows**. This projection is internal data, not permission exposed to a peer.
No new command, direct runtime table access or mutation privilege is granted.

The coordinator independently selects the exact immutable inventory material,
revalidates its full `AgentInput`, and builds the existing process envelope from
those records: tenant, operation, attempt/submission, configuration/source,
snapshot and effective deadline. Nothing in the browser/child response chooses
these values. Existing Python canonical checkpoint hashes are unchanged.

Before external issue, it requires positive remaining budget after the existing
two-second persistence margin. It subtracts the **entire monotonic elapsed time
from before connection/locking** from the DB sample's remaining interval and also
caps by local UTC remaining time and the ten-second fake process maximum. A slow
local wall clock cannot enlarge the DB budget; a fast one may conservatively deny.
It rechecks after external issue/local commit and after the child returns. This
is not an accepted production boot/suspend/host-health clock contract.

Single-use external issue commits first. Only after the local transaction exits
successfully does the coordinator call its fixed bounded process once. No DB
connection or clinical/epoch lock stays open during child I/O. Ambiguous commit,
expired margin or child failure loses this original process's permission; the
external receipt and reserved allowance remain held. A timeout, crash, malformed
reply or missing response never permits another submission or refund.

The framing-validated reply stays in private coordinator memory. It is **not yet
clinically validated**, persisted or exposed as a comparison. `dispatch()` returns
no candidate, receipt or permission. Human review and accounting remain unchanged;
the operation remains submitting for the later narrow publication/recovery path.
Process-memory access, trusted configuration and DB/private registry ownership
remain trusted. Same-host SQLite is fake retained custody, not host-loss/admin or
rollback-of-both protection.

## Verification and remaining acceptance

Offline checks cover exact independently bound envelope, real bounded children,
no public result/selector, single-use/concurrent calls, restart denial, external
history/SQL failures, malformed or enlarged time projections, clock skew, elapsed
budget across external issue/commit/return, ambiguous commit and child timeout,
stderr, crash, flood and invalid frame. Guarded Linux CI exercises actual separate
restricted logins and the fixed stdlib canned-fixture process, fresh clinical and
custody denials, both principal windows, durable issue before child startup and
lock release, exact immutable checkpoint, unchanged human review/accounting and
absence of comparison publication. The owning fixture is used only for operator
setup/assertions; custody executes through its restricted login throughout.

Revision `5a4b91c` passes **39 new offline checks** in the combined **491-check**
offline agent suite, repository Ruff and all four SQL template-format checks.
The [actual-login job](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41627015668/job/125886788579)
passes **205 restricted-login checks**, including **24 new dispatch checks**,
the existing 476 agent checks and fourteen encrypted recoveries. The latter
still use the owner-connected baseline, not restricted execution/recovery.

[Full product CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41627015668)
passes 1,027 root, 2,138 API (twenty expected skips), 72 membership, 58 client,
26 browser, 15 source UI and all eighteen MVP journeys. Catalog, transport
isolation, process containment, contracts/types/lint/build and owned cleanup pass.
[Private preview CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41627015530)
separately passes eighteen MVP journeys, matched encrypted 22-table restoration
and both saved-workflow browser reopenings. Fresh-volume/stack cleanup succeeds.
Both complete workflows select code revision `5a4b91c`.

A fresh read-only check confirms GCP TERMINATED with the unchanged 1,800-second
automatic STOP; Docker Desktop is off. No local container, paid GCP build/run,
provider/source call or deployed image/schema/role/binding change was performed.

Next add narrow submitted heartbeat and **private validated comparison
publication**, with independently checked history and fresh clinical pins under
epoch → bindings → clinical rows → grant → operation locks. Do not expose the
private raw candidate as an outcome or let it finalize a human review. Then add
conservative recovery through intended restricted commands: no clinical locks
after grant/operation locks; submitted unknown retains units/slot even when custody
is unavailable; never-submitted refund requires available, agreeing full history.
No lost reply or missing custody permits retry/refund/reset/new epoch.

Successful publication, revocation/concurrency/child fault journeys and all
fourteen populated encrypted restore journeys still need that restricted path.
The existing fourteen owner-connected recoveries remain a fixture baseline, not
restricted acceptance. Independently retained production custody, authenticated
peer/secret isolation, deployed restore/close/revoke/rotation, effective PUBLIC/
default ACL review, independent live source capture and supported provider
timeout/submission/status semantics remain separate gates. No live grant,
production installer or automatic reconciliation is added.

For the next coordinator step, consume the private candidate before attempting
publication, independently check full retained history on the same connection,
obtain fresh protected clinical scope and validate the candidate with the shared
Python deterministic/citation validator while those locks remain held. Do not
accept caller-supplied "validated" attestations or invoke the owning ledger to
bypass the restricted commands. A failed/ambiguous publication must not make the
original I/O permission reconstructible. Submitted heartbeat may maintain the
current fence/lease within the original deadline/window; it must not create a
new attempt, reclaim a submitted operation or extend the original deadline.


The later [private publication extension](agent-custody-publication.md) implements
the next heartbeat/validation stage above. Its separate acceptance record retains
restricted recovery/restore and production custody/source gates. The dispatch
acceptance in this document describes revision `5a4b91c`, before that extension.
