# Independently authenticated fake receipt peer

3 November 2026. Inactive disposable engineering. No deployed service, provider,
credential, database role, schema or image is changed. The private GCP VM and
local Docker remain off. This is one process-boundary acceptance step, not
production operational custody or live-agent readiness.

## Boundary

The [fake peer](../../apps/api/src/ciq_api/agent_receipt_peer.py) separates the
retained SQLite journal owner from the original custody coordinator. Trusted
construction pins one filesystem Unix socket, fake database/epoch, server UID
and different custody UID. Both sides require Linux, nonroot real/effective/saved
UID equality and kernel `SO_PEERCRED` identity. The client verifies the server
**before sending any history**; the server verifies the caller before framing,
parsing or opening SQLite. A payload cannot claim its own identity.

The fixed parent chain must contain only real directories owned by root or the
journal UID, with no group/other write. Abstract sockets, symlinks, a public
writable `/tmp` ancestor, missing/non-socket endpoints and path adoption fail
closed. Only the trusted supervisor can replace the path after quiescing peers.
`bind()` does not unlink a stale socket. Socket connect permissions alone do not
establish authority: the fake listener deliberately permits unauthorized peers
to connect so tests exercise kernel-identity rejection.

Linux's [Unix socket reference](https://man7.org/linux/man-pages/man7/unix.7.html)
defines `SO_PEERCRED` credentials at connect/listen, pathname permissions and
discarded `SCM_RIGHTS` descriptor behavior. Python's
[socket reference](https://docs.python.org/3.11/library/socket.html) documents the
bounded timeout and `recvmsg` interface used here. This is Linux-only, with no
Mac authentication fallback.

## Protocol and failure behavior

One connection carries one length-prefixed, canonical JSON command and a write
half-close. The entire frame, EOF and response share a two-second monotonic I/O
budget. Requests are at most 32 KiB and thirty receipts. Extra frames/bytes,
truncated headers/bodies, duplicate JSON keys, noncanonical/coerced values,
ancillary descriptors, unsupported versions/commands and epoch mismatches fail
before mutation. No received file descriptor is installed.

Only `check`, `check_issued`, `prepare` and `issue` exist. Payloads contain exact
receipt identifiers/digests, never policy/facts, credentials, a journal path,
tenant/actor selector or transferable I/O ticket. Responses are fixed success or
denial bytes; Python methods return None. There is no journal provision, close,
reset, refund, epoch rotation, reconciliation, inventory dump or execution API.

Existing FULL SQLite commits still happen **before** acknowledgment. Losing a
reply or process after prepare/issue preserves the marker. A client instance
permanently closes after any denial, timeout or malformed/lost response; there
is no retry/fallback. A replacement client can observe status against a full
expected inventory but cannot reconstruct the original coordinator's private
pending issue or response. The existing coordinator consumes those private
values once and still decides whether a bounded fake child may run.
Peer-call latency does not reset an operation, principal window, lease or grant
deadline. The coordinator's original monotonic exchange/publication budget
includes those calls. A committed marker followed by an expired budget still
sacrifices execution; no reply loss purchases another attempt or refund.

The verifier/submission/recovery accept exactly either the original fake journal
or this concrete peer client, not arbitrary duck-typed callbacks/subclasses.
The owner-ledger fixture path is unchanged. There is no CLI, listener loop,
thread, compose service, API route, worker registration or startup activation.
The trusted disposable test supervisor explicitly starts bounded peers.

## Acceptance

The offline protocol suite validates canonical shapes, unsupported authority
selectors, duplicate/oversized histories, encoding faults and platform/UID guards
without opening a socket. The separate guarded Linux CI suite uses actual
different nonroot UIDs, a root-owned private `/run/ciq-receipt-peer-*` hierarchy,
cleared child environments, no inherited file descriptors and bounded processes.
It runs inside a separate disposable CI image containing only selected source,
dependencies and dummy test helpers, with no host mounts or network. A read-only
root filesystem and bounded `/run` and `/tmp` tmpfs hold invocation-owned files.
The trusted supervisor alone retains the six capabilities needed to change UID,
own fixture files and kill/reap children; peers drop to their separate identities.
The image/container have bounded memory, CPU, PID and descriptor limits and are
removed in the CI harness's finally block. The runner checkout and its credential
configuration are never made accessible to the synthetic UIDs.
It exercises client and server authentication, cross-UID file denials, original
coordinator checkpoint/issue, no replacement permission, invalid frames and
descriptor handoff, lost acknowledgments, peer restart, retained issued markers,
concurrent single issue and malformed/trailing/missing acknowledgments,
closed/missing custody and unsafe/stale socket handling. Every process and only
the invocation-owned directory are removed in fixture cleanup, including setup
failures before the fixture yields.

Revision `2f7444c5cc51b1453ded3dd9bfb784013d7ef699` passes **33 actual Linux peer
cases in 214.77 seconds** in the
[dedicated job](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41676442415/job/126058232809).
The harness requires that exact all-passed count plus a stopped container with
exit code zero, no OOM/error, and reviewed actual isolation/resource metadata.
Every child also verifies nonroot real/effective/saved UID equality, zero
effective/permitted/ambient capabilities and `NoNewPrivs=1`. Both internal
process/file cleanup and outer container/image cleanup pass.

The **38 new offline cases** pass locally; 270 related checks pass together.
Repository Ruff, documentation links and the manual-launch guard pass. The local
launcher refuses before Docker; ordinary testing skips the root/Linux opt-in
suite before starting any process or file fixture.

The same revision's existing restricted-login job passes 476 agent checks,
fourteen owner-fixture restores, 290 restricted commands, 53 installation/
revocation/rotation cases and 27 restricted encrypted restores. Its
[private preview workflow](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41676442365)
passes eighteen MVP journeys, matched encrypted 22-table restoration and saved
workflow reopenings after restart (6.7s) and fresh restored-volume replacement
(6.1s), with both cleanup stages successful.

[Full product CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41676442415)
passes that same exact revision: 1,027 root (three expected skips), 2,281 API
(twenty-five expected skips/two existing warnings), 72 membership, 58 client,
26 browser, fifteen source UI and eighteen MVP journeys. Domain wheel,
contracts/types/lint/build, process containment and catalog/transport isolation
pass. Both PostgreSQL-service cleanup steps and main-stack cleanup succeed.
The GCP VM remains TERMINATED with its unchanged 1,800-second STOP; local Docker
is off. No paid build/start, live source/provider call or deployment occurred.

The fake peer does not open a PostgreSQL connection, query Snowflake, call a
provider or create an allowance. The coordinator integration case uses its
existing deterministic offline SQL-engine double; full actual-login lifecycle
tests continued separately at that checkpoint. The subsequent combined
acceptance below joins the peer, actual logins, child, publication and recovery;
combined restored-state acceptance remains open.

The initial CI setup exposed a test-only `Path.chown` mistake, corrected to
`os.chown` with cleanup registered before setup. The runner's private home
directory then denied synthetic UID interpreter access; no runner permissions
were widened. The dedicated copied runtime above solves that boundary. Its
complete process suite needs over three minutes, so the initial 180-second
container deadline was replaced with a bounded 240-second run. Final acceptance
checks the actual test count and container state, never just launcher success.

## Combined restricted database acceptance — 3 November

The later [integration suite](../../apps/api/tests/test_agent_peer_database.py)
passes **eleven cases in 73.16 seconds** at revision
`e973c4cda0eafa704ef92e1347a5a0e0ccd07648` in the
[dedicated CI job](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41681911155/job/126077487485).
Actual distinct clinical and custody OS UIDs receive only their respective
restricted PostgreSQL credentials through private stdin. They assert exact
`session_user`/`current_user`, denied direct product/private table reads, zero
capabilities, `NoNewPrivs=1` and denied journal/supervisor-file reads. Calling any
owner-ledger or direct-journal method in those runtime processes fails the test.
The journal process alone opens retained SQLite; it has no DB credentials.

The original custody process checks retained history, checkpoints, issues,
exchanges with the existing bounded canned child, heartbeats and validates a
private comparison through actual restricted SQL. The successful journey checks
one attempt/comparison, original deadline/fence and consumed allowance. Other
cases cover clinical/assignment/membership revocation, lost prepare/issue ACKs,
replacement processes, submitted expiry with a healthy/unavailable peer,
unavailable custody before checkpoint and clinically invalid child money. Human
request/review/audit/outbox/event rows remain unchanged across every journey.
Lost replies leave committed markers, never reconstructed issue or refunds;
expired submitted work retains its uncertain units and concurrency slot.

The [launcher](../../scripts/test_agent_peer_database.py) creates only an owned
PostgreSQL 17 container and a selected-code supervisor container. They share
the database container's **network-none loopback namespace**, with no host
ports, external bridge, host directories, Docker socket or real credentials.
Both have read-only root filesystems, bounded tmpfs, 512 MiB/one CPU/128 PIDs
and explicit capabilities only for trusted test supervision. Actual inspected
configuration, test count, container exit/no-OOM and process/file/container/image
cleanup are required. Linux/GitHub/exact-repository/explicit opt-in guards refuse
before Docker locally. The related local suite passes 213 cases with the two
Linux-only modules skipped, and repository Ruff/whitespace checks pass.

The first combined fault test damaged the initial history-check reply rather
than the later write ACK. The fixed dummy peer now injects the fault immediately
after the selected SQLite prepare/issue commit; earlier checks remain intact.
This changes test injection only. No runtime permission, accounting rule or
deadline was relaxed.

That same exact revision passes
[full product CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41681911155)
and [private-preview CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41681911168).
The dedicated existing suites pass 476 agent, fourteen owner-fixture restore,
290 restricted command, 53 lifecycle, 27 restricted encrypted restore and 33
separate-peer cases. Full regression passes 1,027 root, 2,281 API, 72 membership,
58 client, 26 browser, fifteen source UI and eighteen MVP journeys, with expected
skips and two existing API warnings. The preview independently passes eighteen
journeys, matched encrypted 22-table restore and saved-workflow reopenings after
restart and restored-volume replacement. All owned service/stack/fresh-volume,
process/file/container/image cleanup succeeds. No local Docker or GCP run/build
was started; the VM remains TERMINATED with its unchanged 1,800-second STOP.

The bounded canned child still shares the trusted custody UID; this suite does
not claim a separate untrusted transport UID or credential sandbox. That
containment probe remains separate. Root/DB fixture owners prepare and assert
state, but their credentials are absent from runtime children. Combined
encrypted restored-state journeys, real operational credential delivery and
retained custody across host loss remain open. No route, service, worker,
provider, migration or deployed configuration is activated by this test.

## Remaining operational gates

The journal UID, custody UID, trusted supervisor and host administrator remain
trusted. Kernel peer credentials identify a local UID at connection time, not
the program's code, a durable UID incarnation or a remote principal. Reusing a
UID, passing an authorized socket to hostile code, sharing a credential/process
owner or compromising the host is outside this proof. No network namespace,
capability, filesystem sandbox or provider egress policy is established by this
module. The separate fake transport containment probe remains separate evidence.

This same-host journal is not independent host-loss/rollback-of-both protection.
Production retained custody, authenticated remote peers, controlled secret
delivery, quiescence/session termination, credential/UID rotation and reviewed
reauthorization remain open. No startup should auto-create/rebind authority or
rehydrate pending execution. Production installation/restore and exact governed
Snowflake source/provider contracts need their own acceptance and any paid
window needs owner approval. The deployed preview remains `7940886`/`0003_mvp`.
