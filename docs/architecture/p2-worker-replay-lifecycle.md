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

Next: separately package the trusted membership service with a narrow DB access
policy and bounded disposable integration tests. No general operational DB
credentials in read/validator workers. Snowflake isolation/query/grant review,
governed evidence display and approved live acceptance remain P2 gates. No P3,
website deployment, real credential provisioning, push or Snowflake/AI spend.
