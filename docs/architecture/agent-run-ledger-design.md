# Proposed durable agent stage

2 November 2026. **Design for review; no migration, executor or live access is
implemented by this document.** It follows the
[inactive comparison contract](agent-comparison-contract.md) and preserves the
[governed identity/source boundary](../product/p2-isolation-proposal.md).

## Placement and operation identity

Use the existing PostgreSQL authority for a dedicated operation ledger. Do not
place a paid invocation in `jobs.compute` or inherit `WorkJob`'s three-attempt
retry. A separate clinical execution boundary owns approved agent credentials;
ordinary processor/nonclinical services must not acquire those credentials.
Process/secret placement and database grants need review before activation.
No new VM, orchestration service or managed queue is assumed. Measure the
reviewed implementation on the existing small preview before considering size.

Reserve an operation by a server-computed SHA-256 over a canonical versioned
object containing tenant ID, request ID, input revision/digest, selected policy
ID/product/version and rules/policy/evidence digests, orchestration version,
agent configuration digest and approved source/tool mapping digest. The two
configuration digests must cover the pinned agent/tool/search definitions and
the exact product/evidence mapping used, not a mutable agent name alone.

Do not include random run IDs, browser command IDs, correlation IDs or worker
fences in this key: changing them must not purchase another invocation. A review
assignment/version change also must not bypass the cost guard. Keep the review
version and authorizing membership separately as publication fences. A changed
input/policy/configuration creates different computation identity but still
needs authorization and available approved case/attempt budget; a new hash is
not spending permission.

## Proposed records and invariants

Names are conceptual, not executable SQL:

| Record | Required constraints and custody |
| --- | --- |
| `agent_operation` | Composite owned request foreign key; unique `(tenant_id, operation_key)`; immutable approved snapshot/configuration hashes; captured review/membership fence; state/version; deadline; current worker fence and lease; approved execution grant |
| `agent_attempt` | Composite tenant/operation foreign key; unique `(tenant_id, operation_id, attempt_number)`; client submission identity persisted before I/O; submission checkpoint; remote run identity when known; timing and safe error code; bounded usage observations |
| `agent_comparison` | At most one accepted comparison per operation; composite tenant/operation key; exact run/configuration/input/evidence provenance; validated clinical result; publication time/fence; no final human action |
| `agent_execution_grant` | Explicitly approved synthetic case/configuration/window, attempt ceiling, case/concurrency ceiling and usage limits; immutable approval reference; reserved/consumed/uncertain accounting |

Use real tenant-scoped foreign keys and uniqueness constraints, not only ORM
filters. Sensitive snapshots/results stay within the clinical trust boundary;
general audit/outbox/log records contain fixed status codes and opaque owned
identifiers only. No full clinical body, provider exception text or credentials
are written to the general workflow event stream. Retention/cleanup must keep
operation and uncertain-cost receipts long enough that deleting a display result
cannot enable an automatic replacement call.

Budget counters are an admission control, not a provider billing cap. The first
live grant should allow **one attempt per selected case**, fixed concurrency
and a separately approved short window. No automatic invalid-output retry.
Record unresolved usage conservatively; timeout does not release reserved cost.
Any retry policy or additional attempt requires a new reviewed allowance and
an explicit transition, never a generic job retry or an operator resetting state.

## Transaction and crash boundaries

1. Resolve fresh application membership, tenant, clinical capability, selected
   approved policy, immutable inputs and open review from locked trusted rows.
   Verify the exact case/configuration/window is authorized. Lock in one fixed
   order across grant, operation and workflow rows to avoid competing lock orders.
   Insert-or-read the unique operation and reserve its bounded allowance in the
   same transaction. Use the same order whenever multiple rows are locked:
   tenant/membership, request/policy/review, grant, operation. An operation-only
   claim transaction releases its lock before a later multi-row transaction.
   A duplicate enqueue returns the existing status.
2. A dedicated worker atomically claims a new fence with a bounded renewable
   lease. Recheck the authorization, snapshot and grant before submission.
   Commit a durable attempt and transition `reserved -> submitting` using
   compare-and-swap of state, version and fence **before any remote invocation**.
   Only the transaction winner may submit once. Failure before this transition
   may retry local admission; after it, absence of a receipt is uncertain.
3. Submit using a stable client operation identity where the reviewed provider
   interface supports it. Provider deduplication or lookup is a prerequisite to
   automatic recovery, not an assumed API feature. Save a returned remote run
   identity/checkpoint durably and promptly. If the process dies before saving
   it, the operation stays `submitting`/`unknown`; a successor may reconcile but
   must not invoke again.
