# First GCP test — 1 November 2026

## Owner decision and observed state

The owner explicitly approved linking `cashlessiq-dev-rush` to the open
**Firebase Payment** billing account, one Cloud Build submission (up to $0.09
build compute), and the first test today for at most four hours from VM startup
(approximately $0.09 VM/IP). Approval includes retaining the 20 GiB standard
disk (approximately $0.80/month) and image/source storage. Traffic, logging and
tax are additional; these estimates are not a hard billing cap. Another build
or a larger VM requires another decision. Stop early when testing ends.

The billing-link command failed with `FAILED_PRECONDITION`, specifically
`Cloud billing quota exceeded`, on billing account
`01D654-F2896E-D5D2E8`. A subsequent read confirmed that CashlessIQ still has
`billingEnabled=false` and no linked account. Five projects are already linked
to that account, and it is the only open account visible to this login. Do not
unlink any of those other projects without a specific owner decision.

**Quota-increase request submitted on 1 November 2026.** After clarifying that
the earlier request had not been submitted, the owner signed in and explicitly
asked the agent to submit Google's
[billing quota request](https://support.google.com/code/contact/billing_quota_increase)
on their behalf. The agent requested capacity for one additional billing-linked
project on the account above, identifying the existing CashlessIQ project and
the bounded synthetic-data test plan. Google displayed “Your email has been
sent” and confirmed successful submission. Follow-up goes to
`hulagerushikesh@gmail.com`, typically in about two business days, possibly longer.
No case number was displayed. Local screenshot receipt:
`output/gcp-preview/quota-request-submitted-2026-11-01.png` (ignored output).
**Quota approval verified later on 1 November.** The agent read Google's
“Quota Granted - Paid Cloud Services” email, received at 17:14:37 IST. Google
says the additional quota should take effect within one hour, approximately
18:15 IST. [Approval email](https://mail.google.com/mail/u/?authuser=hulagerushikesh%40gmail.com#all/1a196ed07755eaa7).
A read-only project check still returned `billingEnabled=false` and no linked
account. The approval email establishes Google's decision; successful billing
linkage has not yet been verified. The owner chose to resume cloud work after
the propagation wait. Keep the existing dedicated project; no payment or new
billing account was created.

No Cloud Build, VM, registry, disk, tunnel or preview runtime was started. No
CashlessIQ cloud-usage ledger was initialized. Docker Desktop remained off.
The four-hour window has not begun. Once the quota is resolved, resume within
the approved window when the owner is available; if it moves to another day,
agree on the new window before starting. Do not start on quota approval alone.

## Prepared inputs

- Application revision: `79408862a15454565f09744edd90c25b3d4df1d4`.
  Both [full product CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41277424482)
  and [private preview CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41277424414)
  were rechecked successful at this revision.
- Runtime archive: `output/gcp-preview/cashlessiq-gcp-preview-3735e6f18f93.tar.gz`;
  manifest/checksum verification passed. Its prepared resource plan is a
  historical preparation snapshot, not a current approval or live cloud receipt.
- Build source: `output/gcp-preview/build-source-79408862a154.tar.gz`, 214
  committed files, 337,651 bytes, SHA-256
  `cfeff9bf70ee7efabdc60f2555109a95272d6abd79e0663304debd2c7342e403`.
  Created locally from the accepted Git revision, with only the Docker build
  inputs and build configuration. No credentials, generated output or owner
  submission media included; nothing uploaded to GCP.
- During the quota propagation wait, the four-file Compose preflight passed
  again without starting Docker or cloud services; the steady container ceiling
  remains 1,408 MiB. Runtime archive verification passed and the build-source
  SHA-256 still matches the value above. This is offline readiness evidence;
  actual GCP memory, HTTPS access and shutdown checks remain for the live run.

Published USD rates were rechecked: [e2-small](https://cloud.google.com/products/compute/pricing/general-purpose?hl=en)
$0.016752855/hour, [IPv4](https://cloud.google.com/vpc/network-pricing)
$0.005/hour, [Cloud Build](https://cloud.google.com/build/pricing)
$0.006/minute, [standard disk](https://cloud.google.com/compute/disks-image-pricing)
approximately $0.04/GiB-month and
[Artifact Registry](https://cloud.google.com/artifact-registry/pricing)
approximately $0.10/GiB-month beyond the shared allowance. No credits or free
allowances assumed. The billing account uses INR; Google's applicable currency
prices and tax determine the invoice.

## Resume sequence

1. Confirm the quota issue is resolved and the owner is available for the window.
2. Retry only the approved billing link, then configure the scoped identities,
   regional registry/source storage, cost alerts and reviewed network/IAP access.
3. Submit the single approved 15-minute build while the VM remains off. Record
   immutable API/web digests. Stop for another decision if it needs a new build.
4. Follow the [operator sequence](../../deploy/gcp-preview/README.md) for VM
   creation, four-hour STOP acceptance, cumulative usage receipts, private HTTPS,
   actual host memory and workflow checks, then the owner's device test.
5. Stop early when done. Verify `TERMINATED`, ephemeral-IP release and absence
   of reserved addresses; record the completed stop and retained storage.
