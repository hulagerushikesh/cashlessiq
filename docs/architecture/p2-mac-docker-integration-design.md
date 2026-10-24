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

The worker Dockerfile now has a separate opt-in `composition-test` target with
`python -m ciq_worker_runtime.composition_service` as its entry point. This test
target inherits the disposable health helper; the default candidate still refuses
service startup. It supports exactly the six reader/validator role names above,
not broker or membership. Shared loopback tests import the exact same handler
builder, avoiding a second implementation of the canonical chain.

Its trusted `/run/ciq/config.json` contains exactly `role`, `listen` (one to three
private IPv4 addresses at port 8443), `peers` (certificate SHA-256 pin to fixed
peer audience) and `membership` (`address`, `pin`). Readers additionally require
`validator` (`address`, `pin`); validators reject that extra field. Membership's
fixed wire audience remains `membership:0`, with tenant derived from the exact
worker role, not request/config tenant fields. Reader peers are broker only;
validator peers are its same-tenant medical/nonclinical readers only.

Each service requires its own `ca.pem`, `identity.pem`, `identity.key` and public
assertion `verify.pem`, plus its already-initialized own v3 store at the existing
test helper paths. Only validators require a synthetic `source.json`, keyed by
request ID with `case`, `decisions`, `evidence` rows. Source reads happen per request
to allow an outage test; missing rows/files never become a MISSING recommendation.
There is no assertion signer, source SQL or automatic initialization in this
entry point. The future launcher must enforce exact mounts and permissions; this
module alone does not prove custody or reject unrelated files on a trusted mount.

All listeners bind before serving starts. Startup stop checks suppress diagnostic
`READY`; partial failure/stop owns listener closure and orderly serving-thread
shutdown. This does not supply the all-eight supervisor receipt/barrier,
independent watchdog, hard I/O deadline or container cleanup. Those remain the
next integration work, alongside the broker/membership container composition and
two-tenant restricted DB fixture. No heavy execution bypass is authorized by the
new test target; the host preflight still gates the approved container run.

Membership now has its own opt-in `composition-test` image target with
`python -m ciq_membership_runtime.composition_service`. Its `/run/ciq/config.json`
contains exactly six private IPv4 `listen` addresses and `peers` (six certificate
SHA-256 pins mapped to the fixed four reader/two validator audiences). Each peer's
tenant is derived from the closed server-side mapping; broker peers and caller
tenant fields are refused. Shared loopback TLS composition uses this same builder.

The command-line path always supplies `db_probe.fixed_factory`, using the existing
`db.json` and `db-ca.pem` format and verified-TLS connection policy. There is no
plaintext/in-memory fallback, source credential, assertion signer or guard store.
The service owns factory closure and listener cleanup on partial start or stop.
Its diagnostic `READY` does not prove a successful DB lookup, distributed
membership consistency or all-eight bound readiness; no prefetch is introduced.

The disposable DB operator helper separately exposes `seed_source_profiles()`
for the six canonical source profiles across TPA001/TPA003. It adds rows in one
transaction with conflict-do-nothing semantics, preserving revocation/downgrade;
normal single-tenant fixture startup does not invoke it. The membership service
cannot execute this provisioning operation. Actual PostgreSQL/TLS/privilege
acceptance is still required; offline SQLite INSERT tests do not substitute.

These targets do not yet supply the broker's separate identity/membership access
edge or API-broker transport. Do not add broker to the six-worker point-lookup
allowlist, pass caller-chosen tenant settings or silently connect all roles to one
common network to bypass that remaining composition work.

**Subsequent broker-edge implementation (23 October):** membership's explicit
test command now requires a third top-level key, `broker`, containing exactly
`listen` (two distinct private IPv4 addresses at port 8443, ordered TPA001 then
TPA003) and `pin` (the broker certificate SHA-256 pin, distinct from worker pins).
These addresses cannot overlap the six worker addresses. Each broker endpoint
maps the single broker peer to one fixed server-side tenant; its request remains
only internal subject UUID plus fresh nonce. No broker is added to the worker
peer map. Both broker endpoints use the same restricted lookup/factory; neither
requires new SQL grants, schema/identity columns or broker-held DB credentials.
All eight membership endpoints bind before serving. Partial failure owns factory
and socket cleanup; READY remains diagnostic, not a readiness receipt.

Enumerate **two additional broker-membership links** outside the existing 14
worker links, one dedicated private network per endpoint. The future launcher
must validate the exact network/interface and mount inventory before startup;
loopback tests do not prove network isolation. The broker is trusted for both
tenants but cannot choose a tenant on the membership wire. Reversed endpoint
configuration causes client tenant validation to deny, not cross-tenant fallback.
No direct broker-validator or shared all-role network is added.

`broker_composition_fixture.py` has a closed synthetic-only principal registry:
verified local issuer + tenant UUID + fixture subject maps to internal user UUID.
Its two immutable trusted callbacks perform fresh remote membership lookups on
each canonical broker check, including after reader delivery. Registry entries
never supply active status or disclosure roles. Unknown principals do no lookup;
errors deny rather than becoming missing recommendations. Production issuer
provisioning and identity lifecycle remain unimplemented, not inferred from this
fixture. The normal authentication system and all default entry points are
unchanged. Membership's CLI refuses missing/null broker configuration; the Python
test helper retains its explicit worker-only option for earlier regression tests.

