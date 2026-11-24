# Complete synthetic journey under manual services

24 November 2026. Disposable Linux CI acceptance only. This adds no deployed
service, production credential delivery, live provider or GCP startup.

The [installed private-plan checks](agent-service-credentials.md) and
[resource/descendant probes](agent-service-supervision.md) cover their respective
boundaries. This suite connects the complete HTTP-to-result path under those
same manual unit contents, without overriding identities, commands, timeouts,
resource limits, paths, environment or output destinations.

## Trusted fixture and launch order

The explicit exact-repository/root/Linux/systemd/cgroup-v2 guards and additional
journey/database opt-ins run before host mutation or database connection. Existing
installation, runtime directories, fixed account/group names, dummy UIDs/GIDs and
loopback database listeners are refused. The API/domain wheel installation and
all package-byte/ownership/dependency checks reuse the private-plan harness.

A disposable PostgreSQL 17 container listens directly on `127.0.0.1:5432` in the
CI host network namespace. There is no Docker published-port/DNAT intermediary,
external bind, host directory mount or Docker socket mount. PostgreSQL is
initialized with explicit SCRAM host authentication, including loopback; initdb's
default localhost trust would invalidate password-retirement assertions. Its filesystem is
read-only apart from bounded tmpfs data/run/tmp directories; it has a 512 MiB
memory/no-swap limit, one CPU, 64 tasks, no new privileges and only the trusted
entrypoint capabilities needed to initialize/drop identity. This database is a
test prerequisite, outside the three runtime service cgroups. These limits are
not a whole-stack capacity estimate or a new VM requirement.

The trusted test supervisor uses development fixtures separately from the
verified installed runtime, which contains no pytest, legacy app or Snowflake
package. It provisions synthetic data, scoped SQL commands and distinct restricted
clinical/custody logins. Owner database connections are used for fixture setup
and assertions; no runtime service receives an owning credential or fallback.

The bounded rehearsal follows this order:

1. An authenticated medical-officer HTTP request creates the held intent.
2. The clinical UID receives only its fixed private plan and restricted login.
   Its exact unit claims that intent once. The supervisor requires confirmed
   service exit, an empty cgroup and one strictly parsed private claim receipt.
3. An independent trusted operator step assigns the custody login to that exact
   committed claim and installs its publication commands. The runtime cannot
   create that assignment from browser input or its own receipt.
4. A separate trusted fixture provisions a fresh private dummy retained journal
   with the existing database epoch. It stages the fixed receipt/custody plans
   and synthetic candidate completely before starting the receipt idle window.
5. The exact receipt unit must be active and emit its sole fixed readiness marker
   for the current systemd invocation ID. `Type=exec`, an existing socket and
   markers from an earlier invocation do not satisfy readiness. Startup is
   bounded; unexpected output or an exited service fails immediately.
6. The exact custody unit runs the original prepare/dispatch/publication
   coordinator and bounded canned child against the real restricted database
   and separately authenticated receipt UID. SQL history and fresh clinical
   context remain authoritative for each command; readiness supplies neither.
7. The authenticated HTTP read returns the validated result or conservative held
   state. Human review remains unchanged.

There are no dependency-triggered starts, service enables, timers, background
scanners, automatic retries, resets, stale-socket adoption or larger resource
overrides. The canned child remains trusted code under the custody UID and API
environment; this does not establish containment for hostile/provider code.

## Acceptance scenarios

| Scenario | Attempt / retained receipt | HTTP result | Allowance |
| --- | --- | --- | --- |
| Valid candidate | One attempt, exact issued checkpoint | Published, INR 95,000 | Consumed once; slot released |
| Invalid payable amount | One attempt, exact issued checkpoint | Submitting; comparison withheld | Held; no refund or retry |
| Disabled independent custody assignment | No attempt or receipt | Reserved; comparison withheld | Held; no execution |

Each case explicitly probes a second clinical and custody invocation as negative
tests; these are not automatic retry/recovery behavior. No second attempt or
comparison is permitted. A new browser command returns conflict, the saved job
remains `executor_claimed` with zero generic-worker attempts and its exact
operation ID, and processor/auditor reads are forbidden. Human state/version,
final payable amount, event count and review outbox are checked unchanged by
agent execution.

Trusted assertions compare the complete retained receipt tuple to the database
checkpoint. The original receipt idle bound must close the process without
changing retained bytes or unlinking its stale endpoint. Only after every owned
unit is stopped and its cgroup confirmed empty does the trusted fixture remove
its own socket, private files and retained test directory. This occurs before
database authority teardown. Unconfirmed quiescence fails and retains private
fixture evidence. Finally the owned units, accounts, installation and database
container/tmpfs data are removed; shared base images are not pruned.

Actual invocation journals, claim packets, assertion values, passwords, plans,
SQL and arbitrary exceptions stay out of Actions logs. The trusted supervisor
checks private output in memory and emits only fixed stage/acceptance markers or
failure phase/code location. Ordinary local invocation refuses before any Docker
or database action. Eighteen offline cases cover opt-in refusal, quiescence,
fresh invocation/readiness evidence, cleanup failure preservation and acceptance
of exactly three successful test-call reports independently of pytest's quiet
text output. No collected/skipped-case count or printed success marker can
substitute for those actual passing reports and an overall successful exit.

