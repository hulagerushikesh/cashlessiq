# Private testing — Saturday, 31 October 2026

The owner will be available on Saturday. Until then, ordinary engineering and
disposable CI continue with Docker Desktop off on the Mac and no paid GCP
resource started. The four-hour usage policy is not spend approval.

## Build preparation

The synthetic policy, intake, assessment, reviewer, document, governance and
access workflows are implemented. The 29 October usability increment removes
manual reloads from request assessment, supporting-PDF extraction, policy
regressions and policy-wording extraction. Only read panels update. Mounted
form entries, command IDs and expected action versions are not replaced.

Progress reads use authenticated, uncached projections of the same tenant/role
as the page. Polling starts only for pending work, runs every five seconds for
up to two minutes, pauses while hidden/offline, stops on a failed read and can
be stopped or restarted explicitly. A completed record makes no automatic
reads. A successful job whose result has not appeared yet is checked again.
The browser never decides policy approval, download release or final amounts.

Dead processing, rejected PDFs and manual-transcription requirements have
separate messages. The specific job can be opened from pending/failed results,
including jobs older than the main list's latest 50 entries. Operations leads
and tenant administrators retain the existing audited, reason-required retry;
other roles have no retry control. Successful retries return to that job.
Policy-wording PDFs become selectable only after extraction succeeds; proposal
entries remain mounted while extraction updates.

This does not add durable drafts across reload/navigation, OCR, antivirus,
external identity, live-source activation or customer readiness. The ordinary
job list/detail pages still use an explicit refresh; pending work has bounded
automatic updates on the request and policy pages.

## Saturday sequence

1. **Before paid actions:** review current prices and the concrete proposed
   four-hour window with the owner. Obtain explicit approval before billing
   linkage, paid builds or provisioning. The target remains
   `cashlessiq-dev-rush`; no action uses the CLI's unrelated default project.
2. **Prepare with the VM off:** use accepted code and immutable image digests,
   private configuration and the reviewed runtime bundle. Select the owner's
   encrypted backup recipient and off-machine destination if we will rehearse
   external backup custody; same-runner CI recovery already passes.
3. **Start only for active testing:** verify the four-hour STOP deadline, whole
   host memory/swap, remote HTTPS, access gate, firewall/IAM and service health.
   The proposed VM size remains a candidate until measured on the actual host.
4. **Agent technical checks first:** run the private workflow and restart/restore
   checks remotely within the approved window. Preserve synthetic audit history
   and record actionable failures; no owner address-bar navigation is required.
5. **Owner device testing:** test phone/laptop navigation, wording, accessibility
   and the new workflows that matter to the owner. Earlier owner testing is
   already acknowledged; there is no need to repeat it as a general prerequisite.
6. **Stop immediately when finished:** verify `TERMINATED`, released ephemeral
   external IP and no reserved external addresses, record cumulative hours that
   day and retained storage. A restart resets the automatic timer, so no daily
   automatic start is configured.

The [operator usage commands](../../deploy/gcp-preview/README.md#record-cumulative-daily-usage)
now prepare a persistent daily receipt ledger. Capture the first start once,
then every later start and completed stop from the operator checkout. The report
shows the remaining four-hour allowance and an India-time `stop_by` deadline
after restarts. Preserve the same ledger across days. Unclosed sessions keep
counting, and missing STOP receipts or unrecorded restarts require reconciliation.
This is conservative operator accounting, not a cloud-enforced cap or billing
meter; no actual VM history has been recorded yet.

Fresh CI evidence for this increment is recorded in the delivery dashboard.
The actual deployment/host acceptance remains unperformed until its approved run.

## Daily usage handoff — 29 October

Revision `3735e6f` adds the persistent cumulative-use helper to the operator
handoff and minimal runtime archive. The
[private preview run](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40910782236)
passes 37 gate checks, all 16 MVP browser tests, encrypted recovery matching
17 tables, browser reopening after restart/fresh-volume restoration and cleanup.
The [full product run](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40910782084)
also passes: 1,018 root checks (three skips), 1,522 API checks (one skip), 72
membership, 35 catalog, 51 client, 26 browser, 15 source UI and all 16 MVP browser
checks, plus contracts/types/lint/build/containment and cleanup. All 88 focused
usage/instance/package/measurement checks pass locally without starting Docker.

The refreshed archive is
`output/gcp-preview/cashlessiq-gcp-preview-3735e6f18f93.tar.gz`, SHA-256
`5233ca09a9ba10d9e825b793caeb1a1587b3c754357593241f4b4d69b65f2cea`.
Its checksum, manifest and clean extraction pass; the extracted checker and
usage CLI work against fictional observations in a temporary directory, which
was then removed. Use this archive for the next handoff rather than the earlier
workflow archive below. Actual VM images, spend approval, access/host acceptance
and off-machine backup custody remain separate. Docker stays off on the Mac.


## Earlier workflow acceptance record

Engineering revision `1adafa8` includes bounded progress panels, specific-job
inspection, supported metadata-only SQL and save-navigation synchronization in
the browser tests. The production
[private preview run](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40906659753)
passes all 16 MVP browser tests, encrypted restoration matching all 17 tables,
browser reopening after restart and on a fresh restored volume, and owned
cleanup. The full
[product run](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40906659813)
also passes: 982 root checks (three skips), 1,522 API (one skip, two pre-existing
warnings), 72 membership, 35 catalog, 51 client, 26 browser, 15 source UI and all
16 MVP browser checks, plus contracts/types/lint/build and containment.
The supported metadata query removes the 19 deprecation warnings from the
superseded API run.

The two integration findings were corrected before acceptance: tests now check
`no-store` semantics through either the gateway or direct development server,
and successful form submissions wait for their document navigation before
checking new results. No automatic page reload was added to the product.


The earlier runtime archive for that workflow revision is
`output/gcp-preview/cashlessiq-gcp-preview-1adafa88fbe7.tar.gz`, SHA-256
`a744de8e39ffce1ba51207d406df81ceb9b9c56b8d56c452c4d0623a313c75de`.
Checksum, manifest and fresh temporary extraction checks pass. The archive is
runtime preparation; API/web images still require a separately approved build
and recorded immutable registry digests before deployment.

The final preview has 16 samples: individual container highs total 273.6 MiB
(the highs need not coincide). Its approximately 16 GiB Linux CI host has zero
sampled swap use. Sampling excludes short peaks and startup, and does not prove
that the proposed 2 GiB GCP VM fits. No local Docker or paid cloud resource was
started for this engineering batch.
