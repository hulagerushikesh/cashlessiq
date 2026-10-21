# P2 container mTLS checkpoint

Date: 21 October 2026. Status: **disposable synthetic test passed; not activated**.
Parent: [worker packaging](p2-worker-packaging.md).

## Implemented

The default loopback classes still bind/connect only to loopback. Separate
`PrivateSummaryServer/Client` and `PrivateMembershipServer/Client` require an
explicit frozen `PrivateEndpoint`: canonical RFC1918 IPv4 plus integer port.
Wildcard, loopback, public, link-local, CGNAT, multicast, IPv6, DNS names, URLs,
ambiguous addresses and invalid ports are rejected before connection/binding.
These are trusted configuration objects, not browser-selected destinations.
Private addressing alone is neither authentication nor an egress firewall.

Private adapters retain the same TLS 1.3/explicit CA, mandatory certificate,
IP SAN, leaf pin, URI identity, strict body/response and capability checks as the
loopback implementation. There is no hostname-resolution/fallback route. Normal
API/Compose startup is unchanged. The stdlib HTTP listener remains a **test
candidate**, not a production server with overall callback deadlines.

## Reproduce

With Docker and uv available, from the repository root:

```sh
make product-worker-mtls
# Or: uv run --project apps/worker --frozen python scripts/test_worker_mtls.py
```

The explicit Docker `mtls-test` target includes a test-only harness, excluded from
the default candidate. Four disposable containers run the real canonical read
relay, delegated validator and remote membership adapters, with a test broker
driver. Four internal pair networks allow only broker/reader, reader/validator,
reader/membership and validator/membership adjacencies. Servers bind to exact
attached interface IPs, never `0.0.0.0`; membership has one listener per allowed
interface. No host ports are published. These networks are bidirectional, not
directional ACLs or protection from an allowed malicious proxy/host administrator.

Docker assigns addresses before certificates are generated. The temporary CA
private key stays in the test driver's memory; each container receives only its
own TLS key/certificate, public CA, public assertion-verification key and fixed
public configuration. Only the broker receives the disposable assertion signer;
only the validator receives the raw synthetic fixture; only the membership test
service receives synthetic membership state. Exact file sets and read-only key
mounts are checked. No general DB credential, Snowflake config or Docker socket
is mounted. Engine inspection verifies non-root UID/GID, read-only roots/mounts,
cap-drop, no-new-privileges, no host ports and internal networks.

Test PKI expires in one hour, is not a usable account/service credential, and is
not a proposed production secret-delivery mechanism. Per-role test files are
readable by the unprivileged container UID through dedicated read-only mounts;
their common host temporary directory is mode 0700. No shared private-key mount.
This does not establish protection from the trusted host/Docker owner.

## Observed acceptance

- Broker -> reader -> validator returns only the canonical validated SAVED
  recommendation summary: synthetic GOL001, payable INR 95,000. Raw decision,
  financial lines, clinical text and narrative do not return.
- Both workers call the separate membership service over pinned mTLS before
  work/delivery. Its test implementation reads fresh synthetic state, **not
  PostgreSQL**. Existing database-membership integration tests remain separate.
- Replay, tampered capability, wrong server pin/URI, broker direct-validator
  access, signed foreign-tenant claim and reader-certificate impersonation of the
  broker are denied. Direct-validator denial is topology-level, not evidence of
  a successful TLS handshake on a forbidden edge.
- Revoked membership denies; restoring it permits a fresh request; stopping the
  membership container then independently denies without cached-role fallback.
- The eight-container dummy topology/direct-IP/package smoke still passes and
  verifies that neither test harness exists in the default candidate image.
- 342 API/PostgreSQL tests (30 new private-configuration tests), 145 root tests,
  Ruff/format/whitespace checks pass. Public OpenAPI is unchanged. No browser,
  web build or remote CI rerun for this internal-only checkpoint.

Invocation-owned containers, networks, image tags and temporary PKI/fixtures are
cleaned up; Docker build cache may remain. Normal product services/volumes are
untouched. Abrupt host/process termination may require exact-prefix cleanup.

## Remaining gates

This smoke covers **one tenant, nonclinical SAVED flow**; it does not establish
all-role/all-tenant container acceptance, medical downgrade during processing,
MISSING behavior in containers, production broker identity or database isolation.
Those broader authorization behaviors have earlier unit/integration coverage,
not this container proof. The default variant uses process-local replay; a separate
[retained-volume variant](p2-worker-replay-lifecycle.md) now passes container
restart, unexpired-token replay and missing-store denial checks.

Next: separately packaged trusted membership service and its narrow DB policy. Real
CA/signing-key custody/unlock/rotation/revocation, production deadlines and
backpressure, exact Snowflake query/views/principals/grants/rollback review,
separately approved live acceptance and governed evidence display remain open.
No website deployment, normal worker activation, real secrets, Snowflake/AI spend,
account changes, push, tag or P3 is included.
