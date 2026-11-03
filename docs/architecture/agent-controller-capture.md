# Principal-bound controller capture

3 November 2026. Inactive, disposable PostgreSQL review package. No production
role, credential, binding, migration or service activation is supplied. No API,
worker or fake executor imports the capture client. Deployed images stay unchanged.

## Implemented boundary

[`scope-capture.sql`](../../deploy/agent-controller/scope-capture.sql) defines a
single `capture(text)` SECURITY DEFINER command. Installation identifiers are
quoted by the trusted disposable harness; callers cannot choose SQL, schema,
connection, tenant, actor, policy or credential. The protected principal registry
pins the authenticated login's name **and OID** to one tenant/medical officer,
one to thirty exact request IDs and an explicit window of at most four hours.
Bindings default disabled; the package creates no runtime login or binding.
The window authorizes test capture only, not a provider call or paid window.

Identity uses `session_user`, not caller-controlled session settings or the
definer's `current_user`. A role switch cannot borrow another login's binding.
Superuser/role/database/replication/BYPASSRLS capabilities and INHERIT are refused.
The intended runtime is a separate NOINHERIT login without any role memberships,
table/column/sequence grants, schema ownership or DDL privileges. Application
owner connections and shared cross-tenant logins are not accepted substitutes.

The command locks its binding, then tenant, user, membership, request, selected
policy and review in the existing clinical writer order. It requires active
medical membership, an open unassigned/owned review and approved, unrejected
policy. It rechecks the database wall clock after waiting for clinical locks.
Unknown, null, oversized or nonallowlisted requests fail before a projection.
The only result is the owned facts/latest revision, selected clauses/rules and
version/digest fields required for validation. No regression examples, full
calculated record, other case or general audit payload is returned.

The nonlogin definer has explicit column reads and minimal UPDATE-column grants
needed for `FOR UPDATE` locking. It owns only its capability schema/registry and
function, not clinical tables. Runtime receives schema USAGE and that one
function's EXECUTE, with no table grants. The function has fixed
`pg_catalog, pg_temp` resolution, qualified application objects, RLS enabled,
no dynamic SQL and a two-second lock wait. Its PUBLIC execution grant is revoked
in the same installation transaction; rerunning the package refuses existing
objects rather than replacing an installed authority.

[`ControllerCapture`](../../apps/api/src/ciq_api/agent_controller_capture.py)
finishes strict shared Python clinical validation and canonical fingerprint
comparison while those locks remain held. It deliberately does not substitute
PostgreSQL JSON serialization for the shared deterministic hashes. Clinical,
driver and connection failures become a fixed `scope_unavailable` error with
chained private traceback details suppressed. A returned snapshot is **not** a
reservation, submission permit, source observation or publication authorization;
later commands must independently recheck fresh scope.

## Disposable verification and limits

The dedicated CI suite refuses execution before connecting unless Linux,
the exact repository, explicit test opt-in and fixed dummy PostgreSQL 17 service
all match. It creates a new disposable database and unique roles, installs the
review package in an isolated migrated product schema, then connects using an
actual nonadmin login/password. It drops only its owned database/schema/roles.
Local collection skips; Docker Desktop and the GCP VM are not used.

The harness explicitly closes stock PUBLIC database TEMP/CREATE and product
function EXECUTE capabilities in its **new disposable database**. Those are
test prerequisites, not an approved blanket revoke against a deployed database.
Tests inventory effective table/column ACLs (including PUBLIC/inheritance), role
flags/memberships, object ownership, function owner/search path and PUBLIC
function ACLs. Before any real installation, independently inventory and review
the target database's schemas, owners, grants, default ACLs and every callable
function, then prepare exact forward/revoke changes. A one-time CI catalog is
not continuing drift enforcement or protection from a database administrator.

Acceptance exercises an owned successful capture and exact shared snapshot,
foreign/missing scopes, processor/revoked identities, disabled/expired bindings,
wrong name/OID, alternate session identity, null allowlist entries, policy/review
drift, direct clinical/ledger reads, workflow writes, allowance/receipt resets,
DDL/role escalation, protected registry access, canonical corruption and lock
serialization/expiry. All **59 actual-login checks** pass at revision `89586d4`,
alongside the existing 476 agent checks and fourteen encrypted recovery cases.
Thirteen offline client checks cover rejection before connecting and fixed private
driver failures. Revision `89586d4` passes [full product CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41576247892)
and [private preview CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41576247912).
Full regression passed 1,027 root, 2,011 API (sixteen expected skips), 72 membership,
58 client, 26 browser, 15 source UI and all eighteen MVP journeys. Catalog,
transport isolation, process containment, contracts/types/lint/build and owned
cleanup passed. The preview separately passed all eighteen journeys, encrypted
22-table recovery and both saved-workflow browser reopenings. Earlier superseded
runs were cancelled; two new denial-test collection/name-resolution assumptions
were corrected before this accepted revision. There was no live deployment.

## Remaining controller work

This is the first read capability, **not a least-privilege replacement for
`FakeAgentLedger`**. That existing test ledger still uses its owner connection.
Reserve/claim/heartbeat/checkpoint, recovery and private publication need narrow
principal-bound commands, protected accounting and fresh clinical locks. The
existing concurrent ledger and fourteen encrypted recovery journeys must pass
under that intended command path before any production permission is proposed.
The next [reservation-only package](agent-controller-reservation.md) prepares
protected fake holds and unsubmitted leases, separately from the still-missing
independent admission/checkpoint/publication integration.
The new registry is outside the application's normal migration/backup manifest;
no deployed recovery compatibility is claimed. A future deployed authority needs
explicit custody/revocation/restore tests and default-closed activation.

Independent Snowflake source capture, governed source/execution credentials,
authenticated controller/transport IPC, live receipt custody, provider
checkpoint/lookup/usage semantics and a bounded approved comparison remain.
No extra VM is required by this package; no paid resource was started.

PostgreSQL references: [SECURITY DEFINER and safe function installation](https://www.postgresql.org/docs/17/sql-createfunction.html#SQL-CREATEFUNCTION-SECURITY)
and [session/current identity](https://www.postgresql.org/docs/17/functions-info.html).
