# Target product architecture

Status: Product Phase P0 approved
Last updated: 18 October 2026

## Architecture goals

- Separate the reviewer experience from Snowflake session mechanics.
- Preserve the pure deterministic domain core.
- Use asynchronous work for document and agent processing.
- Make tenant, policy, rule, prompt, and model versions explicit.
- Keep transactional workflow state outside analytical query paths.
- Retain Snowflake as the governed intelligence and evaluation platform.
- Make every operation observable and safely retryable.

## Context

```text
Hospital / TPA system
        |
   API or secure upload
        |
CashlessIQ application boundary
        |
Reviewer, medical officer, policy analyst, auditor
        |
Customer Snowflake environment and approved storage
```

## Logical components

### Web application

Next.js and TypeScript provide the reviewer and administration experiences.
The browser talks only to the application API. It never holds Snowflake
credentials and never runs policy calculations.

Recommended client stack:

- React and Next.js;
- Tailwind and shadcn/ui-based design system;
- TanStack Query for server state;
- React Hook Form and Zod for action validation;
- generated TypeScript client from OpenAPI;
- Storybook, Vitest, Testing Library, and Playwright.

### Application API

FastAPI owns synchronous application commands and queries:

- authentication context and tenant authorisation;
- request metadata, assignment, comments, and reviewer actions;
- signed upload initiation;
- job submission and status;
- policy-management workflow;
- typed API contracts and idempotency enforcement.

Route handlers remain thin. Use cases live in an application layer and depend
on repository and gateway interfaces rather than concrete databases.

### Transactional store

PostgreSQL is the approved system of workflow record for tenants, users,
requests, assignments, status transitions, comments, reviewer actions,
idempotency records, jobs, outbox events, and configuration versions.

Snowflake remains the governed system for intelligence inputs, analytical
history, evaluation, policy retrieval, and customer reporting. Data movement
between stores is explicit, observable, and minimised.

### Worker and orchestration

Workers execute stages outside the HTTP lifecycle:

- virus and file validation;
- document parsing and extraction;
- fact normalisation;
- policy and member retrieval;
- deterministic rule evaluation;
- evidence retrieval;
- recommendation drafting and validation;
- evaluation and report generation.

Each job carries a tenant ID, request ID, correlation ID, stage, attempt, input
version, and idempotency key. Retries use bounded exponential backoff. Terminal
failures enter a dead-letter state visible to operations.

The first implementation may use a managed queue and worker service. Do not
adopt a complex workflow engine until branching, timers, or compensation logic
demonstrably requires one.

### Domain and policy engine

The existing pure-Python package becomes the kernel of `packages/domain` and
must retain zero Snowflake, HTTP, and framework imports.

Inputs are immutable typed objects. Outputs include:

- result values;
- rule and clause identifiers;
- rule-set version;
- calculation trace;
- warnings and missing prerequisites.

The application rejects any model-generated monetary value that is not backed
by a matching deterministic tool result.

### Snowflake adapter

Snowflake provides:

- governed member and policy analytical views;
- document extraction where approved;
- Cortex Search over versioned policy clauses;
- agent orchestration where it adds measurable value;
- evaluation datasets and quality reporting;
- customer-facing analytical exports.

All Snowflake interaction is behind explicit ports. Product code must be able
to test against fakes without a Snowflake account.

### Object storage

Original uploads and derived document artefacts live in tenant-scoped storage.
Access uses short-lived signed URLs. Malware scanning and file validation occur
before a document becomes available to downstream processing.

## Primary request flow

```text
1. API accepts metadata and returns an upload target.
2. Client uploads directly to approved object storage.
3. API finalises the upload using an idempotency key.
4. Transaction commits request + outbox event.
5. Publisher delivers the event to the queue.
6. Workers validate, extract, normalise, and assess.
7. Each stage persists its versioned result before publishing the next event.
8. Web application receives status through polling initially; server-sent
   events may be added when justified.
9. Reviewer action commits transactionally and emits an audit event.
```

## Reliability patterns

- Transactional outbox prevents database/event divergence.
- Idempotency records protect upload finalisation and reviewer commands.
- Optimistic version numbers protect human edits.
- Circuit breakers and deadlines isolate Snowflake and model failures.
- Stage checkpoints avoid rerunning successful expensive work.
- A poison document cannot block the queue.
- Deployments support database expansion before code activation and contraction
  only after old code is retired.

## Observability

Every request carries a correlation ID through API, queue, worker, Snowflake,
and audit events. Structured telemetry includes tenant-safe identifiers,
latency, status, stage, retry count, model, rule version, and token or compute
cost where available. Clinical text, document content, access tokens, and
direct identifiers are excluded from logs.

Initial dashboards:

- request volume and end-to-end latency;
- queue depth, oldest age, and SLA risk;
- failure and retry rate by stage;
- Snowflake and model latency and cost;
- reviewer edit and override rate;
- accuracy and citation quality by policy version.

## Deployment environments

Use isolated development, staging, and production environments with separate
identity clients, databases, storage, queues, Snowflake schemas or accounts,
and secrets. Production data may not be copied into lower environments.

Promotions use immutable application images and versioned database migrations.
Policy configuration follows its own approve-and-activate lifecycle and is not
silently coupled to application deployment.

## Scalability approach

- APIs remain stateless and scale horizontally.
- Workers scale by queue depth with tenant-aware concurrency limits.
- PostgreSQL indexes serve operational filters; Snowflake serves analytical
  workloads.
- Large files upload directly to storage rather than through application
  memory.
- Cache only non-sensitive, versioned reference data where invalidation is
  deterministic.
- Apply per-tenant quotas to ingestion, agent calls, and exports.

## Architecture constraints

- No final action without an authenticated human actor.
- No executable policy rule without an approved version.
- No cross-tenant database access path.
- No money calculated by an LLM.
- No clinical or personal content in general application telemetry.
- No direct browser access to Snowflake or long-lived storage credentials.
