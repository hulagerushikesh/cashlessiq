# Product P2 — read-only case workspace

Status: In progress — synthetic-only alpha  
Last updated: 19 October 2026

## Authority and limits

Rushikesh approved the P1 research-gate deferral on 19 October. Five target-user
interviews remain outstanding; defaults are hypotheses, not validated findings.
This exception permits synthetic-only P2 work, not real patient data, production
deployment, policy activation, or reviewer writes.

## First slice: local synthetic case reads

- [x] Authenticated, tenant-scoped queue and detail contracts.
- [x] Repository boundary with deterministic synthetic snapshots and provenance.
- [x] Queue filtering, pagination, empty and failure states implemented.
- [x] Case, synthetic member context, calculation trace, and evidence references.
- [x] Clinical narrative restricted by role; no patient identifiers.
- [x] No reviewer mutation or upload endpoints/actions.
- [x] API isolation/revocation tests, browser walkthroughs, mobile checks.
- [x] Existing golden results and generated contracts remain consistent locally.
- [x] Remote CI passes for the new case slice after push.

## Local verification

Remote confirmation: [CI run 39198298419](https://github.com/hulagerushikesh/cashlessiq/actions/runs/39198298419)
passed on 19 October for `d3623da`, including regression, snapshot/contract drift,
lint, type/build, Docker, API/PostgreSQL, and browser checks.

On 19 October: 62 existing/contract regression tests, 36 API/PostgreSQL tests,
and 12 browser tests passed (110 total). Ruff, web lint, TypeScript, Next.js
production build, and Docker startup passed. Desktop and 390px mobile layouts
were visually inspected. The browser suite covers the three roles, all three
case journeys, filter/empty state, missing case, anonymous access, and overflow.

Data consists of GOL001, GOL024, and GOL027 copied from the frozen baseline
`6406d74`. Snapshot regeneration is checked for drift in CI. Financial traces
are copied, never recomputed by the web or API. Query/referral payable is null,
not zero. Policy evidence contains registered source references, not retrieved
clause text. Live member history, SLA clocks, and assignment are not simulated.

The API strips diagnosis, procedure, and submitted clinical note for processors
and auditors. Financial line labels and rule explanations remain visible; this
is not a complete clinical-data masking policy for real data. Synthetic reads
are disabled outside local/test environments. No data ingestion path exists.

## Later P2 integration — not required for first local slice

- [ ] Governed Snowflake read adapter behind the repository interface.
- [ ] Approved economical integration verification and view parity.

Full M2/P2 is not complete until the integration criteria are met. The first
slice must work without Snowflake calls or AI spend. Do not start M3/P3 reviewer
commands as part of this work.
