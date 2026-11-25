# CashlessIQ engineering overview — 25 November 2026

The private workflow MVP is built and has already been deployed and tested on
GCP. The integrated Snowflake agent MVP is still unfinished. Most recent work
strengthens that integration's execution and deployment foundation; it does not
add new visible workflow screens or update the stopped GCP deployment.

| Area | Current position |
| --- | --- |
| Core app | Built: Next.js, FastAPI, PostgreSQL, typed contracts, seven roles and tenant-scoped access. |
| Human workflows | Built: requests, queues/search, assignment, queries/corrections, referral, final decision and reopening. |
| Policies | Built for synthetic testing: PDF intake/quarantine, extraction revisions, rules/clauses, regression, second-person approval, activation and rollback. |
| Operations | Built and rehearsed: durable background jobs, audit/outbox, encrypted 22-table backup/restore and saved workflows after restart. |
| Private deployment | Existing GCP e2-small preview and stable test hostname have been tested. The deployed build remains `7940886` / `0003_mvp`; newer work is in source/CI. |
| Agent foundation | Synthetic execution passes installed Linux service journeys, restricted database access, single-attempt controls, receipt retention, retirement and restored-state checks. |
| Live agent integration | Pending: governed current request/policy data, Snowflake tools/search/provider adapter, runtime credentials, app-to-executor connection and live comparison acceptance. |
| Customer readiness | Later: production identity, real-data storage/retention, malware scanning, monitoring/support and other customer launch gates. |

The latest completed
[product workflow](https://github.com/hulagerushikesh/cashlessiq/actions/runs/45642371334)
passed all nine jobs, including installed service journeys, runtime dependency
installation and the product foundation/browser checks. Recent preparation also
packages exact committed source and 32 hash-locked Linux runtime wheels.
Interpreter/build-tool pins pass both Ubuntu package and service-journey jobs.
The inactive Debian 12 artifact rehearsal also passes installation, source
verification and owned cleanup. It does not activate the agent or update GCP;
Debian systemd and production installation still need acceptance.
Release preparation now stages exact Git source for both first-party wheel builds
and their byte verification, excluding dirty/untracked or newer checkout content.

## How close is a private live MVP?

For testing requests, policies and human review, that milestone has already been
reached. The next fresh-build preview requires migration/restore checks, an
approved cloud build and a short VM testing window, followed by fixes discovered
during joint testing. Live AI can remain disabled for that preview. The stable
address is `cashlessiq-test.hulage.in`; it serves the app only while the preview
and its tunnel are running. The public `cashlessiq.hulage.in` demo is separate.

For a live agent-enabled MVP, the remaining work has three concrete gates:

1. Finish the release runtime and inactive installation, with protected private
   inputs, separate identities and retained receipt storage on the target host.
2. Bind current synthetic app requests/policy versions to governed Snowflake
   data/tools and connect the bounded provider adapter and executor. Confirm
   citations, amounts, usage, timeouts and interrupted-call behavior.
3. Rehearse migration/restore, deploy an approved integrated build and jointly
   compare agent suggestions with deterministic results and human decisions.

The core workflow milestone is complete; the agent integration milestone is in
progress; customer launch is a later milestone. There is no weighted backlog
supporting an honest overall percentage. The remaining integration is substantial
enough that a fixed launch date would be speculative before source/provider
acceptance. A fresh private workflow test does not depend on finishing that work.

## Next action and owner involvement

Continue release artifact preparation and inactive installation, then the current
source/provider integration. Interpreter/build-tool pins and Debian artifact
compatibility have passed CI; target-host service acceptance remains open.
Keep local Docker off and cloud resources inactive during ordinary coding.
No owner action is required for this packaging step.
Before paid cloud/provider testing, agree the exact spend/window and owner
availability. Source access or mapping decisions may need owner input earlier;
request those when a concrete requirement is identified.
