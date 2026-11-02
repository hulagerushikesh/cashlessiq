# First private GCP run — 2 November 2026

## Approval and inputs

The owner explicitly moved the unused first test to 2 November and confirmed
availability: one build (up to US$0.09 compute), one e2-small VM for at most four
hours from startup (about US$0.09 VM/IP), retained 20 GiB standard disk (about
US$0.80/month), plus image/source storage, traffic, logs and tax. Estimates are
not a hard cap. Stop early when testing ends; ask before another build or a
larger VM. Docker Desktop on the operator Mac stays off.

Billing remains linked to Firebase Payment. The [1 November handoff](gcp-first-run-2026-11-01.md)
retains quota approval, billing-link evidence and the accepted source checksums.
Application revision `79408862a15454565f09744edd90c25b3d4df1d4` still has green
full-product and private-preview CI. The runtime archive and minimal build source
were verified again before any upload. Test-harness changes made today are not
application changes and do not require another image build.

## Cloud setup receipts

- Project: `cashlessiq-dev-rush` (`133378676383`), region `us-central1`.
- Enabled Compute, Cloud Build, Artifact Registry, IAM, IAP and Billing Budgets
  APIs. No optional container-scanning API was enabled.
- CashlessIQ-only monthly billing alert: INR 100, notifications at INR 25, 50
  and 100 of spend before credits. Default billing IAM recipients remain enabled.
  This is an alert, not a cap or permission to spend INR 100. Budget ID:
  `88f1eed8-984c-4fc4-96b2-1d6e946c2b5f`.
- Registry: `us-central1-docker.pkg.dev/cashlessiq-dev-rush/ciq-preview`.
  Builder identity has repository writer; runtime identity has repository reader.
  Both use dedicated `ciq-preview-builder` / `ciq-preview-runtime` service
  accounts. Builder additionally has log writer and object viewer on the source
  bucket. Neither has project-wide Editor. Google's automatically created Editor
  grant on the unused default Compute identity was removed.
- Source bucket: `gs://cashlessiq-dev-rush-build-source`, regional, uniform access,
  public-access prevention enforced, soft delete disabled for this disposable
  source storage. Only the verified minimal build archive was uploaded.
- Custom network `ciq-preview`, subnet `ciq-preview-us-central1`,
  `10.42.0.0/24`, IPv4 only. Its sole ingress rule allows TCP 22 from IAP's
  `35.235.240.0/20`, targeting the runtime service account. No public application,
  API or database ports were opened.

## First build

