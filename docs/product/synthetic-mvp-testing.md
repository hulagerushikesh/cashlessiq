# Synthetic MVP engineering and testing

The user approved the full MVP workflow scope on 25 October 2026. This scope
allows synthetic application work before the external governed-source P2 exit.
GCP remains preparation only, with billing and paid gateways unapproved.

## Implemented workflow

- Reviewer assignment, team and restricted clinical comments, query, referral,
  resume, final human approval, approval with deductions and reasoned reopening.
- Optimistic versions, idempotent command receipts, append-only audit and an
  outbox committed with each reviewer action. No settlement or payment action.
- API and web request intake, SLA and priority, deterministic asynchronous
  assessments and policy versions pinned to each request.
- PostgreSQL job leases, fenced completion, restart recovery, three automatic
  attempts, dead-letter state and audited operations retry.
- Synthetic PDF quarantine, bounded text extraction, restricted downloads,
  document hashes and manual handling for scanned documents. Extracted text
  never silently becomes a clinical fact or executable rule.
- Versioned fact correction after a query, immutable input history and a new
  assessment. Previous calculations remain attached to their job and policy.
- Immutable policy proposals, clauses and supported rule parameters; regression
  examples; different-person approval; effective dates; activation concurrency
  checks and rollback through a new activation event. Policy wording PDFs can
  be extracted and bound to a proposal by document ID.
- Seven synthetic roles, tenant membership changes with concurrency checks and
  immediate revocation, governance history and tenant-scoped local reporting.

The baseline template evaluates all 30 existing golden cases with the canonical
rules core. A second product can be proposed through the policy editor without
code changes, using supported rules and its reviewed expected test outcomes.
The approver must inspect the wording, diff, expected outcomes and results.
Unsupported rule types fail closed and still require domain implementation.

## Local runtime

The normal product stack keeps workflows disabled by default. Enable them with
`compose.mvp.yml`; this also enables one local background thread in the API.
The same job lease implementation runs independently with
`python -m ciq_api.jobs` later. A separate worker service is unnecessary for
this small private test. The API container is capped at 512 MiB and one CPU.

The Mac's heavy-build preflight still reports elevated memory pressure. The
development refresh therefore uses the **existing** API image plus read-only
source, migration and locked pure Python/JavaScript dependency mounts. It does not claim to have
rebuilt the image. Prepare these mounts with:

```sh
.venv/bin/python -m scripts.prepare_mvp_local
```

This builds and verifies the small domain wheel and verifies the universal
`pypdf` wheel against the committed lock hash. It also verifies the URI-parser
archive against npm lockfile integrity and mounts the patched JavaScript package
read-only. It never changes Docker services.
The generated override is ignored at `output/mvp-local/compose.json`.

After backing up the local PostgreSQL database, refresh only the owned API,
apply migrations, seed the extra synthetic roles and refresh only the web:

```sh
docker compose --env-file .env.product.local -f compose.product.yml -f compose.mvp.yml -f output/mvp-local/compose.json up --no-build --pull never --no-deps --detach api
docker compose --env-file .env.product.local -f compose.product.yml -f compose.mvp.yml -f output/mvp-local/compose.json exec -T api .venv/bin/alembic upgrade head
docker compose --env-file .env.product.local -f compose.product.yml -f compose.mvp.yml -f output/mvp-local/compose.json exec -T api .venv/bin/python -m ciq_api.seed
docker compose --env-file .env.product.local -f compose.product.yml -f compose.mvp.yml -f output/mvp-local/compose.json up --no-build --pull never --no-deps --detach --wait api web
```

Fresh CI and future approved cloud builds install all dependencies directly
from the lockfile. Do not copy host-native Python/Node binaries into containers.
Do not start a second stack, increase Docker resources or bypass heavy preflight.

## Human test sequence

The [26 October UI testing report](ui-testing-2026-10-26.md) records the owner
navigation findings, fixes and fresh CI validation. Functional workflow testing is
now exercised by the agent; the owner can focus on usability feedback.

1. Open `http://localhost:3000`, sign in as the policy analyst and use **New policy**
   in the visible workflow navigation. Enter a unique product ID and version,
   leave the baseline rules unchanged, add a reason, and save the proposal. No JSON
   editing or manual address-bar navigation is required for this walkthrough.
   An optional fictional wording PDF is available under the upload disclosure.
2. Sign out and enter as the policy approver. Open **Policy library**, choose the
   product/version, inspect its clauses and all 30 regression results, approve,
   then activate with a reason. **Approved** and **active** are separate states;
   an approved-but-inactive version is clearly labelled and excluded from intake.
3. Enter as the processor, use **New request**, choose the active product, keep the
   fictional defaults, confirm fictional data, and queue assessment. The assessment panel updates after
   processing; the baseline yields a deductions draft of INR 95,000.
4. Enter as the medical officer, use **Submitted requests**, open the member
   reference, and select **Open reviewer workflow**. Assign it to yourself,
   inspect evidence, then record a reasoned approval or query/referral.
5. Upload a fictional PDF from the request page. Only medical officers can read
   clinical document text or download a released clinical PDF. A query can be
   corrected and reassessed while preserving previous facts.
6. Enter as auditor to inspect history; operations lead to inspect **Background
   jobs**; tenant administrator to use **Manage tenant access**. Role changes and
   revocation have immediate effect. These navigation controls also work at
   mobile widths. Sign out to select a different synthetic role.

