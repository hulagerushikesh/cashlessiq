# Product delivery — owner dashboard

Updated 25 October 2026. This page summarizes the current product plan; the
[progress index](progress.md) and phase checklists retain detailed evidence.
Hackathon submission is finished and is not counted as product delivery.

### Current target: local two-person testing; GCP preparation only — 25 October

Local Docker already supports the current tests. The production-server preview
passed [37 HTTP checks under small limits](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40180267477),
with a final combined service snapshot of about 190 MiB, versus the current
local development web server alone at about 2.4 GiB. This is not a peak-load
measurement or a need for a large server. Full regression at `f28cb66` passed.

The owner selected a dedicated GCP project; `cashlessiq-dev-rush` is created
without billing. The [GCP review package](gcp-private-testing.md) proposes a
2 GiB e2-small VM and initial eight-hour STOP limit, not a customer platform.
The owner chose **keep local testing; GCP preparation only**. The proposed paid
eight-hour test is not authorized. Retain the prepared unbilled project and
files; do not link billing, submit cloud builds or provision cloud resources.
No VM, paid build, registry or cloud app has been deployed.

### Earlier Mac preview preparation — 25 October

The owner clarified that “go live” means a private preview for personal testing,
with engineering and human checks before a customer MVP. The existing local
synthetic workspace responds (login HTTP 200, API ready). Rushikesh confirms
that he has already tested the current app and explained it to two friends.
The general human-testing checkpoint is complete by owner report; individual
[joint checklist](owner-preview-acceptance.md) outcomes are not reported. A
repeat general walkthrough is not a prerequisite for continuing development.
An owner-only online address is not deployed. Rushikesh selected the existing
Mac first, without hosting spend. The [Mac preview package](mac-owner-preview.md)
prepares a separate built web server, owner-password gateway and internal
API/database. Its [37 HTTP checks and runtime acceptance passed](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40165607337)
at `536e1b5`; [full product CI also passed](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40165607340),
including 885 root, 1,469 backend and 26 browser tests. Actual Mac startup is
resource-deferred (pressure 2, high load, less than 2 GiB Docker headroom), and
HTTPS tunnel acceptance remains open. The checksum-verified native tunnel tool
is prepared locally; no tunnel is running. Ask before new spend/payment actions.

Synthetic owner testing can proceed before governed live-source P2 exit,
customer interviews or later reviewer-write features. Keep those scopes separate.
The revised frontend and database-resource handoff at 47341f6
[passed full CI 40163767366](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40163767366):
1,469 backend, 26 browser, 15 source UI, 870 root, 72 membership, 41 client and
35 catalog tests; lint/contracts/types/build and containment also pass. Fresh
local browser validation passed all 26 cases after an initial intermittent
24/26 run and unchanged focused rerun. Owner testing is recorded separately
from those automated checks. The local Docker-built app has not received the
new copy; no Mac rebuild/start occurred.
The 35-resource launcher handoff is tested with real journals/fake metadata;
full Linux resource admission/eight-service physical integration remains open.

The earlier full [product CI at 6cb02c1 passed](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40161931233),
including the API/browser/source-contract checks. The previously pending
[40161796216 passed too](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40161796216).

### Membership database TLS and clean shutdown accepted — 25 October

[Live Linux CI 40161796204](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40161796204)
passed all four real-container cases at 4b385d0 (33.27-second test phase).
The new case uses the actual volume/initdb/bootstrap helpers and real canonical
membership factory/store on a fresh, explicit internal bridge. It proves TLS
1.3, all six fictional profiles, six cross-tenant absences, nine SQL privilege
denials, bad hostname/CA/missing-CA/password and ambient-setting denials,
plaintext rejection, unauthorized-source HBA rejection, and clean SIGINT stop
with a fresh read-only stopped-cluster/completion probe afterward.

The bridge passes the existing collision gate using real bounded Linux routes
and Docker network snapshots before creation. No host ports, external service,
real credentials or local Docker mutations are involved. This is member-DB edge
acceptance; full allocator/headroom, eight-service readiness/revocation/
containment and operational recovery/custody remain open. P2 is still open.

Negative probes now fail if a connection was accepted, even if cleanup then
fails. Assertions sit outside redacting contexts; database failure cannot become
membership absence. Same-issuer wrong-CA tests recognize a closed set of
certificate/RSA signature failures, while unrelated errors remain failures.
Only fixed stage/reason labels may appear in diagnostics. All 870 root tests
pass (three CI-only modules skipped), all 72 offline membership tests pass,
and Ruff/isolated wheel checks pass. Test probes stay outside default packaging.
The preceding [run 40161677145](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40161677145)
also passed all four cases at cda2b94.

Full product CI passed fd67973 (40160954993), f0c552d (40161164066) and
6bca3a3 (40161313431) and 0979456 (40161499895). The final implementation's
[broader CI 40161796216](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40161796216)
subsequently passed, as did the 6cb02c1 documentation checkpoint (40161931233).
No paid action or Snowflake query was performed. Ask before any new spend or
payment-related action. Next: Linux resource/headroom observation and the
integrated eight-service startup/readiness/shutdown batch.

