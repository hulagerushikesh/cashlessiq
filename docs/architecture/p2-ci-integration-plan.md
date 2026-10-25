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
2. Extend Linux CI to the real disposable volume preparation, initdb, bootstrap
   and membership TLS connection, including permission and connection denials.
   Use generated test identities and fixed fictional source inputs only.
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

At this decision checkpoint the new image smoke has not yet run. Image smoke,
membership TLS, integrated containment, governed live-source access, operational
custody and P2 exit remain distinct evidence gates. No phase completion estimate
or production activation changes with this test-host decision.
