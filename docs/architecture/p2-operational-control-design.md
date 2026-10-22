# P2 operational control contract

22 October 2026. **Offline model implementation explicitly approved and completed;
real provisioning/wiring/activation remains unapproved.** Synthetic read-only P2;
no purchases, deployment or P3. See [acceptance and limits](p2-offline-supervisor-acceptance.md).

23 October follow-up: the owner separately authorized the bounded disposable
Linux process-containment harness. Actual stub termination/escalation, a blocked
callback watchdog and cleanup now pass; [evidence and limits](p2-process-containment-acceptance.md).
This does not approve real secret delivery, product-service wiring or activation.

Next gate after [combined v3 container acceptance](p2-unified-container-acceptance.md).
This consolidates [runtime lifecycle](p2-runtime-lifecycle.md) and
[host health](p2-clock-health-review.md). Fixture acceptance cannot implicitly
authorize real credentials, host changes or source activation.

## Recommended next milestone

One **inactive offline supervisor prototype** with injected process, readiness,
clock and delivery interfaces. Bundle lifecycle, admission/deadline, partial
startup cleanup and recovery-order tests. No real secret store, daemon, Docker
control, Snowflake connection, credential read or application-startup integration.
Normal entry points keep refusing activation. Real integration requires another
review and exact owner approval after this milestone.

## Fixed inventory

| Role | Count | Private material/state boundary |
| --- | --- | --- |
| Broker | 1 | Assertion signer, own mTLS identity and v3 observation state; separately restricted app identity/membership DB access |
| Tenant/disclosure readers | 4 | Each own mTLS identity/v3 state and matching Snowflake reader key only if separately provisioned |
| Tenant validators | 2 | Each own mTLS identity/v3 state and matching Snowflake validator key only if separately provisioned |
| Membership | 1 | Own mTLS identity and restricted DB credential; no assertion signer/Snowflake key |

Eight application roles, **seven independent v3 authority states**. The health
publisher is a separate trust component whose signing key never reaches consumers.
Neither CA signing key enters a runtime service. There is no cross-service ledger.

Host/kernel, Docker owner and unlock operator remain trusted. Shared numeric UID
10001 is not host-user isolation; exact mount/network namespaces are necessary.
No defence against compromised host administrators or whole-host snapshot rollback.

## Lifecycle and external generation fence

```text
STOPPED -> VERIFYING -> STARTING -> READY -> DRAINING -> STOPPED
              |           |         |          |
              +-----------+---------+----------+-> FENCED
FENCED -- explicit stopped recovery and external approval --> STOPPED
```

- Construction is STOPPED, admission disabled, with no I/O or automatic startup.
- VERIFYING requires exact role inventory, artifact/configuration fingerprints
  and approved generation. Missing/extra/duplicate/mixed-domain entries deny.
- STARTING tracks explicit process incarnations, not just PIDs. Readiness binds
  role, controller attempt, generation, artifact/config fingerprints and incarnation.
  Duplicate/stale/foreign acknowledgements cannot advance its barrier.
- READY requires all eight matching acknowledgements plus a current controller
  gate. A caller boolean or listening socket alone is not live attestation.
- Failures close admission first; uncertain stop/cleanup enters sticky FENCED.
  No automatic restart, partial readiness, state reset or override.
- Intentional stop returns STOPPED only when all owned processes/listeners are
  confirmed gone. Ordinary stop never rotates keys or initializes files.

An in-memory fence cannot survive supervisor replacement. Real wiring requires
an external operator-owned current-generation activation record and no automatic
startup without fresh approval. Its custody/rollback protection is unresolved.
An old signed manifest can be replayed: signatures alone do not establish the
currently authorized generation. Losing this external authority or complete old
process inventory blocks activation/recovery.

## Readiness and partial-start rollback

Before any bind, verify the exact delivered file/mount/network inventory, key/
certificate match, peer identity/pins, certificate validity, explicit endpoints
and existing v3 guard health/configuration. Membership also verifies restricted
DB/TLS configuration. Real bounded connection probes need separate approval.

Readiness never decrypts, fetches, initializes, repairs or migrates material.
Unavailability is not MISSING recommendation data. Every operation still checks
identity, membership, scope and fresh guard; readiness is not cached authorization.

For multiple listeners retain every owned handle. Failure of a later listener
closes earlier listeners and joins serving tasks; dropping Python objects is
insufficient. Cleanup uncertainty fences the attempt. Protected work must remain
unavailable before the complete barrier even if a socket has been allocated.

The offline prototype uses injected handles only. Mock cleanup/readiness cannot
prove OS socket closure, cryptographic file custody or process containment;
subsequent disposable-container acceptance must demonstrate those effects.

## Admission, deadlines and late results

Keep the maximum 30-second assertion lifetime and conservative guard interval;
no leeway, extended expiry or timeout-triggered reissuance. Operation, stop-grace,
capacity, queue and health limits are explicit mandatory reviewed inputs, not
runtime defaults copied from fixtures.