**25 October execution decision:** move disposable integration work to standard
GitHub-hosted Linux CI, using synthetic inputs. The Mac is optional as a test
host; its memory-pressure gate must not block Linux image validation. See the
[CI integration sequence and spending boundary](../architecture/p2-ci-integration-plan.md).
All three preceding product CI runs, including ea18e45, passed. The new manual
helper image build/runtime smoke also
[passed on Linux](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40158980750)
at df213a7: both images built and passed restricted identity/binary checks.
Real initialization/bootstrap subsequently passed in
[run 40159814345](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40159814345)
at add3318: three cases cover successful completion, retained SQL/catalog
failures and denied repeat attempts, using fresh volumes and separate probes.
This also identified/fixed Docker's canonical CAP_CHOWN metadata spelling.
All 854 local root tests and repository Ruff checks pass (two CI modules skip
locally). Follow-up 08c8caf tightens test-frame redaction and disables cache
export; its [fresh lifecycle run passed](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40159947450).
Full product CI passed c1fead5 (40159627351); the broader run for 08c8caf is
still pending at this checkpoint. TLS readiness and full composition
acceptance remain pending; this CI harness is not the full allocator/recovery owner.
The owner reports adding Snowflake payment details and requires approval before
payment-related actions or new spend. No paid source access is authorized.

**23 October delivery focus:** the [next-demo and validation plan](next-demo-and-validation.md)
separates a supervised synthetic walkthrough (possible before live P2 exit) from
a public/real-data pilot. Start owner-led workflow conversations now; retain all
deployment and phase gates. The next engineering milestone is integrated
disposable container acceptance, not more unrelated security primitives.

**24 October follow-up:** DB material installation/probing now has a bounded,
journaled coordinator with separate volume authority and UID/GID 10002.
The explicit allocator now includes DB material/data volumes, with the real
resource journal tested through the material helper handoff using fake daemon
metadata. Empty DB data-directory preparation and its separate nonroot probe
are now implemented/tested offline. Nonroot initdb coordination and a separate
structural cluster probe are also implemented with offline fixtures. Actual
PostgreSQL image packaging now has an unbuilt candidate plus account/binary
preflight. Private-socket schema bootstrap and its separate structural probe
now have offline implementation/tests. Image build/inspection, physical
initialization/bootstrap, launch/readiness and
physical lifecycle acceptance remain pending; the host gate still defers Docker. Phase
estimates are unchanged.

### Bootstrap catalog gate — 24 October

Bootstrap now runs a fixed read-only catalog assertion after the schema/seed
transaction and before shutdown/completion. It requires a login-only SCRAM role
with no role memberships, CONNECT without CREATE/TEMPORARY, ops USAGE without
CREATE, no public-schema access, exactly the three expected ordinary tables
owned by postgres without RLS, and only the expected column SELECT privileges
without grant options. Missing columns, extra columns/tables and effective
PUBLIC/role grants fail closed. SQL uses a fixed pg_catalog search path and
3-second statement timeout; diagnostics remain suppressed and failures retain
ATTEMPTED. This is an admin catalog check, not a membership TLS connection or
exact seed/schema-type proof. The separate structural probe stays structural.

A dedicated PostgreSQL 16 CI service tests the valid generated bootstrap plus
24 privilege/schema mutations, plus an actual SET ROLE membership query over
all six profiles and nine permission-denied operations (SQLSTATE 42501).
All 35 live PostgreSQL cases passed in the database-catalog job of
[CI 40107013580](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40107013580)
at commit 2e9db27. The broader foundation job also passed. This uses local
admin SET ROLE, not password/TLS authentication.
Local runs skip that opt-in destructive suite;
it accepts no caller DSN and requires the dedicated GitHub Actions opt-in.
The service does not validate the unbuilt Mac helper image or physical owner.
The PostgreSQL [privilege inquiry reference](https://www.postgresql.org/docs/16/functions-info.html)
defines the effective table/column checks. Prior checkpoint CI 40103096427 passed.
Fresh local headroom remains DEFER (pressure 2, less than 2 GiB Docker headroom,
four existing containers); no local image build or PostgreSQL process was run.
All 848 local root tests and repository Ruff checks pass; the dedicated CI
integration module skips locally. The live catalog job also passed at the
preceding implementation commit 170bdb4 (25 cases before role-operation tests).
P2 remains open; image pinning, membership TLS readiness and full containment
acceptance remain pending. No deployment, paid source access or P3 activation.

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

Operational activation depends on an owner-approved target and custody
arrangement. Disposable synthetic integration can proceed on standard Linux CI
under the [25 October plan](../architecture/p2-ci-integration-plan.md).
There is no approved paid external host or hosting budget.
The owner approved preparing the [no-purchase Mac/Docker integration design](../architecture/p2-mac-docker-integration-design.md).
It now specifies topology, proposed manual encrypted-image custody, clock/fence
blockers and one bounded next service-composition batch. The owner subsequently
approved that disposable implementation with a Mac configuration/load check.
Lightweight preparation now includes seven independent authority-state fixtures,
a journaled launcher/controller bridge, disposable DB material generation and a
shared eight-logical-role, one-process TLS test world. Both tenants/all
three roles and failure/cleanup paths are exercised without live source access.
This is not the separate-container/supervisor acceptance batch or a deployment.
The [resource preflight](mac-resource-check.md) currently refuses heavy execution
at elevated memory pressure. The batch is still pending, not re-awaiting approval;
operational custody/activation remains unapproved.
Docker's VM is not an independently trusted production host. Implementation
using actual keys, secret stores or service activation requires separate approval.

Public release additionally needs browser OIDC configuration, hosting, secret
delivery, rollback and deployment approval. Those are not prerequisites for
continued local testing, nor automatically authorized by accepting this dashboard.

The owner reports adding Snowflake payment information on 25 October; account
status, balance and current resource usage have not been independently checked.
Ask before payment-related actions or new spend, including warehouse/query and
AI/serverless usage. Continued development uses synthetic fixtures without
depending on paid access. Preserve existing private recovery evidence; if
the source is unavailable, use labeled fixtures for development and report
unavailability truthfully. No bulk AI calls or credit-burning work is planned.
