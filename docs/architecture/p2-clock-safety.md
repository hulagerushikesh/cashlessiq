# P2 clock safety — approved offline design and candidate

21 October 2026. **Owner approved offline design/implementation; no activation approval.**
Scope: single trusted host, synthetic workers and retained SQLite replay state.
Parent: [runtime lifecycle](p2-runtime-lifecycle.md). No Snowflake, paid service,
secret provisioning, public deployment or P3 is required for this design.

## Confirmed gap

`SqliteReplayLedger.consume` deletes expired nonces using caller-supplied wall
time inside its consumption transaction. `SummaryAuthority` checks that same
kind of time before/after consumption and before delivery; the broker also uses
wall time for issuance/delivery. None checks clock continuity or clock health.

A temporary-ledger characterization on 21 October reproduced this sequence:

1. Consume nonce A at time 1000, expiry 1030.
2. Consume B at time 1030, expiry 1060; cleanup deletes A.
3. Reconstruct the ledger object and consume A again at time 1001, expiry 1030.
4. The current ledger accepts A again. No signed-token or full transport test is
   claimed by this primitive experiment; it establishes the storage prerequisite
   for replay after forward pruning and rollback. The temporary file was removed.

Keeping a process-local last timestamp is insufficient across process restart.
A durable high-water mark prevents backward reuse after committed forward time,
but alone does not identify an unsafe forward jump or external clock uncertainty.
Never clamp bad time and continue serving: that can prolong capability validity.

## Proposed contract

Use an explicit injected clock guard, with no environment/default clock discovery
or network time lookup in request handlers. Test samples contain integer wall
nanoseconds, monotonic nanoseconds and a trusted host boot identifier. A separate
trusted health attestation must include synchronization status, bounded error and
freshness; the application must not infer those from a successful time read.
The actual host health provider and numerical tolerances are **not selected**.

The guard belongs at broker issuance, authority authorization/consumption and
delivery, including child delegation. A ledger-only patch cannot close the gate.
Guard failures produce generic denial, never a MISSING recommendation or fallback.

Proposed durable state per authority includes schema version, signing generation,
boot identity, last accepted wall/monotonic sample and a latched unsafe flag.
Bind state to the reviewed authority/generation, not a request-selected name.
Broker needs its own durable guard state; it has no authority replay volume and
must not gain access to one. Exact broker storage/mount changes need separate
implementation review. Do not add payloads, tokens or secrets to these records.

### Serialization and transaction rules

- Sample time/health **after acquiring** the guard's serialization lock. Sampling
  before a wait can make ordinary concurrent callers look like clock rollback.
- Reject negative/non-integer samples, backward monotonic time, boot mismatch,
  wall time below its durable high-water, stale/unhealthy attestation or excessive
  disagreement between wall and monotonic elapsed time. Equal samples may pass.
- Any detected discontinuity commits an unsafe latch before returning denial.
  A later apparently healthy sample cannot clear it. Missing/corrupt/unwritable
  state denies even if the latch itself cannot be persisted.
- For retained authority consumption, clock acceptance/high-water advancement,
  nonce cleanup and nonce insertion need one serialized protocol. An ordinary
  duplicate/full/expired-token denial must not roll back an observed forward
  high-water or unsafe latch. The current exception-driven transaction rollback
  cannot simply be reused unchanged. Commit clock state separately from nonce
  denial, without consuming a nonce or pruning on unsafe time.
- Authorization/delivery guard checks also persist observations; a failed
  membership or source operation must not undo clock safety state. No source
  read or delivery follows a failed guard. The nonce remains consumed if work
  later fails, as today; no retry reset is introduced.

An integrity/version check before binding must reject legacy or incomplete
files rather than silently ALTER/initialize them. File custody/TOCTOU and SQLite
durability under power loss remain separate gates; a schema check is not proof
against host administrators restoring a valid older file.

## Restart, outages and recovery

Same-boot process/container restart preserves and validates durable samples;
Linux containers must observe the same host monotonic/boot domain. Prove this in
the target environment, not just fake-clock tests. Across host reboot, suspend
or an unobservable gap, clock health/error and continuity may be uncertain.
Conservatively keep issuance/routes disabled and require reviewed signing-
generation recovery; never auto-rebase persisted monotonic values or reinitialize
under old trust. Suspend semantics and health freshness belong in provider review.