**Subsequent broker ingress/packaging implementation (23 October):** explicitly
select `apps/api/Dockerfile.broker-test`; normal API/worker/membership entry points
are unchanged. The Docker context and COPY set enumerate the canonical worker
modules plus API-side auth/config/models and the two broker modules. No normal
API startup, migrations, source fixture, Snowflake gateway or membership DB
adapter is copied. API dependencies are reused; this is not a claim that all DB
libraries have been removed. The broker receives no DB credential/mount. A
closed-source subprocess import check supplements static manifest checks;
an actual image build/run is still required.

`broker_composition_service.py` is copied only into this test image, alongside
the synthetic identity adapter and frozen health helper. `/run/ciq/config.json`
has exactly `listen` (private IPv4, port 8443), `controller_pin`, `readers` (four
fixed reader wire audiences mapped to `{address, pin}`), and `membership` (two
`{address, pin}` entries ordered TPA001 then TPA003). Addresses must be distinct;
reader pins must be distinct and cannot equal controller/membership pins. There
are no caller tenant, audience, validator, DB, issuer or key-path settings.

Required own material: `ca.pem`, `identity.pem`, `identity.key`, `signer.pem`
(disposable RSA assertion signer, at least 2048 bits), `local-auth.json` with
exactly one `secret` of at least 32 characters, and existing own v3 state at the
test helper's `/var/lib/ciq-replay` paths. No initializer, environment-selected
identity, JWKS fetch or credential fallback occurs. The launcher still must
generate only test material and validate permissions, exact mounts and networks.
The local HS256 verifier is a synthetic acceptance mechanism, not public OIDC.

Ingress is `POST /v1/broker-summary`, only from the pinned `controller` certificate
URI. Strict JSON contains only `token`, `request_id`, `nonce` (canonical UUID).
It invokes the canonical broker and returns only `{nonce, summary}`. Reuse the
canonical bounded framing/TLS checks, no-store responses and redacted denials;
no browser/public port, redirect, retry or operation selector is added. Clients
check returned nonce and request ID and validate the summary contract. Nonce
correlation is not session-token revocation, idempotency or a replay ledger.
Canonical broker/worker guard and fresh membership checks remain authoritative.

The external controller-broker link is **one additional separately enumerated
edge**, outside the 14 worker links and two broker-membership links. Controller
test material must not be mounted in the broker, workers or membership. This
does not authorize wiring the normal API or publishing a port; the acceptance
launcher still owes the exact isolated controller execution arrangement.

The shared fixture now owns nine real loopback TLS listeners (six workers, one
worker-membership endpoint, two broker-membership endpoints) under the same eight
logical roles. Closing the membership role closes all three membership sockets.
With the subsequent broker ingress it owns **ten** listeners and closing the
broker role closes its ingress socket as well. Separate-process readiness/
deadline supervision and actual restricted PostgreSQL composition remain pending. This supersedes
only the earlier broker membership edge gap, not the unimplemented API-broker
production transport or operational custody/provider/source activation blockers.

**Subsequent inactive owner-side launch preparation (23 October):**
`scripts/composition_inventory.py` generates only public descriptors and stopped
container command arguments; construction performs no file, Docker or secret I/O.
It requires the exact eight roles, fixed disposable generation, three distinct
image digests, nine distinct public TLS pins and eighteen UUID-owned network
records. Subnets must be disjoint RFC1918 IPv4 ranges, /16 through /29; the
provisioner must separately check collisions with existing Docker/host routes.
The gateway is explicitly reserved at subnet +1; edge endpoints use +2/+3.
Network allocation/discovery is not supplied by this module.

The eighteen edges are the existing fourteen worker links, two separate broker-
membership links, one membership-DB and one controller-broker link. Each service
receives only its exact attachments. Fifteen unique named test volumes comprise
eight read-only material mounts and seven writable authority state mounts.
Membership has no authority state. These disposable local volumes are not the
unapproved operational encrypted store. The auxiliary controller/DB are outside
the eight application roles and their full CIDs must be independently registered;
they are not adopted from network metadata or arbitrary matching labels.

`composition_launcher.py` lives only under API tests, excluded from all service
images and normal startup. The adapter takes an injected engine and mandatory
material-check callback. Image entrypoint/empty arguments are checked; observed
container entrypoint, command and environment must match that pinned image.
All three explicit service test entrypoints now use `CMD []`; default candidates
remain unchanged. Startup validates exact labels, network IDs/static IPs, local
volume names/labels/options, read-only mounts/root, UID/GID 10001, dropped caps,
no-new-privileges, no ports/host PID/IPC links/devices and fixed test limits.
Broker uses 192 MiB, other application roles 128 MiB; each has 0.5 CPU/32 PIDs.
These are fictional acceptance caps, not measured capacity or reviewed production
budgets. Docker inspect normalization/behavior still requires physical acceptance.

Service fingerprints bind those descriptors, own pin, subnet, artifact digest,
configuration and state/material names. They do **not** establish image provenance,
actual file contents/modes, secret custody or clock health. Material verification
is mandatory but remains an injected fake in current tests; a real bounded,
reviewed materializer/verification step is still missing. The adapter cannot
manufacture a readiness receipt from a socket, metadata or diagnostic READY.

Before create, reject any existing exact container name. Reserve the attempt
before issuing create, register returned full CIDs before fallible attach/inspect,
and reconcile unknown creation only by exact name/image/owner/current-attempt
labels. Never adopt or stop an unrelated/pre-existing container. Any failure
closes replacement launch. Stop verifies ownership and confirms zero PID/exited
state; unknown identity/termination retains ownership/fence. Cleanup preserves
containers and volumes, reporting stop confirmation only; final exact removal
and ambiguous-resource handling remain the outer owner's responsibility.

