# Restricted conservative fake recovery

3 November 2026. Inactive engineering only; no API, worker, startup, provider,
live installation, binding or deployed schema/image is activated.

[FakeCustodyRecovery](../../apps/api/src/ciq_api/agent_custody_recovery.py) uses
the separately authenticated restricted custody connection and an exact protected
request/operation assignment. Its no-argument `recover()` returns None, creates
no transport, and never reconstructs the original coordinator's pending issue or
private response. Replacement instances may check status; they cannot retry an
exchange or publish a lost response.

The same transaction first independently observes the full bounded epoch inventory
and compares it with retained external custody. A savepoint isolates denied SQL
observation so a failed/closed/missing/contradictory journal cannot accidentally
abort the outer conservative status transaction. Verified history keeps the epoch
lock through settlement. No command accepts a caller's history, tenant, actor,
clock, candidate or validation boolean. The journal is only read; no automatic
repair, new epoch, issue, quarantine reset or reconciliation is attempted.

The [SQL extension](../../deploy/agent-controller/custody-recovery.sql) has two
public custody commands. `recover_submitted_fake` cannot release unused reserved
allowance. `recover_verified_fake` requires the trusted custody program's independent
full-history comparison on this transaction and repeats SQL inventory authorization
before settling. SQL cannot inspect SQLite; the separately credentialed custody
program and database/registry owners remain trusted. Neither command is granted
to the clinical runtime. An accidentally granted clinical login still fails the
protected custody identity/assignment checks. The private implementation's refund
boolean is not executable by the runtime.

Recovery locks epoch → custody principal/assignment → grant → operation, with no
clinical locks or current clinical capture, including after acquiring grant/op.
The custody principal must still be enabled, in its independently configured live
window, pinned to the same epoch/database and exact nonadmin NOINHERIT login with
no role membership. The exact request/operation/tenant/actor assignment remains
required. Clinical membership revocation, closed review, stale facts or a disabled
clinical capture binding does not prevent conservative status recovery. Missing
local epoch or expired/disabled custody authorization denies recovery and leaves
allowance held; unavailable external history alone permits status settlement.

Fresh database wall time determines expiry. A submitted attempt becomes unknown
only after its current lease or original deadline expires. Its reserved units move
to uncertain and **its concurrency slot remains held**. A never-submitted reserved
operation expires and releases units/slot only after its original deadline and
only with available agreeing full history. An orphan external receipt, even for
another tenant, blocks that refund. Existing final states and live work are no-ops.
An exact local attempt is required for submitted settlement; inconsistent local
state never authorizes a refund. State/version/accounting settle atomically once;
explicit repeated or concurrent status checks do not settle again.

The definer adds only selected uncertain-unit read/update to previous privileges.
No deadline, snapshot, fence, grant identity/limits/window, attempt, comparison,
human review, audit, outbox or analytics write is added. PUBLIC execute is revoked;
runtime receives command execution only, with no direct table access. Effective
production PUBLIC/default ACL review and credential/process/peer isolation remain
separate gates; the same-host fake SQLite file is not production custody.

Offline sequencing checks cover independent history, lost/closed/orphaned custody,
malformed observations, denied SQL/savepoint rollback, commit errors and strict
configuration. Actual restricted-login CI covers atomic unknown/unused settlement,
cross-tenant forgotten history, independent clinical locks during recovery,
clinical revocation/drift, exact custody authorization, concurrent checks, commit
rollback, effective privileges and accidental clinical execute grants. Acceptance
revision `b7734100d6cc1597210ab38ac0e02735f771d3f5` passes **61 new checks**:
**22 offline** and **39 actual restricted-login** cases. The related local offline
suite passes 205 checks. The
[dedicated restricted job](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41633083440/job/125907313307)
passes all **290 restricted-login checks**, 476 existing agent checks and the
fourteen existing owning-fixture encrypted recoveries.

[Full product CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41633083440)
passes 1,027 root (three expected skips), 72 membership, 58 client, **2,243 API**
(twenty-two expected skips/two existing warnings), 26 browser, 15 source UI and
all eighteen MVP journeys. Catalog, transport isolation, process containment,
contracts/types/lint/build and owned cleanup pass.
[Private preview CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41633083591)
passes eighteen MVP journeys, matched encrypted 22-table restoration and both
saved-workflow browser reopenings. Fresh-volume/stack cleanup succeeds. Both full
workflows select exactly `b7734100d6cc1597210ab38ac0e02735f771d3f5`.
Local Ruff, SQL template formatting, inactive import boundary, edited links and
diff whitespace checks pass.

A read-only check confirms GCP TERMINATED with its unchanged 1,800-second STOP
and Docker Desktop off. No paid build/run, local container, source/provider call,
or deployed role/binding/schema/image changed. The deployed private preview still
selects `7940886`/schema `0003_mvp`; this acceptance is inactive engineering.

Next move the fourteen populated encrypted restore journeys through the intended
restricted commands. Their existing database-owning fixture remains a baseline,
not restricted restore acceptance. The private registries are outside the normal
22-table product backup; deployed restoration/rebinding/revoke/rotation remains
unaccepted. No production source/provider submission or paid window is needed for
this step.
