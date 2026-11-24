# Coordinated synthetic service activation

24 November 2026. Disposable CI only; no operator installation or live credentials.

The complete journey holds one nonblocking advisory lock from before installation
through private-plan delivery, explicit starts, retirement and quiescent teardown.
After obtaining the lease it rechecks that the fixed installation and accounts
are absent. Competing cooperating supervisors fail immediately rather than wait,
adopt an installation, deliver more plans or start a second service lifecycle.

`scripts/agent_service_coordination.py` requires the exact opted-in root Linux CI
repository before accessing the filesystem. It walks root-owned non-writable
parents without following symlinks, opens the fixed `/run` lock without following
the leaf, and requires an empty, root-owned `0600` regular file with one link.
The descriptor is not inherited across exec. The current PID, metadata and named
inode must still match before delivery, activation and private-fixture deletion.
The empty lock file is deliberately retained after releasing the descriptor;
unlinking it could allow simultaneous locks on different inodes. It contains no
private data and disappears with the disposable host.

The supervisor records successful atomic delivery in memory. Custody needs both
its credential plan and its canned candidate; each other role needs its own plan.
Every explicit start also requires fresh stopped-service evidence. Any delivery
or start exception permanently blocks further delivery and activation by that
supervisor, including an error after publication but before confirmed directory
sync. Stopping owned services remains possible. Teardown still requires separately
confirmed quiescence and a valid lease before removing private fixtures. Creating
a fresh supervisor is not recovery: installation/account and no-replacement
guards continue to reject retained state.

This closes a gap where a caller could catch an uncertain delivery error and
later request a start. Explicit replay/retired-password denial invocations remain
test assertions under a successful original delivery; there is no automatic retry,
reauthorization or stale receipt endpoint adoption.

The lock excludes only cooperating supervisors. Trusted root can bypass it;
service-account processes, privileged manual `systemctl`, DDL, installed-code
changes and account/UID reuse still require separate controls. The lock does not
prove database/receipt parity, authorize a clinical action or supply a protected
credential source. The production acquisition/delivery path and governed provider
integration remain open. No unit, application runtime, database authority or GCP
startup configuration changes in this step.

Local acceptance: 27 new checks include actual cross-process lock contention,
release on exceptions, persistent inode reuse, unsafe existing objects, stale or
changed leases, entry guards, permanently blocked uncertain delivery/start and
incomplete custody plans. All 117 focused coordination, journey, atomic-delivery
and quiescence checks pass, with changed-file Ruff. The existing Linux journey
remains the integration gate for actual fixed-path root metadata, installed
services, restricted database authentication and cleanup.

The [Linux journey](https://github.com/hulagerushikesh/cashlessiq/actions/runs/45440469846/job/138609853225)
passes at source `dfcc53fb6026f0ca9c107d9d288ff7e38400936d`: all three scenarios
and 21 installed-service invocations complete under the unchanged unit policies.
All three retirement/rotation markers and owned service/private-file/account/
installation/database/tmpfs cleanup pass. The complete workflow has now finished successfully across all nine jobs.

The next [protected startup-plan handoff](agent-service-source.md) adds root-only
source intake and renews lease/quiescence evidence before publication.
