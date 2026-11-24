# Manual synthetic process supervision

24 November 2026. Source examples and disposable CI only. Nothing is installed,
enabled or started on the operator Mac or GCP. No billing or provider action.

The three examples in `deploy/agent-controller/systemd/` add an external Linux
systemd/cgroup-v2 boundary around the packaged [claim](agent-claim-runner.md),
[custody](agent-custody-runner.md) and [receipt](agent-receipt-runner.md) processes.
They have no install targets, dependencies, timer, queue scanner, pre/post hook,
creation of credential/journal directories, credential installer, provisioning or
reset command.
They are not included in Compose, application startup or the GCP runtime bundle.

## Fixed limits and identities

| Process | Fixed account/group | Memory ceiling | CPU quota | Lifetime ceiling |
| --- | --- | --- | --- | --- |
| Claim | ciq-agent-clinical | 128 MiB | 25% of one CPU | 25s |
| Custody and canned child together | ciq-agent-custody | 192 MiB | 25% | 40s |
| Receipt | ciq-agent-receipt | 128 MiB | 25% | 65s |

Each service has a 16-task cgroup limit, no swap, 64-descriptor limit, disabled
core dumps, a five-second startup timeout and a two-second stop grace followed
by SIGKILL. Lifetime ceilings start at service activation. `KillMode=control-group`
and `OOMPolicy=kill` apply to descendants, including custody's separately
sessioned exchange. The cgroup ceilings include children; they are not per-process
allowances. These are initial synthetic limits, not measured full-stack capacity
or a request for a larger VM. Aggregate DB/web/OS headroom needs joint acceptance.

There is no restart policy. Main exit, explicit stop and the external lifetime
limit end the service and its remaining cgroup. Process termination cannot undo
issued work or establish SQL/history parity, recover a lost claim ACK, refund
allowance or authorize replay. All retained-uncertainty rules remain in force.

The trusted operator must pre-create three distinct static nonroot accounts with
no supplementary memberships, install the trusted API environment at
`/opt/cashlessiq-agent/venv`, deliver private fixed-path plans and separately
authorize the original DB/OID and peer UID bindings. `/usr/bin/env -i` clears
systemd/PAM/cloud variables before Python; the original runner guards still
require isolated mode, no capabilities and NoNewPrivs. This is not automatic
identity creation, UID reuse protection or password delivery/rotation.

## Files, network and output

The host filesystem is read-only, home directories inaccessible and devices,
temporary directories, capabilities, privilege changes and namespaces restricted.
Clinical reads its fixed private plan directory; custody reads its own plan and
the receipt IPC directory. Each is denied the other credential/history paths.
Only receipt can write its existing retained journal and IPC directories.
Directories and metadata must already satisfy the runners' original checks.
Systemd does not create CashlessIQ plans/history or remove the stale socket on
shutdown. Its private temporary directory is unrelated to retained authority.

IP filters deny external traffic. Clinical/custody can reach only IPv4 loopback;
receipt has no allowed IP traffic. The fixed runner still selects PostgreSQL
127.0.0.1:5432. This IP policy does not restrict loopback ports or authenticate the
DB and does not make custody's same-UID canned child a hostile-code sandbox.
AF_UNIX remains available for the separately authenticated receipt protocol.
Future live-provider transport requires a different independently reviewed policy.

Only current packaged runner output reaches the restricted host journal: the
small committed claim receipt, fixed receipt readiness or fixed success/failure
markers. Operators must restrict journal access/retention; no plan, password,
candidate or clinical payload should be logged. A systemd `Type=exec` start means
the executable started, not receipt readiness, clinical authorization or successful
publication. No service dependency treats it as such.
Receipt's ten-second idle limit is unchanged: plans, the confirmed clinical
claim and independent custody assignment must be ready before receipt startup.
A trusted bounded readiness/launch coordinator still needs acceptance; manual
unit startup alone does not implement that ordering or authorize restarting an
expired receipt process.

## Acceptance and remaining work

Fourteen offline checks cover fixed role/entry-point/limit/activation constraints,
CI refusal before host reads/mutations and identity retirement failures. Cleanup
handles automatic private-group deletion, preserves replaced identities and
attempts other owned accounts after one failure. The explicit Linux CI job requires
the correct repository, opt-in, root, systemd PID 1, unified cgroups and absent
fixed runtime paths. It refuses existing paths before allocating fixtures.

The CI harness copies examples to unique `/run/systemd/system` names, replacing
only the payload and account with a trusted stdlib probe and separate dummy
numeric UIDs with invocation-owned locked, no-home NSS accounts. A separate
owned output directory is writable only for evidence; stdout is discarded and
bounded dummy-unit diagnostics may use the journal. It does not run the actual API modules, database,
receipt protocol, live secrets or provider. Existing packaged HTTP-to-result CI
remains the separate evidence for those module behaviors.

Three probes inspect effective memory/swap/tasks/CPU/descriptor/core limits,
identity, capability/environment restrictions, read-only host filesystem and
blocked connections to reachable controlled loopback listeners, with a positive
127.0.0.1 control for clinical/custody. This handles packet-drop timeouts without
mistaking an unreachable external host for an effective filter. Five custody
probes exercise main SIGKILL with a
separate-session child, forced stop, external timeout, cgroup OOM and task-cap
exhaustion. Timeout alone shortens the source ceiling to two seconds; other
resource/shutdown policy remains the example's. Every scenario requires no
restart and an empty owned cgroup, including descendants.

Finally the harness stops/verifies only its owned services, removes their unique
unit files, reloads systemd and removes its dummy runtime paths and NSS accounts. Unconfirmed stop
retains fixture evidence and fails acceptance. It never enables a unit, prunes
host resources or touches pre-existing runtime directories.

The [dedicated Linux job](https://github.com/hulagerushikesh/cashlessiq/actions/runs/45335195636/job/138245520963)
passes all eight scenarios and confirms cleanup at source
`07b4f9d148617b0a1b7b63ae1115f1940489c99b`. Local verification passes fourteen
new checks, ten existing supervisor-harness checks and repository Ruff. The
[full product workflow](https://github.com/hulagerushikesh/cashlessiq/actions/runs/45335195636)
passes all seven jobs on that same source: 1,041 root checks, 2,554 API checks,
69 client checks, 26 browser checks, fifteen source UI checks and eighteen MVP
journeys. API retains 29 expected skips and two existing warnings. The combined
peer/database/restore suite passes 44 cases in 207.96s; the separate peer suite
passes 33. Ledger acceptance passes 476 baseline checks, fourteen encrypted
restores, 313 restricted commands, 53 installation/retirement checks and 27
restricted restores. Product stack and owned peer/container/image cleanup are
confirmed successful. All 198 local links in the four affected documents resolve.
Private-preview CI was not retriggered: no app or preview runtime changed; its
previous accepted receipt-runner result remains separate historical evidence.

These examples are not production installation approval. Remaining work includes
effective installed-artifact checks, private output/secret delivery, account/UID
lifecycle, independently verified quiescence, credential retirement/rotation and
restore reauthorization. Joint acceptance must connect these exact unit policies
to the packaged modules and retained state without test overrides, then governed
Snowflake/source/provider integration. Hosted Ubuntu acceptance does not establish
compatibility on the existing Debian GCP host. A GCP build or startup still needs a new
explicit spend window.

The follow-up [installed services/private-plan acceptance](agent-service-credentials.md)
uses the unchanged unit contents and actual installed modules for private-plan
faults and bounded receipt lifecycle checks. It is separate from both the dummy
resource probes above and a successful unit-backed HTTP-to-result journey.