`npm run test:mvp` automates policy proposal/approval/activation, queued
assessment, final human review, restricted comments, extraction and download.
The main journey now begins at home and follows visible navigation and case
links. It also covers reopening, a query, corrected facts and reassessment,
referral/resume, a stale conflicting tab and saved-decision persistence. Seven
role checks traverse the UI at 390 px, including governance/access pages where
permitted. A separate regression checks inactive-policy intake filtering,
authoritative denial of a stale form and actionable duplicate-version feedback.
Additional checks cover form retention after real validation and a connection
failure, safe handling without scripts, policy clause/rule/example editing, and
searches that traverse two pages at mobile widths.

Owner feedback on 26 October exposed a missing policy-list route, locked legacy
sidebar placeholders, a stale read-only badge, and approved-but-inactive versions
appearing in intake. Dedicated library, request and job pages plus shared role-aware
navigation now address these. Fixed error codes explain known failures without
exposing raw API messages or submitted clinical data. Failed saves now retain the
mounted form's entries, including reasons, costs and conditions; leaving/reloading
still loses unsaved entries. No clinical draft is stored in browser storage or a
URL. Policy clauses, supported rule parameters, regression examples and queried
request facts now have normal editing controls. Policy/request lists include
server-side search, counts and previous/next pages (20 rows per UI page).
The ordinary browser suite remains an independent check of the frozen golden
recommendations. Owner testing of the earlier read-only UI is already complete;
these are the newly added workflows to exercise next.

## Boundaries and recovery

The [current-MVP recovery rehearsal](mvp-recovery-rehearsal.md) verifies an
exact backup/restore of the existing synthetic data in a temporary database.
Its separate disposable preview check restarts services and reopens a saved
human workflow. The local application is not restarted by this check.
New backups include a dump-byte digest and can be checked after a private copy
with `python -m scripts.verify_mvp_backup /path/to/copied-backup-directory`.
See the recovery guide for copy permissions and the remaining custody limits.

- Fictional data only. This is not customer, production or medical validation.
- No Snowflake publishing, model calls, paid OCR, cloud deployment or billing
  changes. The outbox projects into local PostgreSQL with event deduplication.
- PDF checks reject scripts, actions, forms, embedded files, encryption and more
  than 20 pages; cap uploads at 2 MiB and tenant storage at 40 MiB. They are not
  antivirus scanning or OCR. Linux parser children enforce CPU, address-space
  and data limits plus a parent wall timeout. Direct macOS parser tests have
  CPU/wall/input bounds; macOS rejects those address/data limits.
- Audit, proposals, analytics events and input revisions are forward-only.
  Disable both `CIQ_SYNTHETIC_WORKFLOWS` and `CIQ_LOCAL_EMBEDDED_WORKER` on the
  current migrated binary to recover;
  never delete audit history or downgrade it. Retain the pre-migration backup.
- The read-only development overlay keeps the underlying API/web images. The
  running web parser now reports the patched 3.1.9 version from the verified
  read-only mount. Fresh immutable builds use the same committed lockfile.
- Governed source selection, external custody, real AI/search and Snowflake
  analytics delivery remain separate, unactivated integrations. GCP deployment
  follows engineering validation and explicit cost approval.


## Validation checkpoint

Implementation `517215a` passed
[full product CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40203411894):
913 root, 1,512 API, 72 membership, 35 database-catalog, 41 client, 26 browser,
15 source UI and two MVP browser checks, plus contracts/types/build/containment.
Its [production preview](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40203411961)
also passed all 37 existing owner-gate and secure-cookie checks.

Final hardening adds seven API regressions: previously cached user, membership
or tenant state must be refreshed under a write lock, and chunked JSON must be
bounded before parsing. All 37 focused reviewer/MVP tests pass. The two MVP
browser checks also pass with mobile review/request layouts. One earlier local
extraction failure was successfully retried through the actual operations UI,
with its retry reason and previous attempt count retained in governance history.
The complete MVP now also
[passes on the standalone production server](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40204698347)
at `7c73d69`, behind the owner-password gate. All 37 existing gate checks and
the two full MVP browser checks passed (23.2 seconds for the MVP browser phase).
The post-workflow snapshot was about 234 MiB combined across web/API/gateway/DB;
this is not peak use and excludes the host and Docker daemon. Container memory
ceilings total 1,408 MiB with the API/worker capped at 512 MiB. The smoke uses a
disposable CI loopback HTTP origin only after independent HTTPS-origin and
secure-cookie checks; prepared remote origins remain HTTPS.


The final code at `7c73d69` also passes
[full product CI 40204698447](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40204698447):
913 root, 1,519 API, 72 membership, 35 database-catalog, 41 client, 26 browser,
15 source UI and two MVP browser checks. The API phase passed in 156.56 seconds;
MVP browser checks passed in 19.8 seconds. No cloud or paid source was used.


## Progress and job inspection — 29 October

Request results, supporting-PDF extraction, policy regression results and the
source-wording selector now update independently of the page and its forms.
Foreground checks run every five seconds for up to two minutes while work is
pending, with stop/check controls and hidden/offline pauses. A failed progress
read leaves loaded results labelled potentially out of date; an ended session
hides that panel's results. No drafts are persisted or page reloads triggered.

Use **Inspect this background job** to open the specific assessment, regression
or extraction job. It works independently of the latest-50 jobs list. Existing
operations/tenant-admin retry controls remain reason-required and audited; a
successful retry returns to that job. PDF rejection and manual transcription
are distinct from worker failure. The Saturday run is described in
[31 October private testing](saturday-testing-2026-10-31.md).
