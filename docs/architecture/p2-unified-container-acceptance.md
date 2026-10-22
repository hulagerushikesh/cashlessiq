# P2 unified v3 private-container acceptance

22 October 2026. **Disposable synthetic acceptance, not activation approval.**

```sh
make product-worker-guard-tls
```

## What this composes

The existing private mTLS harness now has an explicit `--unified-guard-tls`
mode. Its worker image runs the canonical v3 `GuardedAuthority`,
`GuardedReadRelay` and `GuardedPrivateSummaryServer`, without the legacy replay
or clock adapter. The validator uses canonical saved-recommendation validation.
Each authority has its own explicitly initialized private v3 SQLite volume.

Five disposable containers and five internal pair networks connect broker–reader,
reader–validator, reader–membership, validator–membership and membership–DB.
Exact mounts/network sets, non-root application UID/GID 10001, read-only roots,
dropped capabilities, no-new-privileges and absence of host ports are inspected.
Only membership has the restricted DB password, driver and database network;
actual-IP DB attempts from the other three containers fail. Membership uses the
fixed connection factory with verified PostgreSQL TLS 1.3 and fresh restricted
point lookups. Only the test broker has the assertion private key; only the
validator has the raw fictional decision input. The CA key remains in driver memory.

The membership Docker build context was corrected to include the newly required
canonical guard modules and the previously omitted clock module. Its default
executable remains activation-refusing. The worker test helper is included only
in `mtls-test`, never the worker or membership default candidate/wheel.

## Acceptance observed

- Synthetic TPA001/GOL001 returns SAVED, payable INR 95,000, with no raw financial
  lines, decision JSON, clinical text or narrative in the response.
- Parent and child replay are independently denied after their respective worker
  container restarts, while still valid under the explicit fictional time policy.
  A fresh request succeeds afterward. Both retained v3 states are healthy and
  contain hashed unexpired nonces only.
- Tampered tokens, wrong pins/URI identities, foreign-tenant assertions, forbidden
  direct broker–validator access and reader impersonation of broker deny.
- Wrong DB hostname, plaintext, wrong/missing CA and hostile ambient connection
  configuration deny; restored DB trust permits a fresh delegated request.
- Processor-to-medical disclosure change, independently inactive user/tenant/
  membership, revoked required column SELECT, and paused DB deny. Restoration
  permits fresh requests without rebuilding/restarting membership or its factory.
- With other dependencies healthy, an injected fictional validator clock rollback
  latches unsafe state and denies delivery. Restart does not clear the latch;
  pre-bind startup refuses. Independently removing the reader's test state also
  refuses pre-bind startup without recreating it.
- Invocation-owned containers, networks, volumes, image tags and temporary PKI
  are removed in `finally`; Docker build cache can remain. Normal product resources
  are not removed. Abrupt controller/host loss still needs exact-prefix cleanup.

## Evidence limits

This composition **deliberately freezes fictional health/time** at 1000.5 seconds.
Explicit setup generates separate health signing keys for the two authorities,
then discards them; only public fake signed evidence/configuration remains. It
does not install/query a daemon, demonstrate freshness in real elapsed time,
prove suspend/resume handling or supply an operational health provider. The
separate `make product-worker-guard` probe uses actual Linux clocks and also
fabricates health; neither test is synchronization proof.

Broker here is a disposable signing driver, not the authenticated API v3 broker.
This container mode covers one tenant/nonclinical SAVED flow. Two tenants/all
roles, MISSING and actual v3 broker checks have separate loopback/offline evidence;
they are not silently claimed as container or live source acceptance. No Snowflake
data, principal or account is used. Test files are not real secret custody.

Revocation tests issue new requests after committed changes. They do not prove
atomic distributed revocation during a response. The stdlib listeners are test
candidates; real deadline/backpressure/shutdown/fencing and multi-listener rollback
are still open. No normal startup, public route, SQL grants or deployment changes.

## Latest verification

The v3 combined run `ciq-mtls-82efcd322a84` passed and cleaned its owned resources.
Twelve new fixture tests cover both authority domains, replay, no reinitialization,
missing/corrupt state and retained health/time denial. Two new package regressions
cover the membership build context and explicit-only test helper. Full backend
**898** and root **202** tests pass; one existing invalid-model serializer warning
remains. Isolated worker package/import/default-refusal checks pass.
The legacy combined replay/DB-TLS regression `ciq-mtls-f25b44951161` also passes
with owned cleanup. Fresh isolated membership package checks refuse activation
and exclude API/broker/topology helpers. The actual-Linux v3 clock-domain/artifact
regression `ciq-clock-ac851c27d650` passes with owned cleanup and confirms the new
test helper is absent from the default worker image. Ruff, changed-Python format
and whitespace checks pass. Browser/frontend build and remote CI were not rerun
for this internal test-only milestone.

P2 remains open. Next gates: real-host health/custody/readiness/deadline/recovery
review; separately approved Snowflake governed projections/service identities;
financial/clinical evidence display and authenticated local API/UI source acceptance;
then final regression/remote CI and P2 exit review. No P3 or website deployment.
