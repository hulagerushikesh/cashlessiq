# Product deployment: concrete remaining work

## Current target — on-demand GCP preparation, 29 October

The owner now plans at most four hours of active VM testing per working day,
with builds completed before startup and an immediate stop when finished. The
current [GCP plan](gcp-private-testing.md) uses a four-hour automatic STOP and no
automatic daily start. Billing linkage and provisioning still require approval.
Docker stays shut down during ordinary engineering; use offline checks and CI.
This supersedes the earlier eight-hour proposal below.

## Earlier local testing decision — 25 October

The current local Docker stack is sufficient for owner/engineering testing.
Its development web server was observed at about 2.4 GiB; the built preview
passed 37 HTTP checks under explicit limits and reported about 190 MiB combined
service usage afterward. This is a snapshot, not a peak-load guarantee.

The owner selected a dedicated GCP project. `cashlessiq-dev-rush` is created,
with billing disabled and the CLI default unchanged. The [GCP plan](gcp-private-testing.md)
prepares one e2-small/2 GiB VM, a 20 GiB standard disk and an initial eight-hour
STOP limit as a future option. The owner selected **keep local testing; GCP
preparation only** and did not approve the paid test. Billing linkage, remote
builds, registry storage and provisioning are not authorized. No paid deployment
has occurred.

## Earlier Mac preview preparation — 25 October

The owner clarified that the first online version is for personal testing before
a customer MVP. Use the [joint acceptance checklist](owner-preview-acceptance.md).
The existing synthetic local workspace is responding and the owner reports
having tested it and walked two friends through it. Rushikesh selected this Mac
first, without hosting spend. The [separate Mac preview package](mac-owner-preview.md)
prepares a production web server, owner-password gateway and private backend/DB.
The package at `536e1b5` passed [37 gateway HTTP checks and runtime verification](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40165607337)
and [full product regression](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40165607340).
Mac startup and an actual HTTPS tunnel still need resource admission, exact
origin/session configuration and remote access/rollback smoke checks. Fresh Mac
observations defer startup under pressure 2/high load/insufficient Docker headroom.
A checksum-verified native tunnel tool is prepared, without starting a tunnel. Synthetic
role selection alone cannot protect a remotely exposed app. Ask before new spend
or payment actions. No online deployment is claimed.

The governed-source/customer release bundles below remain separate work. They
are not prerequisites for a correctly isolated, synthetic owner preview. Customer
interviews, P3 writes and later migration phases do not block personal testing.

**23 October local-only milestone:** owner has no additional Linux host and
approved refreshing the existing Mac/Docker synthetic workspace. It is rebuilt,
healthy and regression-verified; [owner testing checklist](local-alpha-testing.md).
This does not require a Linux purchase, Snowflake access or public hosting. Keep
development authentication loopback-only. The three governed live/public release
bundles below remain open; local testing is not an assertion that they passed.
The owner now reports local manual checks working; implementation `c6a4b03` has
green remote CI. See the [delivery dashboard](delivery-status.md) for the concise
phase checklist and next operational decision. No deployment was performed.

Owner subsequently approved drafting the [Mac/Docker integration design](../architecture/p2-mac-docker-integration-design.md).
The owner then approved its bounded disposable service-composition implementation,
subject to a Mac load check. [The resource gate](mac-resource-check.md) currently
defers heavy execution under elevated memory pressure; the batch remains pending.
No encrypted storage, real credential custody, operational activation or public
release is authorized. The local sandbox was not stopped or changed.

22 October 2026. The hackathon website is not the authenticated product release.
The new local Next.js/FastAPI/PostgreSQL workspace exists, but its governed live
source route remains disabled. More passing security tests do not publish it.

## What can be used now

- Existing local authenticated synthetic workspace and offline fixtures.
- Existing public hackathon demo, unchanged by these backend increments.
- Bounded operator Snowflake evidence already captured and validated; not a
  replacement for runtime identities, governed views or production isolation.

## Remaining release sequence — finish in coherent bundles

| Bundle | Required result | Current blocker |
| --- | --- | --- |
| 1. Operational integration | Select actual host/store/unlock and health policy; implement reviewed materialization, lifecycle/readiness, durable external fence and termination/watchdog behavior; prove effects with disposable real processes | Offline supervisor model is implemented, but no real host/custody package is selected or approved |
| 2. Governed live source | Exact tenant views, six restricted runtime identities and key custody/rollback; negative base/foreign-tenant tests; approved financial/clinical projection | Provisioning and evidence-display approvals/acceptance remain open; human OAuth is not a runtime shortcut |
| 3. Release acceptance and hosting | Both tenants/three roles through authenticated API/UI; SAVED/MISSING/outage/revocation; browser/build/contracts and green CI; explicit hosting, identity, secret and rollback configuration, then deployment approval | Live path and release environment have not passed these checks |

