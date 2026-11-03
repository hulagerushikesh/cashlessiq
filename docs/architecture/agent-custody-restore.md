# Populated encrypted restore through restricted fake commands

3 November 2026. Inactive engineering only. No deployed migration, installer,
startup hook, API/worker, source/provider call or GCP testing window is activated.

The [restricted restore suite](../../apps/api/tests/test_agent_custody_restore.py)
uses the existing real PostgreSQL dump/encrypt/transfer/decrypt/restore harness on
an explicitly opted-in disposable Linux CI service. The same exported read-only
snapshot supplies both the 22-table manifest and the dump. Each destination is a
new random database; verification compares every table's rows, columns and digest
before runtime operations. Transient decrypted transfer files are removed. The
source manifest is checked again after destination teardown, so restored runtime
writes cannot silently change source data. Cleanup drops only the database and
roles/schemas created by this harness.

The source database owner prepares fixtures and asserts destination rows; those
are trusted test operations. Historical source fixtures use their existing fake
clock; restored runtime recovery uses fresh database wall time without a caller
clock, identity rewrite or deadline extension. The restored fixture supplies **no owner ledger**.
Every runtime method on `FakeAgentLedger` is additionally replaced with a hard test failure
after restoration. Runtime capture, reservation, lease, history observation,
checkpoint, dispatch, private publication and recovery use the intended clinical
or separate custody connection, each authenticated as an actual nonadmin LOGIN.
No owner connection is supplied to those components or the fixed fake child.

## Restoration does not restore runtime authority

Normal product backups exclude the private capture/reservation/observer/custody
registries. `--no-owner --no-privileges` intentionally does not carry runtime ACLs.
The suite proves the destination has exactly the normal 22-table inventory and
none of those private schemas before trusted installation. A separate explicit
**disposable test installer** then installs the existing reviewed SQL packages,
creates fresh random nonlogin definers and two distinct restricted logins, revokes
new-database PUBLIC CONNECT/TEMP and public-schema access, and stages exact
principal, epoch, original grant/snapshot and operation assignments. This is not
an automatic production restore/rebinding tool.

Original epoch/database identifiers and retained external fake history remain
unchanged. Trusted staging revalidates each exact saved immutable request snapshot,
including its original correlation ID; an earlier fixture capture is insufficient
to replace that snapshot. No new epoch, grant, allowance, deadline or custody reset is created in
the destination. Clinical and custody bindings have independently configured fresh
windows. Disabled bindings stay closed even when function EXECUTE is available.
Both actual runtime connections are checked for their authenticated identities,
absence of superuser/TEMP and denial of direct product and private registry
reads/writes. The trusted SQL definers and host/process owners remain trusted.

## Acceptance cases

The fourteen journeys previously tested only through the owner ledger now have
restricted counterparts:

- Eight restored states: reserved, claimed, submitting, unknown, rejected,
  published, superseded and expired. Available agreeing history permits unused
  expiry/refund; submitted expiry keeps the slot and moves reserved units to
  uncertain. Final states remain unchanged. Repeated status checks settle once,
  submitted work cannot obtain another checkpoint/issue, and immutable receipts,
  snapshots, original deadlines and comparisons remain intact. Hashes of clinical,
  policy, identity, review, event, audit and outbox records match before/after
  every recovered workflow.
- Two unsubmitted operations, with and without an existing valid claim, complete
  their **first** attempt through restricted lease, original custody preparation,
  one bounded fake child and validated private publication before the original
  deadline. A replacement coordinator cannot reconstruct issue permission.
- Four older backups followed by a source checkpoint, issue, publication or
  quarantine retain external evidence that the restored SQL inventory forgot.
  Full history verification and checkpoint/dispatch fail closed; expired reserved
  cost stays held, with no child exchange, new attempt, refund or reset. A
  reservation receipt is only a database mapping, never external execution
  permission.

Thirteen additional cases cover nine binding/history faults, two concurrent
recovery settlements and two dropped/recreated same-name logins. Reusing a role
name with a new OID cannot inherit its old protected identity, even after explicit
command execution is granted again. Revoked custody EXECUTE/window/assignment or
wrong epoch/name denies status settlement. Missing/closed/orphaned external
history prevents unused refunds. Recreated clinical identity denies clinical
capture/checkpoint; status recovery intentionally continues with valid independent
custody authorization and requires no clinical capability.

Legacy rejected/superseded rows are preserved as historical source fixtures.
Their presence does not add those transitions to restricted publication: invalid
or stale private responses remain held submitting work until conservative unknown
recovery. The suite does not bypass that behavior to match the old owner ledger.

Revision `001241b060aaf050671d2482707c1fc148411d4c` passes all **27 new restricted
restore cases** in the
[dedicated disposable job](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41645239219/job/125948726097).
The same job passes 290 existing restricted-login cases, 476 existing agent checks
and the fourteen retained owning-fixture encrypted recovery baselines. Service
container cleanup succeeds. Local Ruff and 205 related offline checks pass; the
restricted suite skips before connecting on the owner's Mac. Actual login/database
acceptance never starts local Docker Desktop.

[Private owner-preview CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41645239508)
selects the same revision and passes eighteen MVP journeys, matched encrypted
22-table restoration and saved-workflow browser reopenings after both restart
and restoration. Fresh-volume and preview-stack cleanup succeed.

[Full product CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41645239219)
passes the same exact revision: **1,027 root** (three expected skips), 72 membership,
58 client, **2,243 API** (twenty-three expected skips/two existing warnings),
26 browser, 15 source UI and **18 MVP journeys**. Domain wheel, contracts/types,
lint/build, process containment, database catalog and separate transport isolation
pass. Main stack and service container cleanup succeed. Across the two restricted
steps, **317 actual-login cases** pass, including the new 27 encrypted restores.

A read-only check confirms GCP TERMINATED with its unchanged 1,800-second STOP;
Docker Desktop is off. No paid build/start, local container, live binding/schema/
image/credential change, or source/provider call was made. Deployed code remains
`7940886`/schema `0003_mvp`.

## Remaining gates

This is same-host fake custody in a disposable test environment. It does not prove
independent production retention, rollback of both stores, host-loss recovery,
production process/credential/peer isolation or safety against an administrator.
The deployment remains the earlier private deterministic preview. The later
[operator rehearsal](agent-controller-installation.md) now covers disposable
installation, effective PUBLIC/default ACL review, retirement and password
rotation without automatic reauthorization. Production installation/secret delivery,
deployed restoration/rebinding, independent Snowflake source capture and supported
provider submission/status/usage semantics remain separate work. Any live build,
source/provider usage or VM testing requires its exact scope and spend approval.
