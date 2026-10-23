# P2 Mac/Docker operational integration design

23 October 2026. Owner initially approved preparing this design, then explicitly
approved the disposable implementation batch below with a Mac load check first.
The [resource checkpoint](../product/mac-resource-check.md) defers heavy execution
at elevated pressure. Operational activation remains unapproved.
Proposed local synthetic integration; no purchase, new Linux host,
Snowflake access, secret creation, host configuration change or public deployment.
This specializes the [operational contract](p2-operational-control-design.md),
not a replacement for its fail-closed requirements.

## Decision and achievable result

Use the existing Mac and Docker Desktop for a separately invoked integration
candidate. Keep the accepted Next.js/FastAPI/PostgreSQL sandbox unchanged.
Do not turn its development role selector into public authentication.

Two modes must remain separate:

| Mode | Inputs and permitted result | Status |
| --- | --- | --- |
| Integration acceptance | Disposable test identities, signed fictional health and synthetic source; exercise canonical handlers in owned containers | Owner approved; shared logical-role TLS fixture prepared, container/supervisor composition still pending |
| Operational source | Real restricted identities, reviewed health policy/provider, protected retained state and current-generation authority | Blocked; no credentials or activation authorized |

The first mode closes service-composition gaps without a trial or payment. It
cannot close live P2 acceptance or justify enabling the normal source route.
Do not keep adding unrelated security primitives or silently extend this to P3.

## Proposed topology and ownership

The eight-role inventory remains fixed. Supervisor indices are mapped explicitly:
tenant index 0 is TPA001; index 1 is TPA003. `clinical` maps to the existing
`medical` disclosure identity; names must not be inferred from request strings.

| Component | Required authority / material | Never receives |
| --- | --- | --- |
| Broker | Assertion signer, own mTLS identity, own v3 state, verified identity/membership interface | Snowflake reader/validator credentials or CA signing key |
| Four tenant/disclosure readers | Own mTLS identity and v3 state; one matching restricted source identity only in the operational mode | Other reader credentials, assertion signer, app DB password |
| Two tenant validators | Own mTLS identity and v3 state; one matching restricted source identity only in the operational mode | Other tenant material, assertion signer, app DB password |
| Membership | Own mTLS identity and restricted DB credential, verified TLS point lookups | Assertion signer, Snowflake credentials, v3 nonce database |
| Health publisher (outside the eight) | Separate signing key, pinned provider and host/boot/epoch policy | Patient data and application assertion signer |
| Owner-side launcher/controller | Exact configuration/resource inventory and one-use launch approval | Permission to infer missing keys/state or initialize on restart |

Seven private v3 stores: broker, four readers and two validators. No shared
authority database. Health state is separate; application DB is not a replay
store. API/web are clients outside this inventory, not extra signing authorities.

Preserve the existing 14 allowed role-pair links: four broker-reader, four
reader-validator and six worker-membership. Broker identity/membership access,
membership-DB, health delivery and API-broker links require separately enumerated
edges; they must not be hidden inside a common network. Pin peer identities and
authorize operations even on an allowed network. No direct broker-validator hop.

For the acceptance mode, all networks are internal and source inputs are fixed
fixtures. No host-published ports, source egress or connection to the running
product DB. Use a disposable synthetic DB and existing restricted TLS factory.
Only the owner-side launcher uses the Docker API; never mount its socket into
the controller, broker, membership, workers or health publisher containers.

Use exact per-service mounts, read-only roots, non-root UID/GID 10001, dropped
capabilities and no-new-privileges. Validate actual ownership/readability and
network/mount sets before binding. Shared numeric UID is not isolation. Never
solve a permissions failure by making secret files world-readable.

## Proposed storage and unlock choice — not provisioned

