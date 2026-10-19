# Migration contracts and identifiers

Status: M0 foundation implemented
Last updated: 18 October 2026

## Frozen prototype baseline

`tests/fixtures/migration/v1.json` records the decision JSON schema and complete
deterministic results for all 30 golden cases at commit `6406d74`. This is a
characterisation baseline, not new clinical or policy approval. It includes
line amounts, calculation text, citations, waiting-period checks, queries,
referral reasons, and clause identifiers.

`tests/test_phase3a_rules.py` compares actual results with this fixture as well
as the independently hand-calculated golden expectations. The decision schema
test compares the live schema with the frozen copy. Never regenerate the
baseline simply to make a changed implementation pass. An intentional contract
change requires an explained diff, regression evidence, and a new version.

Known deployed extraction and agent issues in `docs/evaluation.md` are separate
from deterministic rules parity; passing these local tests does not imply that
the deployed agent has no remaining issues.

## API and schema versions

- Product routes use explicit major prefixes (`/v1` snapshots, `/v2` source reads);
  readiness and liveness routes are operational.
- Existing decision JSON remains the v1 payload without additional fields.
- New API responses wrap historical decisions in an envelope containing
  `schema_version`, `tenant_id`, and the unchanged `decision` payload.
- A breaking field, enum, identifier, money-unit, or semantic change requires a
  new major contract version and an explicit historical-reader adapter.
- Additive optional fields require client compatibility checks. Unknown fields
  inside the strict historical decision payload remain rejected.
- Integer INR values retain rupee units. A future paise contract must use an
  explicit new field or version, never reinterpret existing `_inr` amounts.

## P2 versioned synthetic source reads — 19 October

The `/v1/cases` snapshot contract remains unchanged, including its required
outcome and frozen example journeys. New `/v2/cases` and `/v2/cases/{request_id}`
routes use `schema_version: 2`, `tenant_id`, and `data_mode: synthetic_source`.
They are disabled by default (authenticated 503), require an explicitly injected
repository in local/test, and cannot be configured in staging/production by this
factory. There is no env switch or default operator connection on HTTP startup.

The queue is metadata-only and declares `recommendations_loaded: false`; it
does not infer availability or filter on an unread outcome. Detail separates
the supplied estimate from a discriminated recommendation: `MISSING` has no
outcome/payable, while `SAVED` contains freshly validated outcome, amounts and
amount provenance. A saved QUERY/REFER has a null payable; this is neither an
absent recommendation nor zero. Source failures/invalid records return a generic
503, unknown/unowned requests 404. All v2 case responses use `no-store`.

Detail currently includes validated member/claim aggregates, conditions only
for active medical-officer memberships, and product-clause reference metadata.
Condition arrays are null when withheld, not an invented empty history. Raw
clinical/decision prose, financial line labels/calculation text and historical
decision JSON are deliberately excluded from this first disclosure slice.
The canonical saved JSON is still validated internally; its schema is unchanged.
This is not full calculation-trace, citation-display or UI parity. Evidence
metadata is explicitly a product clause register, not retrieved/grounded text.

## Identifiers and tenant scope

- Preserve existing golden request IDs, policy IDs, rule IDs, and clause IDs.
- New application-owned IDs use UUIDs; external/source IDs are separate fields.
- A tenant is the operating TPA organisation. Insurer and product access are
  permissions within that tenant, not substitutes for tenant identity.
- Every operational aggregate has an immutable `tenant_id`; references and
  uniqueness constraints include tenant scope where an identifier is local.
- Resolve identity and tenant membership server-side. A browser-provided tenant
  value never establishes access.
- External Snowflake references are mapped through a tenant-scoped integration
  mapping. A prototype `TPA_ID` is not automatically a production membership.
- Citation lookup uses the current tenant, source identifier, and policy version.

## Event convention for subsequent slices

Events carry `event_id` (UUID), `event_type` (for example
`cashlessiq.request.created`), integer `schema_version`, UTC `occurred_at`,
`tenant_id`, `aggregate_id`, `aggregate_version`, `correlation_id`,
`causation_id`, and a typed `payload`.

Events are immutable. Consumers deduplicate by `(tenant_id, event_id)` and reject
unsupported versions. Transactional outbox publication is at least once;
reviewer command idempotency is scoped to tenant, actor, and operation. General
event envelopes and logs exclude raw clinical documents and secrets.

## M0 exit evidence

- Complete deterministic comparison exists for all 30 original golden IDs.
- The historical decision schema is frozen and checked locally.
- API/event versioning and tenant/identifier conventions are recorded here.
- No domain package or existing runtime has moved.

Next: M1 product skeleton within Product Phase P1.
