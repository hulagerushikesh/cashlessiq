# Read-only synthetic agent results

23 November 2026. The first app-facing agent integration is a read-only clinical
view. It does not start jobs, activate the controller, create grants, call a
provider or reconcile uncertain work. The deployed GCP image remains unchanged.

`GET /v3/requests/{request_id}/agent-result` is gated by synthetic workflows and
current medical-officer identity. Other roles receive 403 before private ledger
reads; an unowned submitted request receives 404. Responses use `no-store`.
Tenant and actor come from authenticated membership, never request fields.

The existing locked clinical capture was moved without changing its checks to
[`agent_scope.py`](../../apps/api/src/ciq_api/agent_scope.py), shared with the
inactive owner fixture. Fresh tenant/user/membership, assignment, open review,
approved pinned policy, latest input revision and assessment digests are checked
under the same product lock order. The reader has no owning-ledger dependency.

After capture, one tenant/request-filtered statement joins the latest operation
and comparison, observing atomic publication. The response never falls back to an
older successful operation. Exact actor and input/policy/evidence/review fences
must match; a new observation correlation ID alone does not invalidate stored
provenance. Stale, revoked, closed or invalid context withholds the result. A
published candidate is revalidated for strict money, deterministic outcome and
exact owned citation content before projection. Raw snapshots, grants, balances,
credentials, configuration/source digests and submission receipts are omitted.

The request and reviewer screens display the panel only for medical officers.
They label all results synthetic, show operation/version/timing provenance and
validated money/evidence, distinguish uncalculated amounts from zero, and escape
the explanation as text. Unknown status states that automatic retry is blocked.
Before the first assignment, a new request has no saved review row: the reader
returns unavailable without creating one. Once assigned, an empty operation
history is shown as not requested.
An unavailable comparison leaves the normal assessment and human actions usable.
Refresh performs a full document navigation and only repeats the read; it cannot
renew a lease, recover status, issue transport or change allowance. The later
[request-intent workflow](agent-request-intent.md) adds a save-only request
control for assigned current reviews; it cannot run or retry execution.
A completed or changed review withholds prior output.

Validation covers all thirty golden candidates in the pure projection, binding
and storage faults, HTTP role/tenant/revocation and read-side-effect boundaries,
static rendering including explanation escaping/null money, and the existing MVP
browser journey's medical visibility, processor denial and completed-review state.
The HTTP integration uses pre-existing fake-ledger test records; it does not
claim browser-triggered or production restricted-worker execution.

Accepted code `63b3c717e8b895d9a95b18eea472fe5e529e436a` passes
[full product CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/45178031035)
and [private-preview CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/45178030888).
This includes 57 new offline projections, twenty new HTTP/database cases and
eight new rendering checks. Local contract/projection checks pass 203 cases;
the full client suite passes 66. Full CI passes 2,358 API checks with 27 expected
skips and two existing warnings, all eighteen MVP journeys in both workflows,
and the twenty combined restricted-process/restore baselines. The preview also
matches all 22 restored tables and reopens saved workflows after restart and
restore. Owned stack cleanup succeeds. Existing root, membership, source UI,
browser, ledger, restricted-login, peer and isolation suites remain green.

The acceptance corrected two test assumptions without changing runtime gates:
the crash fixture now imports its context contract from the defining module,
and the browser checks not-requested status after the first saved assignment.
Earlier superseded runs were cancelled; the first complete preview exposed the
assignment expectation and cleaned up successfully. No local Docker, GCP start,
live source/provider call or paid build was used for this milestone.

Next is a separately bounded synthetic execution/job integration with explicit
admission and operational custody, followed by the reviewed source/provider
adapter and approved live comparison window. The generic three-attempt MVP job
retry must not become an agent spending policy. Production secret delivery,
receipt durability and source/provider isolation gates remain open.
