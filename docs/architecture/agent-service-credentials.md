# Installed services and private startup plans

24 November 2026. Disposable Linux CI only. No operator Mac/GCP installation,
cloud build, payment, real credential, Snowflake or provider action.

This acceptance connects the three [manual service policies](agent-service-supervision.md)
to their actual installed API modules. The earlier stdlib probes remain the
separate evidence for resource exhaustion and descendant cleanup. Neither suite
is a production installer, a service activation approval or a live agent run.

## Installation and identity

The explicit CI harness refuses an existing `/opt/cashlessiq-agent`, any of the
three fixed runtime directories, any fixed service account/group name and any
dummy UID/GID before changing the host. It requires the existing root, exact
repository, opt-in, systemd-PID-1 and cgroup-v2 guards plus a separate package
opt-in. Ordinary local invocation refuses before installation or network access.

It builds API/domain wheels from the checkout, verifies their complete package
inventories and canonical source bytes, and installs non-editably at the exact
`/opt/cashlessiq-agent/venv` path. Runtime dependencies come from the frozen API
lock without development/optional provider packages and are installed with
exported hashes. A private Python 3.11 installation lives under the same root;
the service does not follow the hosted runner's mutable interpreter toolcache.
The trusted CI installation downloads dependencies/interpreter before runtime;
runtime services retain their original network restrictions.

Isolated installed imports must resolve inside the venv, all installed API/domain
package bytes must match the verified wheels, and the runtime tree including
symlink targets must be root-owned and lack group/other write permission. Legacy
`cashlessiq`, Snowflake and pytest must be absent from that environment. This
checks the trusted installation at a point in time; root remains trusted.
The newly created owned tree has group/other write and special permission bits
removed before verification. Foreign owners, special files and symlinks escaping
that private installation are refused; the harness does not repair an existing
installation or chmod external targets. Managed interpreter version aliases are
resolved to one distinct private interpreter, rather than treated as extra
installations.

Three separate locked, no-home NSS accounts use the source unit names and
distinct dummy UIDs. The unit files have unique invocation-owned names but their
contents are byte-for-byte copies of the examples: no command, identity, path,
environment, output, timeout or resource-policy overrides. The working directory
is `/` and isolated Python cannot import the checkout through `PYTHONPATH`.
This is hosted Ubuntu acceptance; the existing Debian GCP host is still untested.

## Private file and output contract

Only this trusted fixture stages dummy fixed-path plans. Each complete file is
closed before its service starts; its parent is root-owned, its regular leaf is
owned by the corresponding service UID with mode `0600` and one link. This does
not add a production secret-delivery API, accept a browser path or select a
runtime identity. Credential rotation, protected secret sources and UID reuse
remain operator-lifecycle work.

For each of the three installed modules the suite tests seven faults: missing
file, public-readable mode, wrong owner, symlink, multiple hard links, oversize
file and duplicate JSON keys. The duplicate-key case starts with a random dummy
secret as a protocol value, followed by the valid protocol: permissive last-key
parsing would accept it. All denials must finish under the exact service limits,
leave an empty cgroup with no restart and emit only the fixed role failure marker.
They must make no authentication attempt or retained-journal change.

Positive controls prevent an earlier import/process failure from being mistaken
for successful private-file rejection:

- A valid claim plan and a valid custody plan must deliver their exact random
  dummy password to a root-supervised listener at the runner's fixed
  `127.0.0.1:5432`. That listener implements only bounded PostgreSQL startup and
  a cleartext-password challenge, then always returns a fixed authentication
  denial. It cannot authenticate, execute SQL, inspect OID bindings, reserve,
  issue or publish. The custody fixture supplies only socket metadata owned by
  the distinct receipt UID; it never answers a receipt command. There is no
  database, clinical input or provider in this job.
- A valid receipt plan must open its separately provisioned private fake journal,
  emit the fixed readiness marker and exit on the original ten-second idle bound.
  The journal digest and owned stale socket must remain. A subsequent explicit
  negative invocation must refuse that stale endpoint without readiness, unlink,
  reset, adoption or history change. There is no automatic restart.