The 124 new tests use fake engine observations/callbacks and the existing model;
they prove no Docker process exit, socket closure or isolation. **No independent
actor/watchdog has been wired into this adapter.** Synchronous callbacks can still
block; no runtime caller may activate it until the bounded owned actor, independent
watchdog, exact material provisioning, all-eight readiness and physical cleanup
acceptance are composed. This preparation is part of the approved disposable
batch, not operational activation or permission to bypass host headroom.

**Subsequent bounded fake-engine actor checkpoint (23 October):**
`scripts/bounded_composition_actor.py` supplies an explicitly invoked, one-use
POSIX process boundary for trusted disposable test commands. Construction has
no I/O. It fixes the caller's monotonic elapsed deadline before launching a
separate watcher, passing only the command/deadline over private stdin. Empty
environments, closed descriptors, discarded stderr and bounded unique-key JSON
frames prevent accidental ambient credential/config use or uncontrolled output.
The watcher launches the actor in its owned group, bounds output/exit and reaps
its direct child, escalating TERM to KILL for a blocked actor. A printed valid
result without successful exit cannot authorize delivery. Trailing output,
non-finite JSON, bad exits, expired results and unknown termination deny.

The watcher stays alive after its report until its owner kills/reaps it; this
avoids an observed macOS group-only-exited-leader `EPERM` path. The owner also
bounds a stalled watcher, kills the exact owned group before reaping its leader,
and fences on kill/wait uncertainty. Default SIGCHLD disposition and exclusive
child reaping are required: do not embed this into an unrelated shared process
reaper. Closed test actors must not create new sessions/escape the owned group.
This is not arbitrary hostile descendant containment. The existing Linux
subreaper/stubborn-descendant acceptance remains separate, not rerun here.

These test budgets are explicit, at most ten seconds per command, with separate
bounded cleanup allowance; they do not change the 30-second assertion lifetime
or supply reviewed operational limits. Time uses same-host monotonic elapsed
samples, not a trusted health provider or independent rollback authority. Host
suspension pauses the watchdog as well. No external hard-bound/SLA is claimed.

`composition_actor_case.py` runs only five closed fake-engine modes: healthy,
partial start, blocked create, blocked stop and late result. It imports the same
inactive eight-role launcher/supervisor used in the preceding tests; it cannot
select a real Docker backend. Per-test create-exclusive marker files prove a
blocked callback/result stage was reached. `FakeCompositionAttempt` reserves
eight exact names in the caller before starting the actor and retains its test
slot/UNKNOWN reservations on denial. Successful fake metadata is validated
before releasing that test slot. All these helpers remain excluded from normal
startup and service images.

**No real Docker callback/daemon workload is contained by this checkpoint.**
Reaping an actor/watcher is not proof that a Docker-daemon-owned container exited.
The next physical composition still needs a retained, independently available
ownership journal before mutations, bounded real engine actors/reconciliation,
exact material provisioning/verification, all-eight canonical readiness and
confirmed container/socket/resource cleanup. The in-memory test reservation map
does not survive parent replacement or meet the operational generation fence.
No Docker socket, secret custody, live source flag or public endpoint is added.

**Subsequent local material checkpoint (23 October):**
`scripts/composition_material.py` is an inactive, explicit staging/archive helper,
not a normal entrypoint or Docker installer. The trusted test builder supplies
exact per-role bytes/configs and validates supplied disposable TLS identities
against inventory pins. Only broker gets assertion signing/local identity secret;
only membership gets fictional DB configuration/CA; only the matching validator
gets tenant source rows. The controller private key is absent from all eight.
The shared assertion public key belongs to all six workers, not membership.

Each expected inventory retains bounded hashes/sizes, not source bytes, and binds
the caller's role fingerprint. Provisioning creates a new mode-0700 directory
under an explicit current-owner mode-0700 parent, walking without symlinks.
Exclusive/no-follow file creation, mode-0400 final files and fsync precede a receipt
for the root device/inode. Partial failure remains private, unadopted and retained
for explicit test-owner cleanup; no retry/overwrite/auto-repair. Read-back bounds
each regular file, rejects aliases/symlinks/extra files, compares stable metadata
and expected hashes, and checks root identity again. Atime changes caused by reads
are permitted; modification/change timestamps and security attributes are not.
This is a snapshot check, not an exclusion lock against a hostile same-UID owner.

USTAR export contains only the verified in-memory snapshot, flat regular members
and one directory, UID/GID 10001, directory mode 0500/file mode 0400. It performs
no extraction or Docker calls, writes no archive/secret digest manifest to disk,
and hides fields from repr. The caller must treat archive bytes as secrets on a
private bounded channel. There is no zeroization or encrypted/operational custody.
No trusted content semantics are inferred by the generic helper.

Real temporary-file and generated-PKI tests prepare canonical broker/worker
handlers without requests, parse membership configuration without a DB factory,
and use this checker as the fake-engine launcher's material callback. No mounted
volume is attested. Physical installation/read-back of exact volume owner/mode/
contents, replay-state provisioning and restricted DB acceptance are still owed,
as are the independent ownership journal and bounded real Docker actors. These
helpers are excluded from normal/service images. The approved physical batch is
not complete, and operational/P3/public activation remains prohibited.

**Subsequent volume-helper implementation checkpoint (23 October):**
`scripts/composition_volume.py` consumes a bounded private frame containing the
trusted role/fingerprint/file inventory and, for installation only, its canonical
archive. No secret bytes/digests are emitted. `scripts/Dockerfile.material-test`
copies only this helper and the staging module; it has no dependencies/default
action and is not an application image or addition to the eight-role barrier.
Its CLI fixes `/material`, root installer and UID/GID-10001 read-back policy.

