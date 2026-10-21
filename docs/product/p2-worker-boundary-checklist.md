# P2 worker boundary: offline implementation checkpoint

Date: 19 October 2026. Design approved by Rushikesh; provisioning not approved.
Design: [validation/credential boundary](../architecture/p2-validation-boundary.md).

## Implemented slice

- [x] Explicit broker-issued RS256 assertions using injected signing key;
  verification-only worker key, fixed issuer/audience/tenant, case allowlist and
  summary-validation operation. Strict fields, 30-second maximum lifetime,
  no arbitrary SQL/URL/role input and no implicit key discovery.
- [x] Fresh injected membership lookup before source I/O and before delivery;
  revocation, tenant mismatch, medical downgrade, expiry and lookup outage deny.
- [x] Bounded, lock-protected process-local replay ledger. Duplicate concurrent
  attempts have one winner; full capacity denies rather than evicting live tokens.
- [x] Optional offline same-host SQLite replay ledger, explicitly initialized only
  by tests and injected into the authority. Atomic transactions share consumption
  and namespace capacity across processes; retained state rejects replay after
  authority restart. Missing/corrupt/locked/full storage denies without fallback.
  Only hashed authority namespaces/nonces and expiry are stored, never tokens.
- [x] Offline validator handler receives explicitly injected fake coherent input,
  validates request/policy/product/evidence scope and calls canonical Python
  saved-recommendation validation. Only an explicit summary allowlist returns.
  Raw input container has no generated repr; no payload/SQL/token logging added.
- [x] No decision row -> MISSING only after valid owned context. Bad saved amounts,
  citations, foreign/duplicate/overflow evidence and input failure -> unavailable,
  never missing/fallback. QUERY/REFER preserve uncomputed null payable.
- [x] 34 new no-network tests; keys are ephemeral in-memory test objects only.
- [x] Offline summary broker verifies application tokens and resolves active
  PostgreSQL user/tenant/membership using issuer plus subject. Assertions carry
  internal application user UUIDs; workers independently query fresh membership
  by that UUID and their pinned tenant. Fixed immutable tenant/disclosure routes,
  case allowlists and response scope checks have no browser-selected destination.
- [x] Broker re-verifies the application token and fresh membership after worker
  return, denying role changes, deactivated users/tenants/memberships and expiry.
  Seventeen additional tests use disposable PostgreSQL schemas, ephemeral keys
  and fake validator inputs; no Snowflake/network worker transport is involved.
- [x] Offline broker -> fixed read relay -> tenant validator composition. Broker
  pre-signs separate read-detail and summary capabilities, binding parent nonce,
  subject/tenant/disclosure/case/lifetime. Readers have public keys only; swapped
  or widened children fail before validator input. Each hop checks membership/
  expiry/replay independently and only the strict scoped summary returns.
- [x] Fixed reader/disclosure peer-policy checks with injected **fake** peer
  context. This tests authorization policy, NOT actual peer authentication.
- [x] Real loopback mTLS candidate for both broker -> reader and reader ->
  validator hops: explicit CA, required peer certificates, hostname/IP SAN checks,
  leaf pin plus URI identity, certificate-derived TransportPeer, fixed operations,
  bounded bodies/handlers and generic no-store responses. Twenty-three transport
  tests include real handshakes with temporary PKI/fake inputs. See
  [transport evidence and limits](../architecture/p2-worker-transport.md).

Files: apps/api/src/ciq_api/worker_authority.py, validation_worker.py and worker_broker.py,
plus worker_replay.py, worker_delegation.py, worker_transport.py and worker_membership.py,
with tests.
They are not imported into main/create_app or HTTP
startup, do not change public v2/OpenAPI and contain no connector creation.
Delegation/source handlers are test primitives, not running isolated containers.
Transport tests temporarily start loopback listeners; no normal startup changes.

## Remaining, in order

- [x] Integrate broker identity/membership resolution and fixed summary routing
  offline using internal application user IDs. No caller-provided assertion
  minting API. This direct in-process summary composition is not the future
  read-worker path and is deliberately not exposed through HTTP startup.
- [x] Specify and test offline read-worker-to-validator delegation: separate
  audiences/operations, no scope widening, parent nonce binding and no raw export.
  The broker can select this path by trusted fixed route configuration only.
- [x] Establish certificate-derived peer identity for loopback delegation tests.
  OfflinePeer remains a test double; the TLS adapter instead constructs
  TransportPeer only from verified certificate/pin/SAN state, never headers.