Actual module stdout/stderr stays in the host journal. The harness reads only
stdout/stderr records for the exact systemd invocation ID, with bounded output,
and compares them in private memory against the expected fixed marker sequence.
It never prints those records, subprocess errors, password packets, plan bytes,
validation details or a secret hash to Actions logs. Unexpected output fails with
a fixed diagnostic. The dummy authentication listener retains only boolean
outcomes and must record exactly two successful password comparisons. The
existing loopback-only unencrypted PostgreSQL transport is unchanged; a trusted
local listener receives the password by design, not as proof against a hostile
host or compromised local server.

The receipt journal is provisioned by a separate trusted fixture before runtime;
the packaged module still has no provisioning/reset command. Readiness is not
SQL/history parity, a clinical claim or publication authorization.

## Cleanup and remaining acceptance

Before removing private fixtures, the harness stops and confirms an empty cgroup
for every owned unit, then closes its dummy sockets/listener. Unconfirmed
quiescence retains private evidence and fails the job. It removes only its own
unit files, install, plans, journal fixture and accounts; it handles matching
private groups that `userdel` already retired and never enables a unit or prunes
host resources. Test authentication failure never becomes permission to retry
an uncertain real operation.

There are 22 local checks for early refusal, preservation of existing host
objects, complete wheel contents/bytes, bounded dummy authentication and private
diagnostics, safe owned-tree permissions/symlinks and special-file refusal,
alongside the fourteen existing service checks. The Linux job
contains 25 actual packaged-service invocations: 21 unsafe-file denials, two
password controls and two receipt lifecycle cases. The
[installed-service job](https://github.com/hulagerushikesh/cashlessiq/actions/runs/45352266042/job/138301386702)
passes all 25 at source `0feb310b8f951312842e49b585a2c43a6e6a71ff`, plus installed
artifact verification and confirmed cleanup (27 fixed acceptance markers).
Local verification passes all 36 focused service checks and repository Ruff.

The [full product workflow](https://github.com/hulagerushikesh/cashlessiq/actions/runs/45352266042)
passes all eight jobs on that same source: 1,063 root checks, 72 membership checks,
69 client checks, 2,554 API checks, 26 browser checks, fifteen source UI checks and
eighteen MVP journeys. Root/API retain three/29 expected skips, and API retains
two existing warnings. The combined HTTP/peer/database/restore job passes 44
cases; the independent receipt job passes 33. Ledger acceptance passes 476
baseline checks, fourteen owner-fixture encrypted restores, 313 restricted
commands, 53 lifecycle checks and 27 restricted restores. All eight earlier
systemd resource scenarios pass again. Product stack shutdown and owned
peer/container/image/service/account/file cleanup are confirmed. The separate
private-preview workflow was not retriggered: no application or preview runtime
source changed. Earlier failed setup revisions were superseded and their
unfinished workflows canceled; only the source/run above is accepted here.

The follow-up [complete service journey](agent-service-journey.md) connects actual
HTTP intent/result, restricted PostgreSQL, separate receipt UID and canned child
under the exact units. Its trusted fixture stages confirmed clinical claim and
independent custody assignment before the receipt's idle window and requires
readiness for the current invocation. The existing 44-case packaged
HTTP/DB/peer/restore suite remains separate evidence without these systemd
policies. Production credential delivery, account/UID lifecycle, separately
verified quiescence, rotation/retirement, restore
reauthorization and independent retained storage remain open. Governed
Snowflake/source/provider integration follows those gates. GCP rebuilding or
startup needs a new explicit spend/window approval.

The next [read-only quiescence helper](agent-service-quiescence.md) strengthens
complete-journey teardown with stable systemd snapshots, pending-job/PID checks
and direct recursive cgroup evidence. It does not authorize credential or UID
retirement, exclude concurrent root activation or change deployed startup.
