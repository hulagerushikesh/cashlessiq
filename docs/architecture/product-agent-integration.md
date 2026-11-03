# Connecting the product workflow to Snowflake intelligence

2 November 2026. Implementation sequence; no new live-source access, credentials,
Snowflake writes or agent execution is authorized by this document. The
[governed source boundaries](../product/p2-isolation-proposal.md) still apply.

## What exists and what is missing

The tested GCP application runs Next.js, FastAPI, PostgreSQL and the shared
deterministic rules core. `ciq_api.jobs.compute` assesses submitted requests
through `ciq_api.assessment.calculate`; it does not call an LLM or Snowflake.
The eighteen passing deployed browser tests establish synthetic workflow
behaviour, not live agent parity. The public fixed-example website is another
presentation surface, not a backend connection.

The retained `sql/50_agent.sql` defines `CASHLESSIQ.AI.CASHLESSIQ_AGENT`, with
request lookup, waiting-period/payable/SLA procedures, Cortex Search and the
context-only MEMBER_360 semantic view. `app/services.py` invokes it from the
legacy Streamlit path. That SQL accepts a Snowflake request ID: an arbitrary
new `REQ-...` ID from PostgreSQL does not populate Snowflake request/fact tables.
Its tools and search are also not wired to the product's newly approved policy
versions. Calling the old agent with a new ID would not complete the migration.

Do not import the legacy `run_agent` helper as the new worker adapter: it retries
invalid output once and inserts directly into `CASHLESSIQ.APP.DECISION`. That
combines paid invocation, retry policy and legacy persistence. The new gateway
must separate these effects, preserve PostgreSQL workflow authority and require
explicit approval for any Snowflake writes; a read-only service is insufficient.

The retained evaluation reports 27/30 correct outcomes, 29/30 correct amounts
and 55% strict citation recall; those are historical prototype measurements,
not targets already met by the new integration. Use
[the evaluation record](../evaluation.md) as a baseline, including QUERY/REFER
citation gaps and extraction normalization issues.

## Sequence

1. **Keep the operational record in PostgreSQL.** Requests, reviewed input
   amendments, pinned policy versions, jobs and final human actions remain
   authoritative there. The frontend never calls Snowflake or selects a tenant,
   role or credential through request fields.
2. **Finish the governed source/identity boundary.** Resolve effective PUBLIC
   grants and tenant/clinical projections, approve the exact service identities
   and credential custody, and run cross-tenant/clinical/revocation denials under
   a separately approved bounded scope. Do not reuse human OAuth/ACCOUNTADMIN.
   Read access and agent/tool execution are different capabilities: a reader
   identity must not silently acquire agent execution or source writes.
3. **Define a versioned agent input contract before activating new requests.**
   Bind tenant/request ID, immutable input digest, approved policy/rules digest,
   product/version, evidence version, correlation ID and orchestration version.
   Choose and review one transport: explicit synchronization into dedicated,
   governed staging projections, or new tools that consume authorized immutable
   input snapshots. Neither exists yet. Do not mutate legacy source tables or
   rebuild policy search on every browser request. Stage any proposed schema,
   tool/search changes, minimum grants and rollback package before approval.
4. **First compare existing golden requests.** A separately authorized worker
   invocation should use the established Snowflake IDs under approved identities
   before accepting arbitrary product submissions. Compare outcome, every
   monetary line/total and independently resolved product-specific citations
   with canonical inputs. Verify missing facts, waiting periods, missing saved
   decisions and QUERY/REFER null-payable semantics explicitly.
5. **Integrate an explicit background agent stage.** Keep the deterministic
   assessment available as its own labelled result. Persist agent run/status,
   provenance, timings and validation separately; an unavailable agent must not
   be presented as a successful AI-assisted result. Do not overwrite a completed
   human review or publish a result after its input/policy version changes.
6. **Resolve job timing and duplicate-cost behaviour before execution.** Current
   work jobs lease for 60 seconds, while the legacy agent budgets up to 120
   seconds. A direct call risks an expired lease and duplicate expensive work.
   Use a reviewed long-running stage/lease-renewal design with fencing and a
   bounded deadline. Record submitted run identity/checkpoints before deciding
   whether to retry an uncertain remote result. The current generic three-attempt
   job retry is not an approved AI spending policy. A client timeout does not
   establish that remote execution or billing stopped.
7. **Validate before persistence and display.** Resolve citations against the
   exact owned policy/evidence version and compare agent monetary values with
   canonical tool outputs. Reject invalid JSON, changed numbers, unsupported
   outcomes, wrong product/tenant or stale inputs; never auto-deny or auto-finalize.
   Preserve raw clinical output only inside the reviewed clinical boundary;
   processor/auditor responses and logs must not receive it.
8. **Release through bounded synthetic comparison.** Begin with a fake gateway
   and fault tests; then request explicit approval for a small live case batch,
   warehouse/AI budget, attempt ceiling and test window. Measure latency,
   citation quality, errors and cost before selecting broader use. Run joint
   browser acceptance after backend parity. No larger VM is assumed necessary:
   measure the worker's actual footprint first.

## Next engineering batch

The first offline batch is implemented in
[`agent_contracts.py`](../../apps/api/src/ciq_api/agent_contracts.py) and
[`agent_simulation.py`](../../apps/api/src/ciq_api/agent_simulation.py), with
[fake-gateway fault tests](../../apps/api/tests/test_agent_contracts.py).
See the [v1 contract and limits](agent-comparison-contract.md). It remains
inactive and outside the embedded MVP worker: no route, SDK, credentials,
Snowflake staging write or execution adapter was added.

