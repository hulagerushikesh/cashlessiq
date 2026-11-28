# Prepared atomic single-call allocation — 28 November 2026

`deploy/agent-controller/native/single-call-launch.c` is a small Linux bootstrap
for review, compiled only by disposable CI. There is no installed executable,
setuid permission, service, route or deployed host selecting it. It does not
admit an attempt or implement the complete `PreparedHost` contract.

## Ownership before allocation

The future trusted host must first retain an `OwnedSingleCallCgroup`, reserve its
fresh namespace, and retain ownership of the bootstrap process and its private
output pipes **before** any process allocation can become uncertain. Under its
exclusive lease, the host passes the original cgroup directory descriptor, a
fixed role (`receipt`, `provider`, `custody`) and a clean environment to an
immutable root-owned bootstrap. The numeric argument is only this inherited
descriptor; it is not a PID, path, existing-name lookup or externally supplied
launch selector. The C helper cannot establish freshness, consent or ownership
by inspecting a descriptor alone; the trusted host supplies those guarantees.

The bootstrap requires real/effective/saved root UID and GID, null stdin,
separate output pipes, a protected root-owned cgroup-v2 domain directory, and
empty/unfrozen kernel population evidence. Unknown population fields or formats
also deny startup. It independently reads the exact fixed role resource policy:
receipt memory 128 MiB, provider/custody 256 MiB, zero swap, group OOM handling,
32 tasks and 50 ms CPU bandwidth per 100 ms period. Missing or changed controls,
including stricter but unreviewed values, deny allocation without rewriting them.
These checks do not prove ownership or exclude a competing root; exclusive host
ownership is still a prerequisite.

Before clone, the bootstrap selects `SCHED_OTHER` and permanently sets the soft
and hard realtime-priority and locked-memory allowances to zero. The identity
launcher subsequently clears capabilities. This prevents inherited realtime
scheduling from bypassing the fair-scheduler CPU bandwidth limit. Failure is
terminal; these limits also apply to the small root waiter, whose memory/CPU
remain outside the application cgroup. It closes every extra descriptor except the original group,
disables core dumps, normalizes signal state and uses a fixed working directory.
It never reads a private plan, database password, provider token or application
module. A clean environment must be supplied **at exec**; checking `envp` after
dynamic loading cannot protect against a caller supplying loader variables.

The only allocation syscall is `clone3(CLONE_INTO_CGROUP | CLONE_PIDFD)`. The
[Linux manual](https://man7.org/linux/man-pages/man2/clone.2.html) describes how
the kernel creates the child directly in the descriptor-selected cgroup. There
is no fork-then-migrate window, shared virtual memory, Python callback after
fork, caller-selected command or fallback for unsupported/denied syscalls.
Unsupported `close_range`, `clone3`, cgroup controllers or pidfd waiting deny the
operation. A failed allocation is never retried by this helper.

The child starts a separate session, closes the cgroup handle and executes only
`/opt/cashlessiq-agent/venv/bin/python -I -B -m
ciq_api.agent_single_call_identity ROLE` with `LANG=C.UTF-8`. The existing identity
launcher then permanently clears supplementary groups/capabilities and drops to
the fixed role UID/GID before its fixed role exec. The interpreter, dynamic
loader, libraries and installed modules must be independently verified and
immutable to these identities before launch. This helper does not install or
verify that complete runtime.

## Waiter, deadlines and cleanup

The small privileged bootstrap parent remains **outside** the application group
and waits for its original child using the kernel-created pidfd. It forwards no
untrusted diagnostic or PID metadata and emits no stdout itself. Normal child
exit status is preserved; signal termination becomes `128 + signal`. Fixed
bootstrap failures return 125 and only `single_call_launch_unavailable` on
stderr. Child/runner diagnostics are not sanitized by this helper. The prepared
[private-pipe capture component](agent-single-call-output.md) now bounds and
validates those streams; joining it to original launch/waiter ownership remains
the future host's responsibility.

The future host must externally bound bootstrap allocation and observation,
stop the **whole original application cgroup**, collect all directly owned
bootstrap waiters and retain uncertain state. The helper has no timeout,
automatic group kill or retry, and its pidfd wait is not evidence that all
descendants exited. Early parent-death SIGKILL protects only the privileged
child bootstrap interval: Linux clears that setting on the later identity
transition. It must never substitute for group cleanup. Lost start acknowledgment,
waiter death, failed exec, remaining population or uncertain child reaping must
not grant a second launch or reset history. `OwnedSingleCallCgroup.stop()` and
its retained evidence remain separate from collecting the root waiter.

## Disposable evidence and remaining work

CI compiles the exact public C source with warnings as errors and linker/stack
hardening. An exclusive disposable runtime at the exact fixed interpreter path
contains the actual identity launcher and dummy role modules only. Interpreter
initialization checks group membership and absence of inherited extra handles
before role execution; the actual launcher then performs permanent identity
loss. Each role forks a separate-session descendant, followed by recursive group
termination, original-child pidfd status and waiter collection. Normal exit and
signal exit have separate controls. Invalid arguments/environment, ordinary
directories and removed groups are rejected. Test-only linked syscall wrappers
force ENOSYS, EPERM, EINVAL and EBUSY and require exactly one failed clone, with
no alternate launch. Changed resource-control values are separately rejected;
dummy role entries check normal scheduling and zero realtime/locked-memory
allowances. No test selector is compiled into production source.
Every fixture process, cgroup name and copied runtime is retired after testing.

This is allocation/identity/cleanup composition, not a credentialed provider
attempt or an installed containment policy. The complete host adapter, one-shot
launch ownership before allocation, joining bounded output capture, installed resource policy,
read-only mounts, role-specific egress, immutable installation verification,
fresh consent/lease/plans and retained-history recovery remain required. Native
build/install provenance is also outstanding; the review archive includes C
source, not a trusted binary. Existing service examples are unchanged and must
not be redirected to this bootstrap without completing that review. No paid
services or deployed application behavior are changed.
