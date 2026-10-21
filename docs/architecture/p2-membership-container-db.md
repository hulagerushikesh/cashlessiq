# P2 disposable membership container/database acceptance

21 October 2026. Offline candidate only, not activated or deployed.
Parent: [membership DB boundary](p2-membership-db-boundary.md).

## Reproduce

```sh
make product-membership-db PYTHON='uv run python'
```

Requires Docker and the PostgreSQL 17 bookworm image. Explicitly builds the
membership `candidate`/`db-test` images and unchanged worker candidate. The
membership build uses its frozen lockfile and explicit context allowlist, copying
only non-editable installed wheels into the final Python 3.11 runtime. Default
startup refuses activation, and the default image excludes the DB probe,
API/auth/broker/models/Snowflake. Worker images still have no SQLAlchemy/psycopg
or membership DB adapter. Builds may download dependencies/base images.

## Exact disposable scope

The script creates a new UUID-named PostgreSQL container with **tmpfs data**, not
the normal operational DB/volume. PostgreSQL runs UID/GID 999, no Linux caps,
no-new-privileges, read-only root and bounded memory/CPU/PIDs; its data/socket/tmp
paths alone are tmpfs. No host port or persistent named data volume is created.
The cluster has only synthetic IDs/profile placeholders and a random test login.
It is destroyed after the test; this is not permission to modify production roles.

Membership/reader/validator run UID/GID 10001, read-only root, no caps,
no-new-privileges, bounded resources and tmpfs `/tmp`. Three Docker internal pair
networks separate membership↔DB, membership↔reader and membership↔validator.
Membership's **only** bind mount is its own read-only test DB JSON; DB alone has
its separate admin-password file. Reader/validator have no mounts/DB drivers and
cannot reach the actual inspected DB IP/port. Network and mount configuration is
inspected, including absent host-port bindings. The DB password is generated at
runtime, passed to provisioning over stdin and supplied to membership only via
the test mount, never argv/environment or test output. The host temporary parent
is private; mounted test files are readable by their non-root recipients.

This is Docker-owner/host-trusted isolation, not protection against host admins,
an allowed service proxy, all possible egress paths or container escape. The
ephemeral test DB explicitly disables TLS; production verified PostgreSQL TLS,
encrypted secret storage and actual mTLS membership-handler composition are
**not proved here**. No private source/real credential is used.

## Database policy and evidence

The disposable login has CONNECT/schema USAGE and exactly the proposed column
SELECT grants on `ops.tenant`, `ops.app_user`, `ops.tenant_membership`. No superuser,
create-role/create-db, replication, bypass-RLS, inherited roles or column grant
option. Shared PUBLIC database/schema privileges are revoked **only inside this
throwaway cluster**; an application function has PUBLIC EXECUTE revoked. This is
not an account-wide production remediation.

The canonical `RestrictedMembershipStore` runs using the real restricted login:

- Valid medical-officer lookup succeeds; foreign tenant and unknown user do not.
- Eighteen forbidden SQL operations independently fail with PostgreSQL
  `insufficient_privilege` (42501): broad/profile/name/other/future-table reads,
  INSERT/UPDATE/DELETE/TRUNCATE, schema/public/temp-table creation, table alteration,
  admin role activation and private application-function execution.
- Those negative operations run in **read-write** transactions, proving grants
  deny independently of the adapter's read-only transaction setting.
- A committed downgrade to auditor is observed. Deactivating user, tenant or
  membership returns absent active membership. Each container probe invocation
  constructs a fresh store; the earlier same-instance integration tests cover
  repeated lookup freshness.
- Revoking the required role-column grant denies (not absent); restoring it
  permits a fresh lookup. Stopping the DB also denies, never missing/fallback.

The trusted membership service intentionally sees both synthetic tenants; column
grants are **not tenant RLS**. This is a test-sized schema mirroring required
columns, not a migration/live operational schema acceptance or an exhaustive
PostgreSQL system catalog/builtin-function privilege audit. Production effective
PUBLIC/inherited privileges and dependencies still require exact review.

## Cleanup and remaining gates

The test passed. All invocation-owned containers, networks and tagged images
were removed; tmpfs DB data and temporary credentials were discarded. No normal
product service/volume was touched. Docker build cache/base images may remain.
Cleanup reports errors for the exact prefix instead of broad pruning; abrupt
host/process interruption may require scoped cleanup of that test prefix.

Regression verification: 362 API/PostgreSQL and 145 root rules tests pass;
root/API Ruff, changed-file formatting and git whitespace checks pass. Public
API/startup code is unchanged. Browser/build/remote CI were not rerun for this
internal-only container test increment.

The subsequent [private mTLS/DB composition](p2-membership-db-mtls.md) now passes
fresh revocation/outage checks across real delegated hops. This page records the
earlier independent database permission acceptance, not production activation.
Production server/deadlines, private DB TLS, encrypted key/credential delivery,
rotation/recovery, exact provisioning/rollback and the remaining Snowflake,
governed evidence and live API/UI acceptance gates remain open. No persistent
role/grant changes, Snowflake/AI, public deployment, push or P3.
