# Prepared manual single-call entries — 27 November 2026

Three entries now wire the tested components. **No installer, service unit,
application route or generic worker selects them.** This is source preparation,
not an installed supervisor or approval to activate a provider.

| Entry | Exact UID/GID | Fixed private plan | Process alarm |
| --- | --- | --- | --- |
| `ciq_api.agent_single_call_runner` | 53002 custody | `/run/ciq-agent-custody/single-call.json` | 25 seconds |
| `ciq_api.agent_single_call_receipt_runner` | 53003 receipt | `/run/ciq-agent-single-call/receipt.json` | 25 seconds |
| `ciq_api.agent_single_call_provider_runner` | 53004 provider | `/run/ciq-agent-provider/plan.json` | 15 seconds |

All require Linux, isolated Python with bytecode disabled, no arguments, exact
real/effective/saved UID/GID, empty supplementary groups, zero core limits,
NoNewPrivs, no effective/inheritable/ambient/permitted capabilities and only
locale environment variables. Fixed private files retain descriptor-based
ancestor, owner, mode, size, link and duplicate-key checks. There are no stdin,
environment or CLI selectors. Errors are fixed redacted messages. SIGALRM and
SIGTERM stop the entry; the future supervisor must enforce whole-group cleanup.

The strict `ciq-single-call-custody-v1` plan contains database/login names and OIDs,
a custody-only password and the full reviewed pin. It cannot supply a host, port,
DSN, SQL schema, command, candidate, response, path, timeout or retry option.
Only loopback PostgreSQL port 5432 is used with fixed connect/statement/lock/idle
limits and NullPool. Every physical connection verifies the exact database/login
and rejects owner/privileged roles and memberships. Protected SQL checks the
independent installation, authorization and clinical scope again.

Custody constructs the exact two clients bound to the full pin and runs one
original `ProductSingleCall`. It cannot reconstruct a checkpoint, claim a generic
job, create history or read a provider credential. Engine disposal runs on all
outcomes. Success means original local advisory publication completed; it does
not reconcile usage/cost. Lost acknowledgments remain uncertain without retries.

The `ciq-single-call-receipt-v1` plan contains only the full reviewed pin. Receipt
startup checks the fixed existing journal and ancestors at
`/var/lib/cashlessiq-agent/single-call/retained/single-call.sqlite3`.
Missing, invalid, issued or observed history prevents binding. Runtime never
provisions, repairs, deletes, adopts, resets or substitutes history.

New `serve_attempt()` uses one original listener for exactly `issue`, then
`observe`. It authenticates custody before either frame. Each accepted frame,
journal transaction and ACK keeps its two-second budget. A fixed 22-second outer
envelope includes waiting between connections for provider work; custody's
eighteen-second clinical deadline is unchanged. Status-first, observe-first,
duplicate issue, wrong identity/pin, framing faults and lost ACKs terminate the
pair. There is no reconnect loop, new listener, path unlink/rebind or recovery.
The existing `serve_once()` contract is unchanged.

Provider startup validates the existing private v2 full canonical pin before
binding. The provider identity checks that same plan and opens its provider-only
token only after authenticated complete v2 custody framing. This entry does not
open the token directly. The existing twelve-second exchange budget includes
waiting for custody; there are no retries, alternate credentials or redirects.

Still required: a reviewed trusted supervisor must stage actual consent and
disabled SQL assignments, independent retained history, separate credentials and
matching full pins; validate actual provider/model and spend; create fresh IPC
directories with exact ownership; confirm receipt/provider readiness before
custody; and kill/reap every owned process on exit. Readiness is not consent.
Do not replace existing fake service units with these entries.

Installed host acceptance must verify read-only runtime, private files, cleared
groups, memory/CPU/task limits, no swap/core, whole-group cleanup, custody-only
loopback PostgreSQL and provider-only reviewed HTTPS/DNS egress. No broad egress
policy is installed here. External clock fencing and retained-history rollback,
restore/quarantine and off-host retention remain necessary. SQLite alone is not
off-host recovery proof.

Offline tests check strict plans, fixed wiring, existing history only, consumed
history denial, cleanup and redacted outcomes. Disposable Linux UID tests check
one receipt endpoint across a provider-sized wait and reject reordered commands
before mutation. These do not substitute for host acceptance or a paid live call.

The prepared [single-call launch coordinator](agent-single-call-supervision.md)
now enforces original peer readiness, invocation-bound output, fresh host checks,
clock/elapsed limits and all-role cleanup through a trusted adapter contract.
It includes no installed host adapter or activation path. Disposable Linux tests
compose the actual three runner entries with substituted SQL/HTTPS work; they do
not establish installed host containment or off-host recovery.