4. Renew only the local observation lease with fence/version checks, within the
   immutable overall deadline. If a lease expires, a successor can claim
   reconciliation/status observation; it cannot inherit permission to submit
   another attempt. A heartbeat never extends paid permission or the deadline.
   Lease loss/revocation stops new I/O; already-submitted remote work may continue.
5. On completion, parse and validate the result against the captured canonical
   snapshot. In a final transaction lock/re-read current authorization, request,
   policy, review and operation rows. Require the current fence, open review,
   unexpired window and exact captured versions/digests. Insert the comparison
   idempotently and commit its status/audit marker together. Never overwrite a
   completed human decision, `SubmittedCase.record` or a newer assessment.
6. A stale, rejected or late result may retain a bounded clinical provenance
   record under the reviewed retention policy; it is not a current recommendation.
   Do not silently rebind an old candidate to a new correlation/review version.
   An explicit later revalidation/display policy remains a separate design.

The pre-submission reservation crash gap is deliberately conservative: a crash
after `submitting` but before an actual network call can block a call that never
happened. This is preferable to inferring that no charge occurred from missing
local state. Exactly-once remote execution cannot be established by PostgreSQL
locking alone. Reconciliation must distinguish supported remote run lookup from
manual investigation; absent proof, keep the operation unknown and block retry.

## State and timeout proposal

`reserved -> submitting -> observing -> validated -> published` is the success
path. Invalid output becomes `rejected`; post-submission timeout/disconnect or
lost checkpoint becomes `unknown`; stale/finalized input becomes `superseded`.
Unknown/rejected/superseded states never return automatically to `reserved`.
Late results cannot publish; a reconciliation receipt may account for them
without making them current. Pre-submission expiry can release an allowance
only when the durable state proves no worker won the submission transition.

Keep the first implementation within the simulator's 120-second local ceiling
only if a separately reviewed agent configuration uses a shorter remote budget
with measured transport/validation margin. The retained 120-second remote
configuration cannot be inserted into that local ceiling unchanged. Otherwise
revise the lifecycle contract and tests explicitly before execution. Configure
request/connection/poll timeouts and bounded output independently; none establishes
that a provider-side task or billing stopped. Do not lengthen the existing MVP
job lease globally to accommodate an unrelated paid stage.

## Source/tool mapping remains a prerequisite

First choose the exact authorized golden Snowflake IDs and canonical inputs
for a separately approved comparison. Arbitrary product `REQ-...` input mapping
is still absent. The new contract's record/clause hashes are local product
evidence handles, not source permissions or existing Cortex Search document IDs.

For new product inputs, review either governed immutable staging projections
with approved writes/retention, or new authorized snapshot-consuming tools.
Specify tenant predicates, clinical columns, effective PUBLIC grants, pinned
policy/rule/evidence versions, minimum read/execute/write grants, credential
custody, independent citation resolution and rollback. Do not mutate legacy
tables, reuse owner OAuth or import the legacy helper that writes decisions.
This document chooses neither transport and creates no source schema or grant.

## Acceptance before any live execution

Implement and exercise the ledger first on disposable CI PostgreSQL with a fake
gateway, including:

- Concurrent duplicate enqueue/claim/submission; only one fake submit wins.
- Crashes before reservation commit, after reservation, after submitting commit,
  during I/O, after remote acceptance but before ID persistence, after output
  validation and before/after publication commit; zero automatic extra calls.
- Lease expiry, successor reconciliation, late worker completion, lost fences,
  clock/deadline boundaries and repeated local restarts.
- Changed correlation/command/review IDs do not bypass operation uniqueness;
  changed input/configuration cannot bypass approval/case/attempt limits.
- Tenant/clinical revocation, policy changes, amendments, final human review and
  publication races; no stale candidate becomes the current recommendation.
- Retried publication creates one comparison/audit marker; raw clinical results
  cannot appear in processor/auditor payloads, error logs or general outbox data.
- Unknown-cost reservations stay accounted for; counters cannot oversubscribe
  under concurrent workers; retention/cleanup cannot enable another invocation.

Then review the implementation, source mapping, exact service capabilities,
latency margin, observability and proposed case/attempt/spend window with the
owner before any real adapter activation. The stable test domain can be verified
with the existing deterministic app during a separately approved VM window;
that does not require activating or rebuilding a live agent integration.