Before filesystem mutation, installation validates the complete flat archive
against expected sizes/hashes/owner/modes and canonical USTAR encoding; no tar
extract/extractall is used. An empty current-owner target is mandatory. Files
are exclusively created, fsynced and finalized mode 0400/owner; directory mode
0500/owner is finalized last. Partial failure retains state, no repair/retry/rm.
A separate read-only checker verifies regular files, hashes, owner/modes, no
aliases/extras, stable metadata and root identity. Neither operation discovers,
creates, mounts or attests the identity of a Docker volume itself.

The test-image installer is intended to need only CHOWN beyond dropped default
capabilities, with no network/other mounts. A new verifier should run UID 10001
without capabilities and with its exact material volume read-only. This minimal
capability/ownership transition is **not yet Linux/Docker-tested**. Both helpers
must be independently registered before create, engine-inspected for exact image/
volume/security settings, bounded by owned actors, and confirmed exited. A frame
or helper success cannot replace those checks, fresh read-back or readiness.
Unknown outcomes retain the outer ownership journal/fence; no retry/replacement.
No helper receives replay volumes, Docker socket, other role material or network.

Local tests use disposable host directories and the host UID/GID, not root
privilege changes. They cover all eight roles, malformed/aliased archives, changed
files and partial writes. CLI identity/path policy is mocked unit evidence only.
No image build, container, mounted volume or actual UID-10001 transition occurred.
The approved physical batch still awaits its ownership journal and bounded real
engine composition; operational/P3/public source activation stays blocked.

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

**Subsequent launcher/journal integration (23 October):** the inactive launcher
accepts an explicitly supplied fresh journal and reserves all eight exact
container names/fingerprints before engine I/O. Writer validation gates preflight
and create. Identity observation precedes attach/start; a returned create ID
alone is not attestation. Failed create reconciliation uses exact owner/attempt
labels and cannot adopt another resource. Failure/stop fences admission; only
independently confirmed stopped identity/PID/state permits a stopped record.
Partial cleanup keeps unattempted reservations UNKNOWN and reports incomplete.
Failed durable writes do not prevent exact known-container containment but cannot
claim durable cleanup. No resource removal, writer resumption or automatic repair.
Eighteen real-filesystem/FakeDocker cases exercise these lifecycle/write failures;
no daemon or mounted-volume evidence is claimed. No-journal callers remain
historical model-only fixtures. Bounded real engine transport/provisioning and
the approved physical eight-role acceptance are still pending headroom/work.

**Subsequent retained-journal checkpoint (23 October):**
`scripts/composition_journal.py` explicitly creates a private per-prefix directory
and exclusive mode-0600 append journal under a caller-supplied private parent.
Reservations must be durably returned before engine mutations. The record schema
contains only exact namespaced names, closed resource kinds/identities, public
configuration fingerprints and lifecycle observations. No engine output, errors,
tokens, keys or arbitrary configuration is persisted. Append checks existing
canonical bounded contents, metadata/identity and private modes; short writes
are completed and file fsync precedes success. Directory and parent fsync precede
initial creation success. Failure retains state and permanently denies that
writer; partial records are not silently truncated or repaired.

Independent read-only inspection is available after the writer releases its lock
or dies. UNKNOWN reservations remain unknown even after an actor is killed or
reports successful exit. Observation/fence/stop/removal transitions are checked,
but the trusted caller still owes actual engine identity/ownership, confirmed
exit and removal evidence. No journal-only cleanup, discovery/adoption, resumed
writer or automatic replacement is supplied. A journal lives outside disposable
actor/service mounts and must be retained until independent reconciliation.

Real host-file tests and actual process-death/watchdog tests exercise this API
with fake workloads only; it is **not yet wired to a real engine**. Advisory locks
and local fsync are not encryption, hostile same-UID protection, independent
generation authority, complete-rollback detection or externally durable custody.
The next physical batch still owes bounded real-engine callbacks, independently
verified helper/volume operations, seven retained states, restricted DB, all-eight
readiness/delivery and exact cleanup. Elevated Mac pressure still defers builds.


## Controller and DB preparation checkpoint — 24 October

`apps/api/tests/composition_controller.py` is explicitly inactive owner-side
composition plumbing. It requires the journaled launcher and explicit approval,
clock, limits and request-cancellation dependencies. Startup is one-use. Service
readiness is supplied by the caller and bound to exact runtime inspection; Docker
running state never manufactures a receipt. All-eight runtime checks precede
admission and completion. The API separates admission from result completion so
network work need not block controller transitions. Only a revalidated summary
matching the exact operation object/case may pass the supervisor delivery gate.
It does not yet implement the bounded request actor or independent watchdog.

Failure/stop closes delivery, invokes model cancellation and includes the
launcher's cleanup even when an allocation failed before returning a process
handle. Unknown request termination retains capacity; unlaunched journal slots
remain UNKNOWN. Stop success covers app/request containment only, never auxiliary
DB/controller exit, resource removal or permission to restart. Real loopback TLS
requests and real journals are tested against fake engine observations, fictional
clock/approval and explicit test receipts. Their outer fixture still owns real
listener closure; fake Docker exit cannot prove those listeners stopped.