## Retirement and password-rotation extension

Each of the three scenarios now continues into a trusted disposable retirement
rehearsal. All three units are stopped with strict cgroup/quiescence verification
before database changes. The operator pins the original database and five role
OIDs, then commits clinical and custody revocation separately, repeating each as
an explicit idempotence check. An authenticated idle connection stays alive but
loses private-command access. Its connection pool is then disposed; a bounded
check requires no remaining sessions for that unique dummy login.

Only after committed retirement and session closure does the fixture change the
memory-only dummy password. It deliberately restores LOGIN, CONNECT and the
installed command ACLs, but never principal/reservation/submission approval.
Fresh authentication rejects the old password and accepts the new password for
the original pinned role. Clinical capture and custody inventory still fail.
An explicit invocation of each installed service using its unchanged old private
plan must also deny access. Receipt service state and its stale endpoint are not
reset or adopted. These six extra denial invocations bring the journey total to
21; the wrapper still requires exactly three actual passing scenario reports.

All 22 product tables are digested before retirement and checked unchanged after
each role, alongside exact retained-journal and private-plan bytes. Published
results stay published; uncertain operations remain held, without refunds,
additional attempts, comparisons or human decisions. Private bytes and errors
remain inside captured test memory. Normal fixture cleanup follows independently
confirmed service shutdown. This is not a live retirement/rotation installer,
production secret delivery, secure erasure, account-wide hostile-process proof,
activation lock, fresh-credential service activation or reauthorization.

The extension passes 19 existing local harness checks and changed-file Ruff.
Local collection skips the root/Linux integration module before host/database
access. Actual PostgreSQL/systemd acceptance requires the dedicated CI job; no
local Docker or GCP resource is started.

The initial extension run at `d6b6493` failed the old-password denial assertion:
the disposable database inherited localhost trust. This exposed a fixture gap,
not a reason to weaken the denial check. The corrected fixture explicitly uses
`--auth-host=scram-sha-256`.

At corrected source `3a61eba3fd9f865f7078009014d5270d187b2fdd`, the
[Linux journey job](https://github.com/hulagerushikesh/cashlessiq/actions/runs/45387810147/job/138423238026)
passes all three actual scenario reports and all 21 service invocations. Each
scenario emits its retirement/rotation acceptance marker. Owned service, private
file, retained fixture, account, install and loopback database/tmpfs cleanup pass.
The complete workflow has now passed all nine jobs at that corrected source.

## Acceptance evidence

At source `60b4d66b81951e27cd23f2198c09c0157c26e0d3`, the
[exact-service journey job](https://github.com/hulagerushikesh/cashlessiq/actions/runs/45358107478/job/138320934456)
passes all three scenarios: fifteen actual service invocations, including the
explicit replay-denial probes, with seven fixed acceptance markers covering
installation, scenario outcomes and confirmed service/database cleanup. The
unchanged private-plan job passes all 25 scenarios separately. Local verification
passes all 54 focused service checks (eighteen new) and repository Ruff; ordinary
local collection of this Linux-only module skips before host/DB access.

The [full product workflow](https://github.com/hulagerushikesh/cashlessiq/actions/runs/45358107478)
passes all nine jobs on that same source: 1,081 root checks, 72 membership checks,
69 client checks, 2,554 API checks, 26 browser checks, fifteen source UI checks
and eighteen MVP journeys. Root/API retain three/30 expected skips and API has
two existing warnings. The new module accounts for the additional API skip
outside its dedicated opt-in job. All eight existing resource probes, 44 combined
agent/restore cases and 33 separate receipt cases pass. Ledger acceptance passes
476 baseline checks, fourteen owner-fixture encrypted restores, 313 restricted
commands, 53 lifecycle checks and 27 restricted restores. Product stack shutdown
and owned container/image/process/file/service/account cleanup pass.

The separate [private-preview workflow](https://github.com/hulagerushikesh/cashlessiq/actions/runs/45357543195)
passes on `9608454`: eighteen MVP browser journeys, one saved-workflow check
after restart and one after encrypted transfer/restore into a fresh volume.
All 22 restored tables match. Fresh-volume preview removal and preview stack
shutdown both pass. That workflow did not call GCP; the later wrapper-only
correction does not change application modules, service policies or preview
runtime contents.

The earlier `9608454` revision completed all three journeys and cleanup but its
wrapper incorrectly required pytest's textual summary, which inherited quiet
settings suppressed. The correction counts successful call reports and requires
overall success instead. That earlier product run was superseded/canceled; it
is not the acceptance source. No service limit or application behavior changed
to obtain this result.

## Remaining gates

Production private credential delivery and rotation, account/UID reuse, separately
verified quiescence, stale-endpoint retirement, restore reauthorization and
independent retained-storage operation remain open. This fixture provisions
fresh dummy state; it does not add production activation/retirement commands or
replace the separate encrypted restore/rollback acceptance. The systemd topology
is still not part of Compose or the GCP runtime bundle, and Debian-host acceptance
remains separate. Governed Snowflake/source/provider integration follows these
lifecycle gates. Rebuilding or starting GCP requires a new explicit spend/window
approval.

The follow-up [coordination guard](agent-service-coordination.md) holds a cooperative
supervisor lease through installation and teardown and denies starts after
uncertain delivery. Protected production credential acquisition remains open.
