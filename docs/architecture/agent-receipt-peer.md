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
It exercises client and server authentication, cross-UID file denials, original
coordinator checkpoint/issue, no replacement permission, invalid frames and
descriptor handoff, lost acknowledgments, peer restart, retained issued markers,
closed/missing custody and unsafe/stale socket handling. Every process and only
the invocation-owned directory are removed in fixture cleanup.

CI acceptance is pending on the implementation revision. Ordinary local testing
skips the root/Linux opt-in suite before starting any process or file fixture.
The fake peer does not open a PostgreSQL connection, query Snowflake, call a
provider or create an allowance. The coordinator integration case uses its
existing deterministic offline SQL-engine double; full actual-login lifecycle
tests continue separately. Combined peer + restricted PostgreSQL + bounded-child
publication/recovery/restore acceptance remains a next integration step.

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
