# Protected captured single-call product adapter — 27 November 2026

The inactive [`ProductSingleCall`](../../apps/api/src/ciq_api/agent_single_call_product.py)
connects the [original prepared custody](agent-single-call-custody.md) to protected
product admission and advisory publication. It has **no application route,
generic worker, production migration, installer or service entry**. Adding this
code does not enable a provider, create an approval, authorize spend or deploy it.

## Protected authority

[`single-call.sql`](../../deploy/agent-controller/single-call.sql) is a separate
review package after `scope-capture.sql`. Existing fake-only grant, receipt,
operation and controller commands remain unchanged. Its nonlogin definer owns:

| Object | Purpose |
| --- | --- |
| `installation` | One disabled-by-default database name/OID, reviewed database UUID and epoch UUID. |
| `authorization` | One disabled-by-default, owner-staged operation, custody/clinical identities, tenant/actor/request, exact canonical reviewed pin/hash, captured snapshot and configuration. |
| `comparison` | One private advisory candidate and observed raw-response association for that operation. |

There is only one authorization slot per installation. The runtime cannot insert
a second call, renew a window, change a pin, regrant units, reset a phase or read
tables. A trigger rejects in-place static authorization changes and backward
phase changes. Re-enabling a consumed row does not restore it to `staged`.
No permission to drop/recreate an installation follows from an exhausted call.

The database/registry owners and trusted provisioning remain an explicit trust
boundary. They must establish actual owner consent and stage the exact reviewed
approval, synthetic scope, identities, provider plan, attempt/window and allowance.
An approval digest does not establish that consent. No owner approval or live
registry is staged by this implementation. Table owners/root can defeat local
triggers; this package does not claim to prevent a malicious administrator.

Only a distinct, independently authenticated **trusted custody** login can receive
three commands: `checkpoint(uuid)`, `publication_context(uuid)` and
`publish(uuid,jsonb,jsonb)`. That credential must not belong to the API, clinical
controller, receipt owner or provider. The functions derive it from `session_user`,
pin its name and OID, require a login with NOINHERIT/no privileged role flags/no
memberships, and delegate only the operator-pinned, distinct clinical principal.
Caller GUCs, search path, role switches and caller-selected tenant/actor values do
not choose clinical scope. The clinical principal has the existing checks too.

The separate capture definer retains its narrow product grants and private
`_capture_bound` command. Custody's definer can call that helper and read only
the necessary clinical principal locator/window columns. Custody itself gets
neither capability-table reads nor direct clinical, human-decision or fake-ledger
writes. All commands use fixed qualified names, hardened search paths, row
security on, a two-second lock timeout and no PUBLIC execution.

## Original transaction and I/O sequence

1. The original adapter consumes its `dispatch` entry before connecting. SQL
   locks installation, authorization, clinical principal, tenant, user,
   membership, submitted case, policy and review in that order. The existing
   capture checks current medical-officer membership, assigned/open review,
   approval/rejection events, revision facts and the principal window.
2. Inside that transaction, Python strictly validates the exact canonical pin
   and hash, operation, snapshot, fresh protected clinical projection and
   configuration. The existing assembly recomputes binding/source/request/config
   hashes and matches both exact peer types to the full pin digest. Corruption,
   stale revisions, changed policy/record digests or changed provider configuration
   roll back before any independent receipt/provider command.
3. SQL changes `staged` to `checkpointed`. **Confirmed local COMMIT precedes
   receipt issue and provider I/O.** A failed/ambiguous commit stops this original
   object. A consumed database checkpoint is never reconstructed as permission.
4. With no clinical database connection or transaction held, the original
   assembly issues the retained receipt, performs at most one reviewed provider
   exchange and retains the response observation. It returns no response/permit.
5. `publish()` consumes only that original private reply. A fresh protected
   transaction repeats current authority checks and verifies unchanged original
   pin/snapshot/configuration and the original deadline. Under those locks,
   shared clinical validation consumes the original candidate. The narrow SQL
   command checks binding/internal UUID and the unknown-usage observation shape,
   inserts the advisory and changes `checkpointed` to `published` atomically.

