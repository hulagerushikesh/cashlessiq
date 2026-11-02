# Agent source mapping: inactive validation and review

2 November 2026. Repository inspection only; no Snowflake connection, SQL
execution, new credential, staging write or live agent call was made. This is
an inactive integration contract, not applied governance or transport.

## Keep two input paths explicit

The first live comparison should use separately approved, existing Snowflake
golden IDs with an independently captured source snapshot. A new PostgreSQL
request is a different path: it must use its owned, immutable `AgentInput`,
approved policy and exact evidence versions. Passing a new `REQ-...` string to
the old agent does not transport those records.

For new submissions, prefer tools that consume the captured snapshot, rather
than copying product data into legacy tables. This is a design recommendation;
the provider's supported tool transport, execution identity and credential
custody must be verified before implementation. If that transport cannot meet
the boundary, prepare a separate governed staging design with exact objects,
tenant predicates, retention, minimum grants and rollback. Neither path may
silently fall back to legacy lookup or grant source writes to a reader.

## Repository mapping and incompatibilities

The retained SQL and handlers below describe repository definitions, not a fresh
inventory of the live account. Live definitions and effective grants still need
the separately bounded metadata preflight.

| Product authority | Retained Snowflake source | Required decision before transport |
| --- | --- | --- |
| `tenant_id` UUID and active medical-officer membership | `CORE.POLICY.TPA_ID` via the request's policy | Server-owned tenant/TPA registry, exact case allowlist and unambiguous ownership. Never derive entitlement from a prompt, response or product ID. |
| Owned `submitted_case.request_id`, up to 120 characters | `DOCS.PREAUTH_REQUEST.REQUEST_ID`, `VARCHAR(20)` | Preserve separate namespaces. No truncation, hash shortening or implicit match of a new ID to an old row. |
| `case_input_revision` and `input_digest` | Mutable `DOCS.PREAUTH_FACTS` row | Pin a verified content snapshot; matching an ID alone cannot prove the input revision used by the tools. |
| Product `policy_version.id` UUID | `CORE.POLICY.POLICY_ID`, `VARCHAR(20)` | These represent different objects: the product UUID is a reviewed wording/rules version; the legacy ID is a member's insurance policy. Do not equate them. |
| Pinned product, policy version, effective dates and `policy_digest` | `CORE.POLICY_PRODUCT` plus `DOCS.POLICY_RULE`/`POLICY_CLAUSE` | The retained tool fetches rules by product, and search filters by product. Neither pins the new approved product policy UUID/content digest. Version-aware resolution is required. |
| Ordered typed rules and `rules_digest` | `POLICY_RULE` queried `ORDER BY RULE_ID` | Preserve the exact canonical ordered rule projection. String-sorting rules is not a substitute for validating their captured order/content. |
| Strict integer cost lines and nullable estimate | `PREAUTH_FACTS.COST_BREAKUP`/`ESTIMATED_TOTAL_INR` | Preserve absence and strict money types. The retained `_money` strips non-digits and defaults to zero; do not use that conversion for new product inputs. |
| Captured `sum_insured_inr` and `si_remaining_inr` | `CORE.POLICY` and `CORE.CLAIM` | The legacy handler recomputes remaining cover from claims and dates. Choose one governed as-of snapshot; do not silently replace the product's supplied synthetic facts with a later source value. |
| Captured `declared_conditions` | `CORE.MEMBER_CONDITION` by member | Same-tenant clinical ownership must be independently established; shared/ambiguous member identity is unavailable. Do not enrich a new snapshot with unrelated history. |
| Exact clause ID, selected clause content hash and policy ownership | `DOCS.POLICY_CLAUSE`; `AI.CLAUSE_SEARCH` keyed by clause ID | Clause IDs/product filters alone cannot distinguish changed wording or another policy version. Returned text must resolve to the captured owned clause and digest. |
| Request evidence reference and `evidence_digest` | Legacy record citations | A product reference resolves only within the captured request/policy. A separate reviewed registry must prove any cross-system correspondence; matching labels are insufficient. |
| Current review version/state/assignment and authority | No equivalent fence in the retained agent prompt | PostgreSQL remains authoritative; final locked publication must reject amended, revoked, reassigned or completed work. |
| Priority/due time and product progress | Legacy `TOOL_SLA_STATUS` using current time | SLA is a separately labelled operational observation. It cannot modify the captured assessment or reset its agent deadline. |

Inspection sources:
[core tables](../../sql/02_core_tables.sql),
[document tables](../../sql/03_docs_tables.sql),
[tool handlers](../../src/cashlessiq/procs/tools.py),
[tool registration](../../sql/40_tools.sql),
[search definition](../../sql/22_search_service.sql),
[agent specification](../../sql/50_agent.sql),
[product inputs](../../apps/api/src/ciq_api/mvp_contracts.py),
[snapshot contract](../../apps/api/src/ciq_api/agent_contracts.py).

## Versioned mapping package

Prepare a reviewed, immutable `source-mapping-v1` manifest before any live
admission. Its canonical content hash should become the ledger's existing
`source_digest`; today's fake tests use a placeholder hash, so no real mapping
is certified by the current schema.

The manifest must identify the input path, exact product/source schema versions,
tenant registry revision and case allowlist; pinned policy/rules/evidence
versions; exact tool/agent/search definitions and their content digests; the
normalization and strict null/integer contracts; and the deployment/package
revision of the shared deterministic rules. An unchanged tool name or agent
name does not prove an unchanged definition. Include the independently verified
source snapshot/version for a golden case. Do not put credentials, raw clinical
records or general account inventory in this manifest or its logs.