`scripts/composition_database.py` prepares fresh disposable in-memory bundles.
Membership receives only matching db.json and its CA; DB-only material contains
the leaf key/certificate, admin password, exact membership-address HBA and single
bootstrap transaction with narrow grants and six synthetic memberships. The
existing frozen source-profile seed supplies the rows. No arbitrary SQL, ambient
credential, normal product DB connection, image build, file write or startup is
performed. The actual DB launcher must enforce TLS 1.3, private installation,
non-root ownership, pinned image, resource limits and independent exit/readiness.
No PostgreSQL TLS/grant acceptance is claimed by inspecting generated bytes.

The next physical runner still owes private DB material transport, bounded
auxiliary DB/controller lifecycle, independent readiness probes and watchdog,
request actors, full eight-service failure/recovery and exact cleanup. Elevated
Mac pressure continues to defer builds/runs; none of the operational health,
custody, source isolation or P2 exit gates is closed by this checkpoint.

### Journaled DB material helpers — 24 October

The inactive DB coordinator now reuses bounded engine commands and the shared
one-attempt helper lifecycle. It requires DB-specific staging bound to the
invocation/member-db topology, a separately observed exact DB material volume
and a fresh helper ledger. Both container intentions precede engine execution.
The installer is root with CHOWN only; the independent read-only probe is
UID/GID 10002 with no capabilities. Image, mount, labels, receipt and successful
exit must all match. Headroom and resource authority are rechecked before create.

Lost acknowledgements fence admission and retain UNKNOWN. Explicit containment
inspects only acknowledged exact CIDs and cannot turn an unattempted verifier
into success. No retries, name adoption, removal or database-readiness claims.
Fake daemon tests cover metadata corruption, ambiguous outcomes and wrong
volume/binding authority; the real bounded subprocess transport also runs the DB
contract against a fake CLI. No actual Docker or PostgreSQL execution occurred.

Validation: the root regression suite plus the final two constructor checks
pass (681 collected tests), as do 409 targeted API tests, repository lint and
changed-file formatting. No remote CI run is claimed. Next: allocate/journal the
DB-specific material/data resources, supply the pinned UID-10002 PostgreSQL
image and bounded launch/readiness probes, then physical unified lifecycle and
cleanup when host headroom permits. P2 and completion estimates are unchanged.

### Disposable DB volume installer and probe — 24 October

A separate inactive DB helper now converts verified host staging into bounded
private stdin, validates a canonical five-file archive before mutation, installs
only into an empty explicit directory and supports independent read-back.
The DB wire contract requires UID/GID 10002; the application contract remains
10001 and its parser rejects database frames. Traversal, links, changed bytes,
wrong archive ownership and trailing data deny before writes. Existing partial
state is retained without retry or adoption. CLI identity and target directory
are fixed; receipts contain no credentials or hashes.

The candidate helper image has an allowlisted three-file build context and no
credential generation dependency. It is not a PostgreSQL service image. The
future pinned PostgreSQL image must independently establish UID/GID 10002.
The owner still owes bounded journaled helper coordination, exact image/mount
inspection, independent probe exit, PostgreSQL startup/TLS/grants and the full
DB/controller/eight-service lifecycle. No image was built, no Docker was run,
and host filesystem tests do not prove Linux ownership or mounted acceptance.

Validation: 643 root tests and 409 targeted API tests pass, with repository
lint, changed-file formatting and whitespace checks. Nine new regressions cover
DB archive/install/read-back and CLI identity/receipt boundaries. No remote CI
run or physical Docker acceptance is claimed for this checkpoint.

### Private disposable DB staging — 24 October

The generated DB-only bundle can now be staged in a fresh owner-private host
folder, bound to an invocation fingerprint. The existing checked file path is
shared through explicit material-class contracts; application role allowlists
and archive ownership stay unchanged. Database staging requires exactly the
five server files, a private parent, exclusive creation and durable writes.
Verification checks original directory identity, exact names, ownership, modes,
single links, sizes and byte digests. Failed writes remain private and cannot
be silently retried or adopted. No secret bytes or hashes are logged.

The database contract refuses the application UID 10001 archive. This completes
host staging only: PostgreSQL image ownership, bounded volume installation,
DB/controller launch and readiness, request actors/watchdog and physical
all-eight lifecycle/removal remain pending. No Docker or source access occurred.

Validation: 634 root tests and 409 targeted API tests pass, including ten new
DB staging regressions; repository lint, changed-file formatting and whitespace
checks pass. Physical acceptance and remote CI are not claimed.

## Implementation anchors and change exclusions

**Route-collision checkpoint (23 October):** `composition_routes.py` supplies
the previously injected admission gate using bounded, empty-environment numeric
Mac `netstat` output and the explicit engine's read-only network inventory.
At most 128 distinct full IDs are registered into inspect-only slots; container
ID slots remain separate. Every network's IPv4 IPAM is considered, regardless
of label/namespace. Only built-in host/null drivers may have absent/empty IPAM;
bridge/other missing IPAM denies. CIDR overlap, malformed/oversized/duplicate
metadata, expired deadlines, host-route changes or network-set changes deny.
No subnet selection, allocation, retry or implicit default endpoint is added.
The eighteen proposed IPv4 networks must themselves be disjoint. The Mac's
default route is intentionally not treated as occupied address space.

The owner must pass the same overall deadline to collector and engine, and
include its two exact read-only command templates in the engine inventory.
Admission snapshots do not atomically reserve routes or exclude concurrent
same-ID IPAM changes; trusted host/daemon stability is still required. There is
no exemption for already allocated composition networks: this gate belongs
before fresh provisioning, not as an adoption/restart mechanism.

