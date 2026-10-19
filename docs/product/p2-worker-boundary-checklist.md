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

Files: apps/api/src/ciq_api/worker_authority.py, validation_worker.py and worker_broker.py,
plus worker_replay.py and worker_delegation.py, with corresponding tests.
They are not imported into main/create_app or HTTP
startup, do not change public v2/OpenAPI and contain no connector creation.
The handler is an in-process test primitive, not a running isolated container.

## Remaining, in order

- [x] Integrate broker identity/membership resolution and fixed summary routing
  offline using internal application user IDs. No caller-provided assertion
  minting API. This direct in-process summary composition is not the future
  read-worker path and is deliberately not exposed through HTTP startup.
- [x] Specify and test offline read-worker-to-validator delegation: separate
  audiences/operations, no scope widening, parent nonce binding and no raw export.
  The broker can select this path by trusted fixed route configuration only.
- [ ] Establish actual authenticated peer identity for delegation. OfflinePeer
  is explicitly a test double; never construct it from a browser/header claim.
- [ ] Implement private peer-authenticated transport and asymmetric assertion
  issuer lifecycle; current verification does not establish mTLS or peer identity.
- [ ] Implement authoritative membership adapter and before-delivery checks at
  read workers, including medical response downgrade. Broker, relay and validator
  now exercise a database-backed adapter in disposable local tests. No private
  remote membership protocol or distributed revocation behaviour is established;
  separate workers must not receive general operational database credentials.
- [ ] Replace process-local replay state with a reviewed atomic shared strategy
  before multi-process/restart-capable use. The optional SQLite candidate now
  passes same-host multiprocess/restart tests; the default remains process-local.
  All consumers must share one retained local file and fixed capacity. Separate
  files, network filesystems, rollback/restoration/deletion of ledger state and
  untrusted host/file administrators are not supported. Deployment packaging,
  mount/access/capacity configuration, clock discipline and lifecycle/backup
  handling still need review and tests; no live wiring is approved. Do not expose
  consume/before_delivery as independent HTTP endpoints or accept client claims.
- [ ] Package workers separately and test secret/network/mount isolation. Current
  API code location is a development scaffold, not credential/process separation.
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

255 API tests passed, including disposable PostgreSQL tests and the
110 boundary/broker/replay/delegation tests. Eleven replay tests include spawned processes,
restart/capacity/storage failures and expiry during consumption.
The delegation increment adds 32 focused tests and 16 existing broker scenarios
rerun through the delegated route. Both tenant scopes/all roles and SAVED/MISSING
are covered using fake source inputs. Tests reject wrong peer, changed scope,
swapped child, replay, extra output, source failure and delivery-role changes.
All 145 root regression tests pass. API/root Ruff checks,
API format checks and git whitespace checks pass.
Web/browser/build and remote CI are not rerun for this internal-only increment.
No Snowflake/AI calls, credentials, persistent source identities, source routing,
SQL/grants, service startup, push or website deployment. Existing local stack
was already running; regression schemas are disposable and removed by fixtures.
