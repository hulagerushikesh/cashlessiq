# Stopped-service evidence before private-file teardown

24 November 2026. Read-only helper; no installation, activation, credential
rotation, UID retirement or GCP operation.

The [full synthetic service journey](agent-service-journey.md) now checks stronger
shutdown evidence before removing its private plans, socket and retained fixture.
The reusable standard-library helper is
[`scripts/agent_service_quiescence.py`](../../scripts/agent_service_quiescence.py).
It has no command-line entry point or automatic invocation in deployed startup.
Only the already opted-in disposable Linux journey harness calls it today.

After explicitly stopping each owned unit, the trusted supervisor requires:

- A loaded unit with the exact requested identity, either inactive/dead or
  failed/failed, no main/control PID, pending job or recorded restart, and the
  expected no-restart/whole-cgroup kill policies.
- An empty or exact `/system.slice/<unit>` control-group property. The helper
  inspects that expected group even when systemd reports an empty property.
- Either the group itself is absent from an accessible system slice, or a direct
  `cgroup.events` file proves `populated 0`, including descendants. A missing
  event file inside an existing group, inaccessible evidence, symlink, malformed
  or duplicate records, oversize data and populated group all deny teardown.
- Identical validated systemd snapshots before and after the cgroup inspection.
  A changed invocation or any other inspected property denies teardown.

Inspection uses fixed `systemctl show` arguments, a clean environment and a
three-second timeout per snapshot. It neither reads the service journal nor
stops, resets, starts, unlinks or changes permissions. Errors become one fixed
diagnostic without subprocess output, private values or exception details.
The supervisor still attempts to stop every owned service after another stop or
evidence check fails. Any failure exits before private-file removal.

This is point-in-time evidence, not an activation lock or reusable authorization
ticket. The trusted operator must separately exclude concurrent activation and
pin installed unit contents, accounts and code. Another root administrator can
restart a unit after inspection; two snapshots do not prevent that race. The
helper does not search for unrelated processes using the account, authorize UID
reuse, prove database transactions/remote requests ended, revoke SQL authority,
rotate credentials or resolve uncertain submissions. Those lifecycle gates
remain open. The old resource probes and private-plan fixture retain their
separate acceptance; this increment strengthens the complete-journey teardown.

Local verification passes 92 focused checks: 37 new read-only evidence cases,
nineteen journey guards and 36 existing installed-service/resource checks.
Changed Python files pass Ruff. Linux acceptance is recorded after the CI run;
no local Docker, provider, Snowflake or GCP resource is needed.