1. Admit only in READY for the current attempt/generation with bounded capacity.
   No unbounded waiting queue; overflow rejects immediately.
2. Assign opaque operation ID and immutable deadline using injected suspend-aware
   elapsed samples. Reject bool/float, negatives, wrong domain, rollback and
   arithmetic overflow. Wall-clock JWT validity remains the v3 guard's concern.
3. Reject at the exclusive deadline, after readiness loss/stop, or for an old
   attempt/generation/closed operation. Duplicate completion never releases
   capacity twice. Stop closes all result delivery before cancellation/drain.
4. On timeout request cancellation only after closing delivery. Unknown termination
   outcome fences the attempt: do not free execution capacity and launch replacement
   work while old work may still execute.
5. Never refund consumed nonces, retry automatically, translate errors to MISSING
   or record capabilities/raw results in audit output.

Observed-late callback rejection is **not a hard execution/delivery deadline**.
Blocked Python/TLS/signature/SQLite calls require real owned-process containment,
an independent watchdog and confirmed termination/closed response channels.
Thread/socket/SQL timeouts alone do not close this gate. A watchdog sharing a
paused host cannot promise an external availability bound either.

## Stop and recovery ordering

First fence broker admission/result delivery, then bounded drain/cancel, close
listeners/connections and confirm every owned process terminated. Late readiness
or completion cannot reopen admission. Unknown outcome fences the generation;
repeated stop is idempotent, not permission to delete files or pretend exit.

Recovery remains an operator maintenance operation:

1. Confirm every old broker/authority/listener stopped. Waiting for token expiry
   is not proof of termination. Preserve old guard files and incident metadata.
2. Separately authorize new assertion key/generation and health key/generation/
   epoch/boot bindings for all seven authorities. Compromised TLS/DB/Snowflake
   material has its own approved revocation package.
3. Explicitly initialize new absent paths only after old trust is retired
   everywhere. No startup initializer, request-selected path or memory fallback.
4. Verify the full inventory, fresh health/readiness, old unused parent/child
   denial and fresh valid operation before separately reopening admission.

No active-ledger backup restore, old credential rollback or implicit migration.
An older non-secret artifact may run only if it preserves current trust/checks/state.

## Real delivery package: unresolved decisions

| Required owner choice/evidence | Acceptance before real wiring |
| --- | --- |
| Actual Linux kernel/VM and storage | Measured boot/monotonic/boottime/suspend/durability boundary; Docker Desktop is test evidence only |
| One encrypted store and unlock operator | Exact provider/unlock/relock/authorization/crash flow reviewed; no paid service assumed |
| Per-service materialization | Exact read-only mounts; application UID/GID 10001, private files 0400/parents 0700; symlink/hardlink/race and cleanup proof |
| Plaintext custody | Explicit disk/tmpfs/swap/core-dump/backup behavior; no blanket RAM-only claim |
| Health publisher and source policy | Exact executable/version, read-only access, allowed sources, signed delivery, host/boot/epoch; no daemon control socket in workers |
| Numeric budgets | Evidence-based uncertainty/freshness/drift/gap/suspend/deadline/stop/capacity limits; missing values deny |
| Durable external fence | Current-generation approval, controller crash/restart, stale replica exclusion and restore policy |
| Identities and egress | Exact six Snowflake principals/governed views/rollback; restricted DB/OIDC access and endpoint/network allowlists |

No real host/store is selected here. Immediate recommendation is to keep using
the existing local disposable environment for the offline prototype, not purchase
a VM or reuse human Snowflake OAuth. Actual host/store selection is a later owner
decision, not something fake tests can resolve.

## Bundled prototype acceptance

- Exact eight-role/seven-state inventory and wrong/duplicate/missing/mixed bindings.
- Constructor performs no I/O; STOPPED/FENCED deny admission.
- Full readiness barrier; stale/duplicate/foreign acknowledgements never open it.
- Partial launch/bind cleanup; uncertain cleanup/termination fences.
- Capacity, exclusive deadline, domain/rollback/suspend-gap/overflow negatives;
  late/duplicate/old-generation completion and no delivery after stop.
- Cancellation failure/hung-worker model; replacement controller stays inactive
  without fresh external approval. No implicit state initialization/retry/refund.
- Repeated stop/recovery ordering and preserved old state.
- Bounded generic audit metadata only: attempt/operation/role/generation/reason,
  never secrets, tokens, clinical text or raw source output.
- Existing guard/transport/package regressions; normal artifacts/API contracts/
  source routes/public site unchanged.

Stop after this milestone before real wiring. Mock acceptance is not production
readiness and does not close P2 or increase its completion estimate on its own.

## Approval boundary

The owner approved **only the inactive offline supervisor prototype and bundled
acceptance above**, with fake process/readiness/clock/delivery adapters and disposable state.
Not real secret delivery, service wiring, daemon/host changes, Snowflake provisioning
or spend, deployment, or P2 exit.