Fake metadata tests exercise collision/failure/journal integration. A real
bounded read-only scan passed against this Mac's four Docker networks; no
physical resources were allocated. A first denied scan exposed null IPAM on
Docker Desktop's host/none built-ins, now explicitly covered without allowing
missing bridge IPAM. Material helpers, Linux UID transitions, retained states,
DB/controller and eight-role physical lifecycle acceptance remain unverified.
Mac pressure remains 2; no heavy execution or normal runtime change occurred.

**Material-helper coordinator checkpoint (23 October):**

Subsequent host-only retained-state integration lives in
`apps/api/tests/composition_state_fixture.py`, not any service image/entrypoint.
It explicitly initializes all seven plan-named state directories using the
existing fictional frozen-time fixture; membership is excluded. The private root
must be empty, repeat/partial attempts are retained and cannot be overwritten.
Reload checks exact directory/file inventories, ownership/modes, regular
single-link files, unique directory identities, authority/generation bindings
and canonical SQLite inspection before health observations. Observations may
persist canonical high-water marks; there is no all-seven atomic transaction
or filesystem read-only claim. Neither reload nor failure invokes an initializer.
Tests compose real staged material and SQLite with launcher preflight/fake daemon
metadata, preserve spent replay across reload and deny damaged/mismatched state
before create/start. These are host directories, not mounted named-volume UID,
transport/read-back, bounded helper or physical readiness proofs. Fourteen new
cases pass; state-volume installation, DB/controller and all-eight-role physical
lifecycle remain pending at Mac pressure 2.

Subsequent explicit containment adds `Helpers.contain()`, callable only after an
attempt. It fences admission and uses the same bounded engine's inspect/stop
slots for acknowledged full CIDs only. Exact helper configuration is rechecked
before any stop and after it; fresh created/exited/PID-zero, non-dead,
non-restarting state is required. Stop command success alone is insufficient;
a lost acknowledgement can be resolved by fresh inspection. Nonzero exit is
acceptable for containment only, never for material verification. Both reserved
intentions must have fresh stopped proof and durable journal observations to
return true. Journal failure does not prevent bounded attempts on known helpers,
but the result remains false. One failed helper does not skip the other.
Lost create acknowledgements are not recovered by name, and there is no retry,
removal, automatic invocation, readiness receipt or resource-journal mutation.
Twenty offline fake-daemon cases cover these branches. Physical daemon exit,
mounted UID transitions and cleanup are still unproven at Mac pressure 2.

`scripts/composition_helpers.py` is explicit one-role test-owner plumbing, with
no command-line activation or default engine. It requires the public Inventory,
matching Staged role/fingerprint, pinned helper image ID, bounded engine and
headroom callback. The observed material volume must be PRESENT in the still-open,
unfenced resource journal. A separate fresh helper journal uses the same invocation
prefix under a different private parent; the resource writer is never modified.
Use a separate bounded Engine per role (two helper CIDs), not the application's
eight-CID registration set. The caller must supply the returned closed command
inventory when configuring that engine; no permissive fallback is introduced.

Both installer/verifier reservations precede engine calls. Exact-name collision
denies adoption. The helper image's entrypoint/default user/empty command/no
inherited volumes/health/ports/labels are checked; container environment must
match that inspected immutable image. Before private input, full CID, exact
name/image/labels/mount/user/capabilities/security, memory/CPU/PIDs/restart/IPC,
network-none/no-address, read-only root/no host binds and created/PID-zero state
are independently checked. Installer is root with CHOWN only, one writable named
material volume. Verifier is UID/GID10001 with no added capabilities and that
same volume read-only. No entrypoint override, tmpfs, other volume or network.
Headroom and volume metadata are checked again before each helper create.

Each start uses the bounded private input channel. Exact role/fingerprint/state
receipt AND a fresh matching exited/PID-zero/non-OOM/zero-exit inspect precede
the STOPPED journal observation. Success requires BOTH helpers; an installer
receipt cannot authorize application launch by itself. Failure fences admission
and retains intentions/observations. There is no name-based adoption, automatic
retry/removal, or inference that a timed-out CLI means the daemon helper stopped.
An ambiguous create may lack a CID; an ambiguous start may leave an active helper.
The physical runner still owes independent bounded reconciliation/containment
and cleanup of these exact helper resources. Current code returns failure and
requires owner review, not a false successful-cleanup receipt.

41 offline tests exercise all roles with real private staging/journals, bad
metadata/receipts/exits, post-install unsafe verifiers and renewed headroom;
two cases traverse real bounded actors with a fake CLI, retaining only public
fake-daemon metadata. No Docker helper image, mount, Linux UID transition,
seven-state initialization or full eight-role lifecycle is claimed. Memory
pressure 2 defers heavy acceptance; normal app startup and source flags stay off.

**Private helper-input transport checkpoint (23 October):** the existing bounded
actor accepts optional bytes, maximum 2 MiB, through anonymous pipes. A bounded
bytewise control header precedes an exact-size private body with required EOF;
the body is never JSON-encoded into control metadata. The trusted actor must
consume stdin before emitting output. Sending, reading, response and exit all
share the lease, with the existing whole-group cleanup/uncertainty fencing.
Default calls still receive DEVNULL. Invalid private input consumes/fences the
one-use attempt without process creation.

Engine private input requires a predeclared `start --attach --interactive` slot
and registered full CID; the fixed isolated wrapper forwards stdin only to that
explicit CLI invocation. It does not add exec/run or make helper registration an
ownership claim. The future coordinator must inspect helper image, mount and
security configuration before start, then independently confirm exact exit and
non-root mounted read-back. Blocking/partial CLI input cannot extend the actor
deadline; killing that process group does not prove the daemon stopped work.
No payload persistence, shell, argv/environment secret transport or normal
application activation was added. OS/Python may synthesize locale metadata in
an otherwise empty environment. Copies in process memory are not zeroized;
trusted-host assumptions remain. Synthetic process tests are not mounted-volume,
Linux chown, encrypted custody or eight-role acceptance. Mac pressure 2 defers
heavy execution; material verification and seven retained states remain next.

