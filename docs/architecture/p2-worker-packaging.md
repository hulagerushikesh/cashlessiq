# P2 worker packaging and container isolation checkpoint

Status: local offline candidate tested; **no deployment or source activation**.
Parent: [validation boundary](p2-validation-boundary.md).

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

This proves a packaging and topology/mount candidate, **not running worker isolation**.
The mTLS handlers currently bind loopback; no network-facing application listener
was added. Next: strict private-address configuration and end-to-end container mTLS
with disposable PKI, before any actual service bootstrapping. Separately package
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
