# Inactive agent comparison contract v1

2 November 2026. This is offline engineering preparation. It does not activate
Snowflake, close governed P2 gates, authorize spend or change the deployed app.

## Snapshot and authority

`ciq_api.agent_contracts.AgentInput` captures one server-owned request, its
selected policy projection and an immutable binding. Clinical JSON is stored as
canonical strings; returning decoded copies cannot mutate the captured snapshot.
The policy projection includes product/version, effective dates, wording document
identity, clauses and rules. It excludes regression examples for other requests,
authoring commands, names and authoring reasons. Capture first validates the
full proposal through the existing policy contract.

The binding contains:

| Field | Meaning |
| --- | --- |
| `schema_version`, `orchestration_version` | Exact version 1 and `inactive-comparison-v1` |
| `tenant_id`, `request_id` | Owned operational request identity |
| `policy_id`, `product_id`, `policy_version` | Selected approved policy identity |
| `input_revision`, `review_version` | Input amendment and human-review fences |
| `input_digest` | Normalized selected request facts |
| `rules_digest` | Ordered selected rules |
| `policy_digest` | Selected policy projection, including wording and dates |
| `evidence_digest` | Policy ID and clauses plus request ID and facts |
| `correlation_id` | Trace correlation; not an authorization or idempotency key |

Hashes bind content; they do not prove ownership or approval. `AgentContext`
must be reconstructed from trusted product records and current authorization.
Never accept its approval/clinical/tenant/review flags from a browser, response
or old queued payload. Admission and hypothetical publication both require the
entire binding to match, an active tenant, an approved policy, clinical authority
and an open review. A real implementation must perform the final check inside
the publication transaction, with the appropriate row locks/fences.

## Candidate validation

The candidate echoes the binding and server-reserved run ID. Its allowed outcomes
remain APPROVE, APPROVE_WITH_DEDUCTIONS, QUERY and REFER. There is no DENY or final
human-action field. It contains strict integer claimed/payable values, an ordered
monetary line projection, versioned citations and a bounded explanation.

The parser accepts one JSON object up to 128,000 bytes, rejects duplicate keys,
unknown fields and invalid types, and emits a fixed error without raw clinical
input. Model exception objects and raw bodies still must never enter logs.
String/boolean/float money is rejected. Candidate totals, outcome, every line's
item/claimed/payable/deduction and citation set must match the canonical pure
rules calculation. A change that preserves the total but moves money between
lines is rejected. QUERY and REFER retain null payable with no calculation
lines, and an unknown claimed estimate cannot become zero.

`assessment.calculate_rules` runs the same pure calculation as the existing
submission entry point using the selected rule projection. Full submitted policy
validation remains in `calculate`; the agent snapshot separately validates its
clause completeness, rule IDs, singleton rule types and effective dates. The
golden tests compare the full outputs of both calculation entry points.

Root evidence must contain the selected request record and exactly the clauses
required by that calculation. Each monetary line must carry exactly its canonical
clause references. References bind kind, source ID and SHA-256 of the selected
facts or clause content, resolved only within the owned snapshot. Missing,
extra, repeated or altered references fail. These are product evidence handles,
not an invented mapping to legacy Snowflake/Search records. Transport and
cross-system policy/evidence mappings remain to be reviewed.

The explanation is unverified clinical text. Numeric/citation validation does
not establish narrative faithfulness. No processor/auditor response, browser
route, persistence table or final decision consumes it in this batch. Future
display needs the reviewed clinical boundary, safe text rendering and human
review; structured success alone must not imply verified prose.

## Fake lifecycle and explicit limits

`agent_simulation` is pure and has no transport or persistence. Tests reserve an
immutable receipt before a fake call, with a run ID, fence ID, start and aware
deadline of at most 120 seconds. A fake result can become `validated` or
`rejected`; timeout/disconnect becomes `unknown`. Any supplied prior receipt,
including a reservation interrupted before a response, forbids an automatic
second attempt. Unknown/invalid results cannot pass hypothetical publication.
Receive and publication both reject expired deadlines, lost fences, stale
versions, revoked authority and closed human reviews. The simulation checks
time boundaries; it does not cancel or bound a real network call.

This does **not** solve the existing 60-second job lease versus 120-second
agent budget. In-memory receipts can be discarded, duplicated or lost on a
process crash. There is no database uniqueness constraint, durable checkpoint,
cross-worker claim, renewal, budget reservation or reconciliation implementation.
No real paid gateway may use this simulator as its executor.

The next design must specify a durable operation key independent of random
correlation/run IDs, transactional reservation before submission, stable remote
run identity, bounded lease renewal, revocation/final-review fencing, explicit
cost/attempt ceilings and manual reconciliation of ambiguous completion. A
client timeout cannot authorize a replacement paid call. A fresh context must
be checked before I/O and again in the final publication transaction.

## Offline acceptance

Run without Docker, a database, credentials or network calls:

```sh
apps/api/.venv/bin/python -m pytest apps/api/tests/test_agent_contracts.py
```

The 146 cases cover all thirty deterministic golden examples, immutable/minimal
snapshots, full calculation equivalence, wrong/stale bindings, revocation and
completed human reviews, per-line/total/citation faults, invalid JSON/types,
QUERY/REFER null semantics, missing estimates, uncertain completion, second-call
denial, deadline/fence failures and absence of live worker/transport wiring.
The fake gateway echoes independently recalculated expected values; passing is
contract validation, **not live Cortex reasoning or citation-quality parity**.
