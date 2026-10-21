# P2 host clock-health review — not a deployed provider

21 October 2026. Research/input contract for the approved offline clock work.
No host, daemon, operational thresholds or synchronization service is selected,
installed or modified by this review. No payment or deployment is authorized.

## Verified platform constraints

Linux `CLOCK_MONOTONIC` excludes suspend time. `CLOCK_BOOTTIME` includes it;
wall time can jump and is adjusted by time synchronization. Therefore the
existing two-container monotonic/boot-ID test does not establish suspend safety.
A prospective Linux sampler must establish the relevant clock domain, bracket
reads to account for sampling skew, and retain suspend-aware evidence. Boot ID
alone does not detect a same-boot suspend/resume event. This is an inference from
the [Linux clock definitions](https://man7.org/linux/man-pages/man2/clock_gettime.2.html),
not a tested suspend detector in the current candidate. Never suspend or change
the developer machine's clock for acceptance; use injected observations.

Chrony's tracking report describes system offset, root delay/dispersion, source
and leap status. Its documented accuracy bound includes absolute system offset,
root dispersion and half root delay, conditional on the reference clock being
correct. A report collection timestamp is not the reference measurement time.
The local-reference mode is not evidence of external synchronization. Its
command interface can also change daemon settings, so exposing a full daemon
control socket to workers would exceed a narrow read-only health interface.
See [Chrony tracking and command access](https://chrony-project.org/doc/4.7/chronyc.html).
This does not claim that Chrony is installed or approved for our eventual host.

## Required provider contract before activation

The following are engineering requirements/proposals, not implemented guarantees:

- Identify the actual deployment kernel/VM and synchronization authority. A
  macOS host, Linux Docker VM and future Linux host are not interchangeable.
- Keep privileged time adjustment/daemon control outside app containers. Workers
  must receive narrowly scoped health evidence, not clock-setting privileges,
  a Docker socket, daemon control socket or application-selected time server.
- Bind evidence to the reviewed host boot/clock domain; reject wrong-domain,
  malformed, unavailable, future or stale evidence. Record measurement freshness
  separately from the collector's successful read time. Bound collection time.
- Define how synchronization/source policy, uncertainty including system offset,
  aging/holdover and leap handling become conservative integer-nanosecond inputs.
  Do not infer healthy status from a readable wall clock, low reported offset,
  a zero error field or successful `waitsync` alone.
- Specify same-boot suspend detection, measurement-skew allowance and persistent
  event handling. Until proven, uncertainty disables issuance/routes and uses
  stopped-generation recovery; no auto-rebase or restart-based clearance.
- Review trust/delivery/custody of the collector evidence and broker state mount.
  A plain JSON file or an application-provided timestamp is not authentication.
- Select numerical error/freshness/drift/gap/suspend policy using host evidence
  and the 30-second capability lifetime; test values are not deployment policy.
  No amount of time-health evidence protects against a compromised trusted host.

## Ordered acceptance

1. Review provider/host/delivery contract and tolerances. Do not install a daemon,
   add privileged capabilities or activate a service merely to test the contract.
2. Implement a bounded inactive collector/adapter; test wrong source/domain,
   aging, holdover, leaps, malformed/oversized responses and collection failure.
3. Test injected suspend/reboot/gap cases across retained state and process
   restart; demonstrate they cannot clear a latch or revive a pruned token.
4. Compose the same reviewed provider with broker and authority clocks,
   clock-checked pre-bind readiness and signed mTLS authorization/delivery.
5. Verify actual target-host behavior, custody, shutdown/deadlines and live
   isolation before any separately approved activation. Readiness is not a
   cached authorization; every protected operation still checks the guard.

Current executable evidence remains explicitly fake-health/offline; see
[clock safety and container limits](p2-clock-safety.md). This review does not
close the real provider, suspend, encrypted custody or P2 exit gates.

The next [specific offline prototype proposal](p2-clock-health-proposal.md)
selects a candidate collection/trust approach for owner review, not deployment
or daemon installation. Its approval is separate from the existing guard's
offline implementation approval; no real health provider is implemented yet.
