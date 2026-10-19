# Product Phase P1 checklist

Status: In progress
Last updated: 19 October 2026

## M0: Contracts before movement

- [x] Freeze decision schema and all 30 deterministic case results.
- [x] Compare baseline results in golden regression tests.
- [x] Define API/event version conventions and tenant-scoped identifiers.
- [x] Inspect live Snowflake usage and save the economical development plan.

See `docs/architecture/contract-versioning.md` and `docs/product/snowflake-budget.md`.

Verification on 18 October: 61 pytest tests passed, Ruff passed, and whitespace
checks passed. Warehouse, search serving/indexing, and compute pools were
confirmed suspended after the cost inspection. M0 is complete; M1 is next.

## M1: Product foundation

- [x] Monorepo boundaries and one-command local startup.
- [x] Next.js shell and design-system foundation.
- [x] FastAPI liveness/readiness endpoints.
- [x] PostgreSQL tenant/user models and versioned migrations.
- [x] Local identity plus selected staging/customer OIDC approach.
- [x] Authenticated web-to-API GET /v1/me.
- [x] OpenAPI contract and generated TypeScript client.
- [x] CI workflow without Snowflake plus local API/browser smoke checks.
- [x] GitHub CI run passes after pushing the implementation.
- [x] Field-level ownership and data-classification matrix.
- [ ] Interview notes or validated assumptions from at least five target users.
- [x] Existing prototype and golden-rule tests still pass.

## Local engineering evidence

- 61 existing regression tests, 20 API/PostgreSQL/OIDC tests, and 5 browser
  smoke tests passed on 19 October. Python/web lint, TypeScript checks, Next.js
  production build, contract regeneration, and npm audit passed. npm audit
  reported zero vulnerabilities for the new product workspace.
- `make product-up` starts PostgreSQL, Redis, migrated API, and web; repeating
  startup preserves the existing synthetic users.
- API identity is fetched from PostgreSQL through authenticated GET /v1/me.
- Integration coverage includes token expiry/signature/issuer/audience,
  cross-tenant rejection, user/tenant/membership revocation, role capabilities,
  local bootstrap isolation, OIDC signature verification, readiness, and
  migration upgrade/check/downgrade/reapply.
- Browser coverage signs each of the three roles in and out, checks HttpOnly
  session cookies, mobile overflow, and cross-origin login rejection.
- Product builds and tests require no Snowflake connection or paid IdP.

## Remote engineering evidence

- On 19 October, [Product foundation run 39195287483](https://github.com/hulagerushikesh/cashlessiq/actions/runs/39195287483)
  passed for commit `5e9db2e`: existing regression tests, lint, generated-contract
  drift checks, TypeScript, production build, Docker startup, API/PostgreSQL
  integration, and browser smoke tests.
- The first remote run exposed repo-level test imports that depended on the
  launch path. Pytest now explicitly includes the repository root; no domain
  logic or golden expectations changed.
- No Snowflake queries, paid identity service, or cloud product deployment were
  needed for this verification. The existing public demo remains unchanged.

Local engineering work does not close the phase. The remaining gates are a
real research evidence from five target users and reconciliation of findings.
Use `docs/product/research/interview-template.md` to collect that evidence.

P1 is not complete and no P2 work may begin. Research evidence is outstanding;
architecture defaults must not be presented as completed user interviews.
