# Bounded synthetic receipt process

24 November 2026. Manually launched source preparation, without service wiring,
deployment, provider calls or paid resources.

`ciq_api.agent_receipt_runner` replaces the test-only receipt server in the
packaged clinical/custody HTTP-to-result journeys. It opens the original retained
fake-only journal under a separate nonroot UID and serves the existing
kernel-authenticated protocol. It cannot create/reset/close an epoch, reconstruct
history, grant SQL authority, submit a child or retry an operation.

## Fixed operator delivery

The trusted operator supplies `/run/ciq-agent-receipts/peer.json`, at most 2 KiB,
with exactly protocol `ciq-fake-receipt-v1`, a fake epoch pin and distinct custody
UID. The shared descriptor-relative private-file reader requires safe root/runtime
owned ancestors, no symlinks or group/other write, and a single-link regular
runtime-owned `0600` leaf. Duplicate keys, extra fields, coerced UIDs, root UID,
storage/socket selectors, database credentials, commands and limit overrides fail.

The only journal is
`/run/ciq-agent-receipts/journal-parent/retained/fake-receipts.sqlite3`.
Before SQLite opens it, the same private-file reader checks its ancestors and
metadata and bounds the file to 256 KiB. Existing journal code opens `mode=rw`
and validates the active epoch before readiness. No missing directory/file is
created. Startup does not assert that receipt history agrees with SQL; every
existing protocol command retains its independent full-history checks. Journal
UID and root remain trusted, including against metadata races and file rollback.

The only endpoint is `/run/ciq-agent-receipts/ipc/peer.sock`. Binding never adopts
or unlinks a stale name. Existing client/server `SO_PEERCRED` checks run before
payload transfer; the fixed bounded canonical protocol, per-request deadline,
durable commit before ACK and fail-closed client behavior remain unchanged.

## Lifetime and shutdown

Launch the installed API Python with `-I -B -m ciq_api.agent_receipt_runner`, no
arguments/stdin, under the journal UID. The clinical runner's Linux identity,
clean environment, NoNewPrivs and capability checks run before private input.
Core dumps are disabled. A 60-second alarm bounds the whole process, a 10-second
accept timeout bounds idle waiting, and at most 32 sequential connections are
served. Rejected connections also consume that budget. The original two-second
protocol deadline still bounds connected framing; the process alarm also bounds
journal work. Limits cannot be selected through the plan or IPC.

Only successful existing-journal validation and binding emits
`fake_receipt_ready`. Reaching the connection limit closes the listener and exits
0 without additional output; this indicates no claim/publication success.
Startup, timeout, SIGTERM and serving failures emit only
`fake_receipt_unavailable` and exit 1, without private payloads or tracebacks.
The socket name and retained journal remain intact on exit. An explicitly
quiescent trusted operator must verify process exit before removing an owned
stale socket; runtime performs no repair or automatic restart.

This process does not spawn children and has no PostgreSQL connection. It is not
the production supervisor or durable storage policy. External resource limits,
whole-hierarchy cleanup for custody's separately sessioned child, UID lifecycle,
credential delivery/rotation, quiescence and restore reauthorization remain
operator activation work. Neither receipt startup nor a ready ACK authorizes
custody assignment, provider I/O, retries or refunds.

## Verification

Local checks pass 217 focused receipt/claim/custody tests, including 26 new
receipt-startup/lifetime checks; repository Ruff passes. These check strict fixed
plans, retained validation before readiness, denial of equal custody/journal UIDs, listener
and DB cleanup, connection bounds, alarms and fixed failure output. Existing
private-file and process-identity cases are reused without widening permissions.

Disposable Linux acceptance now launches this installed module in both HTTP
publication journeys, all eight custody pre-attempt denials and the missing
candidate-after-issue case. Seven added cases exercise six restart denials
(stale socket, wrong epoch, public plan, injected environment, missing journal
and root) and actual idle exit, preserving committed prepared history. The
combined suite expects 44 cases and retains its existing outer resource/time
limits and invocation-owned cleanup.

Accepted code `eca6b328f7f6c5b426241ebba849517c42fb7aeb` passes
[product CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/45326398663)
and [private-preview CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/45326398601).
All 44 combined cases pass in 210.04s with owned containers/image removed.
The separate receipt-peer suite passes 33 cases. Ledger acceptance passes 476
baseline checks, fourteen owner-fixture encrypted restores, 313 restricted
commands, 53 installation/retirement checks and 27 restricted restores.
Product passes 2,554 API checks (29 expected skips, two existing warnings), 69
client checks, 26 browser checks, fifteen source UI checks and eighteen MVP
journeys. Preview passes eighteen journeys and saved-workflow reopening after
restart (7.5s) and encrypted restore (7.0s). Both stack cleanup steps succeed.

The [clinical runner](agent-claim-runner.md) and
[custody runner](agent-custody-runner.md) remain manually launched fake-only
components. No worker, Compose/systemd entry, migration, runtime-bundle activation
or deployed image changed. Governed Snowflake/source/provider integration follows
operator activation; GCP rebuild/testing still requires a separate spend window.