For a later local operational experiment, prefer an **owner-unlocked encrypted
APFS disk image** created through macOS Disk Utility, outside the repository and
outside a cloud-sync directory. Apple documents encrypted APFS disk images and
manual mounting/ejection; this provides an at-rest option, not service isolation.
[Apple disk-image guide](https://support.apple.com/en-ca/guide/disk-utility/dskutl11888/mac).
The exact installed macOS options and Docker file-sharing behavior must be
verified during a separately approved disposable storage experiment.

Proposed flow: owner unlocks manually; a bounded materializer checks an explicit
volume identity and existing paths; each service receives only its own directory;
stop confirms every owned service and open mount gone before owner ejects.
Do not save the unlock password in repo, environment, argv, logs or container
configuration. No automatic Keychain integration or password collection here.
If unattended unlock is later required, review that as a different custody model.

The image would contain independent role material and retained states, not a
copy of `~/.snowflake`, `.env.product.local` or the existing product DB. Each
authority needs writable SQLite storage with protected parents, while delivered
identity files remain read-only. Permissions and SQLite durability across the
Mac/VM shared-filesystem boundary are **unproven**. Failure blocks use; no
fallback to unencrypted named volumes or permissive modes.

Docker documents that Mac containers run in a Linux VM and host file sharing is
mediated by Docker Desktop. Mac/Docker owners remain trusted; this is not
protection against them. [Docker permission model](https://docs.docker.com/desktop/setup/install/mac-permission-requirements/).
Mounted plaintext, VM memory/swap, core dumps, caches, indexing and backups are
not proven absent. No RAM-only, secure-erasure or rollback-resistant claim.
Do not change FileVault, backup settings or Docker sharing automatically.

## Clock health and activation authority: explicit blockers

Use Linux wall/monotonic/boottime observations from the same pinned VM domain
for the candidate. They do not prove synchronization with a trustworthy clock.
Do not install Chrony, alter macOS time/sleep settings or fabricate healthy
operational evidence. A future approved read-only observation must establish
provider/version/source freshness, uncertainty and boot/suspend behavior.

Mandatory policy inputs remain unset until evidence supports them: reference
age, uncertainty, collection/evidence age, sampling skew, guard step/gap,
startup/operation/stop budgets and bounded capacity. Retain the existing maximum
30-second assertion lifetime; never extend it to accommodate a slow host.
Fictional test budgets must be explicitly marked and rejected by operational
configuration. No health provider or unset budget means no operational bind.

Mac sleep, Docker restart/VM replacement, unknown elapsed gap and boot mismatch
must close issuance/delivery and require stopped review. Test these by injected
observations; never sleep the owner's machine or change its clock for acceptance.
The watchdog shares this machine and cannot guarantee timely action while the
host is suspended. This is not an external availability or hard deadline SLA.

An operator-controlled launch record outside service mounts can prevent ordinary
accidental restart in the local experiment. It **cannot** provide independent
current-generation authority against complete Mac/VM rollback. A signed file,
SQLite file, another container or manual checkbox on the same restored host does
not fix that. Preserve this operational blocker; no live activation until a
separately approved authority/recovery model meets the existing contract.

## Lifecycle and failure behavior

1. Construction stays STOPPED. Explicit launch checks image/configuration hashes,
   exact inventory, existing state and external approval; no initializer/retry.
2. Track owned container identities, not reusable PIDs/names alone. Serialize
   supervisor transitions; Docker/process I/O runs in bounded owned actors so a
   stalled callback cannot monopolize the controller. Watchdog is independent of
   that actor. Unknown completion closes admission and fences; never reuse its slot.
3. Start canonical membership/reader/validator/broker handlers, not marker stubs.
   All eight readiness receipts bind attempt, generation, configuration and
   incarnation. Before the barrier, externally observable protected work denies.
4. Bind alone does not authorize. Every operation rechecks identity/membership,
   scope, signatures, guard state and immutable deadline before delivery. Permit
   only the validated summary contract, never raw decision JSON/clinical payload.
5. Stop closes admission and delivery first, then bounded cancel/drain, closes
   listeners, terminates owned work and confirms exit. Uncertain cleanup stays
   FENCED; no replacement work or automatic restart.
6. Crash/sleep recovery preserves old state and incident metadata. Never restore
   an active ledger backup, repair a suspect file or clear its latch. New trust
   and state require separately approved stopped-generation recovery.

## Approved next implementation batch — pending Mac headroom

**Build and run an opt-in, disposable Mac/Docker service-composition acceptance
mode**, using generated test keys, a disposable membership DB and fictional
signed health/source inputs only. This is not permission to create the encrypted
image, read any existing credential or replace normal service entry points.
Owner approval includes a configuration/load precheck; it is not permission to
stress the machine despite failing headroom. No extra implementation approval
is needed merely because this resource checkpoint deferred the work.

Lightweight preparation extends the existing explicit `mtls-test` fixture to
all seven authority roles, preserving existing test aliases and default image
refusal. The new `guard_composition_fixture.py` test helper composes canonical
broker, four readers, two validators and membership in one test process. Six
worker listeners and membership use real loopback TLS; the broker is invoked
in-process, verifying signed local-test JWTs. Broker membership resolution and
membership storage are injected memory fixtures; workers use six pinned, fresh
membership TLS clients. Source and frozen signed health inputs remain fictional.
The test TLS certificates now permit validators to act as clients for that
membership hop; no actual runtime credential changed.

Shared-topology checks cover both tenants/all three roles, SAVED INR 95,000,
truthful MISSING, retained replay, disclosure routing, mid-read revocation or
downgrade, source/membership outage, invalid health, foreign peer/direct-hop denial
and actual listener closure after normal/partial startup. This does **not** wire
eight independent processes/containers, supervisor/launcher readiness or deadline
control, shared health delivery or restricted membership DB composition. Those
remain the next implementation work and are not accepted by loopback tests.

`guard_supervisor_fixture.py` additionally adopts that already-created test world
into the existing lifecycle model. Individual closures stop real test listeners,
and a supervised result path checks all-eight readiness plus operation completion.
Tests exercise stale receipts, expired/closed delivery and retained capacity under
unknown cancellation. Time, approval and cancellation acknowledgements are fake;
artifact markers are not image attestations. The bridge is not a process launcher,
independent watchdog or protection against trusted test code directly calling the
raw world. Unadopted listeners on partial failure remain owned by the outer test
scope. This closes a model/handler composition test gap, not container acceptance.

- Compose all eight canonical roles with the existing supervisor and bounded
  launcher/watchdog adapters; test the real handlers/listeners, not service stubs.
- Exercise both tenants and all three roles through verified identity context:
  SAVED INR 95,000, truthful MISSING and injected source unavailability. No live
  API route, user browser session or public endpoint is activated by this mode.
- Verify identity revocation/disclosure downgrade, foreign tenant/direct-hop
  denial, retained replay and rejection of stale readiness/late completion.
- Exercise partial start, blocked handler/launch, stop and restart. Confirm
  exact owned container exit and listener unreachability; ambiguous termination
  retains the fence. Verify missing/corrupt state is never initialized/repaired.
- Bound the invocation to 15 minutes including reserved cleanup. Report exact
  UUID-labeled leftovers if cleanup cannot be confirmed; never prune Docker or
  touch existing product volumes, private archives or unrelated resources.
- Commit one coherent implementation/test/evidence batch, run existing regression
  and CI, and report actual limits. No extra primitive redesign unless a defect
  in this composition requires it. Stop before operational custody/provider work.

Passing closes only this service-composition acceptance gap. Encrypted storage,
real health policy, durable independent authority, governed source identities,
approved financial/clinical projection, live API/UI acceptance and public OIDC/
hosting are still open. P3 remains blocked by P2 exit. No percentage increase is
earned merely by writing this design.

## Implementation anchors and change exclusions

Reuse `offline_supervisor.py`, v3 broker/guard/transport, restricted membership
factory, worker/membership packaging and existing container fixtures. The current
worker and membership `__main__.py` deliberately exit; do not remove that refusal
in an integration test target. Keep `compose.product.yml`, normal source flags,
API contracts and `http://localhost:3000` owner sandbox unchanged.

This document is the only new design artifact. No encrypted image, keys,
containers, volumes, account objects or daemon were created during its drafting.
