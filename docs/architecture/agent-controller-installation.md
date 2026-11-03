# Fake controller installation, catalog review and retirement

3 November 2026. **Inactive disposable engineering only.** Nothing here installs
or enables a deployed agent, runs a provider, changes Snowflake or starts GCP.
The running preview image remains `7940886`/schema `0003_mvp`.

The [operator rehearsal](../../scripts/agent_controller_lifecycle.py) consolidates
the six existing SQL packages into one empty installation. The
[actual-login suite](../../apps/api/tests/test_agent_controller_lifecycle.py)
tests forward installation, effective permissions, revocation and a password
rotation sequence. The earlier [encrypted restore acceptance](agent-custody-restore.md)
still covers dropped/recreated same-name logins with a new OID.

## Installation boundary

This helper has no command-line entry point, startup hook, HTTP route or worker
registration. It does not open a connection, accept/deliver a credential, create
a runtime login, stage an approval, enable a binding or commit the caller's
transaction. It requires an already-open transaction on the exact dummy Linux
GitHub Actions PostgreSQL service: explicit repository/opt-in, loopback port,
dummy account/password and a random `ciq_controller_<24 hex>` database. Product
schema must be a random `test_<32 hex>` at `0005_agent_admission`.

The trusted operator creates the two distinct dummy LOGINs. The helper accepts
only fresh private schemas and definer names, installs the original packages,
and pins the database OID plus five separate role names/OIDs: installer, clinical
definer, custody definer, clinical login and custody login. An existing schema or
definer is rejected; a repeated install cannot adopt or replace it.

In this **new disposable database only**, installation revokes PUBLIC database,
public-schema and product-schema access and product routine execution. It closes
PUBLIC global and additive per-schema defaults for the installer and both
definers, then grants only CONNECT, the intended private-schema USAGE and the
fixed clinical or custody command signatures. A catalog review must pass and all
four private registries must be empty. There is no epoch, allowance, deadline or
external journal creation/reset. Existing product rows are hashed before/after.

Each operator mutation uses a nested SAVEPOINT inside the required caller
transaction. A policy/SQL failure rolls back the whole installation even if the
caller catches the exception and commits its outer transaction. The helper
never commits that outer transaction. A failed audit must not be bypassed by
granting broader rights.

These broad disposable PUBLIC revokes are **not** a production migration. A
production inventory may contain other applications and trusted creators whose
access/defaults need separate review. No production database is accepted by this
helper.

## What the catalog review checks

The read-only review returns no authority or clinical projection. It requires:

- Exact name/OID database and role pins. Runtime roles are LOGIN, definers are
  NOLOGIN, all four are NOINHERIT/nonadmin with no memberships in either
  direction. Runtime roles cannot own/create schemas, create temporary objects
  or delegate CONNECT, USAGE or EXECUTE.
- Exact private table and routine inventories/owners. Every routine has the
  reviewed definer, volatility/parallel/leakproof properties, fixed search path,
  row security and lock timeout. Body, language and result type match the
  rendered local SQL package; argument defaults, variadic/set-returning/support
  changes are rejected.
- No unexpected private-schema, private-table/column or routine ACL recipient,
  including an unrelated third role. Private delegated capture execution is
  restricted to the custody definer; a helper must never become a general
  principal selector.
- Exact effective USAGE/CREATE, routine and column privileges for both runtime
  and definer identities across **all non-system schemas**. This catches PUBLIC,
  direct column-only grants, cross-domain execution, grant options, sequence
  access and unexpected human-record access/writes. Explicit current column
  lists reject a newly added column inheriting a whole-table definer grant.
- Effective global fallback defaults and every additive per-schema default entry
  for the installer and both definers. Future table/sequence/routine/schema
  privileges cannot silently go to PUBLIC, a runtime or an unrelated role.

