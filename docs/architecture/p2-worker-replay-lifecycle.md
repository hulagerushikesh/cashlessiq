# P2 retained replay lifecycle — container test

Date: 21 October 2026. Status: **offline candidate; no runtime activation**.
Parent: [private container mTLS](p2-worker-container-mtls.md).

## Reproduce

```sh
make product-worker-replay
# uv run --project apps/worker --frozen python scripts/test_worker_mtls.py --retained-replay
```

This explicit test extends the disposable four-container mTLS harness. It never
loads product secrets, changes Compose, reads Snowflake or starts normal services.
The default container smoke still uses process-local replay; the retained variant
injects the existing canonical `SqliteReplayLedger` into both worker authorities.
No production code or public API contract changes in this increment.

## Mount/provisioning boundary

Each authority has a separate invocation-owned **local Docker named volume**:
reader and validator do not share or mount one another's ledger. The broker and
membership service receive neither volume. All processes serving the **same
authority** must share its one retained file and capacity (1000 in this test).
Separate ledgers for replicas of one authority are unsupported, not a safe
scaling strategy. This is not a multi-host/network-filesystem design.

An explicit one-shot test initializer runs with no network, read-only root,
root UID and only CAP_CHOWN to provision the empty volume. It creates a new ledger
without replacing an existing file, sets file 0600/directory 0700, and gives UID/GID
10001 ownership. It receives **no keys, certificates, source fixture or DB secret**.
This is test provisioning, not a production init-container or secret-store choice.

Workers remain UID/GID 10001, cap-drop ALL, no-new-privileges and read-only root.
Their identity mounts remain read-only; only their own replay volume and ephemeral
`/tmp` are writable. Engine inspection checks exact volume names/destinations and
that broker/membership have no ledger volume. Listener startup requires the
existing file and expected ownership/modes. There is no automatic initialization,
replacement or fallback when replay state is missing. The default image still
refuses normal activation, and neither test harness is in that image.

## Acceptance evidence

The retained variant passes these checks over the actual private mTLS flow:

1. Consume one broker-signed parent and delegated child through a valid SAVED
   summary. Test copies of these capabilities stay only in mode-0600 files on
   temporary broker/reader tmpfs, never in logs, command arguments or the ledger.
2. Restart the **validator container** with the same identity/key/address/volume.
   The original child, forwarded by the reader certificate, remains denied.
3. Restart the **reader container** with its retained volume. The original parent
   remains denied through the broker connection. Both checks explicitly assert
   the token is still unexpired; expiry cannot masquerade as replay protection.
4. A fresh capability succeeds through both restarted workers: failed identity,
   unavailable membership or a broken listener cannot substitute for recovery.
5. Inspect each retained database internally: exactly namespace/nonce/expiry
   columns, SHA-256-shaped hashes and integer expiry, with no capability/raw source
   payload. Explicit reinitialization of the existing file is refused.
6. Remove only the reader's disposable test ledger. A newly issued capability is
   denied; the missing file is not recreated. A second listener startup attempt
   also refuses the missing file before binding. No reset/restoration is attempted
   under the still-valid test key; the test then destroys the entire environment.

The existing 11 replay tests additionally cover atomic multiprocess single-winner
consumption, shared capacity/expiry cleanup, namespace separation, lock/corruption/
missing/full failures, restart and expiry during consumption. They are separate
from the container smoke, which is single-tenant, nonclinical SAVED flow only.
342 API/PostgreSQL tests and 145 root tests pass; Ruff/format/whitespace checks
pass. Public API/startup unchanged; browser/build/remote CI not rerun.

All invocation-owned containers, networks, volumes (including test ledger state),
image tags, PKI and fixtures are removed afterward; build cache may remain. No
normal product volumes are touched. Abrupt interruption may need exact-prefix
cleanup. The local SQLite volume is retained **across tested container restarts**,
not retained after this test completes.

## Operational policy still required

This proves a same-host restart/mount candidate, not anti-tamper/anti-rollback or
production durability under host power loss. Docker/host and code able to modify
an authority's ledger remain trusted. Disk exhaustion, forced filesystem recovery,
volume backups/restores/deletion, multiple hosts and compromised volume owners
are not covered by this container smoke. No encrypted-volume/secret-store or
clock-synchronization policy has been approved or activated.