**Resource provisioning checkpoint (23 October):** explicit owner-side
`composition_resources.py` joins the existing inventory, engine and retained
journal. Constructor validates supplied public layout only; no default subnet,
images, trust or engine discovery. All eighteen network and fifteen volume
reservations precede engine I/O. Mandatory headroom/collision callbacks are
trusted injected dependencies and still require actual bounded collection in
the physical runner. Headroom is rechecked before every create; target-name
collisions deny before mutation. A trusted exclusive UUID namespace is required;
this is not an atomic-name or hostile same-UID race protection claim.

Inspection requires exact labels/name/driver/options, full network identity,
internal bridge/subnet/gateway and no endpoints. Unexpected attachability,
ingress or IPv6 denies. Volume creation never includes host driver options or
fallback storage. Journal observation follows independent inspection, not an
acknowledgement. Failure fences and reconciles only exact attempted names; unknown
is not absence and no retry/removal follows. The launcher accepts the same open
journal's complete expected resource observations, then appends container
intentions; it refuses partial/fenced/mismatched or previously attempted journals.
Actual metadata is still rechecked by launcher preflight. Tests use fake engine
observations with real disposable journals; the full Docker transport/mounted
helper/UID/state/DB/eight-role/cleanup composition remains unverified. No resources
were physically allocated by this checkpoint at elevated Mac pressure.

**Bounded CLI transport checkpoint (23 October):** `composition_engine.py` is
explicit owner-side plumbing, excluded from normal startup. An exact trusted
command inventory and explicit Unix endpoint/private empty Docker config prevent
accidental ambient context/credential selection. Each command has an independently
owned bounded actor; finite output, successful exit and the enclosing deadline
are required. Failure latches create/start/connect admission closed while bounded
inspection/stop can still contain the known attempt. Newly returned full CIDs
may populate only predeclared final-ID slots. This is not resource authorization;
the launcher's exact owner/image/attempt checks and journal remain authoritative.
The caller still owes an accurate inventory, cleanup reservation and independently
verified physical resources. It cannot use this transport for build/pull/exec/rm,
provisioning or generic command execution. No automatic retry or absent-resource
inference exists. Real subprocess tests use fake CLI metadata, not a Docker
daemon. No actual container exit/removal or mounted material is claimed. Physical
eight-role/helper acceptance remains deferred at Mac memory pressure 2.

**Disposable state-helper candidate (23 October):**
`apps/worker/tests/composition_state_volume.py` is an explicit test artifact,
not the normal worker entrypoint or an operational clock-health provider. A
4096-byte maximum stdin request names exactly one of seven authorities and the
fixed disposable generation. The initialize CLI requires UID/GID 0 and an empty
explicit `/var/lib/ciq-replay` directory. It invokes the existing frozen-time
initializer, retains partial files on error, and refuses reinitialization.
The separate verify CLI requires UID/GID 10001 and checks exact files, modes,
ownership, single links, sizes, authority/generation, canonical SQLite and signed
fictional health. It never initializes or repairs. Retained replay/high-water
changes are legitimate, so no original database-byte hash is used as authority.

