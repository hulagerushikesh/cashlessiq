# Two-person testing: existing Docker and a small GCP preview

**Current owner operating decision — 29 October:** prepare code and complete
builds before starting the GCP VM. Run it only during active testing, for at
most **four hours total per working day**, and stop sooner when finished.
There is no automatic daily start. The four-hour automatic STOP is a per-start
backstop; the operator must track cumulative daily use across restarts. This
operating preference does not authorize billing linkage or paid provisioning.
Docker Desktop stays shut down during ordinary engineering; use offline checks
and disposable CI. Earlier local observations below are historical evidence.

The prepared runtime sampler now supports `--include-host` on Linux, recording
usable RAM, minimum sampled available RAM and swap use alongside container
highs. The [operator sequence](../../deploy/gcp-preview/README.md) includes a
bounded two-minute observation during the eventual cross-device test, plus
read-only checks for the actual VM's four-hour STOP deadline and completed
shutdown. CI-host observations do not establish e2-small fitness; these helpers
have not been run on an actual GCP VM.

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

During explicitly requested local interactive testing, use one stack after
checking Mac headroom. Keep Docker shut down during routine engineering. The
built production web server avoids the development compiler overhead. Docker
is a development/deployment tool, not something required on each tester's device. Localhost access remains tied to this Mac; a hosted
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

The full synthetic MVP also needs `compose.mvp.yml`. That overlay raises the
API/embedded-worker limit to 512 MiB. The effective steady limits are web 512 MiB,
API 512 MiB, database 256 MiB and gateway 128 MiB: **1,408 MiB combined**.
The one-time migration has a separate 256 MiB limit and completes before API
and web startup. This leaves less room in a 2 GiB VM for the OS and Docker than
the earlier read-only plan; remote acceptance must check actual host memory and
the VM size may need review if it cannot stay healthy. [CI 40180267477](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40180267477)
passed all 37 HTTP checks under the earlier 1,152 MiB read-only limits at
`f28cb66`. Its final snapshot
reported web **74.13 MiB**, API **73.82 MiB**, database **30.03 MiB** and gateway
**11.53 MiB**, approximately **190 MiB combined**. This is a runtime snapshot
after the checks, not a peak measurement or a whole-VM capacity guarantee.
[Full product CI 40180267473](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40180267473)
also passed all regression stages. The later full MVP browser and recovery tests
passed with the 512 MiB API ceiling on a disposable Linux preview. Run
`python -m scripts.check_gcp_preview_plan` to validate the four-file GCP
composition locally without a cloud API call, build or container start.

The e2-small is a **shared-core 2 GiB VM**, not a high-capacity server. Its size
is driven by running PostgreSQL, the API/embedded worker, the production web
server and password gateway together, with room for Debian, Docker and the
tunnel. Tester count and fictional data volume are small. The development web
server's earlier 2.4 GiB observation included the live compiler and is not the
production preview's size. In [full-MVP preview CI 40806424789](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40806424789),
the end-of-test container snapshot was approximately 253 MiB combined (web
99, API 92, database 48, gateway 16 MiB). That snapshot does not show peak
memory, host memory or future use. Preview CI now samples memory throughout the
browser workflow and reports each service's observed high; the first remote
test must still measure the whole VM. [CI 40812748861](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40812748861)
passed all 13 browser workflows and both recovery browser checks at `4418460`.
Ten samples during the browser suite reported highs of database **47.7 MiB**,
API **116.3 MiB**, web **117.5 MiB** and gateway **16.3 MiB**. Their individual
highs total **297.8 MiB**; they need not have occurred at the same instant.
Samples are separated by the three-second wait plus the Docker observation
time and miss short peaks. They also exclude startup, the host OS, Docker and
the HTTPS tunnel. Both disposable preview stacks were removed afterward.
These observations make a 1 GiB experiment plausible; 2 GiB remains a cautious
initial proposal, not a measured minimum requirement.

An e2-micro would provide only 1 GiB RAM and half the e2-small's sustained CPU
share. Its memory is below the current **1,408 MiB combined container ceilings**
before Debian, Docker and the tunnel, so it is not the initial plan. Those
ceilings are safeguards rather than expected consumption; a later e2-micro
trial is reasonable only after full-workflow peak sampling and a smaller-limit
composition pass with actual host headroom. The GCP free tier can cover eligible
e2-micro time and up to 30 GiB-months standard disk in the selected US region,
but it is shared at billing-account scope, requires billing to be enabled and
does not cover every cost, including most external IPv4 usage. No free allowance
or credit balance is assumed for this project.

Cloud Run can scale HTTP services to zero, but the current API requires
PostgreSQL-backed membership. Its instance filesystem is ephemeral. Moving
this exact app there introduces a durable database choice and service wiring;
creating a managed database merely for these two testers is unnecessary now.
One small VM reuses the tested stack with fewer application changes. Cloud Run
can be revisited when the application or operating needs change.

## Future cost reference — paid deployment not authorized

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

For remote acceptance, the proposed VM has a **four-hour maximum run duration
with automatic STOP**. Four hours of VM and IPv4 usage is about **$0.09**, plus
builds, retained storage, traffic and tax. Complete the build before starting
the VM. Stop immediately after testing; do not leave it running while coding,
waiting for a build or away from the app. Reuse an accepted image until code
changes require a new build. No paid scheduler is needed.

