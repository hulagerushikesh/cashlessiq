# P2 runtime configuration and credential lifecycle review

21 October 2026. **Proposal, not activation or provisioning approval.**
Scope: the single-host synthetic P2 candidate. This consolidates the next gate
after [disposable DB TLS acceptance](p2-membership-db-tls.md); it does not select
a production secret-store product, supply credentials or change normal startup.

## Current evidence versus missing implementation

The private mTLS, restricted membership DB, verified DB TLS and retained replay
tests pass separately. A combined replay/DB-TLS test is now available as
`make product-worker-replay-tls` (acceptance evidence below). Test keys/passwords
are disposable; test bootstrap files are not a secret
delivery design. The membership entry point still refuses activation.

There is one assertion verification key per authority instance, immutable peer
pin maps and TLS contexts constructed explicitly. There is no key-ring discovery,
hot reload, certificate-revocation service, secret manager or operational recovery
controller. The proposal below deliberately uses stop-and-restart rotation, not
unimplemented overlapping-key or zero-downtime renewal claims.

## 1. Next offline implementation: fixed membership connection factory

Add an explicitly constructed factory inside the membership package, not API or
worker startup. Accept a typed, immutable, trusted configuration object. Do not
read an environment variable, connection URL, default password file, Snowflake
profile, service file or request-selected path/host/schema. Configuration and
credentials must have redacted representations; errors must not include them.

The proposed configuration has exactly these fields:

| Field | Validation / use |
| --- | --- |
| `host` | One ASCII DNS certificate identity, no comma, whitespace, URL or port; required |
| `hostaddr` | One canonical RFC1918 IPv4 address; same private-address rules as worker endpoints |
| `port` | Integer 1–65535, not boolean; one endpoint only |
| `database`, `username` | Nonempty bounded explicit identifiers; no connection-string parsing |
| `password` | Explicit nonempty secret value; never rendered in repr/logs/errors |
| `ca_file` | Explicit absolute CA file path from trusted injection; no default root search |

Schema remains separately validated by `RestrictedMembershipStore`, not a URL
query option. Unknown fields and arbitrary libpq/SQLAlchemy options are rejected.
The factory must always set `sslmode=verify-full`, TLS minimum 1.3,
`gssencmode=disable`, two-second connect timeout, `NullPool`, `echo=False` and
`hide_parameters=True`. Construct a SQLAlchemy `URL` object, never interpolate
secrets into a string. Every lookup makes a new connection. No TLS-off option,
connection pool, endpoint fallback, retries or implicit activation is allowed.

Inspect implementation/library precedence before claiming that ambient libpq
configuration cannot weaken explicit options. Test with hostile ambient settings
and a fake connector before real disposable-DB acceptance. Suppress lower-level
connection exceptions at the boundary; parameter hiding alone does not guarantee
that driver exceptions or a caller rendering an engine cannot reveal a secret.
Only the narrow store/factory interface should be exposed to handlers.

This step may use dummy credentials and temporary public CA files. It must not
load real secrets, connect on import/construction, change the test-only plaintext
factory or make the default executable run. Two-second connect timeout and SQL
timeouts are not a whole-operation deadline; server/deadline work remains open.

## 2. Secret ownership and delivery requirements

### Offline factory implementation checkpoint — 21 October

The fixed factory now exists in
`apps/membership/src/ciq_membership_runtime/connection.py`; normal startup does
not import or construct it. Strict frozen configuration, redacted representations,
URL-object construction, fixed verify-full/TLS-1.3 minimum/GSS-disabled options,
two-second connect timeout and NullPool are implemented. Connection, body and
disposal exceptions are converted to generic denial without displayed chaining.
The engine is private by interface convention, not a sandbox against trusted
Python code inspecting attributes or exception context.

