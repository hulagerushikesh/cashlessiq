# Agent executor boundary: fake process seam and remaining review

2 November 2026. Proposed design grounded in the current repository. No service,
principal, credential, grant, SQL function, source write or live execution is
created in a deployed environment by this package. The fake-only ledger remains inactive. The existing
small GCP VM can remain the first testing host; separate processes and identities
do not imply a larger VM or a second server. Measure memory during an approved
window before changing capacity.

## Implemented fake process seam

`agent_executor.py` now supplies an inactive checkpoint-to-process coordinator.
It first commits `begin_submission`, then sends a bounded canonical envelope to
one child, and finally publishes through the existing fresh clinical locks and
candidate validator. The envelope binds tenant, operation, attempt, stable
submission, mapping/configuration digests, captured input and the effective
submission lease/deadline. Publication rejects changed pins or an extended lease.

`BoundedFakeProcess` uses a fixed trusted test command, clean environment, closed
inherited file descriptors and a new POSIX process group. It bounds request,
reply and error pipes; any stderr, malformed frame, changed request hash, nonzero
exit, timeout or excessive output fails with fixed safe errors. The child group
is forcibly cleaned on completion/failure. One object permits one exchange;
the committed ledger checkpoint, rather than that in-memory latch, prevents
another coordinator submission. Failures retain reserved/uncertain allowance.
The child has at most ten seconds, shortened to the original lease/window minus
a two-second persistence margin; this is a fake engineering budget, not a
measured provider latency or a hard remote cancellation guarantee.

`apps/agent-transport` is a stdlib-only fake artifact: one fixed read-only canned
fixture is SHA-256 bound to one exact request. It cannot select a credential,
endpoint, file, command or retry policy through IPC. It does not calculate an
independent recommendation, authenticate a source observation or call Snowflake.
The default image excludes its local test helper and every product/SQL/provider
package. It is absent from product Compose, the minimal cloud runtime bundle and
automatic startup. The isolation harness refuses execution outside its explicit
disposable Linux CI job, before contacting Docker.

Disposable CI exercises that image with distinct numeric identities, exact
read-only dummy mounts, no network/host PID namespace/ports/privileges, dropped
capabilities, a read-only root and bounded CPU/memory/PIDs. Controller/transport
probes cannot read each other's unmounted dummy identity. The transport has no
PostgreSQL credentials/socket/client package or reachable database network.
A separate PostgreSQL suite checks checkpoint visibility before child startup,
private publication, revocation/review drift, bad results, crashes/timeouts and
conservative no-replay accounting. Offline tests cover protocol, environment/FD
inheritance, output bounds and descendant cleanup. Revision `ad38848` passes [product CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41434111010)
and [preview CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41434110762):
56 offline process/protocol and 13 PostgreSQL process/ledger cases join the 358
existing agent checks, all ten populated recoveries and full product/browser
regression. The separate container job verifies cleanup. The new cleanup test
handles disappearance/reaping during observation while retaining a bounded
requirement that no owned runnable descendant survives.

This is **not** a production sandbox launcher, private IPC authentication,
provider credential custody or database least privilege. Offline child tests run
under the test user's OS identity; the separate CI container tests establish the
narrow fake artifact/mount/network boundary. The container controller probe is
only a dummy mount/identity probe, not the real clinical controller service.
The real controller still uses the existing schema-owning test connection.
A [default-closed fake epoch and independent test journal](agent-admission-quarantine.md)
now guard this seam, including old-backup and cross-store crash tests. Live grants,
production receipt custody and source/provider integration remain unimplemented.
No route or worker imports this executor.

## Current database implementation and the gap

`FakeAgentLedger` directly opens SQLAlchemy sessions and reads locked tenant,
user, membership, request, policy, input-revision and review rows. It writes
only its four ledger tables. Tests use a schema-owning PostgreSQL principal.
Those checks establish workflow and transaction behaviour; they do not establish
least-privilege isolation from the rest of the database. The same API process
must not acquire Snowflake administrator credentials to make this seam live.

The source-mapping validator compares independently supplied clinical snapshots
with a pinned manifest. It neither captures source records nor authenticates the
observation. A future preflight must establish that provenance before a permit.
The historical reader roles, owner OAuth and retained `run_agent` helper do not
supply this boundary. The helper retries and writes legacy decisions, while the
new comparison stage must do neither.

## Proposed components and capabilities

Names here are component classes to implement, not provisioned account objects.

| Component | Required capability | Boundary |
| --- | --- | --- |
| Existing web/API and embedded deterministic worker | Existing human workflows and deterministic jobs | No provider secret, direct agent invocation, browser-selected source identity or agent job retry |
| Clinical ledger controller | Fresh owned clinical capture; mapping validation; exact approved admission; claim/heartbeat/checkpoint; validation and private publication | Separate process and PostgreSQL role; no administrator identity, source DDL, human finalization or general audit payloads |
| Source preflight | Independently capture the approved same-tenant projection and exact source definitions | Tenant-specific reviewed read scope; no model call, legacy write or broad MEMBER_360 enrichment |
| Provider transport | One permitted request, bounded response/status lookup and usage observation | Separate process/OS identity; only the selected tenant execution credential; no PostgreSQL credential or human workflow writes |
| Recovery operator | Reconcile durable local/external receipts and release a restore quarantine only under review | No automatic resubmission, deletion of cost history or interpretation of missing receipts as zero usage |

For the small test host, the controller and transport may share a VM while using
separate OS identities and private IPC. This provides a narrower process/secret
boundary, not a claim of VM-level isolation or protection from its administrator.
The transport receives the minimal immutable captured snapshot, operation and
stable submission IDs, exact mapping/configuration digests and original deadline.
It cannot select a tenant, credential, tool inventory or spend allowance from a
prompt. No secrets, raw observations or arbitrary connection parameters belong
in IPC errors, CLI arguments, browser responses, job payloads or general logs.
The implemented fake stdio protocol and disposable hardening above exercise
this shape. Production authenticated IPC, a service launcher and live secret
custody still require implementation and denial tests.

