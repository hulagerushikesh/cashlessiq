# P2 worker packaging and container isolation checkpoint

Status: local offline candidate tested; **no deployment or source activation**.
Parent: [validation boundary](p2-validation-boundary.md).

Subsequent [combined v3 container acceptance](p2-unified-container-acceptance.md)
now passes the private worker/membership/DB-TLS topology with frozen fictional
health/time. It supersedes the combined-topology gap below, not the real-host,
custody, deadline or live-source gates. Earlier counts below are historical.

## Latest v3 artifact/domain checkpoint — 22 October

The v3 authority initially imported the broker's API/SQLAlchemy types. That is
unsafe for the minimal worker artifact even though loopback integration passed.
The broker now lives in API-only `worker_guard_broker.py`; worker-side authority,
health/state and pre-bind transport modules have no broker/auth/model/DB imports.
The explicit wheel and Docker context allowlists include those canonical modules
only. Existing legacy clock/probe context exclusions were corrected as well.

`make product-worker-package` builds a fresh non-editable isolated install and
compares all 19 canonical packaged module bytes to the repository. It actually
imports them with isolated Python and checks that broker/API, SQLAlchemy,
PostgreSQL, Snowflake, collector and test probes are unavailable. Default startup
still refuses activation. Seven offline manifest/import/context tests guard this
boundary; static AST checks alone are not claimed as sandboxing.

`make product-worker-guard` explicitly builds `guard-test` plus the default
candidate. Two network-free disposable Linux containers share one invocation-owned
private v3 volume as UID/GID 10001, read-only root, dropped capabilities and no host
ports/repository/key mounts. Explicit setup signs fictional health with a temporary
key that is discarded; only public fake evidence/configuration and known test
claims persist alongside the private SQLite file. No real host/provider is trusted.

The same canonical v3 guard consumes once, rejects replay from the other container
and after restart while the claim is STILL time-valid, then retains rollback denial
across another restart. Hash/expiry rows remain intact. Actual Linux boot,
monotonic and boottime samples are shared; this is not real synchronization,
suspend/resume or power-loss acceptance. The default image's canonical authority
hash, import/dependency exclusions, missing probe and activation refusal are checked.
The original v1 `make product-worker-clock` path is retained as a separate regression.

Invocation-owned containers, volume and image tags are removed in `finally`; build
cache may remain. Existing product containers/volumes and the public website are
untouched. This closes the v3 artifact/domain acceptance gap, NOT real provider,
encrypted secret custody, service recovery/fencing, deadline/readiness enforcement,
combined v3 private-container membership-DB-TLS topology or Snowflake isolation.
No runtime provider/credential discovery or normal startup/service wiring is added.

Verification: isolated worker package/import/refusal check PASS; v3 Linux test
`ciq-clock-f07c86211c0d` PASS and legacy test `ciq-clock-d3e303fa4ff4` PASS, with
invocation-owned resources removed. Seven new package regressions; **200 root**
and **886 API/PostgreSQL** tests pass, Ruff/changed-Python format/whitespace pass.
The existing invalid copied-model negative test emits one serializer warning.
No full private-container mTLS/DB-TLS topology, browser/build or remote CI rerun.

## Separate artifact

`apps/worker/pyproject.toml` builds `cashlessiq-worker-candidate` from an explicit
allowlist of canonical files, not a copy/fork of their implementations. Minimal
Python 3.11 dependencies are the pure domain wheel, Pydantic and PyJWT/crypto.
The Docker runtime does not contain API startup, database models/seeding, broker,
operator SQL readers, FastAPI, SQLAlchemy, psycopg or Snowflake connector. Shared
source types and synthetic identifiers were extracted from I/O modules; old API
imports re-export the same objects for compatibility. No public schema changed.