The physical runner must supply an exclusive disposable named volume, bounded
stdin/process execution, inspected pinned image/container/mount identity and
independently confirmed exit. Initializer configuration must permit CHOWN only;
the capability-free non-root probe still needs a RW state mount because health
observation may persist high-water marks. No network, host mounts or material
secrets are needed by either helper. The candidate Dockerfile derives from an
explicit independently verified pinned broker-test image (the Dockerfile alone
does not enforce the caller's pin); its separate allowlisted build context adds
only this helper. Normal application packaging and activation remain unchanged.

Host tests use disposable directories and a no-op fixture chown: they do not
prove Linux UID semantics, mount behavior, image construction or process/daemon
containment. Receipts are diagnostic, not readiness. Lost outcomes still require
the future journaled coordinator to retain UNKNOWN and contain exact acknowledged
CIDs without retry/adoption. No such state-helper engine wiring, physical
eight-service lifecycle or cleanup acceptance is claimed here. Mac pressure 2
continues to defer heavy builds; no resources were allocated or Snowflake called.

**Journaled state-helper coordination (23 October):**
`scripts/composition_state_helpers.py` now reuses the material-helper engine,
inspection/journal and containment flow with a closed seven-role state contract.
The shared flow has explicit class-level mode/entrypoint/mount/receipt hooks;
no untrusted input selects a helper implementation. Material behavior remains
root install + independent RO non-root verification. State behavior is root
`initialize` + independent non-root `verify`, both mounting only the exact state
volume RW. Only the initializer gets CHOWN; no network, host bind, entrypoint
override, inherited volumes or other capabilities are admitted. State stdin
contains only version, role and fixed disposable generation, never a signer.

A new helper ledger and bounded engine per role remain mandatory. The matching
observed state-volume resource intention is checked before admission and again
before each create, together with actual volume metadata and headroom. Both
helper intentions precede engine work. Exact image entrypoint/configuration,
created-state inspection, role/generation receipt and independently inspected
successful exit are all necessary. The full invocation's exclusive empty state
volume is still a trusted caller precondition; a success receipt alone does not
prove it, and a new journal is not permission to reset/reuse existing state.

Lost acknowledgements or failed probes retain uncertainty and fence admission.
Explicit containment rechecks exact owned configuration/identity, attempts only
known full CIDs, and requires fresh stopped proof plus durable ledger results.
It never adopts by name, retries initialization, removes resources or certifies
readiness. An unknown/unattempted verifier remains UNKNOWN. Fake metadata and
real bounded CLI/actor regressions cover the shared flow, not actual mounts or
daemon exit. No helper image was built or started while Mac pressure stayed 2.
Full physical state initialization/read-back and the restricted DB/controller/
eight-role readiness, recovery and exact cleanup runner remain unverified.

Reuse `offline_supervisor.py`, v3 broker/guard/transport, restricted membership
factory, worker/membership packaging and existing container fixtures. The current
worker and membership `__main__.py` deliberately exit; do not remove that refusal
in an integration test target. Keep `compose.product.yml`, normal source flags,
API contracts and `http://localhost:3000` owner sandbox unchanged.

This document is the only new design artifact. No encrypted image, keys,
containers, volumes, account objects or daemon were created during its drafting.

### Explicit DB resource allocation — 24 October

`Resources(database=True)` now reserves all 35 intentions before discovery:
18 internal networks, 15 app volumes and separate DB material/data volumes.
The default remains the existing 33-object app inventory. DB names and exact
local-driver/label validation are shared with the material helper. Duplicate
inspection JSON keys, option/label/name/scope drift and unknown observations
fail closed. A lost create acknowledgement can be independently observed but
still fences the invocation; it never permits retry or further allocation.

An offline integration test now connects the real allocator journal and returned
network IDs to DB material helper installation/probing. This proves the authority
handoff with fake daemon metadata, not physical volume ownership or DB readiness.
The host recheck deferred Docker acceptance (pressure level 2, load 15.86).
No containers or host settings changed. Remaining sequence: UID/GID 10002 data
initialization, pinned PostgreSQL packaging, bounded startup and TLS/grant probes,
then full physical lifecycle/containment acceptance. P2 estimates stay unchanged.

Validation: the full root suite passed 699 cases before the final two lost-ack
cases were added; the complete 38-case resource file then passed, covering all
701 collected root cases across those runs. Ruff, formatting and whitespace
checks pass. The broad targeted API run passed 408/409: the existing blocked-stop
watchdog case lacked its callback marker. All six actor cases passed in an
isolated rerun (11.10 seconds), without changing deadlines or assertions. Host
load is a possible contributor, not a diagnosed cause; the initial failure is
retained here and no all-green broad API run is claimed.

### Empty DB data directory preparation — 24 October

Added a DB-only helper that exclusively creates `pgdata` inside the allocated
data volume, sets both directories to mode 0700 / UID:GID 10002:10002, and leaves
partial failures intact. A separate nonroot, read-only probe requires exactly
that empty directory and ownership/mode contract. Existing contents, symlinks,
wrong ownership/modes, duplicate request fields and wrong CLI identities deny.
This is empty-directory preparation, **not PostgreSQL initdb or readiness**.

The bounded coordinator requires the observed data-volume resource journal,
uses separate preparation/probe containers and exact image/mount inspection,
and retains the existing one-attempt fencing/containment behavior. An offline
allocator-to-helper test covers the actual resource journal handoff. The image
recipe is a candidate, not built or digest-pinned acceptance evidence.

Validation: full root suite 741 passed; after adding the data-volume handoff
case, all 79 data-helper/resource checks passed. Ruff and diff checks pass.
These are host filesystem and fake daemon checks, not mounted Linux proof.

Host recheck: pressure 2 and one-minute load 14.70; Docker acceptance still
DEFER. No containers/settings changed. Next: pinned PostgreSQL packaging,
nonroot cluster initialization, bounded startup, TLS/grant readiness and physical
lifecycle acceptance. Phase estimates unchanged.

### Nonroot PostgreSQL cluster initialization — 24 October

Added an explicit PostgreSQL 16 `initdb` helper using UID:GID 10002:10002,
verified DB-only material and the previously prepared empty data directory.
It durably writes an exclusive ATTEMPTED marker before spawning; any partial,
failed or interrupted attempt remains ineligible for retry/adoption. Fixed
arguments use a private password file, reject local/host authentication during
initialization, enable checksums and retain partial initdb files. The child has
a fixed environment, discarded diagnostics and a 30-second wait with owned
process-group termination on timeout; the outer owner still owes its watchdog.
[PostgreSQL 16 initdb option reference](https://www.postgresql.org/docs/16/app-initdb.html).

The separate probe checks the invocation marker, version, ownership/modes,
control-file shape, absence of a PID file and fresh material hashes. This is
**structural read-back only**, not catalog integrity, stopped-process proof,
schema/grant bootstrap or authenticated readiness. No PostgreSQL binary was run
in this checkpoint; command/process fixtures and temporary files are offline evidence.

The journaled coordinator now checks both exact volumes, mounts material
read-only in both containers, allows data writes only during initialization,
and runs both modes nonroot without added capabilities. Existing app/material/
state helper contracts retain their defaults. Unknown outcomes fence and remain
for explicit containment/review.

Validation: all 789 root tests passed; Ruff and diff checks passed. The earlier
allocation commit CI passed; the data-directory commit CI was still running
at this checkpoint.

Host gate remains DEFER (pressure 2, load 9.06); no Docker build/start or settings
change. Still owed: PostgreSQL image packaging/digest inspection, physical initdb,
closed schema/bootstrap, bounded service startup, TLS/grant probes and full
lifecycle acceptance. Product phase estimates are unchanged.
