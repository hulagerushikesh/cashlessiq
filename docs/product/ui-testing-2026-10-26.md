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

## Follow-up usability work

The follow-up replaces the remaining policy and fact JSON editors with labelled
controls, including costs, emergency/ICU details, declared conditions, clauses,
rule parameters and editable regression examples. Only the selected example is
mounted; switching examples retains its edited facts. Regression and independent
approval gates remain authoritative.

Failed workflow and reviewer saves keep the mounted form and its entries.
Feedback uses fixed public messages, focuses the error, and offers a second tab
for checking current state. Values are not copied to browser storage or URLs.
They are **not durable drafts**: leaving/reloading the page still loses unsaved
entries. Successful saves navigate to the authoritative record. An uncertain
response retains the command ID for an identical idempotent retry. Without
JavaScript, editing/submitting is disabled rather than sending stale hidden facts.

Policy and request lists now have tenant-scoped search, result counts and
previous/next navigation, with 20 rows per UI page. Search applies before
pagination, and the same filter stays in navigation links. The API keeps a
50-row default, allows page sizes up to 50 and validates search/page bounds.
Policy ordering includes a stable ID tie-breaker. Literal SQL wildcard characters
are escaped, and counts use the same tenant/search scope as the rows.

Follow-up verification and fresh CI results are recorded below. These changes
improve synthetic testing; they are not a claim of finished customer UX.

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


## Follow-up verification

- All 24 focused MVP API tests pass, including traversal of 55 policies and 55
  requests across pages, matching counts, active-only filtering, search by
  product/version/name/member/request ID, literal wildcard handling, bounds and
  exclusion of another tenant's matching records.
- All 13 expanded MVP browser tests, all 26 existing browser tests and all 41
  client checks pass locally; types, lint, Ruff and contract generation pass.
  The expanded browser suite includes real validation and interrupted-save
  recovery, retained reasons/costs/conditions, no-script submission protection,
  ordinary clause/rule/example editing with 31 passing regression cases, and
  two-page searches using 21 fictional records per list at 390 px.
- The manual app-browser recovery case is `REQ-a7692a5351c44587a0b9`, member
  `SYN-UI-FORM-RECOVERY-20261026`. An excessive remaining cover was rejected;
  correcting it retained the member and fictional note and saved successfully.
  Local screenshot evidence is `output/ui-testing/form-recovery.png`.
- No schema migration or database recreation was needed. Only the existing API
  was restarted to load the search endpoints. No cloud or paid service was used.
