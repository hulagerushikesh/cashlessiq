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
launch ownership before allocation, joining bounded output capture, installed policy verification,
role-specific egress, immutable installation verification,
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

## Prepared controller gate and original waiter handle

`OwnedSingleCallLaunch` owns a fresh private gate before bootstrap creation. It
hands out only the original child endpoint once and closes the controller's copy
in a `finally` after the creation attempt. Nonblocking bounded `recvmsg` retains
all installed descriptor rights before validation. The exact packet must contain
one pidfd and one root sender credential, with no truncation or extra ancillary
records. The received pidfd's procfs sender identity must match the packet; kernel
`waitid(P_PIDFD, WNOWAIT)` must establish that it is an original direct child.
No process is discovered or signaled by a numeric PID. The installed immutable
native source and exclusive controller/descriptor ownership remain prerequisites;
this is not protection against a competing privileged process.

Only after that handoff can `authorize()` send the fixed START packet, once.
A short write, exception or cancellation consumes authorization and preserves
the original pidfd for cleanup. A creation attempt whose return was lost must
never call authorize, even if its bootstrap handle is subsequently recovered.
An expired but authenticated direct-child waiter is retained for reaping while
START remains denied. All faults are terminal for handoff/start; no reconstruction,
retry, adoption or second process allocation is implemented.

Observation uses only the original non-inheritable pidfd and `WNOWAIT`; reaping
is separate, consumes its wait before a possibly lost acknowledgment, and cannot
be repeated. Controller EOF requests native fail-closed retirement. Independent
original application-group stop remains mandatory before forcibly terminating
a stalled root waiter using its original pidfd. Closing handles alone proves no
cleanup. The component never creates a process, makes an admission decision,
installs containment or implements the complete `PreparedHost` adapter.

Offline state/fault controls cover malformed/foreign handoffs, altered identities,
uncertain START and uncertain reaping. Disposable Linux composition uses the
actual native bootstrap, gate, permanent identity, original private pipes and
owned cgroup. It checks a complete marker plus both EOFs, creation-return loss
without START, post-START controller loss and externally killed waiter cleanup.
The fixture's `Popen` object is used for emergency test bookkeeping only: product
observation, signaling and reaping use the previously transferred original pidfd.

## Prepared role filesystem containment

Atomic role allocation now also selects `CLONE_NEWNS`. In that child, before the
first Python instruction, the native bootstrap makes mount propagation private
and recursively sets every inherited mount read-only and nosuid. Custody has no
writable filesystem exception. Receipt receives only
`/run/ciq-agent-single-call/ipc` and
`/var/lib/cashlessiq-agent/single-call/retained`; provider receives only
`/run/ciq-agent-provider/ipc`. These fixed leaves are private bind mounts, writable
with nosuid/nodev/noexec. Plans, tokens, interpreter, modules, `/tmp`, procfs and
cgroups stay on the read-only view. Read-only mounts do not hide readable files
or prevent device/IPC operations; separate UID/mode checks, original-FD closure,
network policy and private-file validation remain required.

There is no caller-supplied path or mount selector. Nofollow traversal checks
protected ancestors and the exact role-owned leaf (0755 IPC, 0700 retained
history), pins its inode before/after binding, and rejects missing, symlinked,
changed-owner or writable-ancestor layouts. The trusted host must stage and pin
these layouts under its exclusive lease before launch; the bootstrap does not
create, repair or adopt them. Read-only mount setup and the fixed exceptions run
before identity loss. `mount`/`mount_setattr` failure denies role exec with no
writable fallback. Native child failure is still retired/reaped by the waiter.

Disposable Linux checks verify a role-owned ordinary probe cannot be written
because of EROFS, each fixed writable leaf supports Unix socket creation, and
receipt's retained directory supports a real SQLite DELETE-journal transaction.
They independently check the host namespace remains writable. Malformed private
layouts and a test-only forced unsupported `mount_setattr` are denied. No real
plans, token, retained journal or database are installed by these controls.
This is filesystem/resource/process containment evidence; role-specific network
egress, complete host admission and immutable installation still remain.

## Receipt network namespace

