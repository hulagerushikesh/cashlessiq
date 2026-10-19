# Product P2 — read-only case workspace

Status: In progress — synthetic-only alpha  
Last updated: 19 October 2026

## Authority and limits

Rushikesh approved the P1 research-gate deferral on 19 October. Five target-user
interviews remain outstanding; defaults are hypotheses, not validated findings.
This exception permits synthetic-only P2 work, not real patient data, production
deployment, policy activation, or reviewer writes.

## First slice: local synthetic case reads

- [ ] Authenticated, tenant-scoped queue and detail contracts.
- [ ] Repository boundary with deterministic synthetic snapshots and provenance.
- [ ] Queue filtering, pagination, empty and failure states.
- [ ] Case, member context, calculation trace, and evidence references.
- [ ] Clinical-sensitive detail restricted by role; no patient identifiers.
- [ ] No reviewer mutation or upload endpoints/actions.
- [ ] API isolation/revocation tests, browser walkthroughs, mobile checks.
- [ ] Existing golden results and generated contracts remain consistent.

## Later P2 integration — not required for first local slice

- [ ] Governed Snowflake read adapter behind the repository interface.
- [ ] Approved economical integration verification and view parity.

Full M2/P2 is not complete until the integration criteria are met. The first
slice must work without Snowflake calls or AI spend. Do not start M3/P3 reviewer
commands as part of this work.
