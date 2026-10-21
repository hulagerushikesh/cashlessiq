# P2 membership database boundary — package and review proposal

21 October 2026. Local offline candidate only; no activation or provisioning.
Parent: [membership transport](p2-worker-membership.md).

## Implemented

`apps/membership` is a separately locked Python 3.11 package. It depends on the
canonical worker wheel plus SQLAlchemy/psycopg; the reader/validator worker wheel
does **not** depend on it. Only membership receives the new canonical
`RestrictedMembershipStore`; it has no API startup, auth/session configuration,
broker, ORM identity models, migrations or Snowflake connector. Default startup
refuses activation. This checkpoint is wheel packaging, not a container or secret
mount proof. The older `WorkerMembershipStore` stays in the broker for OIDC
resolution; it is not included in the membership artifact.

The new adapter receives an explicit new-connection factory and fixed schema,
never a request-selected SQL fragment, DSN, tenant schema or destination. One
fresh read-only transaction joins three schema-qualified tables and returns only
the role for an exact internal user UUID and pinned tenant UUID. All three active
flags must be true. Invalid UUID/configuration denies before connection; bad or
duplicate results/database errors deny, not absent membership. No cache, retry,
profile fields, clinical data or credentials are logged/returned.

`statement_timeout=1000ms`, `lock_timeout=250ms` apply locally to the transaction.
The query limits rows to two so ambiguity denies. These are **not an overall
deadline**: connection establishment, server threads and network delivery still
need bounded configuration. Deployment must supply a dedicated NullPool/new
connection factory, finite connect timeout and private verified PostgreSQL TLS.
No default DSN/env/host-credential discovery is implemented.

## Proposed least-privilege PostgreSQL policy — NOT APPLIED

Review the actual operational schema/database, existing PUBLIC/inherited grants,
owner roles and network policy before producing an executable provisioning file.
The intended dedicated principal is neither the application owner nor migration
user. It must have no superuser, create-role, create-db, replication, bypass-RLS,
ownership, admin membership or grant options. Limit database CONNECT and schema
USAGE to the required operational database/schema, with column SELECT only:

| Table | Permitted columns |
| --- | --- |
| tenant | id, active |
| app_user | id, active |
| tenant_membership | tenant_id, user_id, role, active |

No table-wide SELECT, writes, schema creation, sequences, identity issuer/subject/
display name, other operational tables or future-table defaults. Check effective
privileges, not just direct grants: PUBLIC schema creation/TEMP, function EXECUTE,
role inheritance and database defaults can widen access. Do not revoke shared
PUBLIC privileges without dependency review and separate approval. Client
read-only transactions are defense in depth, **not a substitute for DB grants**.

This trusted service intentionally checks both synthetic tenants; these column
grants are not tenant RLS. Peer-to-tenant mapping and signed capabilities remain
mandatory. A compromised membership service/DB owner is in the trust boundary.

Only membership may receive its DB credential, on a separate private DB network;
readers/validators get membership mTLS clients only. Do not reuse the ordinary API
credential, human Snowflake OAuth or broker signing key. Production secret-store,
rotation/revocation, host trust and rollback must be reviewed before provisioning.
No persistent account/role/grant or secret has been created by this checkpoint.

## Local verification

```sh
make product-membership-check PYTHON='uv run python'
uv run python scripts/product.py test-api
```

The artifact check uses temporary non-editable wheel installations, verifies
byte-identical canonical adapter and absence of API/auth/broker/models/Snowflake,
then verifies fail-closed entry point. Its temporary environment is removed.
The build may access the package registry; it does not contact Snowflake.

Twenty new tests use existing disposable PostgreSQL schemas or mocks. All roles,
fresh downgrade/user/tenant/membership deactivation, foreign/unknown identities,
input/configuration rejection, connection failure and exact read-only/timeout/
qualified-query sequence pass. They use the existing **test admin connection**;
they do not prove dedicated-principal grants or container DB isolation. Full
backend suite: 362 passed; root rules: 145 passed.

## Next bounded checkpoint

The subsequent [disposable container/DB acceptance](p2-membership-container-db.md)
now passes: restricted synthetic principal, column/write/DDL denials, fresh
deactivation/downgrade, missing privileges/outage and per-service network/mount
isolation. This does not apply the production policy or prove DB TLS/secret
custody/mTLS-server composition. The original next-step scope below is retained
as context. The subsequent [pinned mTLS/DB composition](p2-membership-db-mtls.md)
also passes; verified production DB TLS and secret/lifecycle review remain open.

Package the membership container with only its DB identity mount and test it
against a separately disposable database/principal over private networks. Prove
allowed point lookups and forbidden columns/writes/DDL/other tables, fresh
revocation and outage denial. Review exact test provisioning/cleanup scope first;
never apply the production proposal automatically. Compose with mTLS only after
those artifact/DB checks. Production service/key/replay lifecycle, Snowflake
isolation, governed evidence and live API/UI acceptance remain open. No website
deployment, ordinary startup, push or P3.
