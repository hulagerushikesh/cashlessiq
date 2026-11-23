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
renew a lease, recover status, issue transport or change allowance. There is no
run/retry control. A completed or changed review withholds prior output.

Validation covers all thirty golden candidates in the pure projection, binding
and storage faults, HTTP role/tenant/revocation and read-side-effect boundaries,
static rendering including explanation escaping/null money, and the existing MVP
browser journey's medical visibility, processor denial and completed-review state.
The HTTP integration uses pre-existing fake-ledger test records; it does not
claim browser-triggered or production restricted-worker execution.

Next is a separately bounded synthetic execution/job integration with explicit
admission and operational custody, followed by the reviewed source/provider
adapter and approved live comparison window. The generic three-attempt MVP job
retry must not become an agent spending policy. Production secret delivery,
receipt durability and source/provider isolation gates remain open.
