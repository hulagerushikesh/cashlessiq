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

Revision `3436411` passes the [dedicated disposable PostgreSQL job](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41425980997/job/125212572250):
358 contract/mapping/ledger checks in 19.86 seconds and all ten populated encrypted
restores in 11.70 seconds. Both full product and private-preview workflows pass,
including all eighteen MVP journeys in each. Local offline checks pass 268
contract/mapping tests; the restore tests are deliberately skipped without the
explicit disposable CI service. Python lint, whitespace and document links pass.
GCP stays stopped; no local Docker or Snowflake call was needed.

## Captured product tools — 27 November

[`agent_snapshot_tools.py`](../../apps/api/src/ciq_api/agent_snapshot_tools.py)
now provides three inactive, pure clinical tool reads for the captured-product
path: selected case facts, the shared deterministic assessment, and exact owned
policy clause resolution. Each call requires a freshly supplied server-owned
`AgentContext`, revalidates the complete capture and its hashes, and rejects
stale, revoked or unapproved scope. The context is an assertion from the trusted
caller; these functions do not discover membership or establish authorization.

Replies preserve the full product request namespace, captured remaining cover,
integer money and uncomputed null payable. They bind the complete input/policy
revision and content-hashed evidence. Clause lookup returns the exact selected
title/text/page; unknown IDs cannot fall back to another policy or search index.
Canonical payload strings prevent nested mutation and are excluded from repr.
Fixed errors and silent serialization prevent invalid-input diagnostics from
printing clinical values.

These are labelled captured-product or deterministic tool observations, not
independently captured Snowflake observations, provider output, citation-quality
acceptance or a `ValidatedMapping`. They cannot be parsed as agent candidates.
No HTTP route, model request, source lookup, SDK, database, credential or worker
uses them yet. The inactive client-tool codec below now defines their inline
specifications and dispatches synthetic tool-use messages. The existing legacy
Snowflake agent is unchanged and does not call these Python functions.
SLA and member-history enrichment remain outside this captured snapshot path.

Offline acceptance covers all thirty golden outcomes/payables, owned clause
hashes, null/money fidelity, changed wording, revoked/stale scope, corrupted
captures and unknown clause denial. Live source definitions, service identity,
provider transport and the account's availability still need verification before
integration. No Snowflake access or resource activation was used for this work.

## Captured client-tool messages — 27 November

