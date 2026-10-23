# Product delivery — owner dashboard

Updated 23 October 2026. This page summarizes the current product plan; the
[progress index](progress.md) and phase checklists retain detailed evidence.
Hackathon submission is finished and is not counted as product delivery.

## How much is finished?

**Approximately 35–40% overall; P2 approximately 60%.** These remain rough
planning estimates, not measured effort or a production-readiness score.
Equal weighting of seven phases gives about 37%; later phases differ greatly
in effort. There is no evidence-based calendar estimate for the remaining work.

| Phase | Finished | Still required |
| --- | --- | --- |
| P0: product direction | Approved scope, architecture boundaries and initial policy | Closed |
| P1: foundation | Local frontend/API/database, authentication contracts, tenant membership, CI | Five user interviews explicitly deferred; required before customer rollout |
| P2: read-only workspace | Local synthetic case queue/detail, role-specific clinical visibility, deterministic amounts, evidence presentation, source adapter and extensive isolated security tests | Real operational integration, governed source isolation/projection and authenticated live acceptance |
| P3: reviewer workflow | Not started | Assignment, comments, reviewer actions, concurrency, transactional audit and outbox |
| P4: assessment jobs | Not started | Background assessment, job status, restart/retry safety and validated persistence |
| P5: ingestion/policies | Not started | Secure uploads/extraction and policy version/proposal/approval/regression workflow |
| P6: migration completion | Not started | Parallel reconciliation and retirement of operational prototype dependencies |

## Accepted baseline

- [x] Local Mac/Docker application rebuilt and verified; no separate Linux host needed.
- [x] Owner reports manual checks working and accepts the synthetic sign-in role categories.
- [x] Processor, medical officer and auditor identities are development test personas,
  not customer sign-up categories or production identity management.
- [x] Local automated checks: 26 browser, 15 fake-gateway source API/UI, 41 client,
  213 root and 1,003 backend tests; build/typecheck/lint/contracts pass.
- [x] Product CI for implementation `c6a4b03` passed:
  [run 39895921707](https://github.com/hulagerushikesh/cashlessiq/actions/runs/39895921707).
- [ ] Live-source P2 exit and public release are **not** accepted by these results.

The owner's general report is recorded as manual acceptance of the local
baseline, not an independently observed step-by-step security test report.

## Finish P2 in three coherent bundles

1. **Operational integration.** Select the actual host, encrypted state/key
   custody and unlock mechanism, health policy and durable generation authority.
   Integrate the reviewed controller with actual services and verify readiness,
   shutdown, recovery and closed delivery. Disposable test processes already
   pass; they are not actual service wiring.
2. **Governed source.** Review/approve exact tenant views and financial/clinical
   projection; provision six restricted runtime identities with custody and
   rollback. Verify base-table and foreign-tenant denials. Do not use the human
   Snowflake account as the application's runtime identity.
3. **End-to-end acceptance.** Both tenants and all roles through authenticated
   API/UI; saved/missing/unavailable states, revocation and evidence presentation;
   rerun full regression and remote CI, then review P2 exit explicitly.

Do not add more isolated security primitives unless integration reveals a
concrete defect. Do not start P3 while P2's exit gates remain open.

## Deployment and next decision

The new product currently runs only on this Mac at `http://localhost:3000`.
The public hackathon website is unchanged. Local role-selection authentication
must not be exposed publicly, even for synthetic data.

The next implementation depends on an owner-approved operational target and
custody arrangement. There is no approved external host or hosting budget.
The owner approved preparing the [no-purchase Mac/Docker integration design](../architecture/p2-mac-docker-integration-design.md).
It now specifies topology, proposed manual encrypted-image custody, clock/fence
blockers and one bounded next service-composition batch. The owner subsequently
approved that disposable implementation with a Mac configuration/load check.
The [resource preflight](mac-resource-check.md) currently refuses heavy execution
at elevated memory pressure. The batch is still pending, not re-awaiting approval;
operational custody/activation remains unapproved.
Docker's VM is not an independently trusted production host. Implementation
using actual keys, secret stores or service activation requires separate approval.

Public release additionally needs browser OIDC configuration, hosting, secret
delivery, rollback and deployment approval. Those are not prerequisites for
continued local testing, nor automatically authorized by accepting this dashboard.

Snowflake balance and exact expiry today are unknown. Continued work must not
depend on renewal or payment. Preserve existing private recovery evidence; if
the source is unavailable, use labeled fixtures for development and report
unavailability truthfully. No bulk AI calls or credit-burning work is planned.
