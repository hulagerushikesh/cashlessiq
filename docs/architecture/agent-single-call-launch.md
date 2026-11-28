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
fixed role (`receipt`, `provider`, `custody`), an original private Unix
`SOCK_SEQPACKET` gate descriptor and a clean environment to an
immutable root-owned bootstrap. The numeric arguments are only these inherited
descriptors; it is not a PID, path, existing-name lookup or externally supplied
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
remain outside the application cgroup. It closes every extra descriptor except the original group and private gate,
disables core dumps, normalizes signal state and uses a fixed working directory.
It never reads a private plan, database password, provider token or application
module. A clean environment must be supplied **at exec**; checking `envp` after
dynamic loading cannot protect against a caller supplying loader variables.

Before role allocation the bootstrap sends its own original pidfd over the
inherited gate. The root direct parent must retain and validate that handle
before sending the exact `single_call_start` packet. Missing/changed commands,
ancillary data, disconnect and a three-second kernel-clock deadline deny role
allocation. No command selects another role, executable or attempt. The host
must own the gate before creating the bootstrap; an uncertain creation outcome
never authorizes START. No role child exists during this handoff. This is a
single-use internal launch protocol, not admission or provider consent.

The only role allocation syscall is `clone3(CLONE_INTO_CGROUP | CLONE_PIDFD)`. The
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

The native waiter now polls the original child pidfd, private controller gate
and a kernel monotonic timer. The attempt timer is anchored before validation,
expires at 30 seconds and cannot be extended by a controller packet. Controller
disconnect, unsolicited data, timer expiration or poll interruption fail closed.
On **every** normal observation outcome, including a successful main-child exit,
it writes the original group's `cgroup.kill` once and observes empty/unfrozen
population before reporting success. This retires inherited-pipe descendants as
well as the main process. It never retries an uncertain kill write or removes
the namespace. It then boundedly waits/reaps its original direct child using the
kernel-created pidfd. Failure returns 125 and the fixed diagnostic.

The host still owns independent cleanup and must externally bound bootstrap
creation, filesystem operations and observation. A timer polled in userspace
cannot preempt a blocked syscall or dynamic loader. It must stop the **whole
original application cgroup**, collect the original root waiter, and retain
uncertain state even after native failure. Early parent-death SIGKILL protects
only the privileged child bootstrap interval: Linux clears it on identity loss.
Root-waiter SIGKILL cannot execute native cleanup; that path still requires the
host's original group ownership. Lost start acknowledgment, waiter death,
failed exec or uncertain reaping never grants another launch or resets history.
`OwnedSingleCallCgroup.stop()` remains separate from collecting the root waiter.

## Disposable evidence and remaining work

CI compiles the exact public C source with warnings as errors and linker/stack
hardening. An exclusive disposable runtime at the exact fixed interpreter path
contains the actual identity launcher and dummy role modules only. Interpreter
initialization checks group membership and absence of inherited extra handles
before role execution; the actual launcher then performs permanent identity
loss. Each role forks a separate-session descendant, followed by recursive group
termination, original-child pidfd status and waiter collection. Normal exit and
signal exit have separate controls. Additional controls require no role output
before a valid start, denial on malformed/absent/disconnected start, recursive
retirement after controller loss, and deadline cleanup. The deadline control
uses a test-only linker wrapper to shorten the real timer; no capacity or timing
selector is compiled into product source. Invalid arguments/environment, ordinary
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
release/install provenance is also outstanding; the review archive includes C
source, not a trusted binary. Existing service examples are unchanged and must
not be redirected to this bootstrap without completing that review. No paid
services or deployed application behavior are changed.

## Disposable resource enforcement acceptance

The same atomic-launch fixture now tests the caps with actual unprivileged dummy
roles. Sequential allocations touch writable pages until each role's own kernel
OOM boundary terminates it; the test requires an incremented `oom_kill` counter,
original waiter status and empty population. A bounded fork control fills all
32 task slots, requires `EAGAIN` and a kernel pids-limit event, and then retires
all separate-session descendants. A two-second CPU control requires an increased
kernel throttle counter, rather than an unreliable throughput benchmark. Every
control has bounded work and independent fixture cleanup even if a cap is broken.
Zero swap and group OOM settings are verified by readback and native rejection
controls; CI does not claim a swap-pressure or multi-process OOM experiment.

Only explicit disposable Linux CI enables the required controllers on its
throwaway runner ancestors. Product preparation never does so. The exact native
bootstrap, identity transition, caps, output controls and recursive cleanup run
in that disposable environment with dummy public inputs. This is not a deployed
host capacity benchmark or proof of provider timing under these limits; measured
credentialed acceptance still requires the owner's separate spend approval.

## Target Debian build acceptance

The inactive Debian 12/glibc 2.36 rehearsal additionally compiles the exact native
source bytes read from the selected Git commit with Debian GCC 12 and the same
warning/error and linker/stack hardening flags used by Linux launch CI. It
checks the ELF64 little-endian x86-64 PIE header and executes only the missing-
argument refusal, which runs before any allocation or private runtime inspection.
The CI receipt records the full revision and source/binary SHA-256s. This catches
target compiler/header/linker/loader incompatibility without creating an agent
process, cgroup, credential or service. The fresh build directory and binary are
removed with the disposable fixture base; no executable is installed or exported.

This is target compatibility evidence, not a reproducible or signed native
release. Compiler packages come from the disposable Debian build prerequisites;
the complete compiler/linker/sysroot supply chain is not pinned or attested by
this receipt. The eventual installed binary still needs independently reviewed
build provenance and verification together with its immutable runtime and host
policy. Ubuntu cgroup/identity/resource acceptance remains separate from Debian
loader compatibility; the latter container does not exercise systemd or cgroups.
