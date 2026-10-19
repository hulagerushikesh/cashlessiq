# Product foundation: local development

Last updated: 19 October 2026

## Start and stop

Prerequisites: Docker Engine/Desktop with Compose, Python 3.11. Node 24 and uv
0.11.25 are needed for host-side development/tests, not for container startup.

```sh
make product-up
```

Open http://localhost:3000 and select a synthetic processor, medical officer, or
auditor identity. The page obtains the user, tenant, and role from authenticated
`GET /v1/me`. API docs are at http://localhost:8000/docs.

Startup creates `.env.product.local` with random development credentials using
owner-only permissions. This file is ignored and must never be committed or
copied to staging. Startup applies Alembic migrations and seeds three synthetic
users idempotently. PostgreSQL data persists across restarts. Bindings for the
web, API, and PostgreSQL are loopback-only; Redis has no host port.

```sh
make product-status
make product-logs
make product-down
```

Shutdown retains the named PostgreSQL volume. Keep the local environment file
alongside that volume: regenerating its password does not rotate an existing
database password. No command above starts Snowflake or calls a model.

## Boundaries

| Path | Responsibility |
| --- | --- |
| `apps/web` | Next.js reviewer shell, server-side session cookie and API client |
| `apps/api` | FastAPI identity, tenant membership, health, read-only synthetic case repository |
| `apps/api/migrations` | Versioned PostgreSQL schema |
| `apps/worker` | Reserved worker boundary; no consumers yet |
| `packages/contracts` | Generated OpenAPI; canonical definitions are API models |
| `packages/api-client` | Generated TypeScript types and typed HTTP client |
| `packages/domain` | Migration boundary; implementation remains in the existing pure core |

Redis is provisioned for future queue work; a healthy Redis container does not
mean jobs, retries, or assessment workers have been implemented.

## Checks

```sh
uv sync --project apps/api --frozen
npm ci
make product-test
make product-contracts
npm run typecheck
npm run lint
npm run build
npm run test:browser:install
npm run test:browser
make test
make lint
```

API integration tests require running local PostgreSQL. Each test creates an
isolated random schema, applies real migrations, and removes only that schema.
The application tables and seeded sandbox users are not reset by tests.

`make product-contracts` regenerates OpenAPI from Python models and the browser
types from OpenAPI without connecting to any database. Review schema changes
and commit both generated files together. CI checks for contract drift, then
types, builds, starts the stack, and runs API/browser tests without Snowflake.

## Identity approach

Local: the Next.js server creates a short-lived signed session through a
development-only bootstrap route, keeping the bootstrap key server-side. The
browser receives an HttpOnly, SameSite=Strict cookie. Login/logout reject
cross-origin form posts. The API checks the JWT signature, issuer, audience,
expiry, and server-side active membership on every `/v1/me` request.
The same checks protect every case read; tenant scope is derived from verified
membership, not a query parameter or browser header.

Staging/customer SSO: OIDC issuer, audience, and HTTPS JWKS URL with RS256
access-token verification. External identity is the `(issuer, subject)` pair;
a signed `ciq_tenant_id` claim must still resolve to an active membership.
Configure this claim with the identity provider, or implement an explicit
membership-selection flow before integrating a provider that cannot emit it.
The customer controls its workforce provider; no paid provider is required for
local work. Browser OIDC login/callback and customer provisioning are future
integration work, not part of this local sign-in implementation.

The API refuses local authentication in staging/production and omits the local
token route in OIDC mode. No browser-supplied role or tenant header grants access.
Only the three current review roles are implemented; policy/admin capabilities
remain for their own slices.

This is a local development stack. Production deployment, HTTPS session
configuration, OIDC callbacks, and operational job processing have separate
exit criteria and are not claimed complete here.

## Configuration reference

See `.env.example` for names only. Never place credentials in tracked files.
The API reads CIQ_DATABASE_URL via a secret value. Keep database statements and
tokens out of application logs. The web service uses CIQ_API_URL only on the
server and never exposes Snowflake credentials or an access token to client JS.

## P2 synthetic read-only workspace

After sign-in, open http://localhost:3000/cases. Search request/member references
or filter recommendation outcomes. Open GOL001 for deductions, GOL024 for PED
referral, or GOL027 for missing-cost query. All are fixed synthetic scenarios,
not new live assessments. Only the medical-officer role receives diagnosis,
procedure, and submitted clinical note. Financial labels and policy-check
explanations remain visible to all three current review roles.

`GET /v1/cases` accepts `search` (up to 80 characters), `outcome`, `page`, and
`page_size` (1–50). `GET /v1/cases/{request_id}` returns a read-only detail. Both
require `case:read` and active tenant membership. Another tenant sees an empty
queue and 404 for the fixed tenant's IDs, even with valid membership. There are
no assignment, approval, query-send, upload, or policy-write endpoints.

Snapshots are packaged with the API, not stored in PostgreSQL as operational
cases. Reproduce them with `uv run python -m scripts.export_synthetic_cases`.
It copies source facts from the seeded YAML and complete calculation/check
outputs from the frozen migration fixture. CI checks regeneration for drift.
The runtime API imports neither the generator nor the Snowflake/rules runtime.

`CaseRepository` defines the boundary for the future Snowflake adapter; this
slice implements only `SyntheticCaseRepository`. Reads are disabled outside
local/test environments. Evidence links reference the existing policy source
register; clause retrieval, real member history, and live SLA are not present.
Real-data access and rollout require separate research/privacy/security gates.
