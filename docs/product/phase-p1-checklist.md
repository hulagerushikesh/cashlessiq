# Product Phase P1 checklist

Status: In progress
Last updated: 18 October 2026

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

- [ ] Monorepo boundaries and one-command local startup.
- [ ] Next.js shell and design-system foundation.
- [ ] FastAPI liveness/readiness endpoints.
- [ ] PostgreSQL tenant/user models and versioned migrations.
- [ ] Local identity plus selected staging/customer OIDC approach.
- [ ] Authenticated web-to-API GET /v1/me.
- [ ] OpenAPI contract and generated TypeScript client.
- [ ] CI without Snowflake plus appropriate API/browser smoke checks.
- [ ] Field-level ownership and data-classification matrix.
- [ ] Interview notes or validated assumptions from at least five target users.
- [ ] Existing prototype and golden-rule tests still pass.

P1 is not complete and no P2 work may begin. Research evidence is outstanding;
architecture defaults must not be presented as completed user interviews.
