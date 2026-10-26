# Owner navigation feedback and UI verification — 26 October 2026

The owner reported that new workflows could not be discovered in the interface,
`/workflows/policies` returned 404, and request intake led to an unclear conflict.
The earlier browser test visited feature URLs directly and did not catch this gap.

## Findings and fixes

| Finding | Delivered behaviour |
| --- | --- |
| Home kept locked policy/audit placeholders and a read-only badge | Shared workflow navigation on home and authenticated pages; correct synthetic MVP badge |
| Workflow links disappeared at narrow widths | Wrapping navigation visible at 390 px for all seven roles |
| Policy library URL had no page | Dedicated policy library, submitted-request queue and background-job pages |
| Approved but inactive policies appeared in intake | Intake queries active versions, checks current effective dates, and excludes unactivated proposals; backend still independently enforces eligibility |
| Generic conflict hid the next step | Fixed, allowlisted messages for inactive policies, duplicate versions, effective dates, regression requirements and concurrent activation; failed creation stays on its form |
| Baseline policy test required JSON edits | Normal product ID and version inputs; advanced rules and optional PDF upload are disclosures |
| Activation action was far below the policy details | Explicit approved/awaiting-activation status and link to the decision form |
| Medical officer greeting became “Dr..” | Full display name in the welcome heading |

The owner's `HUMAN_TEST_20261026 / HUMAN_V1` was inspected and was approved but
inactive. Its state was preserved. The walkthrough used a separate fictional
`UI_WALKTHROUGH_20261026 / V1` policy and `SYN-UI-WALKTHROUGH-20261026` request.
Through visible browser controls, it was proposed, independently approved,
activated, assessed, assigned and approved with deductions, with INR 95,000 as the
final payable.
Its case is `REQ-b03dcf48e6af45e98070`; the saved review and audit were inspected.
No fictional audit or previous owner work was deleted.

## Local verification

- Ten expanded MVP browser tests passed. The main journey follows visible links
  from home through separate-role policy review, request intake, assessment,
  reviewer decision, private comments, PDF extraction and restricted download.
- The same journey reopens a final review, requests information, rejects a stale
  tab's command, corrects facts, reassesses, resumes, refers, resumes again and
  saves a final decision that survives reload.
- Navigation checks exercise all seven roles at 390 px, including permitted
  governance/access pages. They verify role-specific creation links and no
  horizontal overflow across dashboard/list pages.
- A separate test verifies approved-but-inactive intake filtering, authoritative
  rejection of a stale submitted form, and actionable duplicate-version feedback.
- All 26 existing browser tests and 38 focused API/reviewer tests passed.
- Type checks, lint, Ruff and generated OpenAPI/client updates passed.

The actual in-app browser walkthrough also used visible navigation rather than
editing the address bar. Its home screenshot is ignored local evidence at
`output/ui-testing/home-navigation.png`.

## Remaining usability limits

Advanced rule authoring and structured fact correction still use JSON editors.
Failed creation returns to the originating form with a fixed explanation, but
entered values reset. Policy/request lists remain bounded to the latest 50
records. These are follow-up usability work, not claims of finished customer UX.

GCP, billing, Snowflake publishing, paid model calls and OCR remain deferred.
All validation in this report uses fictional local data or disposable CI.

## Fresh production build

Code `5578c31` passed [private owner preview CI 40272880035](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40272880035).
All 37 owner-gate/origin/cookie HTTP checks passed, followed by the ten expanded
MVP browser tests on the standalone production server (51.9 seconds). This was a
disposable CI preview, not a cloud deployment. The owned preview stack was removed
after validation.

The same code passed [full product CI 40272879945](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40272879945):
913 root tests (three skips), 1,520 API tests (one opt-in skip), 72 membership
checks, 35 PostgreSQL catalog checks, 41 client tests, 26 existing browser tests,
15 source API-to-UI tests and all ten expanded MVP browser tests. Contract drift,
production build, types, lint and containment checks passed. The API suite took
156.11 seconds and the expanded MVP browser phase took about 1.1 minutes.
