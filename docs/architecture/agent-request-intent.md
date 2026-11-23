# App requests for synthetic comparisons

23 November 2026. This adds the request half of the app workflow. **The dedicated
executor is still inactive.** Saving a request does not reserve allowance, issue
a transport attempt, call Snowflake/AI, produce a comparison or change a human
decision. The deployed GCP image is unchanged.

`POST /v3/requests/{request_id}/agent-request` requires synthetic workflows,
current medical-officer membership, fictional-data confirmation and the exact
input/review versions displayed by the server. Fresh locked capture checks the
owned assessment, pinned approved policy, input/evidence digests and open review.
The case must be assigned to that officer. Identity is derived from the session;
the strict command has no tenant, actor, grant, epoch, path or credential fields.

The transaction saves one `work_job` with kind `agent_comparison`, state
`awaiting_executor`, zero attempts and no lease/result. Its payload contains only
the server-captured version/digest binding and its digest, excluding correlation;
no facts or policy wording are copied into the queue. An existing product table
is reused, so the schema and normal 22-table backup manifest do not change.

The tenant-first clinical lock serializes simultaneous requests. A unique
actor/command audit event acknowledges identical retries without another job.
Different command IDs for the same actor/request/current binding share one held
intent; command reuse for a different request conflicts. The event contains only
the job ID and held state. An acknowledged retry after later review changes
returns the original receipt, without creating work. New commands must pass
fresh scope/version checks. Old held bindings remain historical intent and are
withheld from the current view. They are never authority to run later.

An existing operation of any state blocks a new browser request. Unknown,
expired or stale execution needs explicit operator review rather than a browser
retry. The read endpoint offers a request context only for an owned, assigned,
open/current review with no operation or matching held intent. A matching intent
returns `awaiting_executor` and its job ID; it does not expose queue payloads.
The UI requires fictional-data confirmation, saves through the existing exact
origin/session form boundary, and clearly states that nothing has run or spent
allowance. Refresh remains a read. Deterministic assessment and human review are
available while execution is unavailable.

The generic worker now allowlists assessment, regression and extraction for
claim, attempt-limit settlement, compute and completion. Agent intent is also
excluded from generic job lists/details and explicit retry. These checks hold
even if its state/attempt count is changed to resemble a generic job. The existing
60-second lease and three-attempt retry remain unchanged for supported kinds.

Validation adds thirty real-PostgreSQL HTTP/concurrency and worker-exclusion
cases, three client checks, and extends the existing MVP browser journey to save
and refresh a held request before completing the human review. The thirty golden
projection cases also assert that published results carry no request capability.
CI acceptance is recorded in the delivery status after completion.

Next: connect a separately configured, bounded synthetic dispatcher to these
intents through the existing restricted capture/reservation and original custody
path. It must independently revalidate the actor, exact binding, approved fake
grant and current authority before claiming; no browser payload or ordinary API
DB connection supplies authority. It must leave generic retries disabled, keep
uncertain submissions held, and prove one validated result reaches the app.
No production activation, credentials, live provider/source parity or paid
testing is established by this intent workflow.
