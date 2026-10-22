# Disposable Linux supervisor containment

23 October 2026. Owner authorized proceeding with the bounded disposable process
harness after the explicit approval request. This extends the fake-only milestone
to test processes, not actual product services, secrets, provisioning or deployment.

## Implemented and exercised

`make product-supervisor-containment` builds an explicit test image from a
temporary context containing only the Dockerfile, canonical offline supervisor
and test probe. No repository-root Docker context or runtime bind mount is used.
The Python base image/build cache may remain; the uniquely named test image and
container are removed. Base-image resolution may use the registry; there is no
package installation and the build's RUN network is disabled.

The container runs as UID/GID 10001, with network `none`, read-only root,
no mounts or published ports, all capabilities dropped, no-new-privileges,
128 MiB memory, one CPU and 64 PIDs maximum. Inspect checks precede startup.
No application DB, real credential, Snowflake profile, Docker socket, customer
data or existing authority state is mounted. No secrets are needed or generated.
The isolated interpreter explicitly imports only the copied model and standard
library. Product artifacts and their startup refusal are unchanged.

Five scenarios use actual Linux processes and CLOCK_BOOTTIME observations:

1. **Lifecycle:** eight actual service stubs acknowledge readiness before
   admission; duplicate completion denies. An expired operation's SIGTERM-ignoring
   job is killed/reaped with SIGKILL, and its late receipt cannot deliver. Stop
   cancels another real job, terminates the service stubs and rejects late work.
2. **Partial startup:** failure before the fourth launch fences the controller;
   all three returned process handles have confirmed exit. Admission stays shut.
3. **Readiness loss:** pending work and service stubs terminate; the model remains
   fenced and the outstanding receipt never delivers.
4. **Unknown termination:** an injected unconfirmed cancellation leaves the real
   job alive and the capacity slot retained. Admission/delivery deny. Subsequent
   confirmed cleanup kills/reaps that job but does not clear the sticky fence.
5. **Blocked callback:** a separate actor enters the actual supervisor's launch
   callback, allocates a same-process-group child and deliberately blocks before
   returning its handle. An independent watchdog process observes its test timeout,
   sends group SIGTERM then SIGKILL, and the test confirms actor and descendant
   exit. The test parent uses Linux child-subreaper behavior to reap the orphan.

Successful cleanup checks each known PID's `/proc` disappearance after reaping.
The host runner independently bounds the container wait to 120 seconds. Its
overall budget is 15 minutes, reserving the last minute for cleanup commands
(at most 10 seconds each). Only exact UUID-prefixed owned resources are removed;
no prune or shared volume mutation. Cleanup scope is printed before attempting
removal so uncertainty identifies the exact resources requiring review.

## Verification

- Five real Linux scenarios passed on the existing Docker Desktop Linux VM;
  runs `ciq-supervisor-aec149426a9a` and `ciq-supervisor-8a45fdee91ef`
  removed their test containers/images.
- Ten offline runner/package-boundary regressions cover success, build/create
  failure, hostile network/mount inspection, container timeout/nonzero exit,
  missing/duplicate reports and exact resource cleanup.
- Full backend/PostgreSQL: **1,003 passed**, one existing intentional invalid-model
  serializer warning. Root: **213 passed**. Ruff and whitespace checks pass.
- Product CI now includes the bounded disposable acceptance step. This batch's
  remote result is not yet claimed; `8b2ab24` was previously confirmed green.

## Explicit limits and remaining integration

This is **test containment evidence**, not an active supervisor or production
watchdog. Readiness is an owned-child marker, approval is disposable memory, and
delivery is an opaque in-memory receipt—not an HTTP response or source payload.
The watchdog has a fixed test timeout, not an implemented production heartbeat
policy. It and the controller share the host: host suspension/scheduling failures
can delay both. Observed kill/reap is not an external hard availability bound.

The blocked actor and its child intentionally remain in one known process group.
This does not prove containment of adversarial descendants escaping the group,
uninterruptible kernel tasks, PID-identity races in a long-lived service, real
listener closure, power-loss cleanup or full runtime cgroup ownership. Those
cannot be inferred from this short trusted-stub test.

No real host/store/unlock provider, plaintext custody, health-source policy,
durable external activation authority, six Snowflake identities or service
materialization is selected or accepted here. No v3 ledger is initialized or
repaired. The live route, public website and P3 remain unchanged. Continue through
the existing [three release bundles](../product/deployment-readiness.md), not
another sequence of unrelated offline primitives. Snowflake/AI spend: none.
