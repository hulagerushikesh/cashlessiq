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
source, migration and pure Python dependency mounts. It does not claim to have
rebuilt the image. Prepare these mounts with:

```sh
.venv/bin/python -m scripts.prepare_mvp_local
```

This builds and verifies the small domain wheel and verifies the universal
`pypdf` wheel against the committed lock hash. It never changes Docker services.
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

1. Open `http://localhost:3000`, sign in as the policy analyst and open the
   testing workspace. Propose a version, optionally using an extracted fictional
   PDF. Wait for regression results.
2. Sign out and enter as the policy approver. Inspect the diff and results,
   approve, then activate the version with a reason.
3. Enter as the processor, submit a fictional request and wait for its draft.
4. Enter as the medical officer, claim it, inspect evidence, and submit an
   approval or query/referral with a reason. Test a conflicting browser tab.
5. Upload a fictional PDF. Only medical officers can read clinical document
   text or download a released clinical PDF. A query can be corrected and
   reassessed while preserving previous facts.
6. Enter as auditor to inspect history; operations lead to inspect jobs; tenant
   administrator to test suspension and immediate session revocation.

`npm run test:mvp` automates policy proposal/approval/activation, queued
assessment, final human review, restricted comments, extraction and download.
The ordinary browser suite remains an independent check of the frozen golden
recommendations. Owner testing of the earlier read-only UI is already complete;
these are the newly added workflows to exercise next.

## Boundaries and recovery

- Fictional data only. This is not customer, production or medical validation.
- No Snowflake publishing, model calls, paid OCR, cloud deployment or billing
  changes. The outbox projects into local PostgreSQL with event deduplication.
- PDF checks reject scripts, actions, forms, embedded files, encryption and more
  than 20 pages; cap uploads at 2 MiB and tenant storage at 40 MiB. They are not
  antivirus scanning or OCR. Linux parser children enforce CPU, address-space
  and data limits plus a parent wall timeout. Direct macOS parser tests have
  CPU/wall/input bounds; macOS rejects those address/data limits.
- Audit, proposals, analytics events and input revisions are forward-only.
  Disable the workflow feature on the current migrated binary to recover;
  never delete audit history or downgrade it. Retain the pre-migration backup.
- The read-only development overlay keeps the underlying old API/web images.
  The web image's older installed transitive dependencies require a fresh build
  when the heavy-build preflight permits; fresh builds include the URI-parser
  patch already committed in the lockfile.
- Governed source selection, external custody, real AI/search and Snowflake
  analytics delivery remain separate, unactivated integrations. GCP deployment
  follows engineering validation and explicit cost approval.
