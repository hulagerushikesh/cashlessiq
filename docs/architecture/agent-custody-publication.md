# Restricted private fake comparison publication

3 November 2026. Inactive disposable engineering only. No route, worker, startup,
service, provider or deployed role/schema/image is activated.

## Original custody and fresh validation

The [original coordinator](../../apps/api/src/ciq_api/agent_custody_submission.py)
now has no-argument `heartbeat()` and `publish()` stages. Both return None. They
atomically remove the private response before connecting, so another thread or
replacement instance cannot reuse it. A failed/ambiguous stage sacrifices that
response. No API accepts a candidate, tenant, actor, digest, clock or "validated"
attestation, and neither stage creates/reconstructs transport issue permission.
Heartbeat retains the response only after confirmed commit, with the new version
and unchanged attempt/fence, original issue deadline and monotonic budget.

One restricted custody transaction independently reads the full bounded epoch
history and compares it with retained custody, including the exact **issued**
marker. A merely prepared receipt is insufficient. This check returns no ticket
or I/O permit; it is not a repair/reset operation. The fake same-host SQLite
journal and its host/operator remain trusted, without production host-loss,
rollback-of-both or administrator protection.

The new [SQL extension](../../deploy/agent-controller/custody-publication.sql)
authenticates the protected original assignment and clinical principal under
epoch → bindings → clinical rows → grant → operation locks, using the existing
submission context. It returns the exact current attempt and a narrow freshly
locked clinical projection. The private reservation/submission helpers now carry
that projection internally; clinical public reserve/lease command outputs are
unchanged. Historical inventory alone does not establish current clinical scope.

Python reuses capture's independent fingerprint/strict-schema checks, preserving
the original correlation ID when rebuilding the fresh binding. Shared
`require_current` and `validate_candidate` run **before commit releases the same
clinical locks**. Publication checks exact tenant/request/policy/input/review
versions, strict money, deterministic outcome/amounts/lines, and exact owned
citation IDs **and content hashes**. Unverified explanation remains private.

The final narrow SQL command rechecks scope, attempt, state/version/fence, policy,
source/configuration/snapshot pins, principal/grant windows, lease and original
operation deadline. It adds JSON size/binding/run checks and atomically inserts
one append-only private comparison, changes submitting → published/version +1,
and transfers the reserved attempt units to consumed while releasing one slot.
It never writes a human review, audit, outbox or analytics event. Invalid content,
revocation, drift, expired timing or commit failure retains held allowance and
leaves no permission for another exchange or automatic publication retry.

Submitted heartbeat can maintain only the **current live submitted lease**,
within the original operation deadline and both principal/grant windows, for at
most thirty seconds from DB wall time. It changes version and lease only. It
cannot reclaim expired/submitted work, change fence, append an attempt or extend
the original deadline. Its narrow coordinator stage currently requires the
original response after successful bounded I/O; it is not a scheduler/daemon or
in-flight child heartbeat. The existing ten-second child fits the original lease.
The captured pre-I/O issue deadline/monotonic budget still caps later publication;
a later heartbeat does not widen it. Fresh DB checks remain a second timing guard.

## Privilege and deployment limits

Only trusted custody receives context/heartbeat/publication command execution.
PUBLIC execution is revoked. The clinical login cannot authenticate as custody,
even after accidental command execution grants. Runtime gets no direct table or
column privilege. The nonlogin receipt definer adds only comparison INSERT,
operation lease UPDATE and selected grant counter reads/updates. It cannot change
original deadline/snapshot/fence, uncertain units, grant limits/window/identity or
human workflow rows. Existing checkpoint privileges remain separately reviewed.

SQL cannot execute the shared Python validator or independently inspect SQLite.
Its caller is the separately credentialed **trusted custody program**, not an
untrusted clinical runtime. Credential/memory/registry owners remain trusted.
There is no service listener, authenticated peer, production OS/network/secret
isolation or deployed restore/rotation acceptance. The private registries remain
outside migrations and the normal 22-table backup manifest. No existing owning
ledger is invoked as a restricted-execution shortcut.

## Verification and next handoff

Offline checks exercise all thirty golden candidates through a real fixed bounded
fake process, exact fresh projections, nested citations/money/binding faults,
original timing budget, same-instance publication concurrency, missing/closed/
rewound custody, ambiguous commits and no returned/reconstructed permission.
Actual-login PostgreSQL CI exercises restricted successful exchange → heartbeat →
publication, atomic accounting and unchanged human review/audit/outbox, clinical
locks during Python validation, revocation/drift/windows, malformed candidates,
commit failure, concurrency, effective privileges and SQL expiry after validation.
Revision `c9a985f` passes **129 new checks**: **83 offline** (including all thirty
golden candidates) and **46 actual-login** cases. The
[restricted job](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41630406968/job/125898207440)
passes all **251 restricted-login checks**, the existing **476 agent checks** and
**fourteen populated encrypted recoveries**. Those fourteen still use the owning
fixture, **not** restricted recovery acceptance.

[Full product CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41630406968)
passes 1,027 root (three expected skips), 72 membership, 58 client, **2,221 API**
(twenty-one expected skips/two existing warnings), 26 browser, 15 source UI and
all **eighteen MVP journeys**. Catalog, transport isolation, process containment,
contracts/types/lint/build and owned cleanup pass.
[Private preview CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41630407338)
separately passes eighteen MVP journeys, a matched encrypted **22-table restore**
and both saved-workflow browser reopenings. Fresh-volume/stack cleanup succeeds.
Both complete workflows select `c9a985fd4b7ec5189b245d73780809df97cac828`.
Local Ruff, all five SQL template-format checks and edited relative document
links pass. The new offline suite passes 83 checks in 4.19 seconds.

A fresh read-only check confirms GCP TERMINATED with its unchanged 1,800-second
STOP and Docker Desktop off. No paid build/run, local container, source/provider
call or deployed image/schema/role/binding change was performed. The deployed
preview still selects revision `7940886`/schema `0003_mvp`; this code is inactive
engineering, not a newly deployed agent workflow.

Next implement **conservative restricted recovery**, with no clinical locks after
grant/operation locks. Submitted unknown work keeps its slot and uncertain units
even if custody is missing/closed. Never-submitted refund requires available,
agreeing independently observed full history. No lost reply or missing custody
permits resubmission, refund, reset, new epoch or automatic reconciliation.
Then move all fourteen populated encrypted recovery journeys through the intended
restricted path; their existing owning fixture remains a baseline only.
Production custody/peer isolation, deployed restore/revoke/rotation and effective
PUBLIC/default ACL review, independent live source capture and supported provider
submission/status/usage/timeout semantics remain separate gates. No assistance or
paid window is needed for this engineering step.

Later on 3 November, [restricted conservative recovery](agent-custody-recovery.md)
was implemented and accepted at `b773410`, with 22 offline and 39 actual-login
checks and both full CI workflows green. The fourteen populated restore journeys
still need acceptance through that intended restricted path.
