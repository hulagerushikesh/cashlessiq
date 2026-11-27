# Prepared single-call launch coordination — 27 November 2026

`ciq_api.agent_single_call_supervisor` coordinates one original attempt through
an independently prepared trusted host adapter. It has no executable entry,
process launcher, service installer, secret delivery, journal provisioning,
SQL activation or application wiring. No installed host adapter selects it.
The [manual process entries](agent-single-call-runtime.md) remain inactive.

The adapter contract requires independently checked owner consent, exclusive
host ownership, matching full private pins, original ready history, exact
installed identities and effective containment. `check()` must freshly verify
those conditions throughout the launch. Returning true is a trusted adapter
assertion, not proof issued by this module or an approval mechanism. No browser,
request body, readiness message or injected untrusted object may supply it.

## Original launch and completion

The coordinator consumes its entry before preflight, including failed preflight.
It first requires all three roles quiescent, then starts receipt and waits for its
exact original readiness marker. It starts provider and requires its exact marker
while receipt remains ready and alive. It rechecks both peers and current host
authority before starting custody. No plan, body, credential, path or timing
selector enters the coordinator. Readiness does not authorize a provider call;
protected SQL admission and the independently retained issue still govern that.

Each start transfers cleanup ownership before allocation. A missing or malformed
start acknowledgment still causes cleanup of that potentially allocated role.
Original incarnation identifiers must be distinct 32-character lowercase hex;
observations from another incarnation are rejected. Only bounded cumulative
stdout containing the exact fixed readiness/success marker is accepted. Output
cannot disappear after acknowledgment. Any stderr, extra output, failed exit,
changed identity or early peer exit fences successful delivery.

Custody's success marker alone is insufficient. All three original processes must
exit successfully with their exact output before the coordinator can report
`published`. This is local supervised completion, not provider cost verification
or independent source parity. `unavailable` includes uncertain publication; it
must never be interpreted as permission to retry.

Each peer has a three-second readiness allowance. The whole sequence has a
thirty-second elapsed ceiling; the original 18-second clinical, 12-second provider,
22-second receipt pair and 25/15-second process bounds are unchanged. Sampling
rejects backwards/nonfinite clocks, observation gaps over two seconds and wall
versus elapsed drift over one second. Checks occur before and after trusted
adapter calls. They detect delay after a call returns, rather than preempting a
blocked adapter: each adapter method needs its own external bound, and process
lifetimes need effective cgroups and external supervision. These checks cannot
retract an already issued request or establish a durable clock fence.

## Cleanup and recovery

Every outcome attempts all submitted roles in reverse order, even after clock,
lease, readiness or cancellation faults. The adapter must kill/reap the entire
owned cgroup, including separate-session descendants, and verify it empty. The
coordinator checks quiescence again. Any unconfirmed cleanup yields `quarantined`,
even after a success marker; private state must be retained for operator review.
Cancellation is propagated only after all owned cleanup has been attempted.

No stop path removes an endpoint, history, private plan, failed-unit evidence or
credential. No path resets an issue, recreates history, restarts a process,
reuses an entry or creates recovery authority. A new coordinator object cannot
supersede the independent SQL/history/host gates. Quiescence observed without
exclusive ownership is insufficient to avoid racing a different invocation.

## Evidence and next host work

Offline tests exercise launch ordering, uncertain start ownership, stale and
malformed observations, revoked preflight, readiness loss, clock faults, total
timeout, cancellation and cleanup quarantine. Disposable network-disabled Linux
CI runs the actual three runner `main()` functions under UIDs 53002/53003/53004,
with private dummy plans and a dummy provider PAT. It uses the actual one-listener
receipt issue/observe pair, provider identity validation and custody assembly.
The fixture substitutes SQL and the HTTPS process and maps journal storage into
its owned `/run` tree. Its successful result tests coordinator/runner composition,
not actual PostgreSQL publication, real HTTPS, systemd or restored-host acceptance.
Actual protected PostgreSQL publication remains separate evidence.

Still needed: a reviewed installed host adapter, distinct credential delivery,
effective read-only filesystem/egress/cgroup policy, independent retained-history
restore quarantine/off-host retention, and explicitly approved provider testing.
The old canned service examples are unchanged. They cannot simply select these
new entries: among other differences, the reviewed peer guards require **empty**
supplementary groups, while systemd normally initializes groups from the user
database ([systemd.exec](https://www.freedesktop.org/software/systemd/man/251/systemd.exec.html)).
The [prepared identity launcher](agent-single-call-identity.md) now supplies a
fixed permanent identity transition, exercised in the disposable composition
fixture without weakening those guards. New service policy still must be tested
with that exact boundary. No new service examples or host changes are installed,
and external provider egress remains unconfigured.