The [inactive fake-only database ledger](agent-run-ledger.md) is also implemented:
owned grant/operation/attempt/comparison tables, durable submission checkpoints,
leases/fencing, conservative unknown accounting, transactional comparison storage
and 90 PostgreSQL fault/concurrency tests, including conservative cross-version
replacement and unresolved-amendment fences. Fake-only grants cannot activate live
execution. No route, worker or live provider transport uses this ledger; the inactive
fake process coordinator exercises it only in tests. Existing cloud images and
data are unchanged. The original
[durable-stage design](agent-run-ledger-design.md) retains the broader target.
Ten additional populated encrypted recovery cases now preserve receipts/allowance
and reject post-restore duplicate submissions. Recovery of a backup older than
an actual submission is now exercised by four additional encrypted restore cases
through the [default-closed fake gate](agent-admission-quarantine.md). Production
independent custody and reviewed reconciliation remain pre-live gates.

The [source mapping preparation](agent-source-mapping.md) now records exact
legacy/product identifier, policy-version, evidence, money and remaining-cover
gaps from repository inspection. The inactive mapping validator and its 122
offline fixtures now reject ambiguous mappings and content/version drift. It
has no source adapter, and its coherence receipt grants no execution authority.
No source privilege is applied. The [fake executor boundary](agent-executor-boundary.md)
now commits the sole checkpoint before a bounded child process, retains uncertain
allowance on failure and validates/publishes under fresh clinical locks. Its
56 offline and 13 PostgreSQL checks are accompanied by separate disposable
container tests with distinct identities, exact dummy mounts and no network/DB
capability. The fixed canned fixture is not provider or independent-source parity.
No route or worker activates it; the real controller still uses the owning DB
test connection. The default-closed fake epoch, independent test receipts and
pre-checkpoint restore quarantine are implemented; production receipt custody
remains unselected. The [principal-bound capture package](agent-controller-capture.md)
prepares the first narrow database read with an actual restricted-login CI harness.
The [reservation/lease extension](agent-controller-reservation.md) prepares exact
fake holds and reserved-only leases with protected accounting. It does not expose
submission, publication or refunds, and does not replace the owner-connected
fake ledger. Next implement independently authenticated admission/custody and
checkpoint/publication/recovery commands that cannot bypass history verification,
finish
independently captured source/tool mapping and prepare the
provider checkpoint/lookup adapter with a reviewed latency budget. Live run reconciliation, credentials,
allowances and execution require separate review and explicit approval. Do not
wire the existing three-attempt MVP worker to the agent or treat the fake ledger
as proof of provider idempotency, actual usage bounds or live Cortex parity.

The existing source-read integration and its isolation acceptance remain
separate from new assessment execution. This plan supersedes the assumption
that a hostname change or simple call to the legacy agent enables intelligence
for newly submitted product requests. It does not change phase-exit status.


### Independent receipt observation prepared — 3 November

The [receipt observer](agent-receipt-observer.md) now prepares a separate,
principal-bound history command and fake custody verifier. It independently reads
full bounded epoch history; clinical runtime has no observer/table privileges.
The result is not an admission ticket or I/O permit. Restricted checkpoint/issue,
private publication and conservative recovery still need a custody-controlled
transaction path, authenticated IPC and acceptance through all fourteen encrypted
recoveries. No runtime self-attestation or cached observation may bridge that gap.


### Custody-owned checkpoint and issue prepared — 3 November

The [inactive fake custody extension](agent-custody-submission.md) now prepares
exact protected delegation to a clinical principal and restricted checkpoint/issue
commands. Independent full history checking, protected SQL and external prepare
share one custody transaction; only the original coordinator can consume the
external issue marker after confirmed checkpoint commit. No permit is returned,
transport is not dispatched and no publication/recovery or production IPC service
is activated. All fourteen encrypted recoveries still require migration to the
intended restricted execution path.

### Original-custody fake dispatch prepared — 3 November

The [fixed fake exchange](agent-custody-dispatch.md) now consumes the original
coordinator's pending state, independently rechecks history and clinical scope,
commits external issue and the local transaction, then exchanges once within the
remaining DB/monotonic/wall-clock budget. Both principal windows are included.
No command/credential/identity selector, I/O ticket or candidate is returned;
the unvalidated reply stays private. No DB lock spans child I/O. Failed commit,
deadline or child loses permission without retry/refund. This is inactive trusted
in-process fake construction, not authenticated IPC or production custody.
Restricted validated publication, submitted heartbeat and conservative recovery,
including all fourteen encrypted restore journeys, remain the next work.


### Restricted private publication and submitted heartbeat — 3 November

The [private publication extension](agent-custody-publication.md) consumes only the
original coordinator's private response, independently rechecks full issued
history and current clinical scope, and validates strict money/deterministic
results and exact owned citation content under the same clinical locks. A narrow
SQL command atomically saves one private comparison and settles allowance. No
human review/audit/outbox is changed; no caller candidate or validated flag is
accepted. Submitted heartbeat keeps the current attempt/fence and original
deadline/issue budget. Failures sacrifice the candidate without replay/refund.
This remains inactive fake-only code, with no production peer/custody/source gate
claimed. Conservative restricted recovery and all fourteen populated restore
journeys through that path remain next.
