# P2 restricted database membership over private mTLS

21 October 2026. Disposable offline composition, not deployed service wiring.

## Reproduce and boundary

```sh
make product-membership-mtls
```

This extends the [private mTLS harness](p2-worker-container-mtls.md), using the
separately packaged [restricted DB adapter](p2-membership-db-boundary.md).
Explicit `mtls-test` image targets only; default artifacts still refuse startup.
The membership target includes the canonical worker transport probe and DB probe
factory. Neither helper is included in its default `candidate` image.

Five invocation-owned containers: broker, reader, validator, membership and a
new PostgreSQL 17 cluster with tmpfs data. Five internal pair networks:
broker–reader, reader–validator, reader–membership, validator–membership and
membership–DB. No published ports or normal product DB/volume access. Exact
network sets and per-role read-only mounts are inspected. Only membership has
the DB credential, SQLAlchemy/psycopg and point-lookup adapter; actual-IP direct
DB connections from broker/reader/validator fail. Only the synthetic broker has
the assertion signing key; only the validator has raw synthetic decision input.

Membership runs the canonical `PrivateMembershipServer` with pinned peer
certificates, fixed audience-to-tenant mapping and
`RestrictedMembershipStore.lookup`. Readers/validators use canonical private
mTLS clients and fresh authorization/delivery checks. The same membership
process, engine and lookup instance remain running across all committed DB
changes; `NullPool` opens a new connection for each check. No JSON membership
state exists in this variant. DB errors deny access, never become an absent
recommendation or fall back to a fixture.

The temporary login has only database CONNECT, schema USAGE and exact column
SELECT on the three membership tables. PUBLIC database/schema privileges are
revoked only in this throwaway cluster. The separate
[DB permission harness](p2-membership-container-db.md) checks 18 forbidden SQL
operations independently of read-only transactions; those 18 operations are
not rerun through the HTTP membership protocol.

## Acceptance evidence

- Delegated, strictly validated GOL001 SAVED summary returns INR 95,000 without
  raw decision JSON, clinical narrative or calculation lines.
- Replay, changed capability, wrong certificate pin/URI, broker direct-validator
  hop, wrong client identity and a signed foreign-tenant claim are rejected.
- Changing processor to medical officer rejects the old nonclinical disclosure.
  Changing to auditor permits the same legitimate nonclinical read: auditor is
  not an unauthorized read role. This does not test a medical-to-processor flow.
- Independently deactivating the user, tenant or membership denies subsequent
  delegated requests. Restoring each permits fresh requests without restarting
  membership or rebuilding its engine.
- Revoking the required role-column SELECT denies requests; restoring it permits
  them. Stopping PostgreSQL denies requests while membership remains running.
- Test credentials, PKI, tmpfs DB and exact owned resources are removed. No
  broad prune, product-volume deletion, Snowflake calls or account changes.

The harness uses fresh requests after committed changes; it does not inject
revocation during an in-flight response or claim atomic distributed revocation.
Only one tenant, one subject and the nonclinical delegated route are exercised
in this container variant. Broader fake-source/DB tests cover other scopes;
neither is live source acceptance.

## Remaining gates

Verification: this composition and the original file-based private mTLS harness
pass, as do the independent restricted-DB/artifact harness (18 SQL denials) and
the separate retained-replay/restart variant. Cleanup label checks find no
remaining invocation-owned containers, networks or replay volumes.
Backend **362** and root rules **145** tests, Ruff, changed-file formatting and
git whitespace checks pass. Browser/build/remote CI were not rerun for this
test-only increment; public API and normal startup code are unchanged.

PostgreSQL TLS is **disabled only for this isolated disposable test**. This is
not acceptance of production DB transport, encrypted secret-store delivery,
certificate/key rotation, retained replay recovery or production server
deadlines/load handling. Docker owner/host and permitted services remain trusted.
The retained-replay variant is a separate test mode, not combined with DB mode.
No service discovery, retries, fallback or normal application startup is added.

Next: verified PostgreSQL TLS and negative certificate acceptance in this same
disposable boundary; then exact secret/key/replay lifecycle and service wiring
review. Snowflake views/service principals, governed evidence, local live API/UI
acceptance and final P2 exit remain separate gates. No P3 or website deployment.
