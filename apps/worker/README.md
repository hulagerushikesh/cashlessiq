# Worker boundary

This is the inactive P2 synthetic read-only worker packaging candidate. It
packages canonical validation, TLS, signed health and retained v3 guard modules,
but excludes the broker, API, PostgreSQL and Snowflake dependencies. The broker
lives separately in `apps/api/src/ciq_api/worker_guard_broker.py`.

From the repository root:

```sh
make product-worker-package  # isolated wheel install/import boundary checks
make product-worker-guard    # disposable network-free Linux restart/latch probe
```

The default executable refuses activation. Only the explicit `guard-test` image
contains the fake-health test probe; the candidate contains no test entry points.
The probe does not install or query Chrony, prove actual synchronization/suspend
safety, mount real keys or start a source route. No website deployment is implied.

Asynchronous consumers, retries, outbox delivery and assessment jobs still belong
to later migration M4. Real host/provider/custody/readiness and service activation
remain separate P2 gates. See `docs/architecture/p2-worker-packaging.md`.
