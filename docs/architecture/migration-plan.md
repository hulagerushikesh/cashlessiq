# Hackathon-to-product migration plan

Status: Product Phase P0 approved
Last updated: 18 October 2026

## Migration strategy

Use a strangler migration. Keep the hackathon prototype available while new
product slices replace it behind stable contracts. Do not perform a repository
wide move before the new application can execute an end-to-end case.

## Current component disposition

| Current component | Product destination | Action |
| --- | --- | --- |
| `src/cashlessiq/rules` | `packages/domain` | Preserve behaviour; strengthen types and traces |
| `src/cashlessiq/decision_schema.py` | `packages/contracts` | Version the schema; generate API types |
| `src/cashlessiq/procs` | `integrations/snowflake` | Retain thin adapters only |
| `app/services.py` | API use cases and repositories | Decompose SQL, orchestration, and persistence |
| Streamlit pages | `apps/web` | Rebuild workflows; do not translate widgets line by line |
| Public React demo | `apps/demo` | Preserve as public demonstration |
| Numbered Snowflake SQL | `infrastructure/snowflake` | Preserve idempotency and split by environment |
| Golden cases and tests | `tests/golden` | Preserve as regression authority |
| CoCo policy skill | policy-management tooling | Preserve human approval gate |
| Evaluation runner | worker and quality pipeline | Make runs versioned and repeatable |

## Incremental sequence

### M0: Contracts before movement

- Record current decision and rule contracts as fixtures.
- Add characterisation tests around the current rules core.
- Define API and event versioning conventions.
- Define domain identifiers and tenant scoping.

Exit: the current behaviour can be compared automatically with any replacement.

### M1: Product skeleton

- Create `apps/web`, `apps/api`, `apps/worker`, and shared package boundaries.
- Add local PostgreSQL and queue dependencies.
- Implement health, readiness, identity context, and one authenticated API call.
- Establish CI and environment configuration.

Exit: one command starts the stack and the web application calls the API.

### M2: Read-only case slice

- Implement tenant-scoped queue and case-read models.
- Add Snowflake read adapter behind repository interfaces.
- Rebuild the case workspace against live API contracts.
- Keep all mutations in the Streamlit application during this step.

Exit: the new UI reproduces queue, case, member, decision, and evidence views.

### M3: Reviewer command slice

- Add assignment, comments, optimistic locking, and reviewer actions.
- Persist workflow and audit events transactionally.
- Mirror approved outcomes to Snowflake analytics through an outbox consumer.
- Make the new application authoritative for one synthetic tenant.

Exit: a complete synthetic review occurs only through the new product path.

### M4: Asynchronous assessment

- Move agent execution out of `app/services.py` into a worker use case.
- Add job status, retry, checkpoint, and dead-letter handling.
- Wrap Snowflake search, semantic view, and agent calls as gateways.
- Validate generated decisions before persistence.

Exit: request processing survives worker restart and safe retry.

### M5: Ingestion and policy management

- Add secure upload and extraction pipelines.
- Add policy version, clause, rule proposal, approval, and activation models.
- Gate activation on regression evaluation.

Exit: a second supported policy can be onboarded without code edits or direct
database changes.

### M6: Retire prototype paths

- Run a defined parallel-validation period.
- Reconcile decision and audit records.
- Make Streamlit read-only, then remove it from operational use.
- Move hackathon-only runtime artefacts under `legacy/hackathon` in a dedicated
commit after the replacement is proven.

Exit: no production workflow depends on Streamlit or direct user Snowflake
credentials.

## Compatibility rules

- Historical decision JSON remains readable through schema-version adapters.
- Existing golden IDs remain stable.
- Every data migration is forward tested and has a documented recovery path.
- New policy rule types require domain implementation, tests, reviewer display,
  and explicit approval; unknown types fail closed.
- Migration scripts never rewrite historical audit events.

## Rollback

During M1-M5, the hackathon application remains independently deployable.
Feature flags select product slices per tenant. A failed product slice can route
new synthetic cases back to the prototype without deleting product records.
Once real data enters the product, rollback means disabling new processing and
recovering from versioned state—not copying data back into the prototype.

## First implementation milestone

The first code milestone after Product Phase P0 is intentionally small:

1. monorepo directories and build commands;
2. FastAPI health/readiness endpoints;
3. Next.js shell and design-system foundation;
4. local PostgreSQL with a tenant and user model;
5. authenticated `GET /v1/me` from web to API;
6. contract, unit, and browser smoke tests;
7. CI with no Snowflake dependency.

No rules, document, or agent behaviour moves until this foundation passes its
exit criteria.