Receipt's atomic clone additionally requests `CLONE_NEWNET`. It inherits no
network descriptors and receives a fresh network namespace with no host
interfaces, routes, resolver socket or enabled loopback. After fixed identity
loss it has no capabilities to configure one. Receipt needs only its fixed
pathname Unix socket and retained SQLite history; neither requires access to
PostgreSQL, DNS or provider HTTPS. The native bootstrap never enables interfaces
or downgrades a denied network-namespace clone. Root-waiter observation and
cleanup remain in the trusted host's namespace.

Disposable acceptance checks the network namespace differs from the host, that
only the unconfigured loopback interface exists, and that IPv4/IPv6 host-loopback
and a documentation-only external address are unreachable. A root fixture's
public pathname Unix socket exchanges a fixed probe across the namespace boundary,
while the same receipt's retained SQLite transaction succeeds. This establishes
that receipt isolation preserves its required IPC/storage behavior. Custody and
provider currently retain the host network namespace: custody-only loopback SQL
and provider-only reviewed HTTPS containment still require separate completion.
No claim of complete three-role egress isolation is made.

## Custody IP socket policy

Before Python or identity loss, custody now installs two fixed eBPF programs on
its original fresh cgroup. The socket-creation policy admits only IPv4 TCP stream
sockets; the connect policy admits only `127.0.0.1:5432`. UDP/DNS, IPv6, alternate
loopback addresses/ports and external destinations are denied by the kernel.
Programs are fixed instructions compiled into the native source; there is no
DNS lookup, provider selector, external policy file, map update or shell command.
The loader refuses an existing local attachment, verifies the newly loaded
program ID against the exact group's attachment, and never replaces or detaches
policy. Cgroup attachments survive waiter exit/descriptor closure, including an
unexpected root-waiter death, until trusted disposal of the original group.
Partial attachment failure prevents role exec and leaves retained state.

Custody is a client, so a permanent no-new-privileges seccomp filter additionally
denies bind/listen/accept/accept4, including implicit listener autobind. The native
release targets reviewed Linux x86-64; alternate architectures and x32 syscall
entry cannot bypass the filter. The filter is inherited by descendants. No
inbound service or DNS resolver is required by custody. Unsupported/denied BPF
or seccomp setup denies role execution, with no unrestricted fallback. These
policies do not hide unrelated pathname Unix sockets; private host filesystem
visibility and peer authentication remain part of final host acceptance.

Disposable kernel acceptance uses a public dummy TCP listener at the fixed SQL
address, never an existing PostgreSQL instance. It requires the allowed exchange,
EPERM for wrong IP/port/external TCP, UDP and IPv6 socket creation, and denied
bind/listen/accept. A separately linked failure control denies BPF and requires
no role execution. Normal identity, memory/task/CPU, output and whole-group
cleanup controls also run with this policy enabled. Provider still needs its
own reviewed HTTPS destination/resolver policy and end-to-end host admission;
this custody policy grants no provider/network/spend authority.

Custody policy-lifetime controls additionally attach the exact fixed programs
through a disposable fixture and require a subsequent launch to reject that
nonfresh policy rather than replace it. A separate injected root-waiter SIGKILL
leaves a live role in its original group; that role must still receive EPERM for
a forbidden connection before independent host group cleanup. This intentionally
violates normal shutdown order only to test unexpected waiter death. The fixture
never uses runtime `terminate()` as a substitute for whole-group cleanup.

## Prepared provider transport without runtime DNS

`PinnedSinglePostHTTPS` is a separate inactive transport variant for the next
provider egress policy. Trusted construction supplies exactly one canonical public
IPv4 address alongside the already reviewed Snowflake hostname and body digest.
It opens one IPv4 TCP socket directly to that address on 443, with no DNS lookup,
address iteration or fallback. TLS certificate/hostname verification, SNI and the
HTTP Host header retain the original reviewed hostname. Wrong certificates fail
before the authorization header/body is sent. The existing bounded one-POST,
response validation, consumed-attempt and no-redirect/retry behavior is shared.

The class does not resolve or authorize an IP, prove a hostname-to-address mapping,
install a kernel allowlist or update the provider plan. The future trusted host
must bind a freshly reviewed address to the exact full pin and matching kernel
policy. No deployed/manual runner currently selects this variant. Loopback-only
TLS controls exercise valid, wrong-host and untrusted certificates with DNS made
an explicit test failure; public-address redirection exists only in the fixture.
Nonpublic, multicast, IPv6, noncanonical and multiple-address inputs are rejected.