## Database privilege package to prepare

Do not turn the current owner-level SQLAlchemy connection into the execution
identity. First record the exact PostgreSQL ownership/effective grants and role
inheritance on a disposable database. Define an explicit runtime schema/object
inventory, then implement a tenant-bound capability path for the controller:

- No schema/table ownership, DDL, role administration, bypass privileges, broad
  inherited application writer grants or creation of a live grant from a fake
  approval string.
- Read only the clinical projection needed by `_scope`, selected policy clauses
  and immutable input revisions. Other tenants' rows, credential metadata,
  unrelated regression examples and evidence bodies must be denied.
- Mutate only the approved grant accounting and owned operation/attempt/private
  comparison transitions. No direct final-review, submitted-case, audit/outbox,
  analytics or policy-event writes. Preserve fresh membership and review locks.
- Choose and review the exact row-privilege/command mechanism before writing SQL.
  The existing Python tenant predicates are necessary but are not database
  isolation. Any privileged command boundary must fix its object resolution,
  arguments, caller identity and transaction semantics; a generic execute-SQL
  endpoint or broad owner connection is unacceptable.
- Retain one-attempt, append-only, foreign-key and state guards. The current
  cross-mapping fence is application logic under shared tenant/request locks;
  all future admission writers must use the same serialization boundary.

This remains a privilege specification, not a tested grant script. No executable
production SQL is supplied while the target effective grants and supported
mechanism remain unresolved. Prepare forward/rollback scripts with exact newly
created objects only after disposable privilege-denial acceptance; disabling
execution must not delete immutable receipt history.

## Source identities and secret custody

The approved [P2 isolation proposal](../product/p2-isolation-proposal.md) remains
the source boundary. Reading source data and executing an agent/tool are separate
capabilities. Prepare separate tenant-specific clinical read and execution
identities with the exact reviewed objects and no staging/legacy-decision write.
Inspect effective inherited PUBLIC capabilities before claiming isolation.
An agent's tool execution context and access to its underlying objects must be
verified against actual supported provider semantics, not inferred from the
agent object's name or a successful reader query.

Runtime custody must use a reviewed service authentication method, narrowly
accessible by the selected transport identity. No human ACCOUNTADMIN/OAuth
session, password fallback, copied CLI configuration or shared processor secret.
Prepare rotation, revocation and a clean-process reconnection test. Credential
creation and any secret service provisioning require their own concrete review;
this document neither selects a paid product nor authorizes provisioning.

## Restore quarantine before any live submission

The ten populated restore tests preserve checkpoints already present in the
backup. A backup older than a submission can erase its local receipt. The new
cross-mapping guard cannot detect a row absent from the restored database.
No amount of matching local hashes solves that missing-history problem.

The [inactive fake admission implementation](agent-admission-quarantine.md) now
adds migration `0005_agent_admission` with no default anchor row. Ordinary ledger
construction is quarantined. Explicit disposable provisioning binds an empty
local ledger to independently retained private SQLite test custody. Admission
compares the full bounded checkpoint inventory; an old backup missing a later
receipt fails closed even when its anchor/grant counters look valid. Four actual
encrypted pre-checkpoint dump/restore cases supplement the original ten cases.

External prepare precedes local commit; a second single-use issued marker must
commit after the local checkpoint and before fake child I/O. Either cross-store
gap is conservative: contradictory history quarantines, and restart cannot
rehydrate ephemeral issue permission. Lost or terminally closed custody is never
automatically recreated/reopened. Unknown submitted cost remains held. There is
no atomic cross-system or exactly-once remote execution claim.

The SQLite adapter is fake-only and not production custody or protection from
its owner/host. Production independently retained receipts, restore/operator
authentication and explicit reviewed reconciliation remain required. A real
restore must close admission externally before work and reconcile history before
any approved reopening. No service/cost has been selected or provisioned.

## Concrete acceptance before a live test packet

1. In disposable PostgreSQL, prove controller capability on one owned approved
   case and denials for another tenant, processor identity, revoked membership,
   direct finalization/DDL/receipt reset and alternate grant/role access. Run the
   existing ledger/concurrency/restore suites under the intended runtime path.
2. In process tests, prove the web process cannot read the provider secret, the
   transport cannot connect to PostgreSQL or mutate human workflows, credential
   selection cannot be changed by IPC input and clinical data never reaches
   generic errors or metrics. Exercise forced exit and bounded child cleanup.
3. Implement source capture with exact manifest pins, ownership/definition drift
   and revocation denials. Verify supported provider submission/run lookup and
   usage semantics against official documentation before implementing transport.
   Establish a remote budget shorter than the 120-second total ledger deadline,
   with explicit transport, validation and persistence margins.
4. Rehearse restoration from a backup made before a checkpoint and prove that
   external custody/quarantine prevents another admission. Rehearse a lost or
   contradictory external receipt, unavailable lookup and uncertain costs.
5. Present exact identities, cases, tools/search/configuration/content digests,
   attempts, deadline/window, expected charges and shutdown/rollback for owner
   approval. Only then perform bounded source/live golden comparison, followed
   by clinical UI display and joint human testing. A new GCP build/run also
   requires approval; the currently deployed old images remain unchanged.

See the [source mapping contract](agent-source-mapping.md),
[inactive ledger and limits](agent-run-ledger.md) and
[integration sequence](product-agent-integration.md). No current fake grant,
local validation receipt or passed synthetic test is live spending permission.
