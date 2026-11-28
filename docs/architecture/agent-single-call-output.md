# Prepared bounded single-call output — 28 November 2026

`ciq_api.agent_single_call_output.OwnedSingleCallOutput` owns two fresh private
pipes and captures only the fixed readiness/publication marker for one fixed
role. It is a prepared component, without a process launcher, admission gate,
installed service, credential access or activation path. No deployed host selects
it. It does not complete the `PreparedHost` contract.

## Original pipe ownership

The trusted host retains the object before `prepare()` and before any process
allocation. Preparation creates separate stdout/stderr pipes, records each end's
device/inode identity and keeps all descriptors non-inheritable. Only readers
are nonblocking; child writers retain normal blocking semantics. Preparation
failure retires the acquired descriptors and cannot be retried on the object.
There is no constructor accepting existing descriptors, paths or commands.

`take_writers()` consumes the one original handoff before validating and returning
the writer pair. The trusted launcher uses these only as stdout/stderr for the
fixed native bootstrap. It must call `release_writers()` after the allocation
attempt, including when allocation or its acknowledgment fails. Release attempts
both closes, retains descriptors whose validation failed for later retirement,
and never retries an uncertain close. No method issues another writer handoff,
adopts a replacement pipe or creates retry authority. Duplicate handoff/preparation
requests are denied without discarding the original cleanup ownership.

All calls require serialization under the trusted host's exclusive lease. The
host must exclusively own the descriptors and prevent independent close/reuse or
flag mutation. Identity checks reject observed replacement or changed flags;
they do not defend against a competing root process or arbitrary descriptor
mutation between syscalls. Closing only retires still-matching original handles
and preserves any detected replacement. It never resets history or signals a
process. The component has no destructor that could unexpectedly close reused
descriptor numbers.

## Bounded observations and completion

Each observation performs at most one nonblocking read per still-open stream,
with a maximum of 129 bytes per stream and no select, wait, sleep, background
reader, unbounded drain loop or EINTR retry. The extra byte detects overflow of
the 128-byte limit. Retained stdout must be a prefix of that role's exact marker;
any stderr byte, invalid prefix, extra output, overflow, missing/partial marker
at EOF, descriptor fault or interrupted read permanently invalidates capture.
Only EAGAIN/EWOULDBLOCK means no new data. Cancellation propagates after latching
failure. Errors use one fixed message and do not retain arbitrary diagnostics or
expose them in snapshots. This is bounded syscall work, not a substitute for the
host's externally enforced deadline around all kernel operations.

Split marker bytes remain private until the exact complete marker arrives;
observations return empty stdout before that point. Later observations preserve
the same cumulative marker, while still checking for extra bytes and diagnostics.
This allows the existing supervisor to require empty-or-exact markers without
rejecting valid short pipe reads. No output is evidence of consent, identity,
successful SQL publication or provider execution by itself.

`CapturedOutput.drained` requires EOF on **both** original streams and the exact
stdout marker. A readiness marker alone is not a completion acknowledgment. An
exited native waiter is also insufficient: descendants can retain inherited
writers after its original application child exits. The future host must join
the original waiter's collected exit status, drained output, whole original
cgroup evidence and fresh authorization checks. It must not fabricate successful
completion while either stream can still produce output. A descendant holding
pipes open is bounded by that host's deadline and whole-group cleanup, not by
blocking until EOF in this component.

## Evidence and remaining integration

Offline tests use actual private pipes and no local application processes or
containers. Disposable Linux CI composes the exact native bootstrap, permanent
identity launcher and capture component with dummy role modules. All three roles
emit split markers. Separate controls exercise a large blocked writer, unexpected
stderr and an exited main process with a separate-session descendant retaining
both pipes. Whole-group termination and original waiter collection retire every
fixture; no private plans, provider credentials or network access are used.

The fixture's `Popen` return is **not** evidence of production launch ownership
before a lost start acknowledgment. That ownership mechanism, original waiter
handles/reaping, externally bounded host operations, resource limits, immutable
runtime installation, read-only mounts, role-specific egress, fresh consent and
lease verification, private plan delivery and retained-history recovery still
require integration. Existing service examples remain unchanged. No provider
attempt, paid service, local Docker stack or deployed behavior is enabled.
