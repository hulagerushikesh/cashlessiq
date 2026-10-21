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

## Disposable Linux clock-domain/artifact checkpoint — 21 October

`make product-worker-clock` builds the canonical guard into the restricted
worker wheel/image and a separate `clock-test` target. The normal artifact
contains no clock probe or API startup; its packaged guard hash matches the
repository file and its default executable still refuses activation. The Docker
build bypasses local wheel caches to avoid stale repackaged canonical modules.
No runtime imports or defaults select this guard automatically.

The probe reads Linux wall/monotonic nanoseconds and the kernel boot identifier
but **fabricates health synchronization/error evidence**. It is not a host-health
provider. Test limits (two-second drift, 120-second gap) are solely disposable
test configuration, not approved deployment thresholds. No system clock is set.

Two non-root/read-only/no-capability/no-new-privilege containers with no network
or host ports share only one invocation-owned authority state volume. They
observe matching boot identities and nondecreasing wall/monotonic samples.
An unexpired consumed nonce denies in the second container and after restart of
the first. An injected backward wall sample latches unsafe; normal samples in
both containers, including another restart, cannot clear it. Initialization is
explicit and network-free, using root/CHOWN only to provision disposable owned
state; request processes use UID 10001 without capabilities.

Final run `ciq-clock-12356d1b1bac` passed, including exact source-hash/default
artifact checks. Earlier run `ciq-clock-a548d137565e` passed the initial probe.
Both removed their exact test containers and state volume; build cache may
remain. No normal product resources were removed or restarted.

This establishes a bounded clock-domain/restart property on the current Docker
Linux VM, **not** real synchronization, host suspend/reboot safety, a deployment
host guarantee, signed/mTLS clock composition, encrypted custody, integrity-
checked service readiness or an issuance/recovery controller. Production health
provider, tolerance policy and broker mounts still need review before activation.
No network time lookup, Snowflake/AI, real secret, deployment, push or P3.

## Opt-in pre-bind clock readiness — 21 October

`ClockCheckedSummaryServer` and `ClockCheckedPrivateSummaryServer` require an
explicit canonical guard and call it before constructing/binding their socket.
No legacy constructor/default/startup is changed. Their callback still must use
the same guard for authorization/replay/delivery; startup is not a cached grant.
This is clock readiness only, not complete file/certificate/custody/deadline or
multi-listener startup/rollback control.

Eighteen new offline tests verify both adapter variants deny missing, corrupt,
legacy, wrong-version/generation, latched, unhealthy and rollback state before
`server_bind` is reached, with no source work or implicit repair. A healthy
case binds/closes an actual loopback socket after sample/health checks. The
private negative tests never bind a private interface; no private clock/mTLS
composition or real host-health acceptance is inferred.

The [host-health review](p2-clock-health-review.md) records verified Linux suspend
semantics and Chrony evidence/control limitations. It defines the remaining
provider/host/delivery requirements, not an installed or approved time daemon.
In particular, boot ID plus ordinary monotonic time is not a suspend detector.
Membership Docker packaging now includes the canonical clock source required by
its worker dependency and bypasses stale local wheels. No service is activated.

Full API/DB **467**, root **175**, isolated membership packaging/activation-refusal,
lint/format/whitespace checks pass. The existing combined retained-replay/DB-TLS
regression passed on a bounded sequential rerun (`ciq-mtls-4bdccccb5697`) and
removed its owned resources. An initial run (`ciq-mtls-66eb51aa34e2`) denied the
first `prepare-restart` delegated request and cleaned up. Its generic denial did
not establish the cause; no fixed cause or concurrency explanation is claimed.
The rerun changed no code, timeout or security assertion. Keep this intermittent
failure recorded for further diagnosis if reproduced; it is not proof that a
timing problem was fixed. That existing harness still uses the legacy authority
clock/ledger, not the new clock-checked adapters or full guarded mTLS composition.

## Signed two-hop loopback mTLS composition — 21 October

`apps/api/tests/test_worker_clock_mtls.py` adds **42 cases**: both synthetic
tenants, all three roles, healthy behavior and unsafe clock samples at broker,
reader or validator authorization/delivery. Actual RS256 parent/child signatures,
guarded SQLite replay, clock-checked pre-bind listeners and both TLS hops are
composed together. Disposable certificates pin the matching tenant/disclosure
reader and validator identities; the reader endpoint accepts only the broker
certificate and the validator endpoint accepts only the configured reader.

Each case first proves a healthy request returns GOL001 SAVED/INR 95,000 or
GOL024 MISSING. Reusing consumed unexpired parent/child capabilities through
their legitimate TLS clients denies without another source read. Healthy fresh
capabilities still succeed. Unsafe authorization prevents input access; an
injected failure during source work prevents delivery at the selected hop.
Apparently healthy samples cannot clear the committed latch while TLS listeners
remain up or after guard reconstruction following listener shutdown.

The shared disposable PKI fixture now supplies both tenant/disclosure identities.
No application source or startup behavior changes in this increment. TLS uses
the actual system certificate clock; assertion time and health are deterministic
test values. Browser/session identity, membership and source inputs remain fake.
This proves loopback transport composition, not process/container secret
isolation, real synchronization, suspend safety or private target-host behavior.
Threads/listeners and temporary PKI are closed by fixtures; pytest may retain
its temporary hash/time-only guard files under its normal retention policy.
No Snowflake/AI, runtime activation, account changes, deployment, push or P3.