This groups the existing P2 gates; it does not introduce P3–P6 work or another
open-ended series of primitive guard refinements. Freeze the implemented offline
primitives unless integration exposes a concrete defect. Public deployment comes
**after bundle 3 passes**, not after this fake-adapter model. There is no supported
calendar promise yet: real-host decisions and live-source prerequisites are open.
P3 reviewer writes, assessment jobs and ingestion are not required to call a
read-only synthetic P2 alpha complete, but real-customer use is out of scope.

## Trial expiry: preserve value, do not burn the balance

Latest owner screenshot: **$193 remaining, trial ends in 1 day**. This is not an
exact expiry timestamp or a current billing API measurement. The owner says today
is the final usable day; plan conservatively around that. This supervisor batch
uses no Snowflake or AI calls. A working product after expiry must not silently
require a purchase, extension or renewed trial.

Useful pre-expiry work is a bounded final account/object availability check and
verification of existing private recovery evidence. Do not provision hurried
runtime accounts, bypass governance, run bulk AI or keep compute running just to
consume credit. Existing synthetic fixtures/domain tests remain the no-purchase
development path; unavailable live source must fail closed, never become a fake
SAVED recommendation or a misleading MISSING state.

Optional owner/CoCo prompt for a final status check (not executed by this batch):

> Read-only, maximum five minutes and eight metadata statements. Report current
> account/trial expiry and remaining balance only if visible; otherwise say
> unknown. As the appropriate existing role, inspect CIQ_WH state and CIQ_RM
> attachment/quota/usage, and availability of CASHLESSIQ and its existing source
> objects. Do not select patient/clinical rows, resume compute, invoke AI, create
> identities, alter grants/settings or purchase anything. Stop at the limit;
> report visibility limitations and any query IDs returned. Do not infer missing
> objects from a restricted role's empty SHOW output.

An approved local fixture-only preview would be a different release scope from
the governed Snowflake-backed product. It must be labeled honestly and reviewed
for auth/hosting/secrets; it is not automatically authorized by this document.

## Next approval package — 23 October

The inactive supervisor commit `8b2ab24` passed remote product CI, run
`39785213296`. This confirms its regression workflow, not production readiness.
The next integration milestone requires **separate approval** because the prior
approval explicitly allowed fake processes only.

Recommended scope: implement and run a **test-only disposable Linux process
containment harness** using the existing local Docker installation. No purchased
host, actual service wiring or production secret-store selection is implied.

- Use generated dummy material and newly created, task-owned state only; no
  existing credentials, Snowflake profile, application database or host secrets.
- Exercise the existing supervisor against actual owned test processes, not the
  product services. Keep the harness outside normal API/worker entry points.
- Verify full readiness, partial-start cleanup, deliberately stuck children,
  bounded termination/escalation, closed delivery after stop/timeout and stale
  completion denial. Confirm process exit rather than accepting a fake boolean.
- Use a separate watchdog in the disposable Linux test environment; report its
  same-host pause limitation. Do not claim an external availability guarantee.
- Disable container networking; mount no Docker socket, repository root, home
  directory or existing application volumes. A host test runner may create and
  remove only its uniquely named test containers/volumes.
- Bound the acceptance run to 15 minutes; on failure stop the run and report any
  resources whose cleanup cannot be confirmed. Preserve diagnostic metadata only,
  never dummy private keys or process payloads in committed evidence.
- Finish as one coherent implementation/test/documentation batch; leave default
  activation refusal, public website and governed source routes unchanged.

This closes only disposable process-containment evidence if successful. Real
encrypted custody/unlock, health-provider policy, durable external generation
authority, source identities and deployment acceptance remain separate gates.
No Snowflake/AI calls, account changes, purchase or deployment are requested.
The prior screenshot is historical; current balance and exact expiry on
23 October are **unknown**, and no continued trial access is assumed.

### Package outcome — 23 October

Owner authorized proceeding. The five-scenario real-process harness now passes;
see [acceptance and limits](../architecture/p2-process-containment-acceptance.md).
It exercises the existing model with actual stubs and an independent watchdog,
not actual product-service wiring. The uniquely named test resources were removed.
Bundle 1 still requires actual custody/health/current-generation authority and
service integration; bundles 2 and 3 remain open. No deployment date is claimed.
