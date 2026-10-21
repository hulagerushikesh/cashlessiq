# P2 disposable membership database TLS acceptance

21 October 2026. Offline test target only; no production factory or service activation.

## Reproduce

```sh
make product-membership-tls
```

Extends the [restricted DB/private mTLS composition](p2-membership-db-mtls.md).
The five-container, five-private-pair-network topology remains unchanged. A new
tmpfs PostgreSQL cluster and synthetic login are created, not the normal product
DB or any Snowflake object. Explicit test targets alone contain the probes;
default membership/worker artifacts still refuse activation.

## Transport policy exercised

- Separate disposable database CA and one-hour DNS-SAN server certificate,
  independent of the worker mTLS PKI. CA private keys stay in host process memory.
- PostgreSQL requires TLS 1.3. Test-local Unix socket administration is trusted
  inside its container; remote plaintext is explicitly rejected. Remote IPv4
  TLS allows only the synthetic DB/login using SCRAM-SHA-256; IPv6 is rejected.
- Membership libpq uses fixed `sslmode=verify-full`, an explicit root CA file,
  minimum TLS 1.3, finite connect timeout, disabled GSS encryption and `NullPool`.
  `host` is the certificate DNS name; `hostaddr` is the actual inspected private
  DB IP, so no DNS lookup, address list, retry or alternate endpoint is needed.
- Only DB receives its server leaf key. The test bootstrap copies that key to
  DB tmpfs as UID/GID 999, mode 0600 (inspected). The read-only input key is inside
  a host-private temporary parent, not a production secret-store delivery design.
  Only membership gets the DB password and public DB CA in its own read-only
  identity mount. Broker/reader/validator retain no DB driver/credential/network.

Policy details follow PostgreSQL 17's official
[certificate verification](https://www.postgresql.org/docs/17/libpq-ssl.html),
[host/hostaddr connection parameters](https://www.postgresql.org/docs/17/libpq-connect.html)
and [server TLS/key permissions](https://www.postgresql.org/docs/17/ssl-tcp.html).
Encryption alone is not server identity verification; `verify-full` checks both
the trust chain and hostname. No production TLS default has been changed.

## Acceptance evidence and limits

- The real restricted connection reports `ssl=true`, `version=TLSv1.3` in its
  own `pg_stat_ssl` row. The delegated saved summary still validates to INR 95,000.
- A wrong hostname, while keeping the same private `hostaddr` and valid CA,
  produces the specific libpq hostname-verification failure. The canonical
  adapter turns it into `WorkerDenied`, never absent membership. This check is
  a direct DB/adapter negative probe, **not an end-to-end hostname-swapped service**.
- Explicit plaintext connection fails with the server's HBA/no-encryption
  rejection. It is an isolated negative probe, not a runtime fallback attempt.
- Replacing the mounted CA with an unrelated CA produces a certificate
  verification failure. Removing the explicit CA file produces a missing-file
  failure. Both deny actual broker→reader delegated requests while the same
  membership service/engine remain running. Each new connection verifies trust;
  restoring the correct CA permits a fresh request without service restart.
- Existing disclosure-change, user/tenant/membership deactivation, grant loss/
  restoration and DB-outage checks also run in TLS mode. Certificate pin/URI,
  wrong-peer, replay, foreign-tenant and forbidden direct-hop checks still run.
- All exact invocation-owned containers, networks and image tags are removed;
  tmpfs DB/key data and temporary credentials/PKI are discarded. Build caches/
  base images may remain. No broad prune or normal product-volume deletion.

These tests cover one synthetic tenant/subject and the nonclinical route. They
do not exercise expired/revoked certificates, CA/key rotation, recovery during
in-flight work, mutual client-certificate PostgreSQL authentication, production
DNS/secret delivery, malicious hosts or production server/load/deadline behavior.
Retained replay remains a separately tested mode, not combined with this TLS test.
The test-only factory still supports an explicit plaintext mode for the older
isolated DB harness; that is **not an approved production configuration switch**.

## Next gate

Verification: backend **362** and root rules **145** tests pass, along with Ruff,
changed-file formatting and git whitespace checks. The independent restricted-DB
harness still passes all 18 SQL permission denials and default artifact checks.
The earlier plaintext-DB/mTLS composition also passes unchanged. Final Docker
label checks find no remaining test containers/networks/replay volumes.
Browser/build, remote CI and retained-replay mode were not rerun for this
test-only increment; the earlier retained-replay checkpoint remains separate.

Review the exact key/secret/replay lifecycle and production connection-factory
configuration before live service wiring. Synthetic TLS acceptance is not
approval to create real service credentials, change account grants, activate
source routes, deploy the website or start P3. Snowflake isolation, governed
evidence and bounded local live API/UI acceptance remain P2 exit gates.
