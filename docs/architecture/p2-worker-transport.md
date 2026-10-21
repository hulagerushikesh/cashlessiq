# P2 authenticated transport — local test candidate

Status: loopback and explicit private-container test candidates pass;
**not activated or deployed**. Latest: [container mTLS checkpoint](p2-worker-container-mtls.md).
Parent: [worker boundary](p2-validation-boundary.md).

## Implemented boundary

`apps/api/src/ciq_api/worker_transport.py` provides explicitly constructed TLS
listeners/clients for the broker -> read-relay and read-relay -> validator hops.
Default loopback listeners bind only `127.0.0.1` on an ephemeral port. Separate
private adapters require a canonical RFC1918 IPv4/port, not DNS or caller URLs.
No ordinary API/Compose
startup imports or constructs them. No Snowflake connection is involved.

- TLS 1.3 minimum, explicit CA trust, required client certificates; client also
  verifies the server's IP SAN. Common-name fallback and TLS key logging are off.
- Both sides require an exact SHA-256 leaf-certificate pin and exactly one URI
  identity SAN `urn:cashlessiq:worker:<configured-audience>`. No CN/header/JSON
  identity fallback. Pin maps are copied into immutable configuration.
- Server constructs `TransportPeer` from verified TLS state. The validator then
  independently matches that identity to the signed reader/disclosure capability.
  Python objects themselves are not a security boundary from compromised local
  code; broker, validator and host remain trusted as previously approved.
- Clients verify the server before sending a capability. Each call uses a fresh
  connection, one fixed configured operation/path, a three-second socket timeout,
  no redirects/proxy discovery/retries, and closes on all paths.
- The two operations are `/v1/read-summary` and `/v1/validate-summary`; a listener
  accepts exactly its configured path, not arbitrary read/export/SQL endpoints.
- Only `{"token": "..."}` is accepted. Body limit is 8 KiB; token limit is 4096
  characters. Reject duplicate JSON keys, extra fields, duplicate/missing length,
  transfer encoding and unexpected content type. Return a strict scoped summary,
  `no-store`, connection close and generic failures. No request/payload/error logs.
- Eight handler slots and a bounded accept queue; handshake/read socket timeouts.
  These are not an overall operation deadline or proof against denial of service.
  The stdlib HTTP listener is a loopback test candidate, not a production server.

The delegated authority still performs fresh membership/time/replay checks;
transport authentication does not replace application authorization. The read
relay and broker retain their post-return delivery checks and scope validation.

## Evidence and limits

23 transport tests cover configuration and real loopback handshakes with temporary,
test-only CA/leaf keys and fake source inputs. Both hops compose successfully. Missing client certs,
untrusted/foreign/wrong-purpose clients, expired/wrong-host/wrong-identity servers,
wrong pins, spoofed identity headers, malformed messages, replay and source
exceptions fail closed or preserve the certificate-derived identity as expected.
No credentials/certificates are committed. Temporary private files are in a
test-owned temporary directory, private-key mode 0600, removed at fixture teardown.
No real service keys, certificate installation or persistent source identities.

Still open before activation:

1. The [narrow remote membership candidate](p2-worker-membership.md) now passes
   loopback freshness/revocation/medical-delivery tests without worker DB credentials.
   Production service placement, database privilege policy and isolation remain open.
2. Separate worker packages/containers, private addressing, mount/network tests,
   validated production server/deadlines/backpressure and startup/shutdown handling.
3. Exact approved CA/signing-key custody, encrypted store/unlock, least-privilege
   mounts, rotation/revocation/expiry/recovery and retained replay-file lifecycle.
   Static pins are allowlists, not automatic certificate revocation or renewal.
4. Coherent source SQL, exact Snowflake principals/views/grants/rollback, CoCo
   review, separate provisioning and bounded live acceptance approvals.

No public website deployment, P3, PUBLIC/account changes, paid services or live
source activation follows from this implementation.

Implementation references: Python 3.11 [SSL contexts and peer certificates](https://docs.python.org/3.11/library/ssl.html)
and [HTTPSConnection](https://docs.python.org/3.11/library/http.client.html).
