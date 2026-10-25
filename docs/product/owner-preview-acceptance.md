# Owner preview — joint testing before an MVP

25 October 2026. The owner clarified that “go live” means a private app for
Rushikesh to test, with engineering and human checks before a customer MVP.
It does not mean customer access or real patient data. This is the next visible
delivery goal; full governed-source P2 integration continues separately.

## Access and scope

The existing [local sign-in](http://localhost:3000/login) is available on this
Mac. A fresh HTTP check on 25 October returned login 200 and API
`{"status":"ready"}`. This is a running local sandbox, not an online deployment.
The public hackathon site is a separate artifact.

Use fictional cases and the three synthetic roles. No Snowflake connection,
paid queries, reviewer writes, uploads or real documents are required for this
round. The actual source routes remain disabled. Missing, unavailable and saved
preview examples are presentation fixtures, not live-source acceptance.

An owner-only online address remains a follow-up delivery step. Before exposing
it, select the host and an actual owner access boundary, keep the API/database
private, configure the correct origin/cookies and verify an unauthenticated
visitor cannot enter. The synthetic role selector is not an owner access gate:
do not simply tunnel or publish the existing development app. Any new spend or
payment action requires the owner's approval. Synthetic preview delivery does
not depend on Snowflake identities, complete P3–P6 features or customer interviews.

## Run one human pass — about 15–20 minutes

Sign out before switching roles. Record PASS, ISSUE or NOT TESTED for each ID;
do not infer a human pass from automated tests. The detailed
[local alpha guide](local-alpha-testing.md) explains the two fixture datasets.

| ID | Action | Expected behavior | Owner result |
| --- | --- | --- | --- |
| O01 | Sign in as Processor / Asha | Correct name, Processor and Sahyadri sandbox organisation | NOT TESTED |
| O02 | Open queue, then GOL001 | Three fictional cases; draft payable ₹95,000 with calculation and policy references | NOT TESTED |
| O03 | Follow NIA-9.5 | Relevant on-page reference is reachable; no promise of retrieving a policy PDF | NOT TESTED |
| O04 | Open GOL027 and GOL024 | Frozen query/referral outcomes; payable “Not calculated”, never ₹0 | NOT TESTED |
| O05 | Filter QUERY, search a nonexistent reference, then Reset | GOL027 only, then clear empty state, then all three cases restored | NOT TESTED |
| O06 | Inspect GOL001 as Processor, Medical officer and Auditor | Clinical narrative only for the medical officer; sign-in identity changes correctly | NOT TESTED |
| O07 | Open `/source-preview`; compare Saved, Missing and Unavailable | Fixture banner stays visible; absent recommendation is different from unknown status; failure never shows a fallback amount | NOT TESTED |
| O08 | Open Evidence preview; filter a clause and clear the filter | References return after clearing; placeholder links are labelled and are not actual policy documents | NOT TESTED |
| O09 | Sign out, then revisit `/cases/GOL001` | Sign-in screen; no case amount or clinical narrative | NOT TESTED |
| O10 | Use a narrow browser window | Queue/detail/preview remain readable without horizontal page scrolling | NOT TESTED |
| O11 | Look for approve, send-query, refer, upload or assignment actions | These actions are unavailable; read-only scope is understandable | NOT TESTED |
| O12 | Explain the case and amount in your own words | Record anything confusing, missing or difficult to trust; this is human judgment, not an automated assertion | NOT TESTED |

## Engineering and human evidence

The owner-preview copy at `59f42d8`
[passed full product CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40163582801):
root/lint, domain boundary, offline membership, supervisor containment,
contracts/types/build, API/PostgreSQL, browser and source-contract UI checks.
That run passed 870 root tests, 72 offline membership tests, 41 client tests,
1,458 backend tests, 26 browser tests, 15 source UI tests and 35 catalog cases.
The previously pending implementation run
[40161796216 also passed](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40161796216).
These are engineering checks, not owner acceptance or hosted preview evidence.

The subsequent database-handoff implementation at `47341f6` also
[passed the full workflow](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40163767366).
It includes the revised frontend and increases backend coverage to 1,469 passing
tests; root 870 (three CI-only modules skipped), membership 72, client 41,
browser 26, source UI 15 and catalog 35 also pass. Lint, contracts, types,
build and supervisor containment pass. The 180 focused local handoff/launcher
tests use fake Docker metadata; full eight-service physical integration remains
separate. No online owner preview or human pass is inferred from CI success.

The 25 October browser walkthrough found an obsolete overview card claiming the
queue/evidence screens were still future work. The source now describes the
working read-only alpha and links to the in-app state preview. Sign-in copy now
explains clinical visibility rather than implying reviewer actions exist.
Verification of that revision is recorded in the current progress checkpoint;
a Docker-built local app must receive the revision before it shows new copy.

Fresh local browser validation of the existing running app: 24 of 26 cases
passed on the first single-worker run. Auditor sign-out reached the test's
30-second limit, and mobile Evidence navigation did not reach its destination.
Both cases passed when rerun together (2/2 in 6.6 seconds) without source, timeout
or assertion changes. Record these as intermittent observations, not an initial
clean initial run. A subsequent complete single-worker run passed all 26 cases
in 33.8 seconds. Current web lint and TypeScript checks pass. These local checks
exercise the existing Docker-built revision; CI checks the changed web source.

Owner results above remain pending. Earlier acceptance of the 23 October local
baseline does not automatically accept this round or an online deployment.

## Report and close an issue

Send `O-ID · role · route · steps · expected · actual · browser/window size`.
A screenshot is useful for layout; exclude cookies, tokens, passwords and real
medical records. Engineering reproduces and fixes the issue, reruns the affected
checks, then the owner retests that ID. Keep automated and owner results separate.

This round is accepted when engineering checks pass, all owner rows are reviewed
and blocking issues are fixed and retested. Acceptance means the tested synthetic
scope is usable for the owner. It does not close live-source P2 or a customer MVP.