Build ID: `a82604ca-2d43-4026-b9e2-5b9226ffe804`.
[Cloud Build run](https://console.cloud.google.com/cloud-build/builds;region=us-central1/a82604ca-2d43-4026-b9e2-5b9226ffe804?project=133378676383).
Submitted once with the scoped builder identity, `E2_STANDARD_2`, 900-second
timeout, regional source staging and Cloud Logging only. The build succeeded, running from 03:30:12 to 03:32:40 UTC (about 2½ minutes).
Immutable deployment images:

- Web: `web@sha256:3d9e5c8fc93208c4f1195378f50573cc9301bb85422005b84a82699830ad437f`.
- API: `api@sha256:a16ab033c6a4a7ab2f475efeb24074c6b6c939f197812be28accc6a683773b4f`.

Both are in the private registry above. No second build was submitted.

## VM acceptance and initial owner window

After build success, `ciq-private-test` was created in `us-central1-a`, e2-small,
Debian 12, 20 GiB standard boot disk, custom IPv4 subnet and the scoped runtime
identity. Secure Boot is enabled, automatic restart is disabled, project SSH
keys are blocked and serial-port access is disabled. The live instance checker
passed: 14,400-second maximum duration, STOP action, automatic deadline
`2026-11-02T07:33:01.259668Z` (**13:03:01 IST**), one ephemeral IPv4 and no reserved
external addresses. The persistent operator usage ledger was initialized from
this first live start; no prior CashlessIQ VM runtime existed.

Docker Engine 29.9.2 / Compose v5.6.1 and the SHA-256-verified cloudflared
2026.10.5 were installed only on this VM. The verified runtime bundle was
extracted under the dedicated `ciqpreview` operator. The runtime identity
successfully authenticated to the registry without copying a key to the VM.
The exact accepted images started without any VM build. Migration exited zero;
all four steady services became healthy.

Host startup sampling covered credentials, image pulls, migrations and app
startup: 159 half-second samples, 1,976.4 MiB usable RAM, minimum estimated
available 1,170.5 MiB and zero swap use. Samples miss shorter peaks; this is
first-run evidence, not a load-capacity guarantee.

An outbound quick tunnel runs as a transient, restricted systemd unit with no
automatic restart/start. Metrics and gateway listen only on loopback. The exact
assigned HTTPS origin was applied and only the web service recreated. Anonymous
and wrong-password HTTPS requests both returned 401 with no-store/no-index
headers. Live disk, Secure Boot, restart policy and runtime identity checks pass.
Host listener inspection confirms no published 3000, 8000 or 5432 ports; only
the gateway is Docker-published, on `127.0.0.1:3080`. Firewall ingress remains
IAP SSH only. The initial deployed browser suite finished with 17 passes and one overall
120-second timeout in the longest journey. That journey reached the later
reassessment/reviewer stage; its isolated rerun passed in about 1.4 minutes with a 240-second overall
ceiling, retaining the existing per-action/navigation limits. All 18 browser
checks have therefore passed across the initial suite and isolated rerun, not
as one uninterrupted green run. No application change, second build or VM resize
was made to achieve the rerun.

The concurrent five-minute sampler completed 59 samples: individual highs were
DB 61.2, API 113.1, web 117.6 and gateway 33.4 MiB (sum 325.3 MiB, not a single
simultaneous peak). Minimum estimated host available RAM was 1,052.7 MiB with
zero swap use. All containers reported zero restarts and no OOM-killed state;
migration was the expected exited service. Short peaks remain outside sampling.
An additional browser check verified the HTTPS session cookie is Secure,
HttpOnly, SameSite=Strict and scoped to `/`. Sign-out cleared the session and a
subsequent protected-page visit redirected to login. A desktop screenshot was
visually inspected; workflow links are visible in the sidebar. Credentials and
the exact temporary origin are kept only in ignored operator output.

At the initial handoff, the VM was left running for the available owner's manual
test within the approved window, with **13:03:01 IST on 2 November** as the
verified automatic-STOP backstop. That test window has now ended early, with
completed shutdown verified below. No daily startup, automatic restart or extra
build was configured. Keep the persistent operator usage ledger.

Ignored operator receipts are under `output/gcp-preview/`: build response,
accepted digests, creation/live disk and instance acceptance, startup/browser
memory logs, the first-suite log, long-journey rerun log, HTTPS gate/session
checks and the deployed overview screenshot. `owner-password.txt` is mode 0600
and was neither logged nor committed.

## Browser-test scope

The browser smoke harness still defaults to localhost. Remote execution requires
an exact HTTPS `*.trycloudflare.com` origin in both `MVP_BASE_URL` and
`MVP_APPROVED_GCP_ORIGIN`, plus a separate owner-password file. Unapproved hosts,
mismatched origins, paths, embedded URL credentials and unexpected ports are
rejected. Only opt in after checking the live fixed-project VM and exact tunnel
origin. Do not set these variables for production or customer data.

The local harness checks and TypeScript/lint checks passed; all 57 client tests
passed without starting Docker or a browser. Initial live results are recorded above;
completed owner-requested regression and shutdown acceptance follow below.

## Owner-requested regression and completed shutdown

After the owner reported testing the deployed app, they requested another
engineering pass. On the same accepted images, all **18 browser tests passed in
one uninterrupted 4.8-minute run**, without retries. The 240-second overall
ceiling was retained; per-action and navigation limits were unchanged. The long
policy/assessment/review/document journey passed in about 1.3 minutes. All seven
roles' mobile navigation, policy authoring/approval/activation, input retention,
lost-response upload retries, progress recovery, cross-page searches and foreign
origin rejection passed. Traces stayed disabled to avoid retaining auth headers.

A separate manual browser journey submitted `SYN-MANUAL-20261102-MISSING`
(request `REQ-c6bdb9d19b7d43368f0f`) with empty diagnosis and procedure. The app
returned QUERY / Not calculated; the medical officer saw specific prompts for
both fields, while the processor could not see clinical details. Assignment,
request information, fact correction, reassessment to INR 95,000, resume and final
review all saved, with five versioned audit actions. Switching back to processor
retained the completed result while hiding the clinical correction comment.
No blocking defect was observed in these journeys. Test records are fictional
and remain in the retained database; this does not establish production or load
readiness.

A concurrent four-minute sample collected 48 observations. Individual container
highs were DB 65.4, API 121.4, web 136.7 and gateway 40.8 MiB (sum 364.3 MiB,
not a simultaneous peak). Minimum estimated host available RAM was 1,041.4 MiB;
swap use stayed zero. A separate Docker state read confirmed all four steady
services healthy, zero restarts and no OOM state; migration remained exited zero.
Sampling can miss shorter peaks. No new build, VM resize or local Docker start
was needed.

After checks finished, the transient tunnel was stopped and the runtime brought
down without deleting its database volume. The VM was explicitly stopped early.
At **2026-11-02T04:04:46.534262Z (09:34:46 IST)**, the live fixed-project checker
verified **TERMINATED**, no assigned external IPv4, no active automatic deadline
and zero reserved addresses. The next live ledger read closed today's session at
**1,901 seconds**, a conservative observed upper bound of about 32 minutes, not
a billing measurement. The persistent ledger was preserved. The temporary URL
is offline; retained disk, registry images and build source remain. Agree the
next test window before further paid operation; another build or larger VM still
requires explicit approval.

Ignored receipts: `owner-requested-browser-tests.log`,
`owner-requested-memory.log`, `owner-requested-containers.json`,
`manual-review-completed.jpg`, `completed-shutdown.json`, `completed-usage.txt`
and the updated `deployment-receipt.json`. The app images are unchanged.
