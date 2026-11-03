# Restricted fake custody checkpoint and issue

3 November 2026. Inactive disposable engineering only. No provider dispatch,
production service, IPC listener, deployed principal or schema is activated.

## Exact custody authority

The [SQL extension](../../deploy/agent-controller/custody-submission.sql) installs
after capture, reservation and independent observation in one trusted disposable
setup. It uses the separate nonlogin receipt definer and authenticated custody
login. A protected `submission_scope` defaults disabled and pins that custody
login to **one exact operation**, request, clinical controller OID/name, tenant and
actor. The template creates no login, assignment, grant or epoch. Trusted test
setup explicitly stages/enables the exact assignment after reservation/claim.

Epoch-wide historical observation does not authorize epoch-wide clinical writes.
The clinical runtime cannot call checkpoint/issue or their private helpers, even
if public command execution were accidentally granted: its `session_user` still
fails the separate custody binding. Custody has no direct product or registry
access and no grant accounting, comparison, human-action or refund commands.
Its definer gains attempt INSERT, operation state/version UPDATE and only grant
ID UPDATE for row locking. Existing observer history reads are retained; operation
reads also cover the mutable state/fence/lease checks. No grant limit, deadline,
lease, snapshot or immutable attempt can be rewritten through these commands.

Capture/reservation now share private `_capture_bound(oid, request)` and
`_reservation_context_for(oid, request)` helpers. Ordinary runtime wrappers still
resolve only their own authenticated `session_user`; runtime cannot execute the
helpers or choose a tenant/actor/login. Only the receipt definer receives the
private reservation-context capability. Its command resolves the clinical OID
from the protected assignment, checks the pinned name and exact tenant/actor,
then rereads the existing protected reservation approval and fresh clinical rows.
No role impersonation, session GUC identity, caller-selected principal or synthetic
"journal checked" flag is used. Any role membership now also denies the clinical
principal, matching the independent observer's role checks.

`checkpoint_fake(request, operation, version, fence)` authenticates custody,
locks epoch, binding/assignment, clinical scope, grant and operation in that
order. It verifies exact staged snapshot/key/configuration/source/grant, current
clinical access/policy/review, original deadline and current lease/version/fence.
It rechecks the custody window after lock waits and the clinical deadline before
writing. Only reserved work without a prior attempt can append one DB-generated
attempt/submission identity and move to submitting at version +1. Accounting,
lease, original deadline and human review stay unchanged. Cross-mapping or
unresolved historical work on the case denies replacement.

`issue_fake` rechecks those same fresh boundaries against the committed submitting
checkpoint and exact immutable submission identity. It writes no local issue flag
or ticket. SQL alone does **not** inspect independently retained custody: the
separate custody program/credential is trusted to own the external comparison and
transaction. Granting these commands to a normal clinical process, or exposing
arbitrary SQL/credentials from custody, would invalidate the boundary.

## Transaction sequencing

[`FakeCustodySubmission`](../../apps/api/src/ciq_api/agent_custody_submission.py)
is explicitly constructed by trusted fake test code with a separate engine,
already-pinned journal and exact request/claim. It has two no-argument methods;
both return **None**, no inventory, receipt, attestation or I/O permit.

1. `prepare()` independently obtains full bounded epoch history on the custody
   connection and compares it with retained history while holding the epoch.
2. On that **same connection and transaction**, it calls the protected checkpoint
   command, rereads the full independent inventory, validates the exact added
   immutable material and computes the unchanged shared Python checkpoint hash.
3. It commits external prepare before allowing the local transaction to commit.
   A local rollback or ambiguous commit retains the external receipt and closes
   later admission. Only after confirmed commit does the original coordinator
   retain ephemeral pending issue state. A failed stage cannot be retried by that
   instance, and a new instance cannot reconstruct that state from local rows.
4. `issue()` removes that pending state **before** any connection/work. It
   independently rechecks full history on a new custody transaction, calls the
   fresh protected issue check and commits the single-use external issued marker
   before returning. A failed or ambiguous stage cannot be replayed. Issued cost
   stays held even if the following local transaction fails.

This is fake checkpoint/issue preparation, **not transport integration**. No child,
network I/O, candidate publication, refund or recovery is performed. Returning
None is not authorization for another process to dispatch later. A future trusted
coordinator must couple original-process issue to the bounded transport itself,
with fresh deadline margins, authenticated peer dispatch and process/secret
isolation. In-process test construction is not proof of an authenticated OS/IPC
peer. The existing executor and fourteen encrypted recoveries still use their
owner-connected ledger; they must be moved to the intended restricted path before
that integration can be claimed.

Same-host SQLite remains fake custody, not protection from its owner, host loss
or rollback of both stores. Database/private-registry owners and custody-process
memory remain trusted. Protected registries remain outside the normal 22-table
backup manifest. Deployment restore/close/revoke/rotation compatibility and target
PUBLIC/default ACL review remain open. There is no automatic reconciliation,
reset, new epoch or production installer. No ordinary API/worker/startup imports
this module.

## Verification

Offline checks exercise exact transaction sequencing, independent writes before
local commit, ambiguous commit/rollback gaps, no transferable result, original
instance single-use state, typed selectors, changed checkpoint material, lost or
closed custody, SQL failures and inactive runtime imports. Guarded actual-login
CI checks real checkpoint/issue through the two restricted logins, concurrent
claims, protected assignment drift, clinical revocation and expiry after lock
waits, exact effective ACLs, direct-SQL denials, epoch locking across external
writes and conservative cost retention. Existing capture/reservation/observer
and full product/preview regression are required for acceptance.

Acceptance results will be recorded after CI completes. No local Docker or paid
GCP/Snowflake operation is required for these tests.