Do not restore an older snapshot or silently replace a lost ledger while its
signing credentials/capabilities remain valid. Lost or suspect state must fail
closed; a separately reviewed recovery procedure must address issuance shutdown,
in-flight work, capability lifetimes, trusted clock, key revocation/rotation and
recovery acceptance before any reset. Normal rotation/revocation/custody, capacity
monitoring, production request deadlines/backpressure and backup handling remain
open. SQLite initialization in this test is not authorization to implement those
account/runtime changes.

The separately packaged membership service and restricted DB/TLS fixture are now
implemented as inactive candidates. No general operational DB
credentials in read/validator workers. Snowflake isolation/query/grant review,
governed evidence display and approved live acceptance remain P2 gates. No P3,
website deployment, real credential provisioning, push or Snowflake/AI spend.

## Combined replay and DB TLS checkpoint — 21 October

Reproduce with `make product-worker-replay-tls`. This explicit mode composes
both retained authority volumes with the actual fixed membership connection
factory and a fifth disposable TLS PostgreSQL container. Existing individual
test modes remain available; normal startup and Compose are unchanged.

Restart replay rejection (while the original tokens are unexpired), fresh
success, ledger-content inspection and refusal to reinitialize run first.
The same restarted authorities then exercise certificate/CA/missing-CA and
plaintext rejection, ambient-setting denial, trust restoration, role disclosure,
user/tenant/membership deactivation and lost/restored column grants.
For the combined mode the DB outage is a pause/unpause of the same cluster,
not stop/reseed: stopping the tmpfs-only DB would destroy its source state.
After outage denial, verified TLS and a fresh delegated request must succeed
before deleting the reader's test ledger. Missing-state delivery and startup
must then deny without silently recreating storage. Keeping this destructive
step last prevents it from masking independent earlier denial checks.

Acceptance run `ciq-mtls-729cc45feccd` passed this sequence and removed its exact
owned containers/networks/volumes/image tags. The initial run
`ciq-mtls-58102b227a0c` correctly failed after the test attempted stop/start of
the tmpfs DB (its newly initialized cluster lacked the synthetic login); it also
cleaned up. The harness was corrected to pause/resume, not to reseed credentials
or weaken the fixed factory. Root **175**, factory **55** and API/PostgreSQL
**362** tests pass; repository Ruff, changed-file format and whitespace checks
pass. Browser/build/remote CI were not rerun.

This is composition/restart evidence only. It does **not** implement or prove
old-key rejection/new-generation recovery, trusted-clock discontinuity controls,
host-power-loss durability, production secret delivery, whole-request deadlines
or normal service activation. Those remain gates before live operation. No
real credentials, Snowflake reads/AI, deployment or public UI changes.

## Healthy signing-generation transition — 21 October

Reproduce with `make product-worker-generation-tls`. This opt-in test extends
the combined retained-replay/DB-TLS harness, not normal service startup:

1. Establish an old-key SAVED response and issue another parent/child pair that
   neither authority has consumed. Keep those tokens only in broker test tmpfs;
   the child passes through controller memory/stdin, not logs or command arguments.
2. Digest both healthy replay files. Stop both authority containers and verify
   they are not running before replacing the disposable broker signing key and
   both verification keys. No ledger initializer or replacement runs.
3. Restart the same authorities with the same volumes, fixed private addresses
   and unchanged mTLS identities. Verify both ledger digests are unchanged before
   issuing a fresh request; a new-generation SAVED response must succeed.
4. Reject the unused old parent over broker-to-reader mTLS and the unused old
   child independently over reader-to-validator mTLS. Each check asserts the
   token is still unexpired, so neither expiry nor prior consumption explains denial.
5. Continue the existing restart replay, ledger audit, DB-TLS/trust, revocation,
   paused-DB outage/resume and final missing-file denial sequence under the new key.

The first run (`ciq-mtls-58037c68792e`) failed the explicit address invariant:
Docker dynamically reassigned endpoints after both authorities stopped. Cleanup
succeeded. The harness now reserves the observed reader/validator private
addresses explicitly **before** certificates/listeners are created. It does not
weaken certificate identities, peer pins or endpoint checks to pass rotation.

