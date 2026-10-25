# P2 integration on disposable Linux CI

25 October 2026. The owner requested an alternative to repeatedly deferred Mac
execution and explicitly requires approval before payment-related actions or
new spend. This supersedes the Mac-only execution choice in the
[earlier design](p2-mac-docker-integration-design.md); its isolation and lifecycle
requirements still apply. This is a test-host choice, not a deployment target.

## Why containers remain useful

The remaining composition checks need real Linux users, volume ownership,
network isolation, PostgreSQL binaries and independently stopped services.
Docker supplies a reproducible way to test these boundaries. Docker Desktop
on the owner's Mac was selected to avoid a host purchase; the Mac itself is
not a product requirement. Its repeated memory-pressure deferrals must not
block Linux image validation and disposable integration development.

## Execution choice and cost boundary

Use standard GitHub-hosted Ubuntu runners for synthetic, disposable acceptance.
The repository was verified PUBLIC on 25 October. GitHub documents
[free standard runner usage for public repositories](https://docs.github.com/en/actions/concepts/billing-and-usage).
Recheck that condition before expanding execution; do not switch to larger
runners, paid hosts, paid storage or a private-repository billing model without
owner approval. The new image smoke uses no artifact upload, registry push or
build cache export. No Snowflake secrets are passed to it.

The owner reports adding Snowflake payment information. Account reactivation,
current balance and existing resource usage have not been independently checked.
Adding payment details is not permission to spend. Ask before paid queries,
warehouse creation/resume, AI/serverless calls, purchases, billing changes or
other actions that can incur new charges. Prepare the intended operation,
cost estimate, duration and stop controls before requesting that approval.
Do not treat resource monitors as a universal spend cap: Snowflake documents
that [they cover warehouses, not serverless features or AI](https://docs.snowflake.com/en/user-guide/resource-monitors).

## Concrete sequence

1. Build the actual cluster/bootstrap image recipes on a fresh standard runner;
   inspect the image IDs and run the existing identity/binary checks with no
   network, a read-only root and restricted UID/capabilities/resources.
   `.github/workflows/disposable-database-images.yml` is an explicitly dispatched,
   15-minute image smoke. It uses a run-specific local tag for the wrapper build,
   verifies the base tag's ID before/after, and runs checks against exact IDs.
   It does not publish or establish a reusable trusted image digest.
2. Real disposable volume preparation, initdb and private-socket bootstrap now
   pass on Linux CI (see evidence below). Membership TLS, permission/connection
   denials and clean stop now also pass in the dedicated member-DB edge. Use generated test identities
   and fixed fictional source inputs only.
3. Wire and verify the complete owned service lifecycle: readiness barrier,
   tenant/role behavior, revocation, stop, uncertain completion and containment.
   An explicit Linux route collector now exists and is used by the member-DB
   edge. Linux resource/headroom collection and its full-allocator integration
   are still required. Do not bypass those gates or call
   the image smoke full composition acceptance.
4. Keep Mac-specific verification optional for a future Mac runtime target.
   Select any persistent operational/deployment host and key custody separately.
   GitHub's disposable runner is not an always-on product backend or approved
   home for real credentials, patient data or production authority state.

## Evidence and remaining gates

### Database resource journal to launcher handoff — 25 October

Integration review found the inactive canonical launcher expected only the
original 33 resources, so it rejected the allocator's new 35-resource database
batch. Explicit `database=True` now requires a complete observed journal for all
18 networks, 15 app volumes and both DB volumes. Missing/header-only authority,
the wrong selected batch and incomplete/fenced/mismatched journals are refused.
Both database volume names, ownership labels, local driver/scope and absence of
unapproved options are independently rechecked before application creation.
No-journal DB mode is refused; legacy model-only callers remain unchanged.

All 180 focused launcher/resource/controller/journal/engine tests pass locally,
including 11 added cases. Resource-journal handoff and missing/foreign/drifting
DB volume refusals use fake daemon metadata and real private journals. No Docker
command or real container lifecycle is proved by this adapter change. Database
bootstrap/readiness evidence remains separate, and Linux headroom/full-service
physical integration is still open. Repository Ruff and changed-file formatting
pass. Implementation 47341f6
[passed full product CI 40163767366](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40163767366),
including 1,469 backend and 26 browser tests. The revised owner-preview frontend
at 59f42d8 also passed its full workflow (40163582801). These do not replace the
still-required real 35-resource/eight-service Linux admission and lifecycle run.

The existing product workflow already runs the sandbox Docker stack, API/DB,
browser checks and disposable process containment on Linux. All three latest
checkpoints passed: [ea18e45](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40107078653),
[2e9db27](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40107013580)
and [170bdb4](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40106920950).
The separate PostgreSQL job includes 35 live catalog/membership privilege cases.
These do not yet prove the helper images or the full isolated topology.

The new [image smoke 40158980750](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40158980750)
passed at df213a7 on a standard Ubuntu 24.04 runner (27-second job). Both actual
cluster/bootstrap recipes built, image configuration checks passed, and both
exact image IDs passed the existing PostgreSQL 16 account/binary preflight
under the restricted runtime flags above. No local Docker build/start occurred.
This closes that CI image packaging/runtime smoke, not initialization or database
readiness. Images were not published; later runs must inspect their own IDs.
Membership TLS, integrated containment, governed live-source access, operational
custody and P2 exit remain distinct evidence gates. No phase completion estimate
or production activation changes with this test-host decision.

### Real helper lifecycle regression — 25 October

The manual workflow now also invokes three CI-only real-container cases using
the built image IDs. Each uses fresh labeled named volumes, material install and
independent read-back, empty data preparation/probe, real initdb/structural probe,
and private-socket bootstrap. The cases cover a valid bootstrap, SQL failure and
an effective privilege drift rejected by the catalog check. Fresh containers
must deny repeat initialization/bootstrap; read-only probes check retained
completion or ATTEMPTED markers and absence of a running postmaster PID file.
[Run 40159814345](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40159814345)
passed all three real-container cases at add3318 in a 59-second job. The first
attempt caught Docker's canonical CAP_CHOWN spelling; the shared helper
coordinator now accepts only the exact singleton CHOWN/CAP_CHOWN aliases.
Six offline regression cases accept either spelling and reject extra,
duplicate, lowercase or non-list capabilities. All 854 local root tests pass
(two CI-only modules skipped); repository Ruff checks pass.

The test harness inspects actual image/user/mount/network/capability/resource
configuration before starting and exact exit state afterward. Its inputs use
generated fictional material through stdin, with no host ports or network.
Teardown removes only acknowledged, labeled resources on the disposable runner,
including failed test data after retention checks. This is a CI test harness,
not the production composition journal, crash recovery owner or full allocator.
It does not test live TLS, network policy or the eight-service readiness barrier.
Follow-up 08c8caf redacts byte-frame repr in failed test arguments, selects short
pytest tracebacks and disables uv cache export. Its fresh
[run 40159947450](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40159947450)
also passed all three cases. Full product CI passed the initial lifecycle
checkpoint c1fead5 ([run 40159627351](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40159627351));
the broader run for 08c8caf subsequently passed (40159936102), as did
the documentation checkpoint 90a5873 (40160040974).


### Membership database TLS acceptance — 25 October

The same manual workflow now also builds the explicit `composition-db-test`
membership target, inspecting its exact image ID and nonroot identity. It is
absent from the default candidate/wheel. A fresh internal Docker bridge uses an explicit test
subnet/gateway. The existing collision gate now accepts an explicitly selected, bounded Linux
`ip -j -4 route show table all` collector, alongside two real Docker network
snapshots. Collision or incomplete/changing observation denies before creation.
The inspected subnet/ID replace only the member-DB edge in a validated test
inventory before generating credentials, HBA and PKI.
This is a dedicated CI harness; full allocator and Linux resource/headroom
acceptance remain open. Existing host networks/resources are never adopted.

After the actual helpers bootstrap fresh volumes, an inspected PG16 container
runs directly as UID 10002 with only that bridge, TLS 1.3, generated certificate/
key/HBA, no Unix socket or published ports, read-only root/material, and writable
owned data. Fresh UID 10001 clients receive only generated membership credentials
and CA certificates through bounded stdin; the DB private key/admin password/SQL
are not sent. CA files live in private client tmpfs; no secret-bearing request,
raw driver diagnostics, image, cache or artifact is published.

The real canonical factory/store must read all six seeded identities and return
absence for cross-tenant lookups. Nine real SQL operations must fail with 42501.
Raw-driver checks require the specific hostname, wrong CA, missing CA, password
and plaintext rejection reasons, while factory/store checks require redacted
denial without fallback. Ambient PG settings are rejected. A second client from
an unauthorized source IP must be rejected by the generated HBA. The server must
remain running throughout, then complete a bounded SIGINT fast shutdown with
exit 0; a separate read-only helper checks the retained bootstrap marker and
absence of postmaster.pid. PostgreSQL documents the chosen
[TLS configuration](https://www.postgresql.org/docs/16/runtime-config-connection.html)
and [SIGINT shutdown](https://www.postgresql.org/docs/16/server-shutdown.html).

Negative assertions now sit outside the factory's redacting context. Both
factory and raw-driver probes record whether a connection was entered and fail
if so, even when subsequent cleanup raises. Denied connection/store paths cannot
become absent membership. The same-subject/different-key CA fixture can produce
a low-level RSA verification error before the generic certificate error. The
wrong-CA driver test recognizes only an enumerated set of certificate/signature/
padding/modulus failures; unrelated errors and actual acceptance fail. This
matches [libpq's OpenSSL error reporting](https://github.com/postgres/postgres/blob/REL_17_STABLE/src/interfaces/libpq/fe-secure-openssl.c),
which uses the queued OpenSSL reason. Only fixed diagnostic categories are
printed, never raw driver text or request frames.

[Run 40161677145](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40161677145)
passed all four real-container cases at cda2b94 (46.06-second test phase,
83-second job). Earlier attempts caught the need for an explicit Docker subnet
and the overly narrow wrong-CA error expectation. The final raw-driver entry
check is at 4b385d0; its fresh
[run 40161796204](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40161796204)
also passed all four cases in 33.27 seconds. All 870 root tests pass (three CI-only modules skipped), plus all
72 offline membership tests, 58 route tests (16 new Linux cases included in
870), Ruff and isolated wheel checks. Full product CI passed fd67973, f0c552d
6bca3a3 and 0979456; the final implementation's broader run
[40161796216](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40161796216)
remains in progress at this documentation checkpoint.

The route collector uses a fixed bounded read-only `ip` command, empty child
environment and strict all-table JSON parsing. Mac remains the default collector;
Linux selection is explicit. This does not prove full Linux resource/headroom
admission, the complete allocator/journal's physical handoff, eight-service
readiness/revocation/containment, operational custody or P2 exit. Those remain
the next coherent integration work, followed by governed-source approval.