No method accepts caller clinical data, candidate, provider response, receipt
status, callback, actor, tenant or configuration. `run()` is one dispatch followed
by one publication. Methods return `None`; errors use one fixed redacted code.
The original lock prevents competing/repeated entries from reusing in-memory
state. Separate objects contend on the protected row, with one checkpoint winner.

SQL cannot execute shared Python clinical validation or authenticate a remote
response. The exact custody program, its memory and its separate credential are
trusted. A compromised custody executing SQL directly can forge an advisory;
these commands must never be exposed as browser/controller endpoints. Authentic
peer/body/pin association and receipt observation belong to the original program.

## Time, revocation and ambiguity

The original eighteen-second envelope begins **before** database connection and
lock waits. SQL samples current time after its clinical locks and caps the window
at the clinical principal end, reviewed pin end and eighteen seconds. Python
conservatively translates that remaining interval using its earlier monotonic
sample, deducting all elapsed connection/validation/commit time. The assembly's
optional absolute monotonic ceiling can only shorten its own eighteen seconds.
It never creates approval or widens the twelve-second provider process budget.

SQL rejects insufficient time before checkpoint and rechecks expiry after waits.
Publication retains the original monotonic ceiling and accepts only a nonwidened
database deadline. SQL checks time again immediately before insertion; Python
checks before/after command and commit. A late/lost commit acknowledgment is
ambiguous and never triggers publication or provider retries. This is a bounded
admission/publication design, not a kernel scheduling or hard wall-clock guarantee.
External clock fencing and cancellation remain supervisor work.

Admission linearizes under the locked authority checks before checkpoint commit.
Revocation after that point cannot cancel work already admitted/in flight. It
does prevent publication when committed before the fresh publication lock/check.
Review finalization, reassignment, revision/version changes, policy rejection,
principal expiry and disabled owner authorization likewise deny a later advisory.
No database lock is held over remote work merely to delay revocation.

Lost issue ACK means no provider launch. Lost observation ACK means no candidate
handoff even when observation committed. Invalid clinical answers may be observed
but never saved as comparisons. All issued units remain uncertain, including
after an accepted advisory; reported token counts remain unknown, never zero cost.
No human review decision, audit, outbox or analytics record is written by this path.

A product rollback could restore `staged`; the independently retained issued
journal still denies reissue. Database name/OID checks also deny casual clone/name
reuse, but do not detect rollback in the same database. The tests simulate that
rollback deliberately in a disposable database. They are not an authorized reset
procedure or off-host retention proof. Missing/rolled-back/reprovisioned independent
history must be quarantined by the future restore/provisioning process.

## Acceptance and work still required

Offline tests use actual local sockets/SQLite with fake database transactions and
explicit OS/remote overrides. They cover strict material, original/reconstructed
attempts, failed/lost checkpoint and publication commit acknowledgments, elapsed
budgets and lost peer ACKs. An existing Mac malformed-frame test also accepts
Darwin's specific `ENOTCONN` early-close result while retaining the no-provider check.

The existing disposable PostgreSQL 17 CI job additionally exercises real restricted
logins, default-disabled authority, effective ACLs, concurrent checkpoints, lock
ordering, role changes, revocation, fresh revisions, policy rejection, exact
protected projections, no connection during peer I/O, independent history after
a product rollback and unchanged human/fake ledgers. Provider exchange stays
synthetic. Linux UID/worker isolation remains the separate guarded receipt job.
Hosted results must pass before claiming PostgreSQL acceptance for this package.

Remaining activation work:

1. Review and assemble the manual supervised runtime, separate credential delivery,
   reviewed provider v2 plan, durable independent journal and owner-staged disabled
   database assignment. Validate effective host/service/IPC/network/filesystem
   policy, retained-history recovery/quarantine and clock fences together.
2. Review actual provider identity/model support, response shape, latency, usage
   semantics, exact synthetic case, one attempt and expected spend. Obtain explicit
   owner approval before any paid provider/cloud action or enabled live staging.
3. Run the bounded deployed synthetic comparison, confirm uncertainty/history,
   then add the permission-checked advisory UI read/projection and joint human
   testing. Keep the generic job retries and human decision path separate.

Captured-product facts are still not an independently verified Snowflake source
mapping. The existing governed-source/recovery work remains necessary for that
later profile. This code does not activate production data processing.
