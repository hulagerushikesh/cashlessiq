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

19 October increment: an optional, bounded source gateway and dedicated reader
role SQL are prepared with nine offline tests. Unknown tenants make no network
call; queries bind the server-owned TPA mapping and allowlist three golden IDs.
The existing auditor role is not reused because it inherits runtime writes.
Local authentication did not complete during this increment, so no live parity
or cost measurement is claimed. The gateway is not wired to HTTP/UI yet. See
[operator steps](../architecture/snowflake-read-integration.md).

Increment verification: 62 root tests and 45 API/PostgreSQL/gateway tests passed;
API Ruff and git whitespace checks passed. OAuth connection test timed out before
authentication; no source SQL, grants, warehouse activation or AI call ran.

Subsequent authenticated inspection on 19 October: bounded source metadata
parity passed for all three cases under CIQ_ADMIN. Live ownership is TPA001 for
GOL001 and TPA003 for GOL024/GOL027; the offline demo grouping must not become a
cross-TPA live tenant mapping. Dedicated CIQ_PRODUCT_READER does not yet exist;
its CoCo grant review, restricted-role verification, explicit tenant mapping,
and remaining member/decision/evidence parity are still outstanding. No grants
or source-data mutations were applied. This does not complete P2.

After CoCo applied the reader grants, direct grants and single grantee were
independently confirmed. Bounded Python gateway reads returned GOL001 for
TPA001 and GOL024/GOL027 for TPA003. Secondary roles are now explicitly disabled
before reads; tests fail closed if that command fails. 62 root and 46 API tests
pass. PUBLIC still grants Cortex/AI access, so the identity is not effectively
AI-disabled despite having no direct AI grants. No account-wide revocations
were made. This remains an operator spike, not tenant-RLS or full P2 completion.

- [ ] Governed Snowflake read adapter behind the repository interface.
- [ ] Approved economical integration verification and view parity.

Next local increment: immutable operator source scopes now require separate
UUID bindings for TPA001 and TPA003, reject the mixed offline demo tenant, and
bind/validate request IDs against their inspected owner rather than a global
allowlist. Invalid mappings fail before any connection; unknown tenants do no
I/O. No tenant/membership provisioning or HTTP integration was introduced.
62 root and 58 API/PostgreSQL/gateway tests pass (120 total); Ruff passes.
No Snowflake calls, grant changes, policy activation, or reviewer writes ran.
These guards were tested offline; the new query bindings have not been live
re-verified. Member/decision/evidence parity and service-identity hardening
remain outstanding. The two integration exit boxes remain unchecked.

Full M2/P2 is not complete until the integration criteria are met. The first
slice must work without Snowflake calls or AI spend. Do not start M3/P3 reviewer
commands as part of this work.

## Separate source-identity preparation — 19 October

- [x] Fixed, disjoint synthetic tenant mappings for TPA001 and TPA003.
- [x] Optional local-only seed with three distinct role users per source tenant.
- [x] Real PostgreSQL tests for identity/membership isolation, immediate revocation,
  idempotency, preserved database roles, and collision rollback.
- [x] Default demo startup and existing contracts remain unchanged; no snapshot
  fallback or automatic source-profile bootstrap login.

The new tenants were created only in isolated test schemas. Opt-in setup for
the persistent local stack is documented, not executed. No Snowflake calls or
credits were needed. These identity fixtures do not complete the two integration
exit criteria above, grant customer access, or permit P3 reviewer writes.

Verification: 62 root and 71 API/PostgreSQL tests passed (133 total). API Ruff
check/format and `uv run make lint` passed, as did git whitespace checks.
Plain `make lint` selected a system Python without Ruff; running it through
the project's uv environment resolves that tooling issue. No web contracts or
UI changed; browser/build checks were not rerun for this identity-only increment.
