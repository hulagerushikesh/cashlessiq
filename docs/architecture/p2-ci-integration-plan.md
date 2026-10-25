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
   pass on Linux CI (see evidence below). Next add the membership TLS connection,
   including permission and connection denials. Use generated test identities
   and fixed fictional source inputs only.
3. Wire and verify the complete owned service lifecycle: readiness barrier,
   tenant/role behavior, revocation, stop, uncertain completion and containment.
   The current Mac route/headroom collectors need explicit Linux equivalents
   before the full allocator can run there. Do not bypass those gates or call
   the image smoke full composition acceptance.
4. Keep Mac-specific verification optional for a future Mac runtime target.
   Select any persistent operational/deployment host and key custody separately.
   GitHub's disposable runner is not an always-on product backend or approved
   home for real credentials, patient data or production authority state.

## Evidence and remaining gates

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


### Membership database TLS acceptance prepared — 25 October

The same manual workflow now also builds the explicit `composition-db-test`
membership target, inspecting its exact image ID and nonroot identity. It is
absent from the default candidate/wheel. A fresh internal Docker bridge uses an explicit test subnet/gateway. The
existing collision gate now accepts an explicitly selected, bounded Linux
`ip -j -4 route show table all` collector, alongside two real Docker network
snapshots. Collision or incomplete/changing observation denies before creation.
The inspected subnet/ID replace only the member-DB edge in a validated test
inventory before generating credentials, HBA and PKI.
This is a dedicated CI harness, not full allocator or Linux resource/headroom acceptance. Existing host networks and resources are never adopted.

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

This also corrects an older test's assertion inside the factory's redacting
context: unexpected acceptance now raises outside that context. Seven offline
regressions ensure unexpected acceptance/unrelated driver errors and fallback
to absence cannot pass. All 62 offline membership tests and the isolated wheel
boundary pass; all 854 root tests pass with three CI-only modules skipped.
The first [live attempt 40160955766](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40160955766)
passed all three prior lifecycle cases but caught Docker requiring an explicit
subnet for fixed addresses. The corrected explicit subnet and real Linux
collision observation await a fresh run. Sixteen new route parser/collector
regressions pass (58 route checks total); Mac remains the default collector. Full topology, readiness/revocation/containment,
operational custody and P2 exit remain open.