Corrected run `ciq-mtls-63f0e1664f1a` passes the entire sequence and removes its
exact owned containers, networks, replay volumes and image tags. Root **175**,
API/PostgreSQL **380** and offline connection-factory **55** tests pass; repository
Ruff, changed-file formatting and whitespace checks pass. No browser/frontend-build or
remote CI acceptance is claimed; normal product containers remain untouched.

Scope remains one synthetic tenant, nonclinical processor and SAVED flow; the
separate 18 offline generation tests cover both tenants/all roles and lost/corrupt
state. This container sequence tests healthy signing-key replacement only, not
mTLS leaf rotation or container lost-state recovery. The test broker is idle
between explicit probe invocations; this is not an implemented issuance-disable,
drain/deadline, stale-replica inventory or operator recovery controller. No
clock discontinuity protection, production secret custody or runtime activation
is claimed. P2 remains open.

## Lost/corrupt state container recovery candidate — 21 October

Reproduce with `make product-worker-recovery-tls`. This separate opt-in mode
uses the same disposable mTLS/restricted DB-TLS topology and fixed private
addresses. No default executable, Compose file or runtime code is activated.

After an old-key SAVED response, retain an unused old parent/child pair. Delete
only the reader's original test ledger and corrupt only the validator's original
test ledger with fixed dummy bytes. Parent delivery denies because the reader
file is absent; independent reader-to-validator child delivery denies on corrupt
storage. Neither operation repairs the original state. These request denials do
not prove that the current startup preflight detects corrupt SQLite content;
that readiness gap remains open.

Stop both authorities and verify their containers are stopped before replacing
broker signing trust and both authority verification files. Start only idle
container PID 1 processes, verify both mounted public-key digests match the new
generation, and explicitly select the fixed NEW test filename `recovered.sqlite`.
Listener-start attempts refuse its absence in both authorities and create no file.
Only then does the harness invoke an explicit no-network/no-PKI/no-credential
initializer, as UID 10001 with all capabilities dropped. It verifies the existing
directory ownership/mode and refuses existing files; it does not chmod/chown the
old directory or replace old evidence.

Restarted listeners must return a new-key SAVED response before rejecting old
parent and child independently while unexpired. The child was attempted against
corrupt storage earlier, not successfully consumed; expiry and prior consumption
cannot substitute for new-signature rejection. New-key restart replay rejection,
ledger audit, DB trust/revocation/outage/resume and final missing-new-file denial
then run as before. Original reader absence and validator dummy bytes are checked
before initialization, after recovery and after the independent failure sequence.

Initial run `ciq-mtls-2fb0b8ce968b` failed at the permission boundary:
the reused root/CAP_CHOWN initializer could not chmod the already UID-10001-owned
directory. Exact cleanup succeeded. The recovery-specific initializer now runs
as the existing owner with **no added capability**, rather than gaining FOWNER,
DAC override or changing directory permissions.

Corrected recovery run `ciq-mtls-1b7aacf92461` passes the entire sequence, including
original-evidence checks after the final independent failures, and removes its
exact owned containers/networks/volumes/image tags. Root **175**, API/PostgreSQL
**380** and factory **55** tests pass, with repository Ruff/changed-file format/
whitespace checks. No browser/frontend-build or remote CI claim.
The healthy-transition mode was rerun as `ciq-mtls-5b57cc06bfec` after the shared
initializer refactor; its full sequence and exact cleanup also pass.

This is a prescribed test recovery sequence for one synthetic nonclinical SAVED
flow, not enforced operational recovery. The test controller controls issuance
and knows its complete two-authority inventory; no production issuance-stop,
stale-replica inventory, generation journal, clock health, shutdown deadline,
power-loss handling or secret-store mechanism is implemented. All old-state
evidence is disposable and removed with the test volumes after acceptance; this
is not an ordinary backup/restore path. Other roles/tenants and symmetric loss/
corruption combinations are covered only by the separate offline tests. No
normal/live route, real credentials, Snowflake/AI or deployment is authorized.
