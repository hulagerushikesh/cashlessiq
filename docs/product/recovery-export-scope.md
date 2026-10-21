# Bounded synthetic replay-input export — approval package

21 October 2026. **Approved and executed within the bounds below.** See the
[capture/replay evidence](recovery-inputs-evidence.md). The original approval
package follows for audit context; it is not permission for repeated captures.
Current metadata checkpoint is complete. P2 remains open. This proposal expands
local persistence beyond metadata; obtain the owner's explicit approval below
before reading/exporting the additional payloads. No runtime activation.

## Why this small expansion is useful

Counts cannot reproduce canonical saved-decision validation. The existing
operator inspection already defines the required fields, but deliberately has
no general export/HTTP registration. Preserve only its bounded three-case inputs
so that those observations can be revalidated after the trial without live reads.
Do not export whole tables or attempt an account backup.

| Source / projection | Permitted content | Bound per case |
| --- | --- | --- |
| Existing metadata query | Request, owner, policy/product IDs, product name/version, cover/admission dates, supplied integer estimate | Exactly one expected request/owner/policy/product |
| Existing `MEMBER_SQL` | Synthetic member/policy IDs, sum insured, bonus, status, aggregated claim count/paid amount/latest admission | Exactly one row; fetch up to two to detect duplicates |
| Existing `CONDITIONS_SQL` | ICD-10 code, condition name, first diagnosis date, declaration flag and scoped request/owner | At most 20; fetch 21 to detect overflow |
| Existing `DECISION_SQL` | Latest row by CREATED_AT DESC / DECISION_ID DESC: decision ID, outcome, stored payable, **full synthetic DECISION_JSON**, schema flag, creation time and scoped request/owner | Zero or one selected latest row; not all history |
| Existing `EVIDENCE_SQL` | Clause ID/product ID/heading/page/public policy source URL and scoped request/owner | At most 100; fetch 101 to detect overflow |

Use the exact projections and owner predicates in
`apps/api/src/ciq_api/source_inspection.py` and `snowflake_reads.py`; never
`SELECT *`. Metadata uses only the independently approved ownership map:
GOL001/TPA001/POL0001/MEM0001 and
GOL024, GOL027/TPA003/POL0024, POL0027/MEM0024, MEM0027.
All products must be `AS_NIA_V02_2425`.

The decision JSON contains free-text synthetic explanation/line labels and can
carry clinical information. It is **not protected by the CLINICAL_NOTE mask**.
The restricted inspection must treat it and condition rows as clinical payloads
even though these known cases are synthetic. Do not infer permission to disclose
them from a SELECT grant. Only persist privately after this scope is approved.

Exclude names, DOB, phone, city, document/file paths, PDF bytes, CLINICAL_NOTE,
RAW_EXTRACT, other facts/diagnosis/procedure text, clause body text, agent/model
metadata, review actions, audit events, other requests, tokens and credentials.
Do not redact decision JSON and then call it the original validated artifact;
if content is unexpected or cannot be accepted privately, stop without saving it.

## Two sequential execution gates

**Stage A: GOL001 only.** One metadata read, the four existing inspection reads,
one context query and one warehouse SHOW, each followed by its query-ID lookup,
plus one session timeout/tag statement: **15 explicit statements, five source
SELECTs**, at most five minutes wall time including CLI login. Server statement
timeout 30 seconds and queue timeout 15 seconds; no retries. Stop before the
next statement when the elapsed/statement cap is reached. One CLI batch with a
client deadline must not be described as instantaneous server cancellation.

Only after ownership/cardinality, payload size, canonical schema/arithmetic,
stored outcome/payable consistency and independent clause-citation checks pass
may Stage B start. Record-ID citations have an empty verified registry: fail
closed rather than invent record ownership. Ignore SCHEMA_VALID as proof.
On failure do not substitute a fixture, older decision or MISSING; review first.

**Stage B: GOL024 and GOL027 only.** One shared TPA003 metadata query, eight
existing inspection reads, context and warehouse SHOW, each with query-ID lookup,
plus session settings: **23 explicit statements, nine source SELECTs**, at most
five minutes wall time including login. Require successful complete owner-scoped
reads before canonical MISSING validation; a read failure is not missing.
Stop on any unexpected saved row rather than silently adopting new results.

Both stages total **14 source SELECTs, 38 explicit statements**, no automatic
retry. Up to two additional metadata-only warehouse checks are allowed after
auto-suspend, for a total ceiling of 40 explicit statements. CLI connection
setup statements are separately managed by the client. No AI, extraction,
search, Streamlit, source writes, account changes or extra warehouse size.
An exact USD cap cannot be enforced by these statement/time limits; no reserve
allocation, payment or credit purchase. Reconfirm the owner's balance/expiry
before expanding to anything larger.

## Implementation / private persistence acceptance

Implement and test the exporter offline before either stage. Use existing human
CLI auth as CIQ_PRODUCT_READER/NONE with CIQ_WH, **operator-only**. No application
startup or service credential fallback. Validate complete results in memory;
reject unknown columns, duplicate keys/IDs, ownership/identity mismatch,
unexpected cardinality and payloads over 256 KiB per decision / 2 MiB per stage.
Bound subprocess output while receiving it, not merely after buffering an
unbounded CLI response. CLI stdout/stderr and exception chains never reach logs.

Use a new ignored private directory (0700), files 0600, never overwrite a
checkpoint, never save failed raw results. Save successful stage provenance,
query IDs, exact SQL/projection hashes, code revision, timestamps, stage duration,
typed inputs and canonical derived observations, with checksums. A failed Stage B
must not invalidate the already successful Stage A; do not mark the entire export
complete. No committed payloads, public uploads, browser rendering, demo fixture
changes, off-device copy, encryption or whole-machine backup claim.

Replay must run with a connector that fails if invoked and use the same pure
canonical validators with independently scoped metadata/evidence; compare the
replayed observations with those derived at capture. All amounts remain supplied
or canonically validated integer values, never LLM-generated. A successful replay
is not a fresh rules recomputation from complete policy/clinical inputs.

These reads remain separate snapshots, **not coherent live isolation/API/UI
acceptance**. The export cannot restore all decisions, live rules or documents.
The reader has no POLICY_RULE SELECT grant: do not broaden grants or quietly
export rules under ACCOUNTADMIN. Committed SQL/approved generator policy remain
rebuild inputs, not proof of the current live rule registry. Live DDL, grants,
masking definitions and six runtime principals need their own exact review;
GET_DDL/admin access is not included here.

## Original owner approval request — subsequently accepted

Approve **private persistence of the three known synthetic cases' existing
inspection fields, including latest decision JSON and condition rows**, through
Stages A/B and their caps above. This authorizes no public disclosure, deployment,
real patient data, account provisioning, grants or human-policy rule changes.

After approval: offline exporter tests → bounded Stage A → canonical validation
and private save → Stage B only on success → offline replay → final suspended
warehouse check → redacted evidence report. All unrelated P2 gates stay open.
