# CashlessIQ engineering overview — 3 November 2026

The private synthetic application is implemented, has run on GCP, and has been
tested by the owner and automation. The current engineering work connects the
original Snowflake intelligence to the new application's requests and policies.
That integration is not yet active in the deployed application.

## What is built

| Area | Working capability |
| --- | --- |
| Application | Next.js web UI, FastAPI, PostgreSQL, typed API contracts, seven roles and tenant-scoped access |
| Requests and review | Intake, queue/search/pagination, priority/SLA, assignment, comments, queries/corrections, referral, final human decision and reopening with conflict protection |
| Policies and uploads | Synthetic PDF extraction/quarantine, input revisions, clauses/rules, regression checks, second-person approval, activation and rollback |
| Background work | Deterministic financial assessment, durable jobs, leases, bounded retries, failed-job handling, audit/outbox and local analytics projection |
| Private testing | On-demand GCP e2-small deployment, stable private hostname, owner access gate, automatic STOP and cumulative daily-use tracking |
| Recovery and verification | Encrypted 22-table backup/restore, saved workflows after restart/restoration, browser journeys and automated API/permission regression |

The original Snowflake prototype already demonstrates extraction, policy search,
deterministic tools and agent orchestration. Its old case/policy identifiers and
stored decisions do not automatically match the new PostgreSQL workflows.

## Where the recent engineering effort went

Most recent changes strengthen the agent foundation rather than add visible
pages: strict money/evidence validation, exact snapshot/version binding,
separate restricted clinical and custody database commands, bounded spending
reservations and deadlines, single-attempt execution, private comparison results,
conservative recovery, restored-state checks, permission auditing, credential
retirement, and independently authenticated receipt processes. These are tested
with synthetic data and fake transport; they do not establish live AI parity.

The accepted code `e973c4c` passes
[full product CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41681911155)
and [private-preview CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41681911168),
including eighteen MVP browser journeys and matched encrypted restore. Test
counts are regression evidence, not a completion percentage.

## What remains, in order

1. **Finish agent operational acceptance.** The separate receipt process, real
   restricted PostgreSQL logins, bounded fake child, publication and recovery now
   pass eleven combined disposable cases. Complete combined restored-state and
   operational credential/custody acceptance next.
2. **Current Snowflake source and provider integration.** Bind exact current
   requests/policy versions, governed tenant data, tool/search definitions and
   citation content; verify supported submission, status, usage and timeout
   behavior. Wire the bounded agent job/status and authorised comparison API/UI
   into the product; those inactive test components are not yet an app feature.
   Review runtime credentials and a bounded spend window before live calls.
   Human approval remains the final decision.
3. **Deploy and jointly test the integrated build.** Rehearse migration and
   restore, build an approved image, start the existing VM for an approved short
   window, and compare agent suggestions with deterministic and human results.
4. **Customer readiness, later.** Production sign-in, real-data storage/retention,
   malware scanning/OCR as needed, monitoring/support, domain-owner validation,
   authorised external analytics and parallel reconciliation before retiring
   prototype paths. Marketing and SEO are outside this engineering checklist.

The synthetic workflow milestone is complete; the governed live-agent milestone
is unfinished; customer release is a later milestone. The old 35–40% read-only
estimate is obsolete. A precise overall percentage is not supported by a weighted
backlog, so none is claimed. The main remaining engineering block is integration
and operational acceptance, followed by fixes revealed in joint testing.

The deployed revision remains `7940886`/schema `0003_mvp`; newer inactive agent
work is in source and disposable CI. GCP is stopped and local Docker is off.
The next live test requires approved charges/window and the owner's availability;
ordinary engineering needs neither a running VM nor a larger VM.
