# P2 authoritative membership — loopback candidate

Status: implemented locally, **not activated or deployed**. Parent:
[authenticated transport](p2-worker-transport.md).

## Narrow contract

`worker_membership.py` reuses the bounded loopback mTLS framing, required peer
certificates, explicit CA, leaf pins and URI identities. The fixed endpoint is
`/v1/current-membership`; it has no SQL, list, export, browser or signing endpoint.
Ordinary API/Compose startup does not construct it. No Snowflake calls occur.

- Only the trusted membership service receives `WorkerMembershipStore.lookup`.
  It opens a fresh PostgreSQL session and checks active user, tenant and membership.
  Workers receive a pinned client, **not operational database credentials**.
- The certificate-derived audience maps to exactly one configured tenant. The
  map is copied into immutable configuration and must cover exactly the pinned
  peers. Request bodies contain only canonical internal user UUID and random UUID
  nonce; tenant, role and peer identity fields are forbidden.
- The response contains only the echoed subject/nonce, pinned tenant and one
  current role (`processor`, `auditor`, `medical_officer`) or null. Null means the
  authoritative lookup found no active membership; source recommendations are
  unrelated. Database/network/malformed-response errors deny, never null fallback.
- Clients strictly validate scope, nonce and schema. No positive/negative cache,
  retries, connection pool or general DB session is supplied to workers. Every
  authority check calls the service again before input and before delivery.
- This is a privileged internal point lookup. An allowed worker can ask about
  internal UUIDs within its configured tenant; it is not a public directory or
  authorization by itself. The worker must independently verify signed capability,
  audience/operation, case scope, expiry, replay and disclosure matching.

## Local evidence

34 additional tests use real temporary loopback TLS, disposable PostgreSQL schemas
or explicitly injected fake memberships/inputs. They cover all three roles,
fresh role changes, user/tenant/membership deactivation, unknown UUIDs, wrong peer,
tenant mismatch, invalid roles, injection/duplicate JSON, nonce/subject response
binding, lookup failure, and medical downgrade/revocation during source work and
after validator return. Both tenant scopes compose through the existing reader
and validator authorities, preserving SAVED/MISSING and four fresh network checks.

The delegation composition uses fake source inputs and injected in-process
reader/validator invocation; these tests do not establish a fully containerized
three-service deployment. The separately tested summary mTLS hops remain intact.
Test CA/key files and listeners are removed by fixtures; no real credentials exist.

## Limits / next gate

Subsequent checkpoint: a [separate membership wheel and narrow DB adapter](p2-membership-db-boundary.md)
now build and pass disposable-schema tests. The
column-grant policy is review-only; dedicated-principal/container isolation and
live service composition remain unproven. The older broker membership adapter is
not packaged into this service candidate.

Fresh checks are point-in-time observations, not atomic authorization across
PostgreSQL and Snowflake. A change after the last check is not retroactively
prevented. Membership-service consistency/availability, overall deadlines,
production server, private addressing, service placement, exact database access
policy and process/network/mount isolation still need packaging and review.

The trusted service and host remain in the security boundary. Static certificate
pins do not implement automatic revocation/rotation. CA/signing-key custody and
retained replay lifecycle are still unapproved deployment work. No public v2
contract change, source activation, P3, provisioning or website deployment.
