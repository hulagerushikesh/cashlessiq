# Two-person testing: existing Docker and a small GCP preview

25 October 2026. The current target is private testing by Rushikesh and the
engineering agent, before an MVP. Customer scale, marketing, SEO and delivery
planning remain later work; none requires a large server today. Capacity should
grow when measured use requires it.

## Local Docker is sufficient for the current application testing

The existing app responds with login HTTP 200 and API readiness `ready`. The
owner has tested it and explained its state to two friends. Engineering's local
26-browser-check run and remote regression evidence are recorded separately.
Two testers do not need a second complete local stack.

Read-only observations on this Mac found the development web container using
about **2.4 GiB**, API **82 MiB**, PostgreSQL **38 MiB** and Redis **10 MiB**.
The web container runs `next dev`, including the development compiler. Those
observations are a snapshot, not a load test or a production memory minimum.
The earlier requirement for 2 GiB spare Docker memory is conservative admission
for an additional workload; it is not CashlessIQ's minimum server specification.

Use the single existing stack for day-to-day development. A built web server
is the next resource improvement; adding another local database/app copy is
unnecessary. Docker is a development/deployment tool, not something required
on each tester's device. Localhost access remains tied to this Mac; a hosted
preview provides independent browser access from other devices.

## Dedicated GCP target prepared, without billing

At the owner's request, project `cashlessiq-dev-rush` was created with display
name **CashlessIQ Private Test**. A subsequent read confirmed
`billingEnabled=false`. The CLI default remains the existing Atlas RAG project;
every CashlessIQ cloud operation must specify its own project explicitly.
No VM, Cloud SQL instance, image repository, remote build or paid API workload
has been provisioned. Linking billing and incurring charges require approval.

The reviewable resource specification is
[`deploy/gcp-preview/plan.json`](../../deploy/gcp-preview/plan.json).
The proposed first deployment is one **e2-small, 2 GiB shared-core VM**, a 20 GiB
standard disk and one instance of the current fictional-data stack. A custom
network permits SSH only through Google's IAP source range; app/API/database
ports stay private. Browser access uses an outbound HTTPS tunnel terminating
at the owner-password gateway. No domain purchase is required for testing.

`compose.preview-small.yml` caps web at 512 MiB, API at 256 MiB, database at
256 MiB and gateway at 128 MiB: **1,152 MiB combined steady container ceilings**.
The one-time migration has a separate 256 MiB ceiling and completes before API
and web startup. This leaves room in a 2 GiB VM for the OS and Docker, but is not
a guarantee of whole-VM behavior or sustained traffic capacity. [CI 40180267477](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40180267477)
passed all 37 HTTP checks under these limits at `f28cb66`. Its final snapshot
reported web **74.13 MiB**, API **73.82 MiB**, database **30.03 MiB** and gateway
**11.53 MiB**, approximately **190 MiB combined**. This is a runtime snapshot
after the checks, not a peak measurement or a whole-VM capacity guarantee.
[Full product CI 40180267473](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40180267473)
also passed all regression stages.

Cloud Run can scale HTTP services to zero, but the current API requires
PostgreSQL-backed membership. Its instance filesystem is ephemeral. Moving
this exact app there introduces a durable database choice and service wiring;
creating a managed database merely for these two testers is unnecessary now.
One small VM reuses the tested stack with fewer application changes. Cloud Run
can be revisited when the application or operating needs change.

## Cost proposal for approval, not a free-tier promise

Using 730 running hours/month and published US on-demand rates, without assuming
any account credits or shared free allowances:

| Item | Proposed size | Approximate USD/month |
| --- | --- | ---: |
| VM | e2-small, 2 GiB | 12.23 |
| Standard boot disk | 20 GiB | 0.80 |
| In-use ephemeral external IPv4 | One | 3.65 |
| Base total | Before variable usage and tax | **16.68** |

Proposed operating budget: **US$20/month before tax**, including small build,
image-storage and traffic usage. This is a planning budget, not a hard billing
cap. Costs must be reviewed before repeat builds or an increase in use. Free
credits/allowances, if available, reduce actual charges; the other projects may
already use shared allowances. No remaining credit balance has been verified.

Build images away from the small runtime machine. The manual Cloud Build file
has a 15-minute deadline; at the listed default-pool e2-standard-2 rate of
$0.006/minute this is up to about $0.09 compute per submission before credits,
plus source storage, logging and any network charges. Artifact Registry gives
0.5 GiB free per billing account, then charges for storage; it is not a separate
free allowance for this new project. Keep a small set of accepted revisions.
Budget alerts warn about costs; they do not stop billing automatically.

For the initial remote acceptance, the proposed VM has an **eight-hour maximum
run duration with automatic STOP**. Eight hours of VM and IPv4 usage is about
**$0.18**, plus the bounded build and retained storage. Restarting the VM begins
another runtime period; it is not an unlimited free test. The initial duration
limit is explicit in the reviewed plan and needs no paid scheduler. If an
always-on preview is later wanted, review the monthly estimate before removing
that limit.

Stopping the VM ends its compute usage and releases its ephemeral address;
retained disks still incur storage charges. Stop it between testing periods
when convenient. The app remains unavailable while stopped. This is a private
test environment with no uptime promise.

## Deployment sequence after financial approval

1. Link the approved billing account to this dedicated project, enable only the
   needed Compute/Build/Registry/IAP services and set the reviewed cost alerts.
2. Create a regional image repository and narrowly scoped build/runtime service
   identities. Runtime needs registry read access, not project-wide Editor.
3. Submit the manual `cloudbuild.yml` with the tested Git revision. The source
   ignore file and Docker ignore file exclude local credentials, output and
   the owner's untracked submission video. Never build images on the test VM.
4. Create only the reviewed network, IAP SSH firewall, 20 GiB disk and e2-small
   VM with the reviewed eight-hour STOP limit. Install Docker and pull the exact
   accepted web/API image digests.
5. Prepare independent preview secrets on that VM. Set
   `CIQ_PREVIEW_API_IMAGE` and `CIQ_PREVIEW_WEB_IMAGE` to those exact digests in
   its private preview environment. Start with the three Compose files and
   `up --no-build --pull always --detach --wait`. The GCP overlay selects the
   prebuilt images; it does not change the current local app.
6. Verify local password denial first, start the HTTPS tunnel to gateway port
   3080, configure its exact origin, then verify remote anonymous denial,
   three synthetic roles, secure cookies, sign-out, runtime memory and stopping
   remote access. This is a targeted delivery check; it does not repeat the
   already completed general owner walkthrough.

No commands in this document have provisioned a paid deployment. The resource
plan and build configuration are preparation for that approval.

References checked on 25 October: [E2 machine sizes](https://docs.cloud.google.com/compute/docs/general-purpose-machines),
[VM pricing](https://cloud.google.com/products/compute/pricing/general-purpose),
[disk pricing](https://cloud.google.com/compute/disks-image-pricing),
[IPv4 pricing](https://cloud.google.com/vpc/network-pricing#ipaddress),
[Cloud Build pricing](https://cloud.google.com/build/pricing),
[Artifact Registry pricing](https://cloud.google.com/artifact-registry/pricing),
[Cloud Run runtime contract](https://docs.cloud.google.com/run/docs/container-contract)
[VM runtime limits](https://docs.cloud.google.com/compute/docs/instances/limit-vm-runtime)
and [stopped-VM charges](https://docs.cloud.google.com/compute/docs/instances/stop-start-instance).