- [x] Narrow loopback mTLS membership service/client, immutable peer-to-tenant
  mapping, UUID/nonce-bound strict responses and fresh PostgreSQL lookups. Workers
  receive no DB credential. Role/user/tenant revocation and medical downgrade
  fail before delivery across network membership checks. See
  [membership evidence/limits](../architecture/p2-worker-membership.md).
- [x] Separate minimal locked worker wheel/image, canonical code allowlist and
  no API/DB/connector dependencies. Default image refuses activation. Explicit
  test target passes eight-container/14-private-pair-network and read-only dummy
  mount checks, including forbidden peers by direct IP. This is not a running
  application or mTLS-in-container proof. See
  [packaging evidence/limits](../architecture/p2-worker-packaging.md).
- [ ] Implement private peer-authenticated transport and asymmetric assertion
  issuer lifecycle in separately packaged workers. Loopback and a one-tenant
  private-container mTLS/delegation smoke now pass with disposable PKI and fresh
  synthetic membership. Exact private endpoints and key mounts are checked; real
  signing/CA custody, rotation/revocation and production server/deadlines remain
  open. See [container evidence/limits](../architecture/p2-worker-container-mtls.md).
- [ ] Package the authoritative membership service separately with reviewed DB
  access policy/private networking. Loopback remote checks now pass, including
  medical downgrade after validator return; deployed isolation, consistency,
  production deadlines and cross-service acceptance remain open. Separate workers
  must not receive general operational database credentials. A separate synthetic
  membership container now passes mTLS/outage/revocation smoke; it has no DB access.
- [ ] Replace process-local replay state with a reviewed atomic shared strategy
  before multi-process/restart-capable use. The optional SQLite candidate now
  passes same-host multiprocess/restart tests; the default remains process-local.
  All consumers must share one retained local file and fixed capacity. Separate
  files, network filesystems, rollback/restoration/deletion of ledger state and
  untrusted host/file administrators are not supported. Deployment packaging,
  mount/access/capacity configuration, clock discipline and lifecycle/backup
  handling still need review and tests; no live wiring is approved. Do not expose
  consume/before_delivery as independent HTTP endpoints or accept client claims.
- [x] Offline retained per-authority Docker volume candidate: actual reader and
  validator container restarts reject previously consumed **unexpired** tokens;
  fresh requests succeed. Exact mounts/modes and hash/expiry-only storage checked;
  missing ledger denies requests and listener startup without recreation. Test
  volumes/PKI cleaned up. Production custody/recovery and multi-host use remain
  gated. See [lifecycle evidence/limits](../architecture/p2-worker-replay-lifecycle.md).
- [ ] Compose actual separately packaged application workers over private mTLS,
  plus trusted membership DB boundary. Minimal worker artifact and dummy topology/
  mount smoke now pass; live handlers, real secret custody/rotation and retained
  replay volumes remain gated. No actual Snowflake credential/process separation
  is claimed by test probes.
- [ ] Exact approved secret-store/key delivery mechanism, rotation and revocation.
- [ ] Coherent Snowflake input query, duplicates/ownership/version evidence, exact
  view/role/principal/rollback package and CoCo review. Fake ValidationInputs do
  not prove a database snapshot or actual entitlement enforcement.
- [ ] Separate provisioning and capped functional-test approvals; only then
  local live API/UI acceptance. No website deployment or P3.

The canonical full decision validator remains unchanged. Independent clause
registry ownership is required; record-ID citations remain unavailable because
there is no approved independent record registry. No new finance computation,
clinical prose, financial lines or persisted projection is introduced.

## Verification

342 API tests passed, including 30 new private-endpoint configuration tests,
disposable PostgreSQL tests and the
167 boundary/broker/replay/delegation/transport/membership tests. Eleven replay tests include spawned processes,
restart/capacity/storage failures and expiry during consumption.
The delegation increment adds 32 focused tests and 16 existing broker scenarios
rerun through the delegated route. Both tenant scopes/all roles and SAVED/MISSING
are covered using fake source inputs. Tests reject wrong peer, changed scope,
swapped child, replay, extra output, source failure and delivery-role changes.
All 145 root regression tests pass. API/root Ruff checks,
API format checks and git whitespace checks pass.
Web/browser/build and remote CI are not rerun for this internal-only increment.
No Snowflake/AI calls, real/persistent credentials, persistent source identities,
source routing, SQL/grants, ordinary service startup, push or website deployment.
Existing local stack was already running. Regression schemas, temporary test
certificates/keys and test-only loopback listeners are cleaned up by fixtures.
