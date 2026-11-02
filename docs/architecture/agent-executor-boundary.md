# Agent executor boundary: implementation review package

2 November 2026. Proposed design grounded in the current repository. No service,
principal, credential, grant, SQL function, source write or live execution is
created by this package. The fake-only ledger remains inactive. The existing
small GCP VM can remain the first testing host; separate processes and identities
do not imply a larger VM or a second server. Measure memory during an approved
window before changing capacity.

## Current implementation and the gap

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
The concrete IPC protocol and hardening need implementation and denial tests;
there is currently no transport process to launch.

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

This is a privilege specification, not a tested grant script. No executable
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

Proposed default: live execution is disabled after restore, unknown recovery
state or a missing admission epoch. Keep a separately retained execution receipt
outside the restored database, or require bounded remote reconciliation before
reopening admission. Its custody, access, durability and cost require review.
The receipt must bind tenant/request, input identity, mapping/configuration,
attempt/submission IDs and approval window. It must not retain raw clinical
bodies in a general operations log.

Before provider I/O, both the local attempt checkpoint and the independent
receipt must be durable. A crash between either write, or between the writes and
I/O, remains noncallable pending reconciliation. This deliberately accepts a
possible unused reservation rather than assuming a missing response means no
execution. There is no claim of atomic cross-system writes or exactly-once
provider execution. Reconciliation must never replay an uncertain invocation,
relabel it with another mapping/grant, or release its allowance merely because a
lookup failed. The storage protocol and restore epoch enforcement are unbuilt;
they are pre-live acceptance requirements, not current implementation.

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