At 30 days of four-hour use, VM and IPv4 total approximately **$2.61/month**;
the retained 20 GiB disk adds **$0.80/month**, giving **$3.41 before builds,
image/source storage, traffic, logging and tax**. This assumes 120 total running
hours, not an always-on VM. Each 15-minute build adds up to $0.09 in build
compute without free allowances. This is a usage estimate, not a hard cap.

Stopping the VM ends its compute usage and releases its ephemeral address;
retained disks and images still incur storage charges. The app is unavailable
while stopped. Stopping Docker containers alone does not stop VM billing;
verify the GCP instance is `TERMINATED` and its ephemeral IPv4 is released.
Each start resets the runtime timer. Track cumulative daily hours and stop
sooner after a restart rather than treating each start as another four-hour
allowance. An extension requires the owner's approval.

## Future deployment sequence — requires a new owner decision

1. Link the approved billing account to this dedicated project, enable only the
   needed Compute/Build/Registry/IAP services and set the reviewed cost alerts.
2. Create a regional image repository and narrowly scoped build/runtime service
   identities. Runtime needs registry read access, not project-wide Editor.
3. Submit the manual `cloudbuild.yml` with the tested Git revision. The source
   ignore file and Docker ignore file exclude local credentials, output and
   the owner's untracked submission video. Never build images on the test VM.
4. Create only the reviewed network, IAP SSH firewall, 20 GiB disk and e2-small
   VM with the reviewed four-hour STOP limit. Install Docker and pull the exact
   accepted web/API image digests.
5. Prepare independent preview secrets on that VM. Set
   `CIQ_PREVIEW_API_IMAGE` and `CIQ_PREVIEW_WEB_IMAGE` to those exact digests in
   its private preview environment. Start with **all four** Compose files in the
   plan, including `compose.mvp.yml`, using
   `up --no-build --pull always --detach --wait`. The GCP overlay selects the
   prebuilt images and the MVP overlay enables the synthetic workflows; this
   does not change the current local app.
6. Verify local password denial first, start the HTTPS tunnel to gateway port
   3080, configure its exact origin, then verify remote anonymous denial,
   three synthetic roles, secure cookies, sign-out, runtime memory and stopping
   remote access. This is a targeted delivery check; it does not repeat the
   already completed general owner walkthrough.

No commands in this document have provisioned a paid deployment. The resource
plan and build configuration remain preparation only; no financial approval is
currently pending or granted.

## Current go/no-go checkpoint — 28 October

The synthetic MVP is ready for a bounded private cloud acceptance run once the
four-file preflight and preview CI pass at the chosen revision. The remaining
first-deployment work is operational: recheck the current price, agree on a spend
and test window, link billing, set budget alerts, create the reviewed resources,
start the exact image digests and HTTPS tunnel, then test anonymous denial,
roles, workflows, cookies, memory and the four-hour STOP. A budget alert is
not a spending cap. No customer or real medical data should be used.

The owner can choose the first test window and acceptable spend while engineering
prepares the package. Billing linkage, cloud builds and provisioning still need
the owner's explicit approval before execution. A successful remote acceptance
would make the private site available during the agreed VM run window; it would
not establish a customer-ready release.

Price references rechecked on 28 October: [E2 machine sizes](https://docs.cloud.google.com/compute/docs/general-purpose-machines),
[VM pricing](https://cloud.google.com/products/compute/pricing/general-purpose),
[disk pricing](https://cloud.google.com/compute/disks-image-pricing),
[IPv4 pricing](https://cloud.google.com/vpc/network-pricing#ipaddress),
[Cloud Build pricing](https://cloud.google.com/build/pricing),
[Artifact Registry pricing](https://cloud.google.com/artifact-registry/pricing),
[Cloud Run runtime contract](https://docs.cloud.google.com/run/docs/container-contract)
[VM runtime limits](https://docs.cloud.google.com/compute/docs/instances/limit-vm-runtime)
and [stopped-VM charges](https://docs.cloud.google.com/compute/docs/instances/stop-start-instance).

E2 machine sizes, VM/disk/IPv4 prices and [free-tier eligibility](https://docs.cloud.google.com/free/docs/free-cloud-features)
were rechecked on 29 October. The e2-small VM price remains $0.016752855/hour
and standard IPv4 remains $0.005/hour. The four-hour VM-plus-IP estimate is
$0.087 before rounding, storage, builds, traffic and tax. No paid action was
taken as part of the resource measurement.

## Runtime package — 29 October

The [first-test operator sequence](../../deploy/gcp-preview/README.md) now
specifies the exact handoff from accepted CI revision to the bounded VM run.
`scripts.package_gcp_preview` builds a checksum-verified, minimal bundle of
Compose/gateway/plan/runtime files from committed source. It excludes the owner
video, credentials and application source. On the VM,
`scripts.gcp_preview_runtime` accepts only exact API/web image digests from this
project's registry, checks the private environment and resolved four-file
composition, and starts it with `--no-build`. The operator must still verify
the VM's four-hour STOP setting and observed memory during the paid test.
This package has not been deployed to GCP; billing remains disabled.