[`agent_client_tools.py`](../../apps/api/src/ciq_api/agent_client_tools.py)
connects the captured tools to an inactive Cortex message codec. Snowflake's
[client-side tool documentation](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agent-sdk/conversations#execute-client-side-tools)
describes inline generic tools without matching `tool_resources`, client-side
tool-use requests, and submitting the complete tool-result batch. The
[Run API](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-run)
documents the tool-use/result JSON fields. These official references were checked
on 27 November; the account's support for this path has not been tested.

The codec advertises only selected case facts, deterministic assessment and exact
owned clause reads. Model arguments cannot select a tenant, request, policy,
source, command, SQL, URL or credential. It accepts a UTF-8 JSON tool-use array,
up to eight calls and 16,000 input bytes. Unknown tools, server-side calls,
permission-bearing calls, duplicate IDs/keys, malformed arguments, revoked scope
and unknown clauses reject the entire batch. Every batch revalidates the trusted
capture and supplied current context. Results preserve tool-use order and IDs,
include structured observations and binding/evidence hashes, and are bounded to
128,000 encoded bytes, including escaping and framing. Clinical contents are
excluded from repr and errors use one fixed code.

This is a pure codec, not an SDK integration, authenticated conversation or
execution permit. A future transport must prove that tool uses belong to the
original run and parent message; supply fresh clinical authorization; enforce
total turn/tool/deadline limits; and obtain durable approval/accounting for every
billable continuation. Recalling this pure function cannot establish remote
idempotency or permission to send another request. No whole response or SSE stream
is accepted, and no model prose or tool observation becomes a validated result.
The final provider candidate still needs its own complete binding, original run
ID, strict monetary values and exact citations through `validate_candidate`,
followed by the existing locked publication checks. No field is manufactured by
the codec to repair a deficient candidate.

Offline transcripts cover all thirty golden inputs through facts, assessment,
clause resolution and a separately supplied fake candidate, plus malformed,
revoked, cross-tenant, duplicate and output-bound denials. This establishes local
message behaviour, not actual Cortex latency, cost, citations or source parity.
Live transport, custody integration and a reviewed paid test remain open. Docker,
Snowflake and GCP are not required by these checks.

## Complete provider response decoding — 27 November

[`agent_provider_response.py`](../../apps/api/src/ciq_api/agent_provider_response.py)
now connects a complete non-streaming aggregate to the captured tool dispatcher
or the existing final-candidate validator. The official
[Run API reference](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-run#non-streaming-response-stream-false),
checked on 27 November, documents this aggregate and its nested tool-use, text,
thinking and metadata fields. These tests supply synthetic responses; no SDK,
endpoint, runtime service, route or worker invokes the decoder yet.

The supported profile deliberately requires `role: assistant`, explicit
`status: completed`, matching expected provider run metadata and no warnings.
Some documented examples omit status or metadata; those examples are rejected
rather than silently treated as successful. Actual paused client-tool response
status and account wire compatibility remain unverified. Provider IDs are opaque
strings, distinct from the internal operation UUID that the candidate must echo.
A supplied thread cursor must contain strict positive thread, user-message and
assistant-message IDs together, with distinct user/assistant messages.

The decoder accepts only a batch of client tool requests or one final text
block, optionally accompanied by bounded private thinking. It preserves complete
assistant content on tool turns for future reviewed continuation; thinking is
never searched for a candidate. Server-side tools/results, mixed tool/text
messages, unknown content extensions, permission requests and nonempty warnings
reject the whole response. Final text must itself be one valid candidate: no
recursive search, fence removal, prose extraction, field repair or synthesized
citations. Fresh supplied context and capture hashes are revalidated before
either path. All errors use a fixed code, and clinical result fields are hidden
from repr. Both incoming UTF-8 and retained canonical JSON are bounded to
384,000 bytes; the existing smaller call/result/candidate limits still apply.

The 97 new offline checks cover all thirty golden transcripts, remote/internal
ID separation, thread cursor shapes, malformed and duplicate JSON, failed runs,
warning-bearing responses, candidate money/citation failures, revoked scope,
changed review versions and Unicode expansion. The focused contracts, mapping,
snapshot tools, client tools and provider-response suite totals 512 passing
checks. Both CI workflows for preceding revision `4bde491` passed before this
change; the new revision still requires its own CI result.

Matching a caller-supplied run ID does not authenticate the remote response or
prove that its tools belong to the selected request. The future transport must
obtain the expected ID from trusted dispatch state, enforce original operation
and parent-message bindings, and retain reported usage separately from durable
spend authority. This decoder neither starts a conversation nor authorizes,
counts or sends a continuation. Replaying an aggregate is not prevented by this
pure function. The execution ledger must retain uncertain allowance on failures
and prohibit replay; final locked publication remains a separate transaction.

## First-call captured comparison profile — 27 November

[`agent_one_shot.py`](../../apps/api/src/ciq_api/agent_one_shot.py) prepares a
single non-streaming request for the documented no-agent-object endpoint
`/api/v2/cortex/agent:run`. Local captured tools supply request facts, the shared
deterministic assessment and only its cited owned clauses before submission.
The body contains no remote tool resources, tool inventory, analytical search,
thread history or browser-provided instructions. A fixed prompt supplies the
candidate schema and requires the internal operation binding, exact integer/null
amounts and full owned evidence hashes. Prompted JSON is not provider-enforced
structured output, and the existing validator remains mandatory.

This is **explanation assistance over supplied deterministic results**, not an
independent model calculation, legacy agent orchestration or live source parity.
It offers a first comparison path with one API submission, fitting the existing
one-attempt accounting shape without adding automatic billable continuations.
The generic client-tool codec remains an inactive alternative; its multi-turn
accounting must not be inferred from this profile. A provider tool request is
rejected before local resolution. No repair prompt, follow-up or retry is sent.

A trusted configuration must name a reviewed model and strict integer second/
token limits (at most 60 seconds and 16,000 tokens). `auto` is rejected; model
availability, revision stability and pricing are not certified by validation.
The configuration digest covers endpoint, model, instructions/schema and all
nonclinical request settings. A separate digest covers the exact clinical body.
The complete encoded body, including nested JSON escaping, is capped at 256,000
bytes. Provider budgets are neither a local deadline nor a hard spending cap.
Clinical values remain hidden from repr and fixed errors; unrelated clauses and
policy regression examples are excluded. Strict revalidation now preserves
Python types so serialization cannot normalize an invalid boolean to revision
or budget integer `1` before checking it.

The 57 new checks include all thirty golden inputs, exact observation/citation
selection, null money, model/budget changes, malformed configuration, revoked
scope, revision booleans, private text, encoded size and no-tool-dispatch denial.
The six focused suites total 569 passing checks. Both CI workflows for `a5c3108`
passed before this change. No service imports the new profile, and no provider
request, cloud build, VM or local container was started.

Preparation is repeatable and grants no execution permission. The future
transport must still bind the exact request/configuration to original durable
custody, consume one issue before I/O, authenticate its reply, enforce a shorter
local deadline within the original allowance and publish under fresh locks.
Failures must retain uncertain allowance. Existing fake grants/processes cannot
authorize a live call, and no deployed ledger, principal or service is changed.

## Captured profile through original fake custody — 27 November

[`agent_captured_exchange.py`](../../apps/api/src/ciq_api/agent_captured_exchange.py)
connects the single-call request/response code to the existing bounded fake
process envelope. It accepts only a synthetic fixture pinned to the entire
original packet hash and exact prepared request digest. The packet's configured
digest must equal the prepared endpoint/model/prompt/schema/budget configuration.
The original operation, attempt, submission, source, deadline and captured
snapshot are bound by that packet; changing any field invalidates the fixture.
The fixture supplies an opaque expected provider ID independently of candidate
text. Invalid aggregates cannot be reframed as valid candidates.

The module has no network, SDK, credential, database or runtime entrypoint. An
explicit test-only child helper returns the unchanged fake protocol's framed
candidate after the strict final-only validator. It cannot create a tool
continuation, repair prompt, grant, receipt or human review decision. The manual
custody runner still selects its original canned child; nothing deploys or
selects this new test helper automatically. No migration or privilege is added.

Sixty-four exchange checks cover all thirty golden inputs, packet/config/body/
provider pins, invalid results, expiry, malformed fixtures and an actual bounded
child without inherited parent credentials. Five additional offline custody
checks use real retained SQLite and the actual child with a simulated clinical
transaction engine: independent issue commits before exchange, valid output
publishes once, failure preserves issued history, and changed review context
still prevents publication. The combined focused suite passes 760 checks.

Four new guarded restricted-PostgreSQL CI cases stage a new exact fake approval
before reservation, then use the original restricted custody coordinator. They
assert committed issue and released clinical locks before child I/O, one attempt,
atomic valid publication or retained allowance on money/tool/warning failures,
no retry, and unchanged human review. These require the disposable Linux CI job;
they are skipped locally. Both preceding `d8c050d` workflows passed; the new
restricted cases still require their own CI result.

The test fixture is independently supplied synthetic output, not actual provider
execution, source parity, latency, billed usage or credential isolation. The
child still shares custody's trusted UID. The pure bridge alone cannot discover
fresh membership or prevent replay; those remain the original coordinator and
restricted publication's responsibilities. Live activation, provider credentials,
independent usage/reconciliation and the reviewed local deadline remain open.

## Inactive single-POST HTTPS primitive — 27 November

[`agent_https_transport.py`](../../apps/api/src/ciq_api/agent_https_transport.py)
prepares the next transport boundary without selecting it in a service, route,
worker, container or custody runner. It has no entrypoint, credential loader,
database, SDK or environment/profile fallback. Trusted reviewed configuration
supplies one exact account hostname, a PAT and the SHA-256 of the prepared body.
Host syntax accepts a narrow public `snowflakecomputing.com` profile; it does
not establish account ownership, token identity or least-privilege role scope.
Browser/clinical input must never supply these constructor arguments.

The primitive makes at most one direct HTTPS POST to the fixed no-agent-object
path on port 443. An instance consumes its local latch before validation or I/O,
including invalid, failed and concurrent attempts, and drops its stored token
reference. This is not memory zeroization, durable replay protection or an
execution grant. Existing fake receipts cannot authorize this network primitive.
The body is byte-bound to its reviewed digest and capped at 256,000 bytes; its
clinical schema/configuration still belongs to the captured preparer and custody.

TLS requires certificate and hostname verification with TLS 1.2 or later.
No environment key logging is enabled. Direct stdlib HTTPS ignores proxy, CLI
and SDK session/retry configuration; the future isolated launcher must still
provide a clean environment and reviewed CA store. There are no redirect,
credential-refresh, retry, polling, cancellation or continuation requests.
Only HTTP 200 with one JSON content type and unambiguous bounded length/chunked
framing is accepted. Compression, SSE, asynchronous status, duplicate framing,
oversize and incomplete bodies fail with one fixed diagnostic. HTTP error bodies
are never returned. Raw success bytes still require the existing strict provider
and clinical validators; transport success cannot publish or finalize a review.

This uses the documented [Agent Run endpoint and non-streaming headers](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-run)
and [REST PAT headers](https://docs.snowflake.com/en/developer-guide/snowflake-rest-api/authentication).
No real credential was created, loaded or tested. Ninety-two new checks use the
actual stdlib HTTP parser with scripted sockets, plus a temporary loopback TLS
listener with ephemeral certificates. The TLS cases prove a valid exact-host
exchange and rejection of hostname/untrusted-certificate failures before sending
the dummy token. They do not contact Snowflake or establish account capability.
The five focused transport/preparation/response/exchange/dispatch suites pass
315 checks. Hosted CI remains a separate acceptance result.

The ten-second decreasing socket budget is **not a hard process deadline**:
DNS, interim responses and slow header parsing still require external process
supervision. A local disconnect does not prove remote work stopped. A separate
credential UID/delivery path, pinned live authorization and durable issue,
request/response association and provider-ID reconciliation, retained uncertain
allowance and fresh protected publication remain required before activation.
The first synchronous response's opaque provider ID is not known in advance;
copying it from its own body into an expected-ID argument is not authentication.
No Docker, GCP or provider resource is started by this change.

## Inactive supervised HTTPS child — 27 November

[`agent_https_process.py`](../../apps/api/src/ciq_api/agent_https_process.py)
adds a single-use POSIX supervisor for the fixed
[`agent_https_worker.py`](../../apps/api/src/ciq_api/agent_https_worker.py) module.
No route, running worker, service or custody coordinator selects it. In particular,
the fake coordinator's exact transport type remains unchanged; fake grants and
receipts cannot authorize this child. There is no live credential discovery,
provider call, deployment or new approval implied by preparing these modules.

Trusted construction supplies the installed interpreter, reviewed host/token,
exact request bytes and their digest. Configuration and clinical data travel
only through the child's bounded private stdin pipe. The command is fixed to
isolated Python, bytecode writing disabled and the module name; no secret enters
argv, environment or a temporary file. The child runs from `/`, receives only
the fixed locale environment and no inherited extra descriptors, and disables
core dumps before reading the pipe. It rejects CA, key-log, profile and other
environment overrides. Python/macOS may add locale/text-encoding hints.

The parent consumes its locked one-use latch before validation or process
creation, then drops its stored control reference. This is reference disposal,
not memory zeroization or durable admission. Nonblocking input/output, response
size, any stderr, child exit and process-group cleanup are supervised against
one decreasing deadline of at most twelve seconds. The network primitive retains
its ten-second socket limit. Stalls, partial output, failed cleanup and uncertain
send outcomes cannot grant a retry or release an allowance. Cleanup has its own
one-second reap limit. Raw successful output still needs provider/clinical
validation and authenticated association with the original durable issue.

Forty-eight checks cover real isolated children, blocked DNS in the actual
worker, unread stdin, slow/partial response, a descendant retaining pipes,
stdout/stderr bounds, failed exits/spawn/cleanup, exact maximum-size exchange,
concurrent attempts, malformed controls and inherited credential/CA/FD rejection.
They use dummy credentials and no external network. The six focused suites pass
363 checks locally; hosted Linux acceptance is separate.

This closes the ordinary blocked-DNS/HTTP exchange supervision gap, **not**
credential isolation: the child still shares its caller's UID and file access,
and the parent receives the token. Process groups cannot contain a hostile child
that escapes its session. Process creation or unkillable kernel tasks still need
an outer service/cgroup bound. A separate credential UID and delivery mechanism,
reviewed provider identity/role/CA store, live durable authorization and issue,
response-ID reconciliation, uncertain usage accounting and fresh publication
remain required. No real credential should be delivered through this same-UID
preparation. The provider budget also must fit the reviewed local envelope;
the captured profile's allowed sixty seconds is not silently expanded here.

## Inactive provider credential identity — 27 November

[`agent_provider_identity.py`](../../apps/api/src/ciq_api/agent_provider_identity.py)
adds the provider-side entry for a separate Linux UID/GID, both `53004`. No route,
service, custody coordinator, installer or IPC endpoint selects it. It never
switches identities or retains root: real, effective and saved UID/GID must all
match, supplementary groups must be empty, core dumps disabled and Python
isolated with bytecode disabled. Only the fixed locale environment is accepted.

The caller supplies request bytes and its remaining local deadline. It cannot
supply a token, account hostname, credential/configuration path or interpreter.
The fixed private `/run/ciq-agent-provider/plan.json` must contain exactly the
protocol, reviewed hostname and original body digest. Identity, environment,
input, budget and plan faults are rejected before opening the credential. The
token is read only from `/run/ciq-agent-provider/identity.pat`, using the existing
bounded, no-symlink private-file reader. Every ancestor must be root/provider
owned and not writable by group/others; each regular leaf must be provider-owned,
mode `0600`, single-link and within its size bound. No whitespace repair,
environment token, administrator CLI profile or discovery fallback exists.

Only the provider process constructs the existing bounded HTTPS child. Both
processes here share the provider UID; the clinical/custody identity receives
neither the token nor a transport object. The local attempt is consumed before
validation, including concurrent or failed calls. Time spent reading/validating
private inputs is deducted before child supervision, without extending the
original twelve-second envelope. The raw result still needs independent
provider/clinical validation and authenticated association with durable issue.

Thirty-seven offline identity checks and nine early CI-refusal/preservation
checks pass. Together with transport and child supervision, 186 focused checks
pass locally. The guarded hosted acceptance stages only five stdlib modules and
dummy files in fresh root-owned directories. Its twenty controls use actual
unprivileged numeric UIDs without creating users, groups, services or containers:
the provider reads its PAT but cannot read a custody-owned dummy database secret;
custody reads its own secret but cannot read the PAT/plan or pass the provider
guard. Actual isolated parent/child supervision passes a dummy token through its
private pipe to a test-only network replacement. Unsafe ownership/modes, missing,
linked, special, malformed and oversized inputs fail without retry. It refuses
existing paths/UIDs and removes only its own fixtures. The original twenty
controls passed in hosted Linux CI for `8a0ea63`.

This is private-file access and token-flow preparation, **not** a live credential
delivery service or permission to run a model. No real token has been created,
loaded or staged. Protected production provisioning/rotation and UID lifecycle,
authenticated custody-to-provider IPC, fixed outer service/cgroup/filesystem/
network policies, live durable authorization/issue, provider-ID reconciliation
and uncertain usage accounting remain open. A private plan is not a grant and
reconstructing this class cannot create one. The unchanged inactive installer
still knows only the original three fake-service identities. No GCP, Snowflake,
Docker or paid resource is started by this change.

## Inactive custody/provider IPC — 27 November

[`agent_provider_peer.py`](../../apps/api/src/ciq_api/agent_provider_peer.py)
prepares the fixed `/run/ciq-agent-provider/ipc/provider.sock` boundary. No route,
runner, installer, fake coordinator or service selects it. Custody UID/GID
`53002` and provider UID/GID `53004` mutually authenticate using Linux
`SO_PEERCRED`, including positive PID and exact GID. Custody sends no bytes until
it has authenticated the provider; the provider reads no bytes or private files
until it has authenticated custody. The processes require exact unprivileged
real/effective/saved identities, no supplementary groups, disabled core dumps,
isolated Python, no bytecode and a clean locale-only environment.

The endpoint is fixed in source. Every ancestor must be root/provider-owned and
not writable by group/others, with no symlinks. The socket must be provider-owned
mode `0666`: connecting is permitted without sharing the provider group, while
kernel authentication remains mandatory. Other local users can cause denial of
service; this is not availability isolation. Runtime never removes or adopts an
existing socket. A trusted supervisor must create fresh directories, own process
lifetime and remove its endpoint after all peers have stopped.

One request contains only a fixed protocol marker, bounded length, SHA-256 and
the complete original body. Malformed, truncated, extended, concatenated or
descriptor-bearing frames fail before credential access. A write-half close is
required before the provider opens its private plan/PAT. That existing plan then
independently pins the body and host. The raw response carries the same body
digest, a bounded length and fixed protocol marker; complete EOF is required
before custody returns it. No token, credential path, hostname, permission,
timeout or recovery command crosses IPC. Request/response limits remain
256,000/384,000 bytes. This digest associates the local exchange with its body;
it does not authenticate a provider run ID or create a clinical candidate.

Each client and bound listener has one attempt, including faults, concurrent
consumption, lost responses and timeouts. A single decreasing local budget of at
most twelve seconds covers accepting, framing, credential preparation, child
supervision and response transfer. Idle/missing-EOF peers cannot reset it. Child
cleanup retains its separate bounded reap allowance. Disconnecting or timing out
does not prove remote work stopped and cannot authorize a retry or refund.

Sixty offline IPC checks cover real local sockets with dummy exchange, limits,
framing, peer rejection, deadline consumption and fixed errors. The existing
guarded Linux acceptance additionally tests the actual custody-to-provider-to-
isolated-child path with its random dummy PAT, without network access. Eleven
controls include rejected clinical/receipt UIDs, a false server with correct
socket ownership, bad plan/body pins, malformed frames, passed descriptors,
missing EOF and a stalled child. It asserts rejected requests open no PAT and
spawn no provider child. CI status must be checked separately after pushing.

This closes a prepared local transport boundary, **not** live admission. No
durably issued live request authorizes constructing or launching this peer yet.
Recreating objects/listeners is not durable replay protection. Live issue and
independently retained accounting must precede launch, with uncertain use held
after any ambiguous exchange. Provider-ID reconciliation, fresh protected
clinical publication, outer service/cgroup/filesystem/network policy, credential
provisioning/rotation and reviewed identity/role/model/CA store remain open. The
existing fake-only coordinator and grants are unchanged. No service, paid call,
GCP VM, real PAT or Docker container is activated.

## Next concrete acceptance

1. Offline manifest/normalization fixtures and the conservative fake-ledger
   replacement fence are implemented above. Settle the actual governed source
   registry, independently captured observations and supported transport before
   connecting validation to a future live admission.
2. Prepare the clinical executor's process/secret/database access package and
   source preflight. Source-reading approval does not authorize tool execution,
   staging writes or a remote model call. Keep human administrator OAuth out of
   runtime custody.
3. Bind the single-call captured profile to reviewed provider custody and verify
   submission/checkpoint/lookup semantics with a bounded adapter. Keep client
   continuations disabled for the first comparison. The current 120-second
   legacy remote budget cannot fit unchanged inside the ledger's 120-second
   total deadline; the new request budget still needs a local deadline fence.
4. Present exact synthetic cases, identities, definitions, attempts, time window
   and expected spend for owner approval only after the package is reviewable.
   Then run live comparison and joint UI acceptance in a bounded VM window.

The [source isolation proposal](../product/p2-isolation-proposal.md),
[integration sequence](product-agent-integration.md) and
[inactive ledger](agent-run-ledger.md) remain applicable. No source or live
execution gate closes merely because this mapping has been written down.