Ambient `PG*` environment variables are **rejected before connecting**, including
otherwise harmless ones; they are not consumed as configuration or temporarily
removed. This avoids claiming that explicit options override every libpq service
file/default. The dedicated process must keep its environment immutable: the
check is not a defence against trusted code mutating it concurrently. Explicit
`/dev/null` password-file path and `sslcertmode=disable` prevent default password
file fallback and sending a client certificate for this password-only Linux
candidate. An empty search path is explicitly requested. CA path validation is syntactic,
not file ownership, symlink, existence or certificate-readiness verification.

This choice follows libpq's documented environment/default behaviour and its
requirement to disable GSS encryption to force TLS:
[PostgreSQL connection parameters](https://www.postgresql.org/docs/17/libpq-connect.html).
Fifty-five offline tests pass, including actual SQLAlchemy dialect parameter
assembly with a fake psycopg connector that stops before any libpq I/O. This is
not an actual TLS handshake, certificate-file check, runtime principal acceptance
or whole-operation deadline. Subsequent
[disposable DB/TLS acceptance](p2-membership-db-tls.md) now passes with this
factory inside the running test membership service, including failed trust,
restored trust, disclosure/deactivation/grant changes and DB outage. The old
test-only factory is unchanged for diagnostics/legacy plaintext tests. Combined
retained replay/TLS composition is recorded in the replay lifecycle document;
actual custody, key-generation recovery, durable clock
controls and normal service wiring remain open. No real credentials, source
access, deployment or activation.

| Material | Only permitted runtime recipient |
| --- | --- |
| Broker capability signing private key | Broker |
| Broker verification public key | Exact reader/validator authorities |
| Per-process mTLS private key and leaf certificate | Matching service only; never shared between services |
| Public peer CA/pins/URI/endpoint/tenant manifest | Matching service's reviewed configuration |
| Membership restricted DB password and public DB CA | Membership service only |
| PostgreSQL server leaf private key | DB service only |
| Six separate Snowflake service private keys, if later approved | Matching four readers/two validators only |
| Per-authority retained replay file | Its reader or validator authority only |

The broker's existing application DB access is separate from the membership
credential. No table above authorizes provisioning a Snowflake user or opening
network egress. CA signing private keys are non-runtime material and never enter
an application container. No shared operator OAuth, API DB-owner credential,
repository bind mount, Docker socket or key embedded in an image/environment.

Before real delivery, review one exact encrypted-at-rest store, operator unlock
mechanism, host/Docker trust boundary and per-service file materialization method.
Specify cleanup after crash/power loss and whether plaintext reaches host disk,
swap or backups. Do not call a macOS directory or Docker volume RAM-only without
evidence. No paid service or new tool is selected by this proposal.

Required runtime delivery contract: UID/GID 10001 for application services,
non-root/read-only root, private-key/credential files 0400 owned by that UID,
parent directory 0700 and read-only mount. Public CA/cert files may be 0444.
The DB server's own UID/key permissions follow its separate reviewed image.
Exact mount inventory excludes other services' material. A separate operator
step may populate delivery mounts; the application must not decrypt, initialize,
fetch or silently repair them. Missing, wrong-owner, writable, unexpected or
expired material blocks readiness before binding. File/symlink and TOCTOU policy
must be implemented/tested rather than inferred from mode checks alone.

## 3. Planned rotation: maintenance window, no overlapping keys

1. Disable the new source route and stop broker capability issuance. Confirm no
   new external requests enter this path; do not rely only on hiding a UI button.
2. Stop all affected readers/validators/membership listeners and terminate their
   connections. Bound/drain in-flight work using the future deadline mechanism;
   if that cannot be demonstrated, keep routing disabled and processes stopped.
3. Operator prepares a separately approved generation of keys/certificates and
   matching explicit trust/pin manifests. New private keys remain service-local;
   public verification material matches the broker generation. Do not hot-edit
   mounted secrets in running services or accept both generations implicitly.
4. Preserve healthy replay files. Restart with the exact reviewed generation;
   verify current identity/expiry/trust, fresh membership and readiness before
   permitting issuance. Prove an old token/leaf is denied and a fresh legitimate
   request succeeds. A failed acceptance leaves routing disabled.

DB password rotation likewise closes membership connections/processes and uses
an independently approved DB change. CA changes replace both explicit trust and
matching leaves/pins while services are stopped. Static leaf pins are allowlists,
not CRL/OCSP enforcement. Expiry blocks connections; it does not renew a leaf.
Choose actual lifetimes/renewal lead time in the provisioning package, not the
one-hour values in disposable tests. No unattended renewal is approved here.

Rollback may restore an earlier **non-secret application artifact** only if it
preserves current trust/configuration, fail-closed checks and replay state.
Never roll back credentials, trust manifests or replay files to make a failed
deployment pass. Suspect old keys stay revoked/untrusted.

## 4. Replay custody, loss and recovery

One retained local file per authority, shared by all its same-host processes;
separate authorities have separate files. No network filesystem, cross-host
replication, separate per-replica ledgers or active-token eviction. Keep directory
0700/file0600 owned by UID10001. Capacity remains explicitly fixed at 1000 for the
candidate; exhaustion denies and requires capacity/load review, not a reset.
There must be no ordinary backup/restore path for an active replay ledger.

Loss, corruption, suspected rollback or uncertain clock history:

1. Disable source routing and broker issuance. Stop all authorities and their
   connections. Preserve suspect state for restricted incident review; do not
   recreate it during restart, switch to memory or treat failures as MISSING.
2. Require a new broker signing key and replace the verification key on **every**
   affected authority before a new empty ledger can be considered. Old signatures
   must be rejected cryptographically, not merely by waiting 30 seconds. If key
   compromise is possible, also retire affected mTLS/DB/Snowflake credentials
   under their separate approved revocation packages.
3. Explicit separately authorized offline initialization may create new files
   only after the old generation is no longer accepted anywhere. No file may be
   overwritten implicitly. Record generation/custody evidence outside the ledger
   without recording capabilities, credentials or clinical payloads.
4. Test old signed parent/child denial, fresh request success, restart replay
   rejection and missing-file startup refusal before re-enabling routing.

Trusted host time is still a prerequisite. A forward clock jump could prune
nonces; moving backward afterward could otherwise make old tokens valid again.
The current ledger has no durable clock high-water protection. Proposed readiness
must check trusted clock health, and any uncertain clock discontinuity takes this
path out of service until reviewed recovery. An operator checklist alone is not
implemented automatic clock protection. No activation until that control is
defined, implemented and negatively tested. Host/Docker administrators remain
trusted; this is not tamper-proof storage.

The subsequent [clock-safety design](p2-clock-safety.md) reproduces the current
forward-prune/backward gap and specifies a proposed durable guard, transaction
semantics, host-health boundary and acceptance sequence. It is not implemented;
host-health integration and operational thresholds remain unselected.

## 5. Bounded acceptance order

1. Offline fixed factory: strict configuration, hostile ambient settings,
   redaction, no-I/O construction, fixed TLS/options and artifact exclusions.
2. Reuse the disposable restricted DB/TLS fixture with that factory; reject bad
   hostname/CA/plaintext and preserve fresh revocation/outage denial. No real DB.
3. Compose retained replay with DB TLS in one disposable mTLS test. Include old
   key rejection/new key acceptance and explicit lost-state refusal/recovery;
   test clock discontinuity controls once designed. Never reset under old trust.
4. Review exact secret-store/delivery, readiness/deadline/shutdown, generation
   inventory and provisioning/rollback package. Obtain separate owner approval
   before any real secret, principal, grant, live connection or service wiring.
5. Continue Snowflake isolation, governed evidence and two-tenant/all-role local
   live API/UI acceptance before the P2 exit review. No website deployment/P3.

This document closes the **written review proposal**, not the implementation or
production security gate. No new source reads, AI, spend, persistent credentials,
normal service startup, public contract change, push or deployment are required.

## Offline signing-generation recovery acceptance — 21 October

`apps/api/tests/test_worker_generation_recovery.py` adds 18 acceptance cases:
two synthetic tenants, three reviewer roles and healthy/missing/corrupt ledgers.
The real signing/verification and retained SQLite authorities are exercised;
membership, source input and peer identity are offline fixtures. Time is fixed
at 1000, with old and new tokens unexpired. No private key is persisted.

Each case consumes a valid old-generation request, then discards the old test
authority instances. Healthy rotation preserves existing ledger files. Lost or
corrupt state denies unused old capabilities without recreating or modifying
the damaged files. Replacement authority instances receive only a new public
key; fresh-generation requests still deny while replacement ledgers are absent.
Only the explicit test initializer creates NEW files, never overwrites evidence.
Afterward, unused old parent and child capabilities deny independently before
source reads, while fresh new-generation requests return truthful SAVED/MISSING.
Reconstructed authorities with the same new key/files reject consumed tokens
and still reject the old signatures; another fresh request succeeds.

This proves the cryptographic/ledger primitives under an explicit offline
sequence, **not an enforced operational recovery mechanism**. Discarding Python
objects models stopping workers; it does not prove shutdown, no stale replica,
atomic generation inventory, issuance disablement, transport certificate
rotation, or live mount replacement. That offline test itself is not composed
with container TLS; the separate healthy-transition test is described below.
Trusted fixed time cannot prove clock health or rollback
protection. Host-file tampering, production secret custody and the actual
recovery controller remain unresolved; normal startup stays disabled.

The subsequent container checkpoints cover healthy old/new signing transitions
and an explicit lost/corrupt-state recovery candidate; see
[container evidence and limits](p2-worker-replay-lifecycle.md).
Those tests do not implement an operational recovery controller. Enforced
issuance/shutdown/generation inventory and a reviewed durable clock-discontinuity
design remain gates. No source/AI calls, deployment or P3.

The subsequently approved [offline clock candidate](p2-clock-safety.md#offline-implementation-checkpoint--21-october)
now provides durable observations/latches and serialized replay, with signed
broker/reader/validator tests across both tenants/all roles. It is explicitly
injected in tests only. Actual host health/thresholds, worker artifact/container
clock-domain composition, custody/readiness and service activation remain open;
neither the old ledger nor normal startup was silently switched to this candidate.

Subsequent [clock-domain/artifact acceptance](p2-clock-safety.md#disposable-linux-clock-domainartifact-checkpoint--21-october)
packages the canonical guard without activating it. Two network-free disposable
containers retain replay/latch state across restart and share a Linux boot/
monotonic domain. The probe fabricates health; it does not close actual health,
suspend, deployment-host, signed/mTLS composition or readiness/custody gates.

The next [opt-in clock readiness](p2-clock-safety.md#opt-in-pre-bind-clock-readiness--21-october)
candidate calls the explicit guard before summary-listener socket construction.
Eighteen tests prove unsafe retained state/health never reaches socket bind;
healthy loopback binding is checked without source work. Default constructors,
normal startup and membership lookup behavior are unchanged. Actual credential
custody/readiness, signed/private clock composition and multi-listener rollback
remain separate. The [health review](p2-clock-health-review.md) documents why the
current monotonic/boot probe is not suspend detection or synchronization proof.

The next [signed two-hop loopback checkpoint](p2-clock-safety.md#signed-two-hop-loopback-mtls-composition--21-october)
composes guarded broker/reader/validator time and replay with the clock-checked
listeners over both actual TLS hops. Both tenants/all roles are covered by 42
cases. Health, application identity/membership and source inputs remain fake;
the real provider/suspend, private container wiring, custody and controllers
are not closed by this test composition.