PostgreSQL distinguishes existing object permissions from future object defaults;
per-schema default grants add to global defaults, and the role actually creating
an object determines its defaults. The rehearsal checks both surfaces rather
than treating a schema revoke as proof. See the official
[default privilege reference](https://www.postgresql.org/docs/17/sql-alterdefaultprivileges.html)
and [privilege model](https://www.postgresql.org/docs/17/ddl-priv.html).

This is a point-in-time trusted operator review, not enforcement against a later
administrator/DDL change. System catalog/builtin privileges and production
extension installation, peer authentication and process/host ownership need
separate treatment. Runtime secret/process compromise is outside this proof.

## Revoke, quiesce and rotate

Revocation first verifies every original role/database pin, then takes the fake
epoch lock **before** protected bindings. A two-second lock timeout fails the
whole SAVEPOINT; tests verify there is no partial NOLOGIN/ACL/binding change and
that an explicit retry after quiescence succeeds.

Clinical retirement disables its principal and reservation bindings, removes
private routine/schema/database privileges and sets NOLOGIN. Custody retirement
instead disables its principal and submission assignments and removes its own
privileges/LOGIN. Clinical retirement deliberately preserves the independent
custody assignment needed for conservative status recovery. It does not grant
custody permission to issue or publish with revoked clinical scope.

The tests retain an already-authenticated idle connection across committed
revocation: subsequent commands fail. Prepared/issued work and an original
private candidate lose further issue/publication/heartbeat capability. An
already-issued child or a command committed before retirement cannot be undone;
quiesce trusted peers and close their pools as part of an actual rotation. No
receipt, allowance, accounting, original deadline or human record is rewritten
by retirement. Submitted uncertainty remains held. Repeating retirement is safe.

The password rehearsal commits revocation **first**, changes only a random dummy
password through the trusted operator, then deliberately restores LOGIN/transport
and command ACLs without enabling any binding. The old password fails fresh
authentication; the new password authenticates the same pinned identity but
still cannot capture/checkpoint/issue or resurrect pending permission. Replacing
or recreating a login likewise requires new explicit reviewed OID bindings;
restoration tests prove a matching name cannot inherit an old OID's authority.
Neither path automatically re-enables or copies approved authority. Actual secret
delivery, session termination and separately approved reauthorization remain
deployment work; no credential is returned, persisted or logged by this helper.

## Acceptance and next gates

Revision `3b6b3aaba6938a391180a6efe9e36bbc991dac5e` passes **53 lifecycle cases**
in the [dedicated CI job](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41667545689/job/126026809738):
35 permission/source/column drift cases, three identity-pin faults, empty forward
installation, rollback despite an outer commit, a spoofed caller search path,
eight retirement stages, two password rotations and two bounded-lock retries.
The same job passes 476 existing agent checks, fourteen owner-fixture encrypted
restore baselines, 290 existing restricted-login cases and 27 restricted encrypted
restores. This step runs after the existing restricted commands and before the
restored-database suite; all service-container cleanup succeeds.

Local lint and 175 related offline checks pass. The new module skips before
connecting on the Mac. Offline guard checks reject ten unsafe connection/environment
envelopes without issuing SQL, and all sixteen expected routine sources render.
The browser authorization test also now waits for the role-switch login cookie
before using the shared request context: the first preview run exposed a 401/403
race in the test. No application authentication rule was weakened.

[Full product CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41667545689)
passes the same exact code: 1,027 root (three expected skips), 2,243 API
(twenty-four expected skips/two existing warnings), 72 membership, 58 client,
26 browser, 15 source UI and eighteen MVP journeys. Domain wheel, contract/type,
lint/build, process containment, database catalog and separate fake transport
isolation checks pass, and main-stack cleanup succeeds.

[Private preview CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41667545933)
also selects the same exact code: eighteen MVP journeys, matched encrypted
22-table restoration, saved-workflow browser reopenings after restart (8.0s)
and restored-volume replacement (7.3s), with both fresh-volume and stack cleanup
successful. GCP is freshly verified TERMINATED with its unchanged 1,800-second
STOP; Docker Desktop is off. No paid/live action occurred.

These checks require a quiescent trusted DDL/operator boundary. They do not provide
an atomic snapshot against a concurrent administrator changing catalog privileges.
Ordinary development keeps Docker Desktop off; no local container or live provider
is used. The [delivery dashboard](../product/delivery-status.md) records the current
scope and remaining production gates.

Next: independently authenticated production peer/process/credential isolation
and retained receipt custody, then deployed restore/rebinding/retirement checks.
The independently captured Snowflake clinical source and supported provider
submission/status/usage/timeout contract remain separate gates. Only after those
are concrete can an exact source/provider/build/test window be approved. There
is no new paid approval, production install, source query or VM start here.

The subsequent [Linux fake receipt peer](agent-receipt-peer.md) begins the process
boundary work with distinct actual UIDs, bilateral kernel peer authentication
and retained markers across reply loss/restart. Its separate acceptance does not
close the production process, secret-delivery or independent host-loss gates.
