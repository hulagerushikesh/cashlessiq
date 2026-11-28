# Prepared original-cgroup cleanup — 28 November 2026

`ciq_api.agent_single_call_cgroup.OwnedSingleCallCgroup` prepares the kernel
ownership and recursive-stop primitive for a future trusted launch adapter. No
route, command entry, installer, service or deployed host selects it. It does not
launch a process, admit an agent attempt, deliver credentials or grant egress.
It is not an implementation of the complete `PreparedHost` contract.

## Fresh ownership and retained evidence

The trusted host constructs and retains one object per fixed role before any
allocation. Only `receipt`, `provider` and `custody` are accepted. The object
generates its own random cgroup name; callers cannot select a PID, cgroup path,
existing group, timeout or kill signal. `prepare()` requires real/effective/saved
root on Linux, opens each component of `/sys/fs/cgroup/system.slice` without
following symlinks, and verifies a root-owned, protected cgroup-v2 filesystem.
The filesystem magic is checked through `fstatfs`, rather than inferring it from
a filename or substituting ordinary files.

Preparation exclusively creates one fresh group and retains its directory
descriptor and device/inode identity. Existing names are never adopted. Every
observation and stop verifies both the pinned kernel directory and its current
name, the parent identity and domain-cgroup type. Replaced, removed, threaded,
unreadable or malformed state is unavailable, including a removed group that
appears empty. A rejected second preparation preserves the original cleanup
handle. Failed initial preparation is terminal and retains any partial state.

The host must serialize all methods under its exclusive lease, establish fresh
owner consent and installed-source checks independently, and place each child
inside its reserved group **before** it can execute or fork. It must exclude
other privileged migrations, namespace replacement and new starts after cleanup
begins. This helper cannot defend against a competing root administrator or
restore of an earlier host. No membership/attachment API is provided here. A
separate [prepared native bootstrap](agent-single-call-launch.md) now provides
atomic kernel allocation into the retained descriptor for disposable composition
testing; the complete host adapter and installed policy remain outstanding.

## Recursive stop and uncertainty

Before `prepare()` can succeed, the original empty group now receives fixed
limits: receipt memory 128 MiB, provider/custody memory 256 MiB each; every role
has zero swap, group OOM termination, 32 tasks and 50 ms fair-scheduler CPU per
100 ms period. Each protected kernel control gets one write and exact readback,
with original identity and empty-population checks between operations. Missing
controllers, cancellation, short writes or uncertain acknowledgments leave
preparation terminal. There is no retry, repair, shared-ancestor controller
enablement or unconstrained fallback. `resource_limited()` supplies fresh exact
readback, without granting launch authority. A drifted limit never prevents the
separate original-group kill path from attempting cleanup.

These values are a prepared test policy, not measured capacity or a host-wide
memory guarantee. The three groups total 640 MiB in configured memory maxima;
bootstrap waiters, the trusted host, database, web services and kernel overhead
remain outside that sum. The kernel permits temporary memory-max overshoot;
task accounting includes threads, and CPU bandwidth applies to fair scheduling.
The native launcher must enforce that scheduling class before allocation. A
complete host still needs fresh resource checks during the attempt and the
external time bounds. See the authoritative
[cgroup-v2 resource semantics](https://docs.kernel.org/admin-guide/cgroup-v2.html).

`stop()` consumes the original kill attempt before writing `1` to the pinned
group's `cgroup.kill`. A kernel write alone never confirms cleanup. The helper
requires two fresh validated `cgroup.events` observations with `populated 0`,
within a one-second observation allowance and fixed iteration ceiling. Missing
or malformed evidence, a changed inode, failed/short write, lost acknowledgment,
bad clock or remaining population returns false. An uncertain kill is never
retried, even if a later read shows empty population. After confirmed cleanup,
repeated stop only rechecks quiescence and never writes another kill.

The [kernel documentation](https://docs.kernel.org/admin-guide/cgroup-v2.html)
defines population recursively across descendants and specifies that
`cgroup.kill` handles concurrent forks and migrations. Consequently, leaving a
process session with `setsid()` does not escape this boundary. Unsupported kernels
without `cgroup.kill` fail closed; there is no PID-list or process-group fallback.

The future host still must reap its directly owned children. Empty live
population does not establish that its child handles were collected. It also
needs an external bound for potentially blocked syscalls; elapsed checks only
evaluate after those calls return. A successful cleanup is not permission to
retry an agent call or reset SQL/history state. `close()` closes descriptors only:
it never kills, removes a cgroup, deletes private inputs or clears evidence.
The caller must retain and review an uncertain result.

## Evidence and remaining launch integration

Offline tests exercise namespace ownership, replacement and missing evidence,
malformed population, syscall failures, nonempty timeout, lost acknowledgment,
one-shot lifecycle and filesystem ABI checks. Disposable root Linux CI creates
only fresh dummy groups and runs bounded dummy processes under UID 53002. Each
role is tested with a child in a separate session, a nested cgroup and a further
descendant. Controls verify an empty group, rejection of a replaced group while
its replacement remains alive, and an actual successful kill whose acknowledgment
is deliberately lost. Fixture-only cleanup independently retires its dummy
processes and cgroup names. Production cleanup retains its names and evidence.

This does not test a new installed service policy, identity-launcher composition,
real provider traffic, installed resource policy, read-only mounts or egress. The complete
host adapter must still integrate the identity launcher, bounded process
allocation, original incarnation/output capture, reaping, filesystem/network
policy and resource verification with this cleanup. The systemd-managed versus direct
cgroup allocation policy requires review before installation; these raw groups
are not installed systemd units. Durable retained-history/clock recovery and a
separately approved provider attempt remain outstanding. Existing services and
deployed application behavior are unchanged.
