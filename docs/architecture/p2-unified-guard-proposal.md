# P2 unified health, clock and replay guard — approved offline prototype scope

22 October 2026. Follow-up to the
[signed health composition](p2-clock-health-proposal.md#signed-worker-composition-checkpoint--22-october).
Owner directed “push the commits … and go next” after the offline implementation
approval request. This authorizes the bounded offline prototype below, not real
host provisioning, migration or runtime activation. The existing test-local
bridge must not become the runtime adapter.

## Approved implementation boundary

Implement an **inactive, offline v3 guard prototype** with one existing-file SQLite
transaction per observation/nonce consumption, independently signed fake health,
injected clock samples and disposable test keys/state. No real daemon, host,
credentials, Snowflake calls, network deployment, purchases or default startup.
Existing v1/v2 prototypes remain unchanged; no compatibility fallback or automatic
state conversion. Subsequent real-host/service activation is a separate decision.

## Why a new boundary is needed

The transport tests currently compose `RetainedHealthConsumer` and
`SqliteClockGuard` using separate SQLite files/transactions. A health observation
can commit independently of nonce consumption. The old guard samples before its
health callback, which can delay returning; passing that bridge's tests is not a
freshness or atomicity guarantee. The old `consume(namespace, nonce, expiry, now)`
also lacks `iat` and relies on caller-supplied seconds. Do not silently retrofit
these limitations through an object satisfying the old replay interface.

## State ownership and compatibility

Each broker/reader/validator authority owns a private v3 database. No distributed
transaction or global replay ledger is claimed. Parent and child consumption are
independent; a later denial may leave an earlier nonce spent, which is safe denial,
not a reason to restore it. Broker observation state needs no nonce insertion.

One exact, versioned singleton stores authority namespace, assertion generation,
health generation, pinned health-key fingerprint, policy fingerprint, host/boot,
collector epoch, health sequence/content digest, reference/measurement end high-
water marks, local wall/monotonic/boottime high-water marks and unsafe latch.
One bounded nonce table stores hashed nonce and expiry in this authority's pinned
assertion generation. It contains no patient, session, decision or raw health token.
Fingerprint encodings must be canonical and tested; they are configuration bindings,
not secret material. Unknown policy/key/generation/epoch changes deny, not rebase.

Explicit offline provisioning creates a new private path and schema once; startup
opens existing files only. Reject missing, corrupt, wrong-version, unexpected schema,
invalid rows, latch, binding mismatch or invalid nonce entries without rewriting
suspect state. Validate constraints/indexes as well as column names. Bound rows/file
size and fail closed on unsupported journal mode or custody uncertainty; exact
offline limits are explicit test configuration, not operational recommendations.

## Proposed transaction ordering

1. Open the explicit existing path, configure required durability, take a bounded
   write lock, and validate schema/state/configuration before evidence callbacks.
   No retries, source reads or implicit initialization. Lock/storage failures deny.
2. Bracket evidence delivery with independently injected wall/monotonic/boottime
   samples in the pinned boot domain. Receive a bounded immutable envelope; do not
   execute a collector or make network/membership/source calls under this lock.
3. Verify the pinned health key, strict envelope/domain, original source freshness,
   conservative uncertainty, sequence/digest and measurement/reference continuity.
   Check local rollback, suspend skew, excessive gap and sampling/delivery budget.
4. Sample again **after signature/continuity work** and revalidate freshness/error
   and continuity at that later sample. Use this sample for authorization, not a
   timestamp captured before delivery. Record the accepted observation/high-water
   marks in this same transaction; never call the v2 consumer recursively.
5. For consumption only, check immutable, already signature/schema-verified claims:
   exact authority namespace/generation, bounded hashed nonce, `iat`, `exp`, maximum
   lifetime and conservative validity interval below. No supplied `now` is trusted.
   Membership/scope/peer checks still belong to the authority and are rechecked
   before delivery; a valid health observation cannot grant application access.
6. Only after safe time checks, prune definitely expired nonces, check duplicate
   and capacity, and insert at most one new nonce. Commit observation and accepted
   consumption together; return success only after commit acknowledgement.
   Ordinary expired/replayed/full/wrong-namespace claims still persist a valid
   observation, without inserting the rejected nonce. Pruning itself requires
   safe time and must never happen on unsafe health/clock state.
7. For invalid evidence/clock continuity after structurally valid state, commit
   only the unsafe latch and deny; do not advance high-water marks or prune/insert.
   If storage/commit fails, deny but do not claim a durable latch. An ambiguous
   commit may have spent the nonce: never retry, undo or report success to hide it.

No source work or response leaves the boundary before successful authorization.
Every delivery uses a fresh guard observation plus current membership/scope and
claim validity checks. A consumed token is not refunded on downstream failure.
Pre-bind checks use the same guard, but do not confer cached readiness or consume
an application token. Missing/unsafe state must prevent binding/issuance.

## Time interval and interface changes

All internal values are bounded integer nanoseconds, with checked arithmetic.
Given accepted local wall time `w` and conservative error `e`, use inclusive
`[w-e, w+e]`; reject overflow/negative bounds. A claim is time-valid only if
`iat * SECOND <= w-e` and `w+e < exp * SECOND`, and its positive lifetime is within
the existing maximum. Prune only when `exp * SECOND <= w-e`. No positive leeway,
rounding that widens validity, or allowance for an untrusted token timestamp.

For the offline issuance candidate, set `iat = floor((w-e)/SECOND)` and
`exp = iat + existing maximum lifetime`, then require the whole current interval
to fit. Reobserve and check that same claim before returning the signed token;
never extend its expiry after signing. Cross-authority uncertainty can cause
conservative denial; do not weaken checks to make a test succeed. Operational
error budgets and cross-host behavior remain unapproved.

Expose explicit observation and verified-claim consumption methods, not a drop-in
legacy `ClockHealth`/replay adapter. Integrate only into offline authority/broker
variants after primitive tests. Verification and membership checks are outside
the transaction, but authority delivery checks remain mandatory; no guarantee of
an atomic external membership database snapshot is added.

Synchronous sampling, verification and SQLite commit can stall. Bracketing and
post-checks detect observed elapsed-budget failures but **cannot guarantee a hard
deadline or an atomic wall-clock check at commit/network delivery**. Real host
containment, cancellation, storage and supervised shutdown/readiness enforcement
remain activation blockers. The prototype must label this limit, not market it
as a production authorization deadline or power-loss guarantee.

## Restart and recovery

Ordinary restart reopens exactly the same healthy state/bindings; it cannot clear
a latch or forget a consumed nonce. Missing/corrupt/legacy/uncertain state and
boot/collector epoch changes require stopped recovery, never in-place reset.

For offline recovery tests, stop issuance and all affected consumers/listeners,
retain old state as evidence, rotate the assertion generation/key and health trust
generation/epoch as an explicit coordinated test operation, and provision new
absent paths with matching configuration. Start only after all bindings agree.
Old unused parent/child capabilities and old health envelopes must fail. New
healthy capabilities may pass; old state files remain unchanged. No production
recovery CLI/controller or real key rotation is included in this offline scope.
Whole-file rollback by a trusted administrator and stolen trusted keys cannot be
detected solely by SQLite/signatures; external custody/fencing remains necessary.

## Ordered offline acceptance

1. Strict models/schema and explicit new-file provisioning; reject v1/v2, missing,
   corrupt, mismatched policy/key/authority/generation and unexpected schema.
2. Fake time plus signed evidence: rollback/suspend/gap, stale after delivery or
   verification, sequence conflict/regression, expiry/iat boundary/rounding,
   excessive uncertainty, wrong epoch/key, no nonce pruning on unsafe time.
3. Real temporary SQLite transactions: concurrent same-nonce attempts allow at
   most one success; reopen/separate-process replay and latch persistence; bounded
   lock contention; fault-injected write/commit failures never yield success.
   Process termination tests do not prove hardware power-loss durability.
4. Stopped-generation recovery tests with preserved old paths and no auto-reset.
5. Explicit offline broker/authority/pre-bind/two-hop TLS integration across two
   tenants/three roles; truthful SAVED/MISSING, zero source reads on early denial,
   no result delivery on later denial, replay and current-membership negatives.

Real provider, packaging/secret mounts, target-host policy, governance/service
identities and authenticated live acceptance stay in the P2 checklist. No P3,
deployment or completion-percentage increase follows from this proposal.

## First implementation checkpoint — state foundation, 22 October

`worker_guard_state.py` implements only item 1's inactive state foundation.
Explicit strict/frozen configuration binds authority, assertion generation,
health key fingerprint, health host/boot/generation/epoch, full canonical health
policy and fictional capacity/size/gap/step limits. Canonical source ordering
makes the configuration fingerprint deterministic. Fingerprints are bindings,
not evidence that a private key exists or that the host is healthy.

Explicit new-file test provisioning creates exact v3 singleton and nonce schemas.
The stored canonical configuration includes the complete policy, not just its
hash. Existing-file inspection checks ownership/mode, regular file/symlink/hardlink
shape and byte size, DELETE journal mode, integrity, exact schema SQL including
constraints and indexes/triggers, row counts, strict numerical/continuity shapes,
configuration identity, unsafe latch and bounded hashed nonce/expiry rows.
Missing/legacy/invalid state is denied without repair, pruning or row mutations.
Lock acquisition is bounded; no retry/fallback exists. Read-only inspection takes
the planned write lock then rolls back; it is **not** health or authorization.

This module exposes no `check`, `consume`, evidence callback, live provider,
collector, clock, authority wiring or recovery operation. A freshly provisioned
sequence-zero state is data, not readiness. It has no effect on the old v1/v2
prototypes, worker package, API startup or website. File checks are preliminary:
parent-directory custody, path races, malicious storage and whole-file rollback
are not solved; hardware power-loss and hard deadlines remain unproven.

Next: item 2, the unified signed-evidence observation/latch and conservative time
interval primitive, before nonce authorization and any transport integration.
Verification: **44 new state tests**, full API/PostgreSQL **725**, root **193**,
Ruff/format/whitespace pass. Browser/build/container/remote CI not rerun locally.
No Snowflake calls, real credentials, account changes, deployment or P3.

## Second checkpoint — signed observation and retained denial, 22 October

`worker_guard_health.py` adds an inactive `OfflineHealthGuard.observe` primitive
over the exact existing v3 state transaction. Its explicit RSA public key must
match SHA256 of DER SubjectPublicKeyInfo in the canonical stored configuration.
State/schema/configuration/latch/lock checks precede clock and evidence callbacks.
No key discovery, collector execution, network/source/membership operation,
application token consumption or startup wiring is added.

Injected strict wall/monotonic/boottime samples bracket immutable envelope delivery.
The final sample follows signature and retained-evidence continuity work. All
samples must remain in the pinned boot domain; rollback, suspend/read skew,
excessive retained gap and whole-operation elapsed-step limits deny. The same
verified immutable measurement is rechecked for original freshness and conservative
error at the final sample, without a second signature callback outside the sample
bracket. Sequence/content conflicts and regressing measurement/reference marks
deny. Equal sequence/content is accepted only while still fresh.

A successful observation commits its clock/evidence high-water marks and returns
inclusive bounded integer nanoseconds `[wall-error, wall+error]`. Arithmetic
underflow/overflow and non-integer inputs deny rather than clamp or round. Invalid
health/time after valid state commits only `unsafe=1`; no high-water advance or
nonce pruning/insertion occurs. Reopening with restored healthy input cannot clear
the latch or invoke callbacks. Invalid existing state is never repaired. Storage
failures deny; durable latch persistence cannot be promised if its commit fails.

Verification: **39 additional tests**, full API/PostgreSQL **764**, root **193**,
Ruff/format/whitespace pass. Tests cover final-time uncertainty, repeated and
advancing measurements, callback/lock/state failures, bad signature/epoch, stale
delivery and verification under a separately permissive elapsed budget, rollback,
suspend/gap/step limits, sequence/reference regression, exact interval extremes,
unchanged nonce rows and reopened denial. No browser/build/container/remote CI
rerun; no Snowflake spend, deployment, live credentials or P3.

Remaining ordered scope: verified-claim `iat`/`exp` interval and lifetime checks,
atomic nonce consumption and conservative pruning (then concurrency/process and
commit-fault tests), stopped recovery and explicit offline authority/transport
integration. This observation API is not application authorization or cached
readiness. Synchronous callbacks/verification/commit can still stall; real host,
custody, hard deadlines, external fencing and activation remain unproven.

## Bundled consumption/process/fault/recovery checkpoint — 22 October

`consume_verified` now takes a strict immutable internal `VerifiedGuardClaims`
contract, not raw JWTs or supplied `now`. It is only for an authority that already
verified signature, schema, scope and membership. Its name/type are not proof of
verification, and no public route or default startup exposes it. Exact namespace
and generation, bounded hashed nonce, integer timestamps, positive lifetime at
most the existing 30 seconds and whole inclusive uncertainty bounds are checked.

The same existing-file write transaction retains health/time marks, prunes only
entries whose expiry is definitely past the lower bound, checks replay/capacity,
and inserts at most one nonce. It acknowledges success only after commit. Ordinary
claim denials still commit the valid observation; invalid health commits only the
latch with no pruning. Database exceptions roll back uncommitted changes and
return generic denial, never retry. A commit that succeeded but lost its
acknowledgement may spend a nonce while returning denial; it is never refunded.

28 added tests cover exact `iat`/exclusive-expiry/lifetime boundaries, final rather
than pre-verification time, strict copied-model validation, safe pruning/capacity,
unsafe preservation, real lock contention, three independently spawned processes
racing one nonce, fresh-process replay/latch, observation/insert faults and both
pre/post-commit failures. Stopped primitive tests preserve old files, explicitly
provision absent paths and rotate health trust plus assertion generation. They
reject old claims and old signed health and accept new already-verified claims.
They do **not** prove assertion-signature/key rotation: full offline authority,
broker/pre-bind/two-hop integration and stopped issuer/listener recovery are next.

Legacy v1/v2 interfaces and startup remain unchanged. This is not live readiness,
a hard deadline, power-loss or whole-file rollback guarantee. No Snowflake calls,
account changes, deployment or P3 are included.