The Dockerfile uses a separate build stage, frozen lockfile and non-editable wheels.
Its dedicated build-context allowlist excludes secrets, configuration, repository
metadata and unrelated application files. Final image has no source checkout or
build toolchain copied from the build stage; it retains the Python base image.
UID/GID is 10001. No ports are exposed. Default `candidate` target exits nonzero
with an explicit activation-unavailable message instead of starting a service.

The explicit `isolation-test` target adds a **test-only TCP probe**; it is absent
from the default candidate. This is not a membership server, application broker,
live reader, validator endpoint or TLS substitute. The shared artifact contains
verification/validation primitives; per-role credentials and capabilities, not
Python module availability, must enforce runtime authority.

## Reproducible local test

From the repository root, with Docker running:

```sh
uv run python scripts/test_worker_isolation.py
# Equivalent: make product-worker-isolation PYTHON='uv run python'
```

This explicitly builds both targets, checks the final artifact excludes test/API/
DB/connector modules, and starts eight disposable test-role containers:
broker, four tenant/disclosure readers, two tenant validators, membership service.
It does not edit or run `compose.product.yml` or load `.env.product.local`.

Fourteen internal pair networks model only these adjacencies:

- Broker <-> each reader: four networks.
- Reader <-> its own tenant validator: four networks.
- Each reader/validator <-> membership: six networks.

Docker networks are **bidirectional**. They are not application authorization or
directional firewall rules. Certificate pins, operation/capability scope and fresh
membership checks are still required. Broker/membership/host remain trusted; this
does not claim isolation from a malicious proxy on an allowed edge or Docker owner.

The test inspects actual Docker configuration and checks:

- All 28 allowed directed peer edges work; all 28 forbidden directed peer edges
  fail by hostname **and every inspected destination IP**, not DNS alone.
- No host ports, ordinary product `db`/`api` names, or successful reserved-address
  TCP canary. All attached networks have Docker `Internal=true`. The canary is not
  an exhaustive internet/host-gateway firewall or Snowflake-egress test.
- Non-root UID/GID, read-only root filesystem and exact dummy identity mount;
  all bind mounts read-only, no Linux capabilities, no-new-privileges, bounded
  PIDs/memory/CPU and an ephemeral noexec/nosuid `/tmp`.
- Only broker has a dummy signing-file mount; only membership has a dummy DB-file
  mount. No worker gets those files, another identity mount, Docker socket,
  repository mount, human Snowflake config or application credentials in env.
- Worker imports succeed without API/DB/connector dependencies.

Dummy files contain only `dummy-only:<role>`: no certificate or usable credential
is generated. Test-owned UUID-named containers/networks/image tags are removed in
`finally`; temporary files are deleted. Docker build cache may remain. Existing
product containers/volumes are untouched. Cleanup failures report the test prefix
instead of broadly pruning Docker resources. Abrupt process/host termination may
require operator cleanup of that exact prefix.

## What remains

The original probe proves packaging/topology/mount configuration, not application
authentication. Subsequently, strict private-address adapters and an explicit
`mtls-test` image passed a [four-container mTLS smoke](p2-worker-container-mtls.md)
with disposable PKI and synthetic membership. Neither test helper is present in
the default candidate. No normal startup changed. The optional
[retained-volume restart test](p2-worker-replay-lifecycle.md) now also passes;
production recovery policy stays gated. Next: separately package
the trusted broker/membership service with its reviewed PostgreSQL access boundary.
Do not give general DB credentials to readers/validators.

Production server/deadlines/backpressure, exact encrypted secret delivery and
unlock, CA/signing-key rotation/revocation, retained replay mount/lifecycle,
coherent Snowflake SQL/identity/view/grant/rollback review and separately approved
provisioning/live acceptance remain open. No host Snowflake egress, real secrets,
service identities, API source activation, P3, push or website deployment.

Verification: the eight-container smoke passed, plus 312 API/PostgreSQL and 145
root regression tests. OpenAPI is unchanged; lint/format/whitespace pass. Browser/build/remote CI not
rerun for this internal packaging increment.
