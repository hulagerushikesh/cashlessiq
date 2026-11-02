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
and 72 PostgreSQL fault/concurrency tests. Fake-only grants cannot activate live
execution. No route, worker or provider transport uses this ledger; existing
cloud images and data are unchanged. The original
[durable-stage design](agent-run-ledger-design.md) retains the broader target.
Ten additional populated encrypted recovery cases now preserve receipts/allowance
and reject post-restore duplicate submissions. Recovery of a backup older than
an actual submission remains a separate pre-live reconciliation/quarantine gate.

The [source mapping preparation](agent-source-mapping.md) now records exact
legacy/product identifier, policy-version, evidence, money and remaining-cover
gaps from repository inspection. No mapping or source privilege is applied.
Next settle the governed source/tool version mapping and clinical execution
identity/process/database privileges, then prepare the provider checkpoint/lookup
adapter and reviewed latency budget. Live run reconciliation, credentials,
allowances and execution require separate review and explicit approval. Do not
wire the existing three-attempt MVP worker to the agent or treat the fake ledger
as proof of provider idempotency, actual usage bounds or live Cortex parity.

The existing source-read integration and its isolation acceptance remain
separate from new assessment execution. This plan supersedes the assumption
that a hostname change or simple call to the legacy agent enables intelligence
for newly submitted product requests. It does not change phase-exit status.