A host administrator can modify clocks, boot identity or SQLite state. This is
not anti-tamper storage, a distributed clock protocol or a defence against a
compromised trusted host. High-water alone does not detect restoring a complete
older snapshot. Existing no-active-ledger-backup policy still applies.

Unsafe-state recovery follows the stopped-authority/new-signing-generation
procedure, preserves evidence and creates explicitly authorized new state only
after old signatures are rejected everywhere. No automatic latch reset, timer-
based recovery, overlapping old trust, active-volume restore or paid service.

## Bounded implementation and acceptance order

1. Review this contract; implement a standalone inactive guard with deterministic
   fake time/health and disposable SQLite only. No production health-provider
   claim. Define exact tolerance configuration as validated, explicit input;
   fake-clock test values are not operational thresholds.
2. Test forward-prune/backward, backward-before-prune, excessive forward jump,
   stale/unhealthy health, same-sample concurrency, duplicate/full-token denial
   followed by rollback, failed latch persistence, lock contention, corrupt/
   missing/version/generation state and same-boot object/process restart.
3. Compose actual signed parent/child authorities and broker with guard checks
   before input/source access and delivery. Verify failure leaves zero source
   reads/delivery, restart cannot clear a latch, and fresh legitimate requests
   still succeed. Cover both tenants and all roles; no disclosure expansion.
4. Review/prove the host time-health source, uncertainty/freshness/tolerances,
   host boot/suspend policy, broker mount and stopped-generation recovery, then
   compose disposable containers and test their real clock domain. Never alter
   the developer host clock to test jumps; inject the test provider.
5. Only after custody/readiness/deadline and remaining isolation acceptance may
   separately approved service wiring activate the guard. Existing default
   executables and live HTTP source path remain disabled throughout this work.

## Offline implementation checkpoint — 21 October

Owner explicitly approved the offline design and implementation. The inactive
`apps/api/src/ciq_api/worker_clock.py` candidate uses explicit immutable sample,
health and tolerance inputs and an existing-file SQLite guard. It binds one
authority/signing-generation/boot identity; no default clock or health provider
is installed. All numerical thresholds used in tests are fictional test policy.

An immediate transaction lock precedes sampling. Durable high-water/unsafe
observations and nonce cleanup/insertion share serialization; ordinary expired,
duplicate, full or wrong-namespace denials commit clock observations first.
Unsafe observations latch before denial without pruning/consuming. Missing,
corrupt, legacy, mismatched-generation, locked and failed-write state denies
without auto-reset or fallback. Integrity/version checks run on each guard call,
not an implemented service readiness/bind controller. FULL synchronous SQLite
configuration is not proof of power-loss durability on the eventual host.

**69 offline tests** cover primitives and actual RS256 broker/parent/child
composition. Separate broker, reader and validator files are explicitly injected
as clock callbacks; authority files also implement the replay protocol. Both
tenants/all three roles preserve GOL001 SAVED/INR 95,000 and GOL024 MISSING.
Unsafe authorization denies before source access; jumps injected during source
work deny delivery independently at validator, reader and broker. Reconstructing
guard/authority/broker objects cannot clear a committed latch. Separate Python
processes verify healthy retained replay/fresh use and sticky unsafe rejection.
Identity, membership, peers, source inputs, boot identity and health remain fake;
these tests do not establish HTTP authentication, mTLS or real host continuity.

The first composition run used a nonexistent `status` field; corrected to the
existing `state` contract rather than changing the contract or expected outcomes.
The final complete regression results are recorded in the product progress log.

No existing authority/broker constructor, legacy replay implementation, worker
wheel, default executable, HTTP route or normal startup was changed. The legacy
ledger alone still has the characterized gap; it must not be activated as a
substitute for the guarded composition. The new candidate is not deployed.

**Still open:** real host health/freshness/tolerance and suspend/boot review,
broker storage/custody, worker packaging/container clock-domain acceptance,
readiness/deadline/generation controllers, live source isolation and P2 exit.
Latch-write failure guarantees denial, not persistence through failed storage;
trusted-host snapshot rollback and power-loss recovery remain outside this test.
No new credentials, Snowflake/AI spend, public deployment, push or P3.
Completion estimate remains 35–40% overall, P2 approximately 60% until the
remaining operational/live gates pass.