The immutable `AgentInput` already stores the selected clinical snapshot. Any
additional source snapshot needs its own reviewed clinical custody/retention;
a manifest digest is neither a substitute for that snapshot nor an access
grant. Mapping definitions, approval receipts and data provenance are distinct.

Reject a missing, ambiguous, changed or unsupported mapping before submission.
Once a submission checkpoint exists, a new manifest/grant must not be used to
retry the same uncertain execution under a different label. The present ledger
deduplicates only within its exact config/source binding; future cross-version
replacement and uncertain-cost reconciliation therefore need explicit review.
The existing grant/window/attempt allowance cannot be treated as an automatic
authorization for another configuration.

## Output translation must preserve the validation boundary

The old agent returns a legacy decision shape. The new comparison expects an
echoed immutable binding, reserved operation ID, ordered canonical monetary
lines, nullable QUERY/REFER payable and exact content-hashed citations. A
translator cannot manufacture those values and then claim the provider returned
them. Preserve independently verified provenance, distinguish provider output
from deterministic validation, and reject missing/mismatched monetary or source
evidence. No fabricated citations, inferred zero payable or fallback fixture.

`app/services.py::run_agent` remains outside the new adapter: it retries invalid
output and inserts into `CASHLESSIQ.APP.DECISION`. New comparison publication
belongs only in the private ledger transaction; it must not write a legacy
decision, mutate the human workflow or imply that generated prose is verified.
The retained broad `MEMBER_360` tool must remain disconnected from new product
execution until a separately governed same-tenant clinical projection exists.

## Implemented offline validation

[`agent_source_mapping.py`](../../apps/api/src/ciq_api/agent_source_mapping.py)
implements the immutable `source-mapping-v1` package. It has separate discriminated
identities for existing golden source IDs and captured product snapshots. A
manifest covers one tenant and input path, at most thirty exact request pins,
a registry revision, source schema, strict normalization version and exactly
seven definition roles (agent, case/waiting/payable/SLA tools, clause search and
shared rules package). Duplicate request/source mappings, mixed paths and
missing/duplicate/unknown roles are rejected. Names and content hashes both pin
definitions. Definition/case inventory order is normalized for hashing; the
clinical rule order is preserved.

Validation requires an independently supplied clinical `SourceObservation`, a
separately pinned expected manifest digest and the server-owned `AgentInput`.
It checks tenant/registry/schema/definitions, exact request/input/policy/rules/
evidence pins, distinct legacy insurance-policy IDs, source identity and capture
digest, then compares the entire canonical normalized facts/policy projection.
Strict integer money and explicit null/default values survive; no `_money`
conversion, remaining-cover recomputation, legacy lookup or fabricated evidence
is performed. JSON parsing rejects duplicate keys, unknown fields and packages
over 128,000 bytes. Boundary errors contain fixed codes rather than clinical data.

The observation's digest binds the normalized projection and source identity;
it is not a hash of a complete raw Snowflake export. A trusted future preflight
must establish actual source ownership, definitions, freshness and normalization,
with independently retained raw-source custody where required. This module
cannot authenticate a caller's assertions or prove database isolation. Test
observations intentionally copy synthetic fixtures; they are not source parity.
The `ValidatedMapping` receipt authorizes no I/O and is not a submission permit.
No route, worker, ledger, credential or transport imports this module yet. Both
paths are offline contracts; neither claims a working source adapter.

The accompanying 122 offline checks cover all thirty examples under both input
paths, changed tenant/registry/schema/definition/content/pins, strict money and
nulls, duplicate/ambiguous mappings, namespace boundaries and immutable receipts.
Review/correlation changes do not alter source capture identity; they still
remain fresh publication fences in the ledger. The source/schema/definition
revision must be reviewed before any live admission.

The fake ledger now separately blocks new reservations for the same request
under changed config/source digests while any nonexpired operation exists,
including completed/rejected work. It also blocks amended inputs under an
unresolved `submitting`/`unknown` execution, even with unchanged digests. Only a
never-submitted reservation already settled `expired` can be replaced under a
new exact fake grant. The same fence is rechecked before the durable submission
checkpoint, including databases with old conflicting reservations. Eighteen new
PostgreSQL cases cover state/identity changes, a concurrent cross-configuration
race, valid expiry replacement and the final permit boundary. The populated
restore suite also exercises changed-digest denial on restored published work.

This is intentionally conservative application logic under the existing trusted
tenant/request transaction locks, not a new SQL uniqueness guarantee, a provider
idempotency contract or an automatic cross-version reconciliation protocol.
There is no override endpoint. Live execution must first resolve the broader
identity/privilege, provider reconciliation, stale-backup and spend gates.

## Next concrete acceptance

1. Offline manifest/normalization fixtures and the conservative fake-ledger
   replacement fence are implemented above. Settle the actual governed source
   registry, independently captured observations and supported transport before
   connecting validation to a future live admission.
2. Prepare the clinical executor's process/secret/database access package and
   source preflight. Source-reading approval does not authorize tool execution,
   staging writes or a remote model call. Keep human administrator OAuth out of
   runtime custody.
3. Verify supported provider submission/checkpoint/lookup semantics and prepare
   a bounded adapter. The current 120-second legacy remote budget cannot fit
   unchanged inside the ledger's 120-second total deadline.
4. Present exact synthetic cases, identities, definitions, attempts, time window
   and expected spend for owner approval only after the package is reviewable.
   Then run live comparison and joint UI acceptance in a bounded VM window.

The [source isolation proposal](../product/p2-isolation-proposal.md),
[integration sequence](product-agent-integration.md) and
[inactive ledger](agent-run-ledger.md) remain applicable. No source or live
execution gate closes merely because this mapping has been written down.
