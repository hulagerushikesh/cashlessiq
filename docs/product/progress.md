# CashlessIQ product delivery checklist

Last updated: 29 October 2026
Current engineering scope: **synthetic MVP workflows (M3–M5), private testing**.
Governed live-source P2 and production gates remain separate.

Current operation: Docker Desktop stays shut down for ordinary engineering;
offline checks and disposable CI provide verification. GCP remains preparation
only, pending explicit spend approval. The owner selected at most four hours of
active testing per day with immediate shutdown afterward. A read-only instance
checker now verifies the reviewed four-hour STOP configuration and completed VM
shutdown when that run is eventually approved. The
[delivery dashboard](delivery-status.md) records current evidence and the
[operator guide](../../deploy/gcp-preview/README.md) records the run sequence.
The localhost and eight-hour descriptions below are historical checkpoints.

### Daily usage accounting accepted — 29 October

The preview handoff adds persistent operator receipts for starts/completed stops
and cumulative four-hour usage across restarts in Asia/Kolkata. The report gives
the remaining allowance and earlier stop deadline, while unclosed sessions keep
counting. Missing STOP receipts and replaced/mixed-evidence histories fail without
resetting prior usage. It is an operator aid, not cloud-enforced daily limits or
a bill estimate. The operator guide and Saturday sequence include the commands;
no Docker or paid GCP action was started. Revision `3735e6f` passes both
[full product CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40910782084)
and [private preview CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40910782236):
1,018 root checks, 1,522 API checks, all 16 MVP browser journeys, encrypted
17-table recovery, browser reopening after restart/fresh-volume restore and
owned cleanup, plus the existing contracts/types/lint/build/containment checks.
All 88 focused local checks pass. The refreshed archive's checksum and fresh
temporary extraction pass the checker and historical usage CLI; the temporary
ledger was removed. The delivery dashboard records its exact checksum.

### Saturday build preparation accepted — 29 October

The owner will test on Saturday, 31 October. Revision `1adafa8` adds bounded
progress updates for request assessments, supporting PDFs, policy regressions
and policy wording while keeping forms and action versions mounted. Specific
background jobs have inspect/retry pages; metadata reads avoid full job payloads
and deprecated SQL. Successful-save browser checks wait for navigation before
looking for a new assessment.

Both [full product CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40906659813)
and [private preview CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40906659753)
pass. This includes all 16 MVP browser checks, 51 client checks, 1,522 API checks,
encrypted 17-table recovery, browser reopening after restart/fresh-volume
restore and owned cleanup. The [Saturday handoff](saturday-testing-2026-10-31.md)
records the archive checksum, verification and remaining actual-host acceptance.
No Docker or paid cloud resource was started. GCP remains preparation only until
explicit approval of the spend and testing window.

### Synthetic MVP workflows implemented locally — 25 October

The owner's expanded scope is now implemented for fictional private testing:
reviewer commands and immutable audit/outbox, durable assessment jobs and retries,
PDF quarantine/extraction, versioned fact correction, two-person policy approval
and activation, access administration and local reporting. See the
[workflow and recovery guide](synthetic-mvp-testing.md).

Final code `7c73d69` passes [full product CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40204698447):
913 root tests, 1,519 API tests, 72 membership checks, 35 database-catalog checks,
41 client tests, 26 existing browser checks, 15 source UI checks and two full MVP
browser checks, plus contracts/types/build/containment. The separate
[production preview](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40204698347)
passes all 37 owner-gate checks and the full MVP browser flow under constrained
container limits. Mobile review/request layouts, cached-identity revocation,
chunked request limits and transactional outbox rollback are covered.


The current localhost app uses the existing API/web images with read-only source
and locked pure Python/JavaScript dependencies. API readiness passes at migration
`0003_mvp`; the API and local worker share a 512 MiB container. Database and Redis
incarnations are unchanged. The owner-only pre-MVP backup was successfully
restored in a temporary database, migrated forward and seeded for all seven
roles, then the temporary database was removed. No second stack or heavy build
was started. Earlier local extraction failures were caused by isolated parser
imports not seeing the development dependency mount; the parser now receives
only that explicit trusted module path, with no database/auth environment.

The full synthetic eight-service source chain also
[passed physical Linux acceptance](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40201098649),
including fresh membership revocation/restore, outage denial and owned cleanup.
Operational source custody and real external gateways remain unactivated.
GCP billing, paid service use and deployment remain deferred by owner decision.

**25 October scope expansion:** the owner explicitly selected full MVP workflows,
including reviewer actions, background jobs, uploads and policy management, before
GCP deployment and joint testing. Continue that synthetic implementation while
keeping governed live-source/production activation gates separate. GCP remains
preparation-only; no billing linkage or paid service use is authorized.

The frontend production dependency audit found `fast-uri` 3.1.8 through AJV.
The lockfile now resolves the compatible patched 3.1.9; all 41 client contract
tests pass and a fresh `npm audit --omit=dev` reports zero known vulnerabilities.
The [maintainer advisory](https://github.com/advisories/GHSA-w74x-v6f9-j3xg)
identifies 3.1.9 as patched. The local web runtime now uses a checksum-verified read-only 3.1.9 mount;
the underlying image is unchanged and fresh builds use the lockfile. This scan is not a claim of zero application risk.

This is the current-status index. The migration plan defines sequence; phase
checklists contain verification evidence. Earlier entries in those checklists
are historical checkpoints, not the latest status. Hackathon submission is done;
demo-video work is not part of this product plan.

[Short owner dashboard: completed work, remaining phases and next decision](delivery-status.md).

**Owner decision — 25 October:** keep local testing; GCP preparation only.
The owner declined the proposed paid eight-hour test. Billing linkage, cloud
builds, registry storage and VM deployment are not authorized. Keep the existing
unbilled GCP project and prepared files for a future decision; continue current
application testing locally without a second complete stack.

## Historical engineering checkpoints

The entries below retain earlier evidence and scope restrictions. The current
synthetic MVP scope and delivery summary above supersede their earlier P3–P5
status and percentage estimates; the spend restrictions still apply.

### Local review navigation refreshed — 25 October

**Engineering continuation:** full allocator/private-helper physical acceptance
now [passes on disposable Linux CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40187526295)
at `f9807d7`: 18 internal networks, 17 volumes, eight material bundles, seven state
stores and database material/data/initdb/bootstrap through 19 helper pairs;
exact owned teardown and reopened journal checked. The shared module/type and
private-frame handoff defects are fixed. All 913 root tests and 198 focused API
tests pass locally (the physical test skips outside its dedicated runner).
This is the earlier allocator checkpoint. The complete physical chain now passes
as recorded above; governed source and operational custody remain open. See the [integration evidence](../architecture/p2-ci-integration-plan.md).

Filtered queue → case → queue navigation now retains the reference,
recommendation and page. Unknown case IDs show a recovery link without a
substitute record. Implementation `8aa2511` passed
[full product CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40185775870)
and the [37-check production preview](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40185775770).
The existing local development web container was then refreshed without an image
build or pull, using a read-only mount of `apps/web/src`. Its API, database and
Redis container IDs are unchanged, and all 26 browser checks passed locally in
34.7 seconds with one worker. These source changes are visible on localhost;
dependencies/build configuration still require rebuilds. No duplicate stack,
cloud deployment or new spend. P2's governed-source/integration exits remain open.

### Two-person runtime verified; dedicated GCP target prepared — 25 October

The owner clarified that this is private development/testing before an MVP,
with hardly two testers. Local Docker is sufficient for current testing; a
second local app/database stack is unnecessary. A read-only snapshot found the
current development web server at about 2.4 GiB versus API 82 MiB, PostgreSQL
38 MiB and Redis 10 MiB. This is not evidence that the application needs a large
server; the development compiler and a duplicate stack drove the local concern.

The built preview at `f28cb66` passed [37 HTTP checks under explicit small-runtime limits](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40180267477).
Final observed usage: web 74.13 MiB, API 73.82 MiB, PostgreSQL 30.03 MiB and
gateway 11.53 MiB — about 190 MiB combined. These are post-check snapshots,
not peak-load measurements. Steady container ceilings total 1,152 MiB; builds
remain separate. [Full product regression 40180267473 passed](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40180267473).
The first bounded run found a Compose JSON string/number mismatch in the
configuration assertion; it was corrected without changing the resource limits.

The owner chose a dedicated GCP project. `cashlessiq-dev-rush` now exists as
CashlessIQ Private Test, and billing was independently confirmed disabled. The
CLI default Atlas RAG project was not changed. [The reviewable GCP plan](gcp-private-testing.md)
proposes one e2-small/2 GiB VM, 20 GiB standard disk, private app/backend and
an initial eight-hour automatic STOP. Full-month base estimate is about
US$16.68 before variable usage/tax; the initial eight-hour VM/IPv4 estimate is
about US$0.18 plus build/storage. Financial approval is still required before
billing linkage, remote builds, image storage or VM provisioning. No paid
resources, Snowflake queries or customer activation were performed.

### Mac owner-preview package accepted in CI — 25 October

Rushikesh chose the existing Mac first, without hosting spend. The separate
[owner-preview package](mac-owner-preview.md) now builds a non-root Next.js
standalone server, requires an owner password on every gateway route and keeps
web/API/database ports unpublished. Only the gateway publishes 127.0.0.1:3080;
backend services stay on an internal network. Independent generated secrets and
a separate database volume preserve the existing localhost:3000 app.

Implementation `536e1b5` passed both [private-preview CI 40165607337](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40165607337)
and [full product CI 40165607340](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40165607340).
The preview run passed **37 HTTP checks** covering anonymous/wrong-password
rejection, protected built assets, all three roles, origin rejection, Secure
session-cookie headers, logout and published-port restrictions. Non-root
runtime and absence of web source files in the standalone image also passed.
Full regression: **885 root tests** (three CI skips), 72 membership, 41 client,
1,469 backend, 26 browser, 15 source UI and 35 catalog cases; lint, types,
contracts, build and supervisor containment passed. All 15 new local preview
policy tests, web lint and TypeScript checks passed as well.

CI caught and fixed Caddy executable capability compatibility, gateway entry
network publication and private response headers on authentication errors.
The successful final run includes those fixes and confirmed disposable cleanup.
These HTTP checks use an explicit HTTPS origin through a loopback gateway;
they do not prove end-to-end browser TLS or a live online address.

Actual Mac startup remains deferred by a fresh read-only resource check:
pressure 2, one-minute load 12.18 on eight CPUs and approximately 1.29 GiB
Docker memory headroom (below the required 2 GiB). No Mac containers were
created, rebuilt, stopped or changed. Existing login still returns 200 and API
readiness is ready. No Snowflake query, purchase, payment action or remote
exposure occurred. The next delivery check is admitted Mac startup followed by
the authenticated HTTPS tunnel, exact origin, remote denial and stop checks.
This does not close the separate governed-source/eight-service P2 gates.

### Private owner preview before a customer MVP — 25 October

The next integration handoff is repaired offline: explicit database mode accepts
the fully observed 35-resource allocator journal instead of expecting the older
33-resource batch. It refuses absent/header-only authority or a mismatched batch
and rechecks both database volume identities/options before app creation. All
180 focused launcher/resource/journal/controller/engine tests pass (11 new cases),
with Ruff/format checks. These use real private journals and fake Docker metadata;
full Linux headroom and physical eight-service lifecycle acceptance remain open.
The full implementation at 47341f6 subsequently
[passed product CI 40163767366](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40163767366):
870 root (three CI skips), 72 membership, 41 client, 1,469 backend, 26 browser,
15 source UI and 35 catalog tests, plus lint/contracts/types/build/containment.
The owner-preview copy at 59f42d8 also passed its full run (40163582801).

“Go live” now explicitly means personal owner testing, with engineering and human
acceptance before a customer MVP. The [joint checklist](owner-preview-acceptance.md)
records the test scope and expected screens. Rushikesh now confirms he has
already tested the current app and explained its state to two friends. The
general local human-testing checkpoint is complete by owner report; per-row
results and independent feedback from the friends are not reported. Do not
require a repeat general walkthrough before continuing development. Local login
returns 200 and the API is ready. Owner-only online hosting/access remains to be
configured; no paid action or deployment occurred. This synthetic preview does
not require closing the separate governed-source or later reviewer-write gates.
Full [product CI 40161931233 at 6cb02c1 passed](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40161931233);
the formerly pending 40161796216 and 40161676816 also passed.

The engineering walkthrough exposed stale overview/sign-in descriptions. The current
web source describes the working read-only alpha, links directly to its state
preview and describes role-specific clinical visibility. Local browser checks
passed 24/26 initially; the two intermittent sign-out/mobile-navigation cases
passed unchanged on a focused rerun (2/2, 6.6 seconds). A subsequent complete run
passed all 26 cases in 33.8 seconds. Web lint and TypeScript pass.
The local Docker-built app has not been rebuilt for the copy change;
changed-source CI acceptance is recorded separately when available. No human
acceptance is inferred from these checks.

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

### Real database helper acceptance on Linux — 25 October

The [manual image/lifecycle run 40159814345](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40159814345)
passed all three real-container cases at add3318 (59-second job). Fresh named
volumes now exercise actual material install/read-back, UID/GID 10002 data
preparation/probe, PostgreSQL 16 initdb/structural probe and private-socket
schema/grant/catalog bootstrap. Valid completion is independently read back;
SQL and catalog failures retain ATTEMPTED. Fresh containers deny repeat initdb
and bootstrap, preserving the completed/failed marker and stopped cluster.

Live Docker inspection exposed canonical CAP_CHOWN spelling. The shared helper
coordinator accepts only that exact alias for the existing CHOWN singleton;
six regression cases reject privilege expansion or ambiguous capability values.
All 854 local root tests pass, with two CI-only modules skipped; repository Ruff
checks pass. Follow-up 08c8caf redacts request-frame repr/tracebacks and disables
uv cache export; [run 40159947450](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40159947450)
also passed all three real-container cases. Full product CI passed c1fead5
(40159627351); the broader run for 08c8caf is still pending at this checkpoint.

The CI harness checks exact images, users, mounts, network-none, capability and
resource settings plus stopped exit state. It removes only its own acknowledged
labeled CI resources. It is not full journal/allocator recovery acceptance.
Membership TLS, Linux full-allocator observations and integrated eight-service
readiness/containment remain open. No Mac Docker mutation or paid access.

### Linux CI alternative and spending boundary — 25 October

The owner requested an alternative to repeated Mac memory-pressure deferrals.
Use standard GitHub-hosted Linux CI for disposable synthetic integration;
Mac execution is optional and operational hosting remains a separate decision.
The public repository qualifies for free standard runner compute under GitHub's
documented terms. The [concrete sequence](../architecture/p2-ci-integration-plan.md)
started with a new manual, time-bounded cluster/bootstrap image smoke;
[run 40158980750 passed](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40158980750)
at df213a7 on Ubuntu 24.04 in 27 seconds. Both image recipes built and passed
configuration plus restricted account/binary runtime checks against exact IDs.
That initial run was image smoke only; real initialization/bootstrap evidence
is recorded in the newer checkpoint above. TLS/full composition remain open.
No larger runner, paid host, artifact upload or registry push
is introduced by that workflow. Linux route/headroom collectors and full
container lifecycle/TLS acceptance still need implementation.

All preceding product CI runs passed (40107078653, 40107013580, 40106920950).
The owner reports adding Snowflake payment details; ask before payment-related
actions or new spend. Account status and usage have not been independently
checked. This decision does not authorize paid queries or alter P2 exit gates.

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

### Private-socket schema bootstrap — 24 October

Added an explicit one-shot bootstrap helper and journaled two-container
bootstrap/structural-probe coordinator. It requires the initialized cluster and
verified material, durably records an exclusive ATTEMPTED marker inside PGDATA,
then starts the owned PostgreSQL process with TCP listeners disabled. A new
0700 Unix-socket directory lives inside the writable data volume; the helper
root filesystem stays read-only and container networking stays `none`.

A bounded read-only `SELECT 1` connection probe may retry connection failures.
Database creation and the generated schema/grant/seed transaction run once via
psql stdin with `--no-psqlrc`, `--no-password` and `ON_ERROR_STOP=1`; no credentials
or SQL diagnostics are emitted. The generated material supplies the fixed local
admin HBA rule. This private admin probe is not membership TLS/grant acceptance.
The owned supervisor must exit zero after SIGINT fast shutdown before a
BOOTSTRAPPED completion marker can be written. Failed SQL/startup/shutdown and
partial markers remain ineligible for retry; forced shutdown retains failure.
The outer owner still owes invocation-wide watchdog and container containment.
See the PostgreSQL 16 [psql](https://www.postgresql.org/docs/16/app-psql.html),
[connection](https://www.postgresql.org/docs/16/runtime-config-connection.html)
and [shutdown](https://www.postgresql.org/docs/16/server-shutdown.html) references.

The separate read-only probe checks material, cluster structure and the exact
completion marker; it does not inspect live catalogs or independently prove
SQL/grant correctness. A bootstrap image wrapper requires an explicit built
cluster base and inherits its nonroot runtime. Neither image has been built or
pinned locally. The preceding runtime checkpoint passed CI (40100083540).
Fresh host preflight remains DEFER (pressure 2, load 4.97, less than 2 GiB Docker
headroom, four existing containers); no PostgreSQL/container process was run.

Offline tests cover marker retention/tampering, no duplicate bootstrap, private
SQL transport, startup/SQL/shutdown failures, read-only probe retry limits and
the shared coordinator's daemon uncertainty matrix. All 847 root tests passed;
Ruff and `git diff --check` passed. Physical image acceptance,
actual SQL/catalog validation, service startup, membership TLS/grant readiness
and integrated lifecycle acceptance remain pending.

### PostgreSQL 16 image candidate and runtime preflight — 24 October

Added `scripts/Dockerfile.database-cluster-test` with a narrowly allowlisted
build context, Python 3.11 and PGDG PostgreSQL 16 server/client packages.
The recipe disables automatic Debian cluster creation and package service
starts, requires an empty package data directory, and creates the real
`ciqdb` account at UID:GID 10002:10002. It declares no volumes, exposed ports,
healthcheck or service startup. Its default entrypoint remains the explicit
cluster helper; it is **an unbuilt candidate, not a pinned acceptance image**.
Repository/package inputs float; the physical owner must build, inspect and
pin the resulting image ID before use through the existing strict coordinator.
The package source follows the [official PGDG Debian instructions](https://www.postgresql.org/download/linux/debian/).

A closed runtime preflight runs at image build time and before cluster CLI
request parsing or volume mutation. It verifies the current OS account,
root-owned non-writable regular binaries at the fixed PostgreSQL 16 paths,
and successful major-version output for initdb, postgres and psql. Each command
has a five-second timeout, fixed environment and redacted failure diagnostics.
This establishes package/account compatibility only; it does not prove schema,
TLS, grants, readiness or process containment by the outer owner.

Both preceding commits passed CI (40080642100 and 40080314225). The fresh host
gate still returns DEFER: memory pressure level 2 and less than 2 GiB estimated
Docker headroom (load 3.66, four existing containers). No image build or database
process was attempted. Physical build/inspection, schema bootstrap, bounded
service startup, authenticated TLS/grant probes and full lifecycle acceptance
remain pending. Offline validation: all 802 root tests passed, including 13
new runtime/CLI rejection cases; Ruff and `git diff --check` passed.

### Nonroot PostgreSQL cluster initialization — 24 October

Added an explicit PostgreSQL 16 `initdb` helper using UID:GID 10002:10002,
verified DB-only material and the previously prepared empty data directory.
It durably writes an exclusive ATTEMPTED marker before spawning; any partial,
failed or interrupted attempt remains ineligible for retry/adoption. Fixed
arguments use a private password file, reject local/host authentication during
initialization, enable checksums and retain partial initdb files. The child has
a fixed environment, discarded diagnostics and a 30-second wait with owned
process-group termination on timeout; the outer owner still owes its watchdog.
[PostgreSQL 16 initdb option reference](https://www.postgresql.org/docs/16/app-initdb.html).

The separate probe checks the invocation marker, version, ownership/modes,
control-file shape, absence of a PID file and fresh material hashes. This is
**structural read-back only**, not catalog integrity, stopped-process proof,
schema/grant bootstrap or authenticated readiness. No PostgreSQL binary was run
in this checkpoint; command/process fixtures and temporary files are offline evidence.

The journaled coordinator now checks both exact volumes, mounts material
read-only in both containers, allows data writes only during initialization,
and runs both modes nonroot without added capabilities. Existing app/material/
state helper contracts retain their defaults. Unknown outcomes fence and remain
for explicit containment/review.

Validation: all 789 root tests passed; Ruff and diff checks passed. The earlier
allocation commit CI passed; the data-directory commit CI was still running
at this checkpoint.

Host gate remains DEFER (pressure 2, load 9.06); no Docker build/start or settings
change. Still owed: PostgreSQL image packaging/digest inspection, physical initdb,
closed schema/bootstrap, bounded service startup, TLS/grant probes and full
lifecycle acceptance. Product phase estimates are unchanged.

### Empty DB data directory preparation — 24 October

Added a DB-only helper that exclusively creates `pgdata` inside the allocated
data volume, sets both directories to mode 0700 / UID:GID 10002:10002, and leaves
partial failures intact. A separate nonroot, read-only probe requires exactly
that empty directory and ownership/mode contract. Existing contents, symlinks,
wrong ownership/modes, duplicate request fields and wrong CLI identities deny.
This is empty-directory preparation, **not PostgreSQL initdb or readiness**.

The bounded coordinator requires the observed data-volume resource journal,
uses separate preparation/probe containers and exact image/mount inspection,
and retains the existing one-attempt fencing/containment behavior. An offline
allocator-to-helper test covers the actual resource journal handoff. The image
recipe is a candidate, not built or digest-pinned acceptance evidence.

Validation: full root suite 741 passed; after adding the data-volume handoff
case, all 79 data-helper/resource checks passed. Ruff and diff checks pass.
These are host filesystem and fake daemon checks, not mounted Linux proof.

Host recheck: pressure 2 and one-minute load 14.70; Docker acceptance still
DEFER. No containers/settings changed. Next: pinned PostgreSQL packaging,
nonroot cluster initialization, bounded startup, TLS/grant readiness and physical
lifecycle acceptance. Phase estimates unchanged.

## Phase scoreboard

| Phase | Status | Exit gate |
| --- | --- | --- |
| P0 — product direction | Complete, approved | Scope, boundaries, initial policy and synthetic pilot decisions agreed |
| P1 / M0–M1 — foundation | Engineering complete; research deferred explicitly | Local authenticated stack and CI pass; five interviews still owed before customer rollout |
| P2 / M2 — read-only workspace | **In progress** | Governed source adapter and verified queue/case/member/decision/evidence views |
| P3 / M3 — reviewer commands | Not started | Assignment, comments, concurrency, transactional audit/outbox; full synthetic review |
| P4 / M4 — asynchronous assessment | Not started | Validated assessment survives worker restart and safe retry |
| P5 / M5 — ingestion and policy management | Not started | Secure ingestion; second supported policy onboarded through approval/regression gates |
| P6 / M6 — prototype retirement | Not started | Parallel reconciliation passes; no operational dependency on Streamlit/user credentials |

### Completion estimate — reviewed 23 October

Owner-facing planning estimate: **35–40% of the full P0–P6 migration; P2 about
60%**. P0 is complete, P1 engineering is complete under the explicitly deferred
research gate, and P3–P6 have not started. As a transparent, rough phase indicator,
equal weighting gives `(100 + 100 + 60 + 0 + 0 + 0 + 0) / 7 ≈ 37%`.
Phases are not equal in effort or risk, so this is **not** an earned-effort,
time-remaining, customer-readiness or production-security percentage. Counting
historical checklist entries or passing tests would exaggerate completion.

P2's implemented local workspace/contracts, bounded operator reads and extensive
offline boundary tests explain the partial estimate. Remaining acceptance is
substantial: lifecycle/clock/custody/readiness, exact Snowflake isolation and
service identities, governed financial/clinical evidence, live authenticated
API/UI parity and final remote verification. Current backend-only increments
do not change the public website or make the disabled live route available.

## Completed foundations

- [x] Approved Indian TPA / hybrid deployment / PostgreSQL / Next.js + FastAPI direction.
- [x] Frozen canonical decision contract and 30 golden rule results.
- [x] Local web/API/PostgreSQL stack, migrations, identity and tenant membership.
- [x] Authenticated API contracts and generated TypeScript types.
- [x] Three-role synthetic queue and case UI, responsive layouts and browser tests.
- [x] API isolation/revocation tests and no-Snowflake CI for the implemented slice.
- [x] Separate source-alpha identities and immutable TPA001/TPA003 ownership scopes.
- [x] Bounded metadata/history/decision/clause inspection code; unknown scopes do no I/O.
- [x] Pure-Python saved-decision/citation and member-history validators with offline tests.
- [x] Approved inspection grants independently verified: 13 direct USAGE/SELECT grants,
  no grant option, only RUSHIKESH2001 as grantee. PUBLIC caveat remains open.

## P2 remaining work — in order

Current sequence after the 25 October membership-DB TLS acceptance:

1. Add explicit Linux resource/headroom observations and connect the reviewed
   allocator/journal to the complete eight-service disposable lifecycle. Linux
   route collection is implemented and used by the member-DB CI edge.
2. Verify the integrated readiness barrier, tenant/role behavior, revocation,
   bounded stop, uncertain outcomes and containment with the real services.
3. Approve operational host/custody separately; review governed source views,
   projections and restricted runtime identities before paid/live acceptance.
4. Complete authenticated API/UI evidence for both tenants/all roles and review
   P2 exit. P3 remains unauthorized until that exit review.

Earlier implementation checkpoints below retain their original evidence and
counts; their next-step notes are superseded by this sequence and the latest
checkpoint above.

### Explicit DB resource allocation — 24 October

`Resources(database=True)` now reserves all 35 intentions before discovery:
18 internal networks, 15 app volumes and separate DB material/data volumes.
The default remains the existing 33-object app inventory. DB names and exact
local-driver/label validation are shared with the material helper. Duplicate
inspection JSON keys, option/label/name/scope drift and unknown observations
fail closed. A lost create acknowledgement can be independently observed but
still fences the invocation; it never permits retry or further allocation.

An offline integration test now connects the real allocator journal and returned
network IDs to DB material helper installation/probing. This proves the authority
handoff with fake daemon metadata, not physical volume ownership or DB readiness.
The host recheck deferred Docker acceptance (pressure level 2, load 15.86).
No containers or host settings changed. Remaining sequence: UID/GID 10002 data
initialization, pinned PostgreSQL packaging, bounded startup and TLS/grant probes,
then full physical lifecycle/containment acceptance. P2 estimates stay unchanged.

Validation: the full root suite passed 699 cases before the final two lost-ack
cases were added; the complete 38-case resource file then passed, covering all
701 collected root cases across those runs. Ruff, formatting and whitespace
checks pass. The broad targeted API run passed 408/409: the existing blocked-stop
watchdog case lacked its callback marker. All six actor cases passed in an
isolated rerun (11.10 seconds), without changing deadlines or assertions. Host
load is a possible contributor, not a diagnosed cause; the initial failure is
retained here and no all-green broad API run is claimed.

### Journaled DB material helpers — 24 October

The inactive DB coordinator now reuses bounded engine commands and the shared
one-attempt helper lifecycle. It requires DB-specific staging bound to the
invocation/member-db topology, a separately observed exact DB material volume
and a fresh helper ledger. Both container intentions precede engine execution.
The installer is root with CHOWN only; the independent read-only probe is
UID/GID 10002 with no capabilities. Image, mount, labels, receipt and successful
exit must all match. Headroom and resource authority are rechecked before create.

Lost acknowledgements fence admission and retain UNKNOWN. Explicit containment
inspects only acknowledged exact CIDs and cannot turn an unattempted verifier
into success. No retries, name adoption, removal or database-readiness claims.
Fake daemon tests cover metadata corruption, ambiguous outcomes and wrong
volume/binding authority; the real bounded subprocess transport also runs the DB
contract against a fake CLI. No actual Docker or PostgreSQL execution occurred.

Validation: the root regression suite plus the final two constructor checks
pass (681 collected tests), as do 409 targeted API tests, repository lint and
changed-file formatting. No remote CI run is claimed. Next: allocate/journal the
DB-specific material/data resources, supply the pinned UID-10002 PostgreSQL
image and bounded launch/readiness probes, then physical unified lifecycle and
cleanup when host headroom permits. P2 and completion estimates are unchanged.

### Disposable DB volume installer and probe — 24 October

A separate inactive DB helper now converts verified host staging into bounded
private stdin, validates a canonical five-file archive before mutation, installs
only into an empty explicit directory and supports independent read-back.
The DB wire contract requires UID/GID 10002; the application contract remains
10001 and its parser rejects database frames. Traversal, links, changed bytes,
wrong archive ownership and trailing data deny before writes. Existing partial
state is retained without retry or adoption. CLI identity and target directory
are fixed; receipts contain no credentials or hashes.

The candidate helper image has an allowlisted three-file build context and no
credential generation dependency. It is not a PostgreSQL service image. The
future pinned PostgreSQL image must independently establish UID/GID 10002.
The owner still owes bounded journaled helper coordination, exact image/mount
inspection, independent probe exit, PostgreSQL startup/TLS/grants and the full
DB/controller/eight-service lifecycle. No image was built, no Docker was run,
and host filesystem tests do not prove Linux ownership or mounted acceptance.

Validation: 643 root tests and 409 targeted API tests pass, with repository
lint, changed-file formatting and whitespace checks. Nine new regressions cover
DB archive/install/read-back and CLI identity/receipt boundaries. No remote CI
run or physical Docker acceptance is claimed for this checkpoint.

### Private disposable DB staging — 24 October

The generated DB-only bundle can now be staged in a fresh owner-private host
folder, bound to an invocation fingerprint. The existing checked file path is
shared through explicit material-class contracts; application role allowlists
and archive ownership stay unchanged. Database staging requires exactly the
five server files, a private parent, exclusive creation and durable writes.
Verification checks original directory identity, exact names, ownership, modes,
single links, sizes and byte digests. Failed writes remain private and cannot
be silently retried or adopted. No secret bytes or hashes are logged.

The database contract refuses the application UID 10001 archive. This completes
host staging only: PostgreSQL image ownership, bounded volume installation,
DB/controller launch and readiness, request actors/watchdog and physical
all-eight lifecycle/removal remain pending. No Docker or source access occurred.

Validation: 634 root tests and 409 targeted API tests pass, including ten new
DB staging regressions; repository lint, changed-file formatting and whitespace
checks pass. Physical acceptance and remote CI are not claimed.

### Controller lifecycle and disposable DB preparation — 24 October

The inactive owner-side controller now joins the journaled launcher to the
existing serialized supervisor. Explicit readiness receipts must also pass
fresh exact runtime inspection; polling/admission and result completion recheck
all eight runtimes. Requests are admitted separately from transport, so the
future bounded request actor and independent watchdog remain external duties.
Validated summaries must match the original operation object and request ID;
late, duplicate, changed-runtime and closed-delivery results cannot escape.

Stop includes launcher-owned partial allocations that never returned a handle
to the supervisor. Unconfirmed request cancellation retains capacity even after
container exit; unknown journal intentions remain UNKNOWN. This is containment
of app/request work, not removal or proof that DB/controller auxiliaries stopped.
The real loopback TLS chain passes through this bridge for both tenants/all
three roles, using fake daemon observations and explicitly supplied test receipts.

Disposable DB preparation now generates matching one-hour TLS material and a
fresh restricted membership credential for the exact member-db edge. Its HBA
permits only that membership IPv4 address, and its single bootstrap transaction
creates narrow column grants plus all six synthetic identities. Only membership
receives its credential/CA; the DB leaf key, admin password and bootstrap SQL
remain in the separate in-memory server bundle. No files, DB objects, images or
containers are created by preparation. Existing explicit seed behavior is reused.

624 root and 409 targeted API tests pass, with lint and changed-file formatting. Mac memory pressure remains 2, so physical acceptance is deferred.
Next: privately install the DB bundle, wire bounded DB/controller auxiliary
launch/probes and request actors, then run the unified eight-service lifecycle
and exact cleanup once headroom permits. PostgreSQL TLS/grants, mounted ownership,
actual readiness, watchdog/exit/removal and operational custody remain unproven.
No P2 exit, completion-estimate change, normal activation, deployment or Snowflake
work is implied by these offline integration results.

### Journaled state-helper coordination — 23 October

The inactive state coordinator now reuses the material coordinator's bounded
engine, strict image/container/mount inspection, separate helper journal and
explicit containment. Both state-helper intentions precede engine work; the
initializer runs as root/CHOWN only and the independent verifier as UID 10001
with no capabilities. Only the exact observed state-volume intention can
authorize this attempt. A material-volume observation or membership role cannot.
Both helpers have no network or host mounts and use RW retained state.

Each receipt must match role/generation, followed by exact successful exit proof.
Unknown create/start, changed configuration, bad receipts, nonzero exit or lost
headroom fence the attempt without retry/adoption. Containment uses only known
full CIDs and fresh exit inspection; an unattempted/unknown verifier stays
UNKNOWN, and no resource-journal mutation, readiness or removal follows.
Shared material tests still require a read-only verifier. Real bounded actor/CLI
tests exercise both paths against fake metadata; no Docker daemon was used.

Mac pressure remains 2. Physical state/image/ownership acceptance and the unified
restricted DB/controller/eight-role lifecycle/cleanup runner remain next. This
does not close operational custody/clock-health, Snowflake isolation or live
API/UI parity. No deployment, Snowflake spend, normal activation or P3 changes;
P2 and the completion estimate remain unchanged. Prior helper commit `1997813`
and seven-state checkpoint `4634f8c` now have successful remote CI runs.

### Disposable state-volume helper candidate — 23 October

An explicit test-only helper now accepts a small closed role/generation request
for one of the seven canonical authorities. Initialization requires an empty
directory, uses the existing frozen-time fixture, and retains partial outcomes.
The separate probe checks UID/GID, private modes, exact regular single-link
files, canonical SQLite/config/authority and signed fictional health. It never
initializes or repairs state. Replay remains spent across repeated probes.

The candidate image derives from a caller-supplied, independently verified pinned
broker-test image and adds only the helper; its deny-by-default build context
excludes credentials. Initialization must run as root with only CHOWN; the
independent probe runs as UID/GID 10001. Both use the explicit state mount;
verification requires RW because health observations may persist high-water
marks. Neither receipt is service readiness or proof of a stopped container.

Thirty-three new host tests cover the helper and CLI boundary. No image was
built or volume mounted: Mac pressure remains 2. Bounded journaled state-helper
coordination, actual Linux ownership/read-back, restricted DB/controller and
eight-role lifecycle/cleanup remain next. No source flags, normal startup,
deployment, Snowflake spend or P3 changes. P2 and its estimate remain unchanged.

### Seven-state/material preflight integration — 23 October

An inactive host-side test fixture now joins all seven canonical retained guard
stores with the eight staged role bundles. Explicit initialization requires an
empty private root, creates exactly the plan's state-volume names, and uses the
existing frozen-time initializer once. Membership has no state. Failed/partial
initialization is retained; neither the same nor a new fixture may overwrite it.

Reload checks exact inventory, private directories, regular single-link files,
modes, authority/generation binding and SQLite integrity before any canonical
health observation. Health observations may persist high-water marks; this is
not a read-only filesystem probe. Missing/corrupt/swapped/latched state, wrong
generation, extra paths or changed material deny. Replay remains spent after
reload. A real launcher preflight with fake daemon metadata now requires the
combined gate and denies missing state before any container create/start.

This is host-directory/SQLite integration, not named-volume installation,
Linux UID/chown proof, operational clock health or physical eight-service
acceptance. Mac pressure remains 2. Mounted retained-state transport, restricted
DB/controller and full lifecycle/cleanup remain next. No normal startup,
Snowflake, deployment or P3; the completion estimate is unchanged.

### Explicit helper containment — 23 October

The inactive helper coordinator now has an explicit containment method using
only acknowledged full CIDs and its existing bounded inspect/stop slots. It
fences admission, rechecks exact configuration before stopping, and requires a
fresh created/exited, PID-zero observation afterward. Lost stop acknowledgements
are resolved by inspection, not assumed successful. Other known helpers still
receive containment attempts if one inspection or the journal fails; the result
stays false when durable observations or any intention are unresolved.

Containment does not certify material or erase failure: nonzero exited helpers
may be stopped but never become verified. Missing create acknowledgements remain
UNKNOWN; no name adoption, retry, removal, resource-journal change or automatic
startup follows. Twenty new offline cases cover these boundaries. Physical
Docker acceptance remains deferred at Mac pressure 2; seven retained states,
restricted DB/controller, all-eight-role lifecycle and exact cleanup remain next.
No deployment, Snowflake spend or P3. P2 remains open; completion estimate unchanged.

### Material-helper coordinator — 23 October

An inactive one-role coordinator now joins staged material, bounded private-input
transport and two independently inspected helper containers. It reserves both
intentions before engine work, refuses existing names, checks the observed named
volume and pinned helper image, and checks exact configuration before sending
input. Installer success alone cannot pass: a separate UID-10001, read-only,
capability-free verifier must return the expected receipt and independently
exit successfully. Helpers have no network or host mounts; only the installer
receives CHOWN. Failures fence and retain ambiguous outcomes for owner inspection;
there is no automatic retry, removal or daemon-exit claim.

Each role uses a dedicated helper journal under a separate private parent and
a separate bounded engine registration set; the observed resource journal is
checked but not modified. Application launcher journals/admission are unchanged.
Tests cover all eight roles with fake daemon metadata and real disposable
staging/journals, plus a real bounded subprocess/fake-CLI success and failed-exit
round trip. This is not physical mounted-file/chown proof. Mac pressure remains
2; mounted acceptance, seven retained states and full lifecycle remain next.
No normal startup, Snowflake access, public deployment or P3 is enabled.

### Private helper-input transport — 23 October

The bounded actor now accepts an explicit, at-most-2-MiB private byte body over
anonymous pipes, separate from its small control/result frames. The engine uses
that channel only for an exactly inventoried attached/interactive start of a
registered full container ID. No payload is placed in argv, environment, files
or journal. Unknown/blocked/early-exit outcomes fence admission; this does not
prove daemon-side cancellation. Real subprocess tests use synthetic bodies and
fake CLI executables only. Mounted material installation/read-back, Linux UID
transitions, seven retained states and eight-role lifecycle remain pending.
Mac memory pressure remains 2, so no Docker build/allocation was attempted.
P2 remains open; no website, Snowflake or normal runtime change.

### Bounded Mac/Docker subnet collision gate — 23 October

The disposable provisioner's collision callback now has a concrete collector:
bounded numeric Mac IPv4 routes plus full-ID Docker network/IPAM inspection,
with no ambient CLI context or credentials. It rejects overlap (including host
routes and enclosing subnets), malformed/incomplete metadata, duplicate IDs,
unbounded inventories and changes in host routes or Docker network membership
between snapshots. The default route is excluded, not other occupied networks;
there is no own-namespace exemption, automatic subnet search or allocation.
Discovered network IDs authorize only bounded metadata inspection, not container
operations or ownership. Fresh checks are required; successful results are not
cached. Snapshots are not atomic reservations: a trusted stable host/daemon is
still required during acceptance, and same-ID IPAM changes after inspection are
not excluded by these snapshots.

Offline tests compose this gate with real disposable journals: conflicts prevent
all provisioning engine calls and retain UNKNOWN intentions. A bounded read-only
check also passed on this Mac against four actual Docker networks and eighteen
proposed `10.81.*.0/29` subnets. The initial check safely denied Docker Desktop's
null IPAM on its built-in host/none networks; explicit support for null or empty
IPAM is now limited to those two non-IPAM drivers and regression-tested. No
network/container/volume was created, modified or stopped. Temporary empty CLI
configuration was removed automatically; no credential files were accessed.

Verification: **478 root tests**, **169 targeted API composition tests**, lint,
changed-file formatting and whitespace checks pass. Mac pressure remains 2, so
image builds and physical mounted-helper/eight-role acceptance remain deferred.
Next: bounded private helper input, actual mounted-material installation/readback
and retained-state integration, then auxiliary DB/controller and eight-role
lifecycle acceptance. No Snowflake spend, public deployment, normal startup
change or P3; P2 and the overall completion estimate remain unchanged.

### Disposable resource provisioning integration — 23 October

`composition_resources.py` prepares eighteen internal bridge networks and fifteen
local volumes (eight material/seven state), within the existing disposable scope.
All 33 exact names/configuration fingerprints are journaled before engine I/O.
Explicit headroom and route-collision callbacks must approve before allocation;
headroom is checked again before each create. Existing target names deny rather
than adopt. Exact independent inspection checks names/labels, network ID/subnet/
gateway/empty endpoints and volume driver/options before recording PRESENT.
A create acknowledgement alone is insufficient. Lost acknowledgements reconcile
only attempted exact names with matching metadata; uncertainty fences the batch,
retains UNKNOWN and prevents retry. No removal/prune or fallback storage exists.

The same open journal can feed the inactive launcher only after all 33 expected
resource identities are observed; partial/fenced/mismatched records deny before
engine calls. Container intentions are appended without resetting the resource
history. Tests use real private journals and fake engine/headroom/collision input,
not physical resources. The bounded transport accepts the exact provisioner
command inventory; no default CLI or normal entrypoint is activated.

The actual route-collision collector, private mounted-material helper, seven
retained stores, auxiliary DB/controller and eight-container readiness/cleanup
acceptance remain owed. No helper build, Linux UID transition, Docker mutation,
live source, website deployment or P3 occurred. Mac pressure remains 2, deferring
heavy execution; existing four product services remain untouched.
Verification: **432 root tests**, **169 targeted API composition tests**, lint,
changed-file formatting and whitespace checks pass. Prior transport commit
`a2f130b` passed remote CI ([run 39982829113](https://github.com/hulagerushikesh/cashlessiq/actions/runs/39982829113)).
P2 and the readiness estimate remain unchanged; these are integration plumbing
checks, not production isolation or physical resource acceptance.

### Bounded engine/launcher integration — 23 October

The explicit disposable transport now runs a closed Docker command inventory
through the existing owned actor/watchdog. It requires an explicit Unix endpoint,
absolute trusted executable and empty private CLI configuration, with no ambient
context, shell, credentials, retry or image pull. Time/output/exit failures latch
admission closed; independently bounded inspection/stop remain available. Returned
full container IDs can fill only predeclared final-ID command slots, not arbitrary
operations. Registration is not ownership attestation: the launcher/journal still
checks exact owner/attempt metadata before recording observations or stopping.

New tests use actual subprocesses, disposable local sockets and fake executables;
launcher tests replay fake metadata through the real process transport and private
journal. A killed create retains UNKNOWN reservations/fence; successful partial
cleanup records only the observed stopped container and leaves seven UNKNOWN.
No Docker mutation, transport-to-daemon acceptance, mounted-volume/UID transition,
network isolation or
canonical eight-container readiness is proven. Physical resource provisioning,
helper installation/read-back and full composition remain next. Mac pressure is
still 2; heavy builds were deferred and four existing product services untouched.
Verification: **416 root tests**, **165 targeted API composition tests**, whole-
repository lint, changed-source formatting and whitespace checks pass. These
results do not close P2 or increase the readiness estimate. No source/AI spend,
public deployment, P3 or operational credential change occurred.

### Journal-backed launcher lifecycle — 23 October

The inactive launcher now accepts an explicit fresh private journal. It durably
reserves all eight container names/configuration fingerprints before any engine
call, checks the writer before admission/create, and rejects reused or foreign
journals. A create acknowledgement alone cannot record ownership: an exact
name/image/attempt/owner observation is required before network attachment/start.
Ambiguous creates reconcile only against that same attempt; failed inspection
leaves UNKNOWN rather than inferring absence. Launch failure and stop close
admission and persist a fence when storage remains healthy.

Confirmed stop is recorded only after observing zero PID, stopped state and the
same full container identity. Repeated cleanup does not duplicate transitions.
Write failure still permits containment of an independently known container but
cannot report durable success. Unattempted reservations remain UNKNOWN, so even
successful containment of a partial launch does not report the whole attempt
clean. No removal, journal repair, replacement or retained-attempt adoption is
introduced. Historical no-journal callers remain model-only tests.

**18 new integration cases combine real private files with FakeDocker, not a
real daemon.** They cover all-eight stop, ambiguous creation, foreign ownership,
failed inspect/start/stop, closed/replaced/reused journals and reserve/observe/
stop/fence write failures. This connects the journal to lifecycle callbacks;
it does **not** yet provide bounded real Docker transport, resource provisioning,
helper-volume acceptance or eight-container readiness. Those remain next.
Mac pressure is still `2`; no builds, new containers, Snowflake spend, public
deployment or UI changes. P2/overall estimates are unchanged.

Verification: 392 root regression tests, 163 targeted API lifecycle/material/
supervisor cases, lint, changed-file formatting and diff checks pass.

### Retained disposable ownership/recovery journal — 23 October

Added an explicitly created, owner-private journal outside actor/service mounts.
It fsyncs each exact UUID-namespaced reservation before a trusted caller may
mutate the engine. Container/network IDs, volume names and image digests have
closed formats and bind a public configuration fingerprint; arbitrary payloads,
credentials and engine errors are not accepted. Exclusive writer locking,
canonical bounded records, no-follow opens and file/directory identity checks
reject concurrent writers, aliases, replacement and malformed/truncated records.
Short writes are completed; write/fsync uncertainty permanently closes that
writer. Nothing is overwritten, repaired, retried or deleted.

A separate inspection-only recovery API reopens the retained file after process
death. Unobserved reservations stay **UNKNOWN**, never absent or stopped. Trusted
engine observations may be recorded after a fence; no new resource reservations
may be added. A container cannot be recorded removed before confirmed stop, and
one engine identity cannot be assigned to two reservations. **These are journal
transition checks, not Docker attestations or automatic removal authorization.**
There is no reopen/resume writer, operational rollback protection or independent
generation authority. Same-owner rewriting/complete rollback remains trusted.

Real disposable filesystem tests include abrupt writer exit, failed fsync and
partial writes. Composition with the existing real actor/watchdog retains all
eight UNKNOWN reservations after blocked/late fake workloads; successful process
exit also cannot promote them to stopped. Docker is not called by these tests.
The journal remains excluded from normal and service-image startup. Actual engine
callbacks are **not yet wired**: next compose the journal with bounded real-engine
creation/inspection/reconciliation and exact cleanup, then run helper/volume and
eight-role acceptance when Mac headroom permits. Current pressure is still `2`;
no new Docker resources, local UI changes, Snowflake spend or deployment.

**40 new journal tests pass; 392 root regression tests, 145 targeted API
launcher/actor/material/supervisor tests and lint/format checks pass.**
P2 and overall completion estimates remain unchanged; physical acceptance and
operational source gates are not satisfied by this filesystem checkpoint.

### Disposable volume installer/read-back implementation — 23 October

Added a separately invoked, standard-library material helper and closed two-file
test-image context. It has no default action or normal-service wiring. Its CLI
accepts only `install` (root) or `verify` (UID 10001), fixes `/material` and final
UID/GID 10001, and receives bounded private stdin frames rather than credential
arguments/environment. Output contains only state, role and inventory fingerprint;
denials are redacted and report an unknown outcome, not successful cleanup.

Installation validates the entire archive before touching the target: exact
role allowlist, sizes/hashes, owner/modes, flat members and canonical USTAR bytes.
Traversal, links, devices/FIFOs, duplicates, PAX/compression/trailing payloads and
noncanonical metadata deny. It never calls tar extraction. Only an empty,
current-owner target is accepted; files are created exclusively, synchronized
and assigned final mode/owner. The directory is finalized last. Failure retains
partial state with no automatic retry, overwrite or deletion.

The separate read-only checker verifies every regular file's ownership, mode,
size/hash, link count and stable metadata plus root identity. Installer success
is not read-back success or readiness. Tests exercise all eight inventories on
real temporary host directories using the host's unprivileged UID/GID, **not Linux
UID-10001 transitions or named Docker volumes**. CLI fixed paths/UID policy are
unit-tested; the helper image has not been built/run. Proposed root CHOWN-only
installation and a separate capability-free UID-10001 read-only probe still need
physical verification in independently owned/bounded helper containers.

**50 new volume tests and two packaging boundary tests pass**; root regression
**352 passing**, targeted API regression **596 passing**, lint/format checks pass.
Prior `d055a0c` is green in CI. Host pressure remains `2`; no new Docker resources,
existing app changes, Snowflake calls, deployment or P3 work. The local API and
website remain unchanged. Next: retained ownership/recovery journal and bounded
engine wiring, then actual helper/volume and eight-role acceptance when host
headroom permits. P2/completion estimates remain unchanged.

### Private per-role material staging and verified archives — 23 October

Implemented the local file-material prerequisite for the approved disposable
composition. Each role has an exact file allowlist: broker alone receives the
assertion signer/local-test identity secret; membership alone receives fictional
DB configuration/CA; validators alone receive their tenant's synthetic source;
readers receive only assertion verification material and their own TLS identity.
The test builder checks each certificate pin and matching private key against
the explicit inventory. Missing source decisions remain empty, not demo copies.
The controller's key is never copied into an application-role bundle.

The inactive standard-library helper creates new role directories only under an
explicit private owner directory. It refuses existing directories and never
repairs, adopts or removes partial state. fd-relative exclusive/no-follow writes,
file/directory fsync, mode 0700 directories and mode 0400 files precede an in-memory
receipt binding expected hashes, role fingerprint and root device/inode.
Read-only snapshot verification bounds file sizes and rejects extra/missing files,
changed content/security metadata, insecure modes, symlinks (including parents),
hard links, FIFOs and root replacement. A first run exposed legitimate access-time
updates; comparison now excludes atime but retains content/security timestamps.

Archive export uses only the verified byte snapshot, without rereading files.
It emits an exact flat USTAR inventory with UID/GID 10001, directory mode 0500
and file mode 0400, with no links/host paths. Archive bytes are secrets and must
remain on private bounded input, never argv/logs/public artifacts. Hash manifests
are not persisted/printed; expected/staged object representations omit contents.
This is not encryption, memory zeroization, same-user hostile mutation prevention
or operational credential custody. PKI/source/DB semantics are not inferred by
the generic staging helper; its caller is trusted disposable test provisioning.

Tests use real temporary files and generated test PKI, prepare all seven canonical
broker/worker handlers and parse the eight-edge membership configuration. They
also replace the launcher's fake material callback with the actual local snapshot
checker; Docker observations remain fake. No DB factory/connection is opened.
**35 new root tests and 4 API tests pass**; root regression is **300 passing**,
expanded targeted API regression **596 passing**, plus lint/format checks.
Prior `bb47829` is green in CI. All helpers stay out of normal/service images.

Host preflight remains pressure `2`; no Docker build/new resources or existing
app changes were made. **Actual named-volume installation/read-back, independent
ownership/recovery records, bounded real-engine actors and physical eight-role
acceptance remain next.** A verified host bundle/tar is not proof of mounted file
ownership, live TLS/DB connectivity or container cleanup. P2/completion estimates
are unchanged; no public deployment, live Snowflake use or P3 work.

### Bounded process/watchdog around the fake-engine launcher — 23 October

Added an opt-in, one-use process boundary and a separate watcher, then composed
it with the actual inactive launcher/supervisor using the fake Docker engine.
Healthy all-eight model start/readiness/admit/stop and partial-start fencing run
inside an owned actor process. Blocked create/stop callbacks and valid-looking
output followed by a blocked actor are interrupted and denied. Disposable marker
files prove those callbacks were reached, rather than treating an import timeout
as successful containment evidence. No real Docker engine is used by these cases.

The caller sets one immutable elapsed deadline; framing is bounded and rejects
duplicate keys, non-finite JSON, extra output, non-object results and failed exits.
Child errors/output on denial are discarded, not leaked. Actor arguments contain
only a closed test mode and disposable marker path; no credentials or tokens.
The watcher owns/reaps its direct actor. The caller bounds and forcibly stops/
reaps the watcher in its separately owned process group before reaping that group
leader. Unknown cleanup denies, with no automatic retry or replacement attempt.
The fake-case wrapper reserves all eight names outside the actor and retains its
test slot/name reservations on unknown completion. This is not a durable Docker
ownership journal or a guarantee of container absence after process termination.

The first run exposed a raw macOS `EPERM` cleanup path after a watcher exited;
the watcher now remains alive until owner termination and syscall/cleanup errors
remain redacted, fenced outcomes. A separately run partial fixture produced the
expected FENCED/stopped metadata; subsequent integrated checks pass. Stalled-
watcher, late-result and malformed-output cases also deny. PID-group ownership
requires default SIGCHLD disposition, exclusive child reaping and closed test
actors that do not escape the process group; unknown SIGCHLD handling denies.
Same-host suspension still pauses this mechanism. It is not external deadline,
clock-domain continuity, arbitrary descendant containment or operational safety
proof. Explicit Linux containment acceptance remains a separate evidence set.

**21 root tests** cover process/framing/policy/cleanup behavior; **6 API tests**
cover the real actor/watcher around the fake-engine lifecycle and reservation
handling. The expanded targeted API suite has **592 passing tests** and root
regression has **265 passing tests**, plus lint/format checks.
Previous `77e1260` is green in CI. No service image/default startup includes the
actor/watchdog or closed test-case helpers. Existing app containers/settings are
unchanged; host preflight again reports pressure `2`. No Docker resources,
auth material, Snowflake use, public deployment or P3 work was added.

**Next: material provisioning/verification and physical all-eight composition**,
including bounded real Docker callbacks, independent retained ownership/recovery
records, canonical service readiness/delivery and confirmed exact cleanup. This
process fixture alone does not close those gates or advance the completion estimate.

### Inactive eight-role inventory and owner-side launch adapter — 23 October

Added a pure, no-I/O launch inventory covering all eight application roles,
three pinned test image digests, nine distinct public certificate pins, fifteen
per-role named volumes (eight read-only material plus seven writable state),
and **eighteen separately enumerated private links**: the fourteen worker links,
two broker-membership links, membership-DB and controller-broker. No host bind,
shared ledger, direct broker-validator link or public port is generated. The
controller and disposable DB remain explicitly registered auxiliaries, not
extra signing authorities or replacements for the eight-role readiness barrier.

Generated configs pass the actual broker/worker/membership configuration parsers.
Service fingerprints bind image, configuration, own public pin, network/subnet
inventory, role volumes and fixed test resource/security limits. Inspection
checks refuse foreign labels, external networks, unknown endpoints, volume
driver/bind aliases, extra mounts/ports, privilege/restart changes and resource
limit mismatches. This is a strict engine-metadata contract, not measured file
ownership, clock health, TLS custody or readiness attestation.

The **inactive test-only owner-side adapter** connects this inventory to the
existing supervisor interface with injected engine and mandatory material-check
callbacks. It verifies stopped metadata before start, then checks the full
running container incarnation. Every attempted name is reserved before create;
a failed/unknown create is reconciled only by exact name, image, ownership and
attempt/fingerprint labels. Existing names are never adopted. Failed launch or
stop closes the adapter to replacement launches; unknown stop retains ownership
and the supervisor's fence/capacity. Cleanup confirms stops only, preserving
containers and all volumes for explicit owner-side incident/removal handling.
It does not prune, erase state, initialize material or manufacture readiness.

**124 new tests pass using a fake Docker engine**, including all-eight model
adoption/stop, partial creation, network failures, unknown start/stop and foreign
ownership. The expanded targeted API suite has **586 passing tests** and the root
suite has **244 passing tests**; lint/format and whitespace
checks pass. Three explicit test image entrypoints now set `CMD []` to exclude
inherited default arguments; normal image targets/startup remain unchanged.
Previous `e2efe87` is green in remote CI.

These tests invoke no real Docker commands and create no network, volume,
container, key or credential. Host preflight still reports pressure `2`; existing four containers
are untouched. **This adapter is not the independent actor/watchdog or complete
eight-container runner.** Mandatory material verification is injected/fake, not
an implemented custody provider. Provisioning, measured Docker metadata behavior,
bounded actor/watchdog wiring, confirmed resource removal and real restricted-DB/
all-eight physical acceptance remain next. No public deployment, Snowflake spend
or P3 work; completion estimate unchanged.

### Private broker test ingress and isolated packaging — 23 October

Added `apps/api/Dockerfile.broker-test`, an explicitly selected synthetic test
artifact, not a new normal API entry point. It copies a closed canonical module
set and the disposable broker/health helpers, runs as UID/GID 10001, and omits
normal API startup, migrations, source gateway, source fixtures and membership
DB adapter. Its import closure is tested in a subprocess from only those copied
sources; this is not a successful Docker build/run. The broker's existing
`ALPHA_REFERENCES` import now points directly at its canonical identity module
rather than pulling the same re-export through the source repository/gateway.

The private mTLS ingress accepts only a pinned test-controller certificate and
strict `{token, request_id, nonce}` JSON. It calls the canonical broker, returning
only a nonce-bound validated summary. Caller tenant/role/destination/signer
settings, duplicate fields, wrong paths, foreign peers and widened/mismatched
responses deny without source access. The response nonce binds a transport
exchange; it is not an idempotency key or replay ledger for user sessions.
Both loopback and explicit private-endpoint clients are test-only.

Trusted configuration fixes four reader destinations and two broker-membership
destinations; it permits no caller URL, shared peer identity, DB fallback or
validator shortcut. Runtime material is only the broker's own TLS files, own
existing guard state, disposable assertion signer and disposable local-auth
verification secret. Verifier settings do not read ambient CIQ authentication/
DB settings. Missing/weak/invalid material never discovers or generates keys.
The test service owns socket/thread cleanup and suppresses READY on partial
startup/stop; the external controller still owes readiness receipts, operation
deadlines and confirmed process termination.

The shared chain now enters through this actual TLS broker listener, bringing
the fixture to **ten real loopback TLS listeners under eight logical roles**.
It still uses fictional health/source, a synthetic identity registry and fake
membership storage in one Python process. This is not real OIDC, restricted
PostgreSQL or eight-container acceptance. **55 new broker ingress/packaging tests
pass**; the expanded targeted API suite has **462 passing tests** and the root
suite has **243 passing tests**. Lint/format and whitespace
checks pass. Previous `24d541b` is now green in remote CI.

Mac preflight initially passed at pressure `1`, then the required pre-build
recheck returned pressure `2`; no image build or new container was started.
Four existing containers/settings remain unchanged. No public deployment or
Snowflake spend occurred. **Next: assemble the bounded all-eight container
launcher/watchdog and run physical acceptance when headroom permits.** Custody,
health provider/current-generation authority, governed source identities and
live API/UI acceptance remain separate P2 gates. Completion estimate unchanged.

### Broker's separate fresh-membership edges — 23 October

The disposable membership test target now supports **two additional broker-only
endpoints**, fixed to TPA001 and TPA003 respectively. They reuse the strict
nonce/internal-UUID lookup contract without accepting a tenant, issuer or role
on the wire. The existing six-worker allowlist is unchanged; broker certificates
cannot enter it, and worker/foreign certificates cannot enter broker endpoints.
The future launcher must isolate these two edges on separate exact networks.

The shared logical-role TLS composition now routes broker membership checks over
these endpoints rather than reading its fixture dictionary directly. Its closed
synthetic identity registry maps verified local principals to internal UUIDs,
not roles; every resolve fetches current membership remotely. This is a test
registry, not production OIDC identity provisioning. The broker receives no DB
password and has no cached-membership or outage-to-MISSING fallback.

**50 new broker-edge/configuration/lifecycle tests pass**. Six additional shared
chain tests verify that revocation, downgrade or outage after a successfully
validated reader result still blocks broker delivery across both tenants.
The expanded targeted API suite has **407 passing tests** and the root suite
remains **242 passing tests**, with lint/format and whitespace checks
passing. Previous `e643f3d` and `b2f470b` are now independently **green in CI**.

The membership command-line test target requires the explicit broker endpoint
configuration; missing/null configuration cannot silently start worker-only.
All eight membership endpoint binds precede serving/diagnostic READY, and partial
broker bind failures close owned worker endpoints and the DB factory. Shared
tests exercise nine real loopback TLS listeners under eight logical roles;
this is still not eight independently supervised containers or restricted-DB
acceptance. Broker HTTP ingress/image packaging and bounded all-eight launcher/
watchdog wiring remain next. Normal app startup/source flags are unchanged.

Host preflight still defers heavy Docker work: memory pressure `2`, roughly
6.39 GiB allocated swap, four running containers using about 741 MiB. Allocated
swap is not proof of active swapping or a fault. Existing services/settings are
untouched. No public deployment, live Snowflake use or purchase occurred, and
the completion estimate is unchanged.

### Six-worker restricted membership test service — 23 October

Added the membership image's explicit `composition-test` target. Six pinned
worker certificate audiences map to the two fixed source tenants; the service
accepts no caller tenant, broker peer, fallback store or schema/grant option.
The command-line path pins the existing verified-TLS DB factory and canonical
restricted membership store. Every lookup remains fresh; it adds no prefetch or
positive cache. The shared real-TLS suite now uses the same server builder.

The disposable PostgreSQL helper can explicitly seed the six canonical source
profiles in one additive transaction. Re-seeding does not overwrite inactive or
downgraded rows, change grants or alter the old single-tenant smoke by default.
The service itself never provisions rows/schema. No actual DB was seeded here.

**29 new service/configuration/lifecycle tests pass**, including pre-credential
refusal, exact tenant mapping, partial startup, stop suppression and factory/
listener cleanup. Seed registry and portable INSERT semantics have offline tests;
these do not establish PostgreSQL/TLS privileges. **351 targeted API tests and
242 root tests pass**, plus lint/format/whitespace checks. Earlier `b2f470b` remote
CI was still running when checked; it is not yet claimed green.

The Mac still reports pressure `2`; the existing four-container app is healthy
and untouched. No Docker build/run, separate membership DB acceptance, public
deployment or Snowflake spend. Diagnostic `READY` means listeners started, not
DB availability or a supervisor readiness receipt. Broker transport/identity
resolution, all-eight launcher/watchdog wiring and actual container acceptance
remain open. P2 and its completion estimate remain unchanged.

### Separately runnable worker test handlers — 23 October

Added an explicit worker `composition-test` image target for the four readers
and two validators. It assembles canonical v3 authorities/relays/validators with
fixed tenant/disclosure mappings, fresh pinned membership clients and existing
own guard state. Readers receive no source callback/file or assertion signer;
validators read only their tenant's synthetic fixture and reject mismatched rows.
The shared TLS tests now call this same handler builder instead of maintaining a
second assembly. Normal worker/membership candidates and API flags are unchanged.

Configuration rejects unknown roles, extra authority settings, public endpoints,
foreign/extra peer audiences and malformed pins before binding. Partial bind
failure closes the listeners already owned; orderly stop shuts down serving
threads and closes sockets. Stop during startup suppresses `READY`. That output
is only a diagnostic, not an attempt/configuration/incarnation-bound supervisor
receipt. External process deadlines and exit confirmation are still required.

**37 new service/configuration/lifecycle tests pass**, plus the existing shared
TLS and supervisor regressions: **322 targeted tests and 239 root tests** in this
batch. Service cleanup tests use injected listener/thread doubles; actual TLS
handler behavior is exercised by the shared loopback suite. No separate process,
Docker build/run or mount/network isolation acceptance is inferred. Earlier
commits `cf59c3f` and `c24f421` now both have confirmed green remote CI.

Mac pressure is still warning (`2`); four existing product containers are healthy
and remain running. Eight-container broker/membership composition, restricted DB
seeding, bound readiness and launcher/watchdog wiring remain open. No Snowflake
spend, public deployment, P2 exit or completion-estimate increase in this batch.

### Supervised logical-role delivery — 23 October

The shared TLS fixture now has independent, idempotent listener closers and a
test-only bridge to `OfflineSupervisor`. The model adopts the already-created
eight logical roles; it does not launch independent processes/containers. The
supervised call path admits no work until all eight bound readiness receipts
match, and returns a validated summary only after model completion permits it.
The model/audit receive opaque receipts, not recommendation payloads. Raw Python
fixture access remains trusted test internals, not a security isolation boundary.

**11 new tests pass** for readiness barrier and stale receipts, both tenants/all
roles, duplicate completion, expiry at the deadline, stopped delivery, readiness
or approval loss, unknown cancellation, source outage and partial adoption.
Stop closes actual loopback listeners; outer fixture cleanup owns any listener
not yet adopted during a partial failure. Missing/corrupt-state and TLS checks
remain covered by the preceding shared composition suite.

Clock, approval, cancellation confirmation and artifact marker are fictional.
The model bridge stops its test world on a failed request; this does not decide
the product's source-outage policy. No hard deadline/independent watchdog,
container-launch readiness, restricted DB or real custody acceptance is claimed.
Mac pressure remains warning (`2`), so the approved multi-container run is still
deferred. P2 estimate and exit remain unchanged; no deployment or source spend.

Verification: **285 targeted supervisor/TLS/guard/fixture tests and all 238 root
tests pass**; Ruff, changed Python formatting and whitespace checks pass. Four
existing product containers remain healthy. No Docker builds or full DB/browser
regression locally; latest remote CI completion is not yet confirmed.

### Shared logical-role TLS composition — 23 October

The canonical broker, four readers, two validators and membership now share one
explicit test world, rather than testing each tenant/disclosure path separately.
Signed local-test JWT verification selects fixed source identities; six workers
check fresh membership over pinned loopback TLS. Seven listeners use real TLS,
while broker membership resolution, membership storage, source and frozen health
remain test fixtures. Seven independent authority stores retain replay/latches.
The broker is an in-process call, not a public/private HTTP service.

**21 new shared-composition tests** cover all three roles and both tenants,
SAVED INR 95,000/MISSING, privacy-safe summary payloads, replay, revocation and
downgrade during source work, outages, invalid health, foreign/direct-hop denial
and listener cleanup after three partial-start failures. An affected reader's
failure does not poison the other tenant's independent state. Existing fixture
commit `e9f0083` passed [remote CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/39903446086).

No Docker build, independent service-process/custody proof, restricted membership
DB, supervisor readiness/deadline wiring, live-source/UI activation or deployment
is claimed. The Mac still reports warning pressure, so the multi-container run
remains deferred. Continue the approved container/supervisor composition next;
P2 exit and the rough completion estimate are unchanged.

Verification for this batch: **169 targeted TLS/guard/fixture tests and all 238
root tests pass**; repository Ruff, changed Python formatting and whitespace
checks pass. The full PostgreSQL/backend/browser suites and Docker acceptance
were not rerun locally. Remote CI for this batch is pending until independently
observed; the earlier green run above does not stand in for it.

### Integration fixture preparation — 23 October

Continued lightweight source work while the Mac's heavy-run preflight still
reports warning pressure (`2`). The explicit test-only helper now maps all seven
supervisor authorities to independent disposable v3 stores: broker, four readers
and two validators. Membership has no v3 store. Clinical role names map explicitly
to the `medical` wire audience; tenant indices map to the frozen source tenants.
Existing single-tenant test aliases remain compatible. Initializing over either
existing fixture file refuses, including a public-only partial fixture; loading
missing/corrupt state never repairs it. No real key, default entry point, normal
API/source flag or public UI changed.

**31 focused tests pass (19 new)**, including all seven role bindings, retained
replay, restrictive file modes, cross-authority claims and partial-state refusal.
This prepares the all-role harness; the eight-service container composition,
supervisor wiring and restricted-DB acceptance remain unimplemented/unrun.
No P2 exit or completion-percentage increase follows from fixture tests.

### Mac resource gate — 23 October

Owner approved the disposable canonical-service integration batch, subject to a
Mac load/configuration check. [Read-only observations and policy](mac-resource-check.md)
show 8 GiB RAM, about 3.82 GiB Docker allocation and elevated Mac pressure. The
new bounded metrics-only `make product-host-check` correctly returns DEFER;
no extra containers/builds or host settings/process changes. Existing four
services remain healthy. **25 new tests; all 238 root tests**, Ruff/format and
whitespace pass. Heavy backend/browser/container runs deferred. The eight-role
composition is not implemented/run or accepted yet; approval remains valid once
headroom allows it. No source/AI spend, activation, public deployment or P3.

### Next integration design — Mac/Docker, 23 October

Owner approved preparing the [local operational integration design](../architecture/p2-mac-docker-integration-design.md).
The design fixes the eight-role/seven-state mapping, private network/material
ownership, proposed owner-unlocked encrypted-image storage and fail-closed
clock/activation limits. Real storage, health policy and independent generation
authority are not proven or provisioned. One separately approvable 15-minute
disposable all-role canonical-service composition batch is specified; no actual
credential, encrypted image, container, source activation or deployment created.
No implementation/test-count or completion-percentage increase is claimed.

### Current owner-testing milestone — local synthetic alpha, 23 October

Owner has no additional Linux host and approved a usable local-only synthetic
alpha rather than hosting/provisioning. The Mac's existing Docker stack is rebuilt
and healthy at `http://localhost:3000`; DB data is retained. No website change,
Snowflake/AI call, purchase, source activation or P3. This is not a UI redesign.

[Start the 10-minute owner checklist](local-alpha-testing.md). Verification:
**26 browser, 15 source API/UI fake-gateway, 41 client, 213 root and 1,003 backend
tests pass**; typecheck, production build, lint, contract/no-drift and whitespace
checks pass. Three new browser tests verify sign-out blocks protected case access
for each role. One existing intentional backend serializer warning remains.
Prior containment commit `2d10fcc` passed remote CI. Local-alpha implementation
`c6a4b03` also passed [remote CI run 39895921707](https://github.com/hulagerushikesh/cashlessiq/actions/runs/39895921707),
independently checked on 23 October. The owner subsequently reported manual
checks working as expected and welcomed the synthetic sign-in role categories.
This closes the local owner-testing checkpoint, not P2's live acceptance gates.

P2's governed live acceptance and public release are still open. Continue local
owner testing without depending on trial renewal or treating synthetic snapshots
as live records. Customer SSO, hosting and real custody/source integration require
their own configuration and approval; do not expose the development role selector.

### Latest integration — disposable process containment, 23 October

The owner authorized the bounded Linux process harness. Five actual-process
scenarios now verify the supervisor model's readiness/partial cleanup, deadline
and stop denial, confirmed escalation/reaping, sticky unconfirmed cancellation,
and an independent watchdog killing a blocked launch actor plus its descendant.
No actual product service, source route or secret is activated. Ten runner safety
regressions bring root verification to **213**; backend remains **1,003 passed**
(rerun), with the existing intentional serializer warning. Ruff/whitespace pass.
The explicit CI containment step is added; its new remote result is pending.

See [acceptance and limitations](../architecture/p2-process-containment-acceptance.md).
Owned test resources were removed. Actual custody/health/activation authority,
governed identities/projection, authenticated live acceptance and hosting remain
the deployment blockers. No Snowflake/AI spend or website change; no trial
availability assumed on 23 October. P2 remains in progress, not release-ready.

### Latest implementation — inactive supervisor, 22 October

The owner explicitly approved fake processes and disposable state only. The
standalone offline controller now models exact eight-role/seven-state inventory,
full readiness, partial startup cleanup, admission/capacity/deadline denial,
shutdown fencing and externally approved stopped-generation recovery. It does
not launch services or read credentials; no application or website wiring changed.
See [acceptance and limits](../architecture/p2-offline-supervisor-acceptance.md).

Verification: **105 focused supervisor tests; full backend/PostgreSQL 1,003;
root 203**. Ruff/changed-Python format/whitespace and both isolated worker/
membership package/default-refusal checks pass. One known intentional serializer
warning remains. No frontend/browser/build or real container topology rerun
locally. Remote product CI for `8b2ab24` passed (run `39785213296`), checked on
23 October. This is regression evidence, not acceptance of real operational wiring.

The [deployment checklist](deployment-readiness.md) groups remaining work into
three coherent bundles: operational integration, governed live source, then
authenticated release acceptance/hosting. Avoid more isolated primitive guard
increments unless integration reveals a concrete defect. Actual host/store,
health-provider policy, durable fence, live identities/projection and acceptance
remain open; no supported deployment date or P2 exit is claimed.

The subsequently approved disposable Linux process-containment batch is recorded
above. Actual host/custody/service activation is not implicitly authorized.

Latest owner evidence is **$193 remaining / trial ends in 1 day**, with today
identified as the final usable day. No exact expiry/balance API refresh or
Snowflake/AI spend in this batch. Preserve verified recovery/source evidence;
do not provision in haste or consume credits for their own sake. No purchase,
trial extension, deployment or P3 is assumed. P2 estimate remains about 60%.

### Current completion gates (latest summary)

The local application and bounded operator source checks are implemented. P2 is
**not complete**: the live product path is still disabled and must not reuse the
operator's credentials or raw-input API adapter.

| Remaining gate | What closes it |
| --- | --- |
| Worker security | Private mTLS/delegation, retained replay, package/network/mount, restricted DB/TLS and healthy container signing transition tests pass; enforced recovery, custody/clock/readiness/deadline controls and service wiring remain |
| Snowflake isolation | Exact tenant views/coherent validation query, six runtime identities, secret custody/rollback and relevant PUBLIC/MFA/live-definition gaps reviewed; separately approved provisioning and negative tests |
| Governed evidence display | Approve the financial-trace/clinical projection and verify calculation/citation presentation; current source contract intentionally returns summary/reference metadata only |
| Local live acceptance | Both tenants/all roles through authenticated API/UI; foreign/base-table denial, role revocation/downgrade, true missing states and source failure, with bounded spend/evidence |
| Final delivery verification | Full regression/browser/build/contract checks, push verified commits under standing approval, remote CI and P2 exit review |

**30-hour trial priority:** the owner requested immediate useful live tests.
The [bounded single-statement operator check](single-statement-source-evidence.md)
now passes GOL001 SAVED, then GOL024/GOL027 MISSING with canonical validation.
Two source statements total, no retries/AI/new grants/credentials or activation;
redacted reports only. Eighteen new offline controls and **193 root tests** pass.
Final CIQ_WH check confirmed SUSPENDED/zero running/queued. A fresh private
offline code archive also passed integrity verification; it is not a DB backup.
This verifies the operator query shape, not the governed runtime/service boundary;
all five gates above remain open. Backend stays at its prior **590** result, not
rerun here. Completion estimate and public UI unchanged. Exact balance/expiry
now have owner screenshot evidence of **$194 / trial ends in two days**, but no
exact expiry timestamp; retain the stricter owner-stated 30-hour planning window.
Remaining live work must not bypass security
gates just to exhaust credits; preserve useful evidence and avoid paid purchase.

**Retained-state checkpoint:** the approved host-health prototype now retains
versioned epoch/sequence/digest and clock/measurement high-water marks in its
own explicit test-only SQLite state. Unsafe evidence latches across new
connections and separate Python processes; no silent v1 migration/reset.
This is not integrated clock/nonce authorization or stopped-generation recovery.
See [continuity checkpoint](../architecture/p2-clock-health-proposal.md).
Verification: **104 health tests** (23 new), full API/PostgreSQL **613** and
root **193** pass; Ruff/format/whitespace pass. No browser/build/container/CI rerun.
P2 remains about 60%; public UI and disabled source routes are unchanged.

**Latest offline increment:** bounded collection now checks a fixed monitoring
request with injected fake subprocesses only. It limits output/time, rejects
diagnostics and failed exits, and cleans up disposable process groups/pipes.
Bracketed clock/boot checks precede returning unsigned evidence. A retained-
consumer regression now samples after delivery to reject evidence that becomes
stale during delivery. Real daemon/version/host custody, hard synchronous-call
deadlines and worker authorization/wiring remain unaccepted. See the
[collection checkpoint](../architecture/p2-clock-health-proposal.md).
Verification: **130 health tests** (26 new), full API/PostgreSQL **639** and
root **193** pass, with Ruff/format/whitespace. No browser/build/container/CI rerun.
No Snowflake calls, grants, real credentials, deployment, push or P3.

**Signed health composition — 22 October:** the two-hop mTLS test now checks
independently signed synthetic health through a retained consumer for broker,
reader and validator, rather than returning a constant healthy flag. Across both
tenants/all three roles it preserves SAVED/MISSING, replay denial and rollback
checks; new signature and stale-at-delivery failures deny and remain latched.
Six additional loopback/private pre-bind checks deny without binding or source
work. The bridge is test-local only, with separate health and clock/nonce files:
it does **not** establish atomic state, real host health or runtime readiness.
Verification: 84 composition/pre-bind tests (42 additional), full backend 681,
root 193 and Ruff/format/whitespace pass. No browser/build/container/remote CI
rerun, Snowflake call, deployment or push. P2 remains about 60%.
The [unified state/lifecycle proposal](../architecture/p2-unified-guard-proposal.md)
defines one transaction, fresh conservative time bounds,
explicit claim interface, retained denial and stopped-generation recovery.
**Offline implementation approved:** the owner directed pushing the completed
commits and continuing. All 14 prior commits were pushed through `baf7849`.
The v3 state foundation now implements strict configuration, explicit new-file
test provisioning and bounded exact-schema/row inspection with no repair or
reset. A separate inactive signed-health observation primitive now uses that
same state boundary, with a pinned key, post-verification freshness, bounded
integer uncertainty and retained denial. Invalid health never advances prior
high-water marks or modifies nonce rows; reopening cannot clear its latch.
The next bundled milestone adds explicit already-verified claim consumption:
health/high-water marks and a single hashed nonce commit atomically. Whole
uncertainty intervals must fit `iat`/exclusive `exp` and the existing 30-second
lifetime. Safe pruning, capacity and ordinary rejection preserve truthful state;
unsafe health never prunes. Fresh-process races/replay/latch, lock and write/commit
fault tests cover conservative denial, including an ambiguous committed nonce.
Stopped primitive recovery tests retain old files and reject old assertion
generations/health trust. Assertion-signature rotation and full authority recovery
remain integration work, not proven by constructing internal verified claims.
Verification: 28 additional consumption/recovery tests; full backend 792, root
193 and Ruff/format/whitespace pass. One expected serializer warning is emitted
by an intentionally invalid copied-model negative test.
No browser/build/container/remote CI rerun locally.
No Snowflake spend, live credential, startup change or deployment. P2 remains
about 60% pending the live/operational gates below.

**Latest bundled integration:** explicit inactive v3 broker/reader/validator
classes now use the unified guard directly, not a legacy seconds-clock/replay
adapter. Generation-bound parent/child assertions are signature/schema/scope
checked before nonce spend, with fresh membership and conservative health/time
checks before delivery. Local two-hop TLS covers both tenants/all three roles,
SAVED ₹95,000 / MISSING, replay, peer/domain/child binding, permission changes,
source failure and retained health denial. Stopped offline recovery rotates both
assertion/health keys and generations/epoch, rejects old UNUSED capabilities and
preserves old files. Explicit v3 pre-bind checks deny before socket binding.
See the [latest phase checkpoint](phase-p2-checklist.md#unified-v3-broker-authority-tls-and-stopped-recovery--22-october).
Latest verification: **94 new integration tests; backend 886, root 193**, lint,
changed-Python formatting and whitespace pass. Existing negative-model serializer
warning remains; no browser/build/container/remote CI rerun in this milestone.

**Latest artifact checkpoint:** v3 broker was split into an API-only module to
remove accidental API/SQLAlchemy imports from workers. The minimal wheel/image
now packages and imports the canonical v3 authority/guard/health/transport only,
with no broker/DB/Snowflake/collector dependencies. A network-free two-container
Linux probe verifies still-unexpired replay and retained denial across restart;
default startup remains disabled. See [packaging evidence and limits](../architecture/p2-worker-packaging.md#latest-v3-artifactdomain-checkpoint--22-october).
Verification: **backend 886, root 200**, isolated worker package checks and both
v3/legacy Linux container probes pass. Lint/format/whitespace pass; invocation-owned
resources removed. Existing negative-model warning remains. No full private
mTLS/DB-TLS topology, browser/frontend build or remote CI rerun this milestone.

**Latest combined container checkpoint:** canonical v3 reader/validator guards now
pass in the five-container private mTLS + restricted membership DB-TLS topology,
including still-valid restart replay, DB trust/revocation/outage, retained unsafe
denial and pre-bind refusal. The membership image build context was corrected for
the newly packaged canonical modules. Explicit frozen fictional health/time and
a test signing driver are used; this is not actual host health or API activation.
See [acceptance scope and limits](../architecture/p2-unified-container-acceptance.md).
Twelve fixture and two package regressions added; **backend 898, root 202** pass.
Worker isolated package/default-refusal check and combined v3 container run pass.
Legacy combined replay/DB TLS, actual-Linux v3 clock/artifact, membership isolated
package/default-refusal and lint/format/whitespace also pass; owned test resources
removed. Existing negative-model warning remains; browser/build/remote CI not
rerun in this internal-only milestone.
No Snowflake/AI calls, live credential/account changes or deployment. P2 estimate
remains about 60% because the operational/live gates are not closed by test counts.

Next remaining P2 work is operational, not more primitive nonce increments.

The [operational control design](../architecture/p2-operational-control-design.md)
now specifies the next bundled milestone: an inactive supervisor with exact
eight-role/seven-state inventory, all-or-nothing readiness, bounded admission and
late-result denial, partial-start cleanup, stopped recovery and an external
generation fence. It explicitly distinguishes mock behavior from real process
containment/hard deadlines and lists unresolved host/store/health choices.
**That design-only checkpoint is now superseded by the approved offline
implementation above**; no host, daemon, secret store, provisioning or runtime
wiring is selected/activated. The model does not close real operational gates.

Remaining execution order: review real-host lifecycle/health-provider/custody/readiness/deadline/fencing and
service wiring; independently complete approved Snowflake governance/service
identity provisioning and negative acceptance, then authenticated source UI and
final regression/remote verification. No real-host provisioning or live activation
is implied by completing these offline tests. Website/default startup unchanged.
Owner permits pushing completed verified commits without another prompt;
deployment/live account changes remain separate gates.

No website deployment or P3 is included. User interviews/customer rollout and
real-data operational gates remain separate; synthetic-alpha permission does
not waive them. Detailed evidence and next actions are below.

1. [x] Complete Python reader authentication and bounded live source inspection.
2. [x] Compare all three cases against independent metadata/history expectations;
   validate available saved decisions and every citation; explicitly preserve
   absent recommendations under the approved gate revision below. Record discrepancies, never hide
   them with fixture fallback, fresh AI output or changed golden expectations.
   Live repository check passed on 19 October: GOL001 SAVED, GOL024/GOL027
   MISSING, no compared-field differences. This is summary/reference parity,
   not full calculation-trace or narrative-grounding/UI parity.
3. [x] Establish the explicit shared-domain package boundary for the API.
4. [x] Implement and test the preliminary v2 repository adapter, including source
   failure, missing data, separate tenant ownership and condition disclosure.
   Default HTTP reads remain disabled; this is not full workspace parity.
5. [x] Review source identity/effective privileges with CoCo. Operator table
   grants and disabled secondary roles are not production tenant RLS; inherited
   PUBLIC capabilities are unresolved. No account-wide revocations are approved.
   CoCo report and policy-reference follow-up received; see
   [reconciled findings](source-access-findings.md). Review is complete, but
   remediation/service identity/isolation approval and implementation remain open.
   None of the eight source tables has a row-access policy; only CLINICAL_NOTE
   has the reported masking policy. No unattended/customer deployment is approved.
   CoCo subsequently reports the approved reader/empty-secondary user defaults
   applied with grants unchanged. The reader/NONE worksheet context is verified
   after explicit USE commands; automatic fresh-login context remains unverified.
   Next: [bounded MFA/PUBLIC/isolation follow-up](source-hardening-followup.md).
   Local follow-up independently confirmed stored defaults, zero enrolled MFA
   methods and 109 visible PUBLIC grants; CIQ_WH remained suspended at inspection.
   [Results/design proposal](source-hardening-results.md) records enforcement and
   dependency visibility gaps. No new service/views or PUBLIC changes applied.
   Subsequent owner passkey enrollment is independently verified: one PASSKEY,
   HAS_MFA true; stored defaults unchanged. This supersedes the zero-method
   observation. Effective policy enforcement and second interactive login remain
   unverified; administrative dependency review is still pending.
6. [ ] Opt in separate local source identities and exercise authenticated API/UI
   parity. Keep the existing mixed offline demo and public site unchanged.
   Presentation groundwork: the authenticated local `/source-preview` now renders
   fictional v2 fixtures for SAVED/MISSING, saved QUERY/REFER and source failure.
   It does not call `/v2/cases` or Snowflake, seed source tenants, or establish
   source parity. No source access has been activated. See the latest P2 checkpoint.
   The Evidence fixture now exercises searchable clause-reference metadata and
   page links; it does not retrieve PDF content or establish narrative grounding.
   The offline v2 HTTP-client boundary is implemented with exported-schema
   validation and 41 no-network tests. It is now exercised through gated
   `/source-cases` routes in an isolated contract-test stack: real API/PostgreSQL
   identity checks, fake source gateways, two tenants and all three roles.
   Fifteen browser integration tests pass; this is not live source parity.
   Normal local startup and production return 404 for these routes. No
   persistent source identities or live connections have been activated.
7. [ ] Run regression/API/PostgreSQL/browser/build/contract checks, push verified
   commits under standing approval, then verify remote CI. Review P2 exit evidence before P3.
   - [x] Full local regression, API/PostgreSQL, client, offline source integration,
     web build/typecheck/lint, domain-wheel and contract-drift checks rerun.
   - [x] Standing owner approval to push completed verified local commits.
   - [ ] Verify remote CI for the resulting commits.
   - [ ] Live security/source acceptance and full financial-trace/evidence gates.

## Remaining P2 blockers (not website deployment)

- [x] Receive CoCo administrative follow-up report (28 metadata statements,
  owner-supplied; not independently rerun). Review found policy/count
  inconsistencies and unsafe proposed auth restrictions; receipt is not acceptance.
- [ ] Resolve effective MFA/PUBLIC dependency and live-definition gaps identified
  in the [corrected review-only proposal](p2-isolation-proposal.md).
- [ ] Review/approve the narrow service-authentication and database tenant/
  clinical-isolation implementation before provisioning anything.
- [ ] Approve a governed financial-trace/clinical projection and verify the
  calculation/citation display; the current v2 contract deliberately omits prose.
- [ ] Bounded live API/UI parity after those security gates, then review P2 exit.

Rushikesh approved the corrected architecture on 19 October. It separates tenant
projections, clinical validation, service authentication and human login changes.
The [bounded metadata preflight](p2-isolation-preflight.md) was separately approved;
CoCo reports 21 attempts with no changes/data reads/AI. Its column inventory was
compared with repository DDL; [report limitations](p2-isolation-preflight-results.md)
include missing query IDs/time evidence, policy scope and inherited-role checks.
No independent rerun or isolation acceptance is claimed. Validation hosting and
credential custody must be settled before the implementation package. Architecture
approval is not provisioning approval. No new SQL, credentials, source activation
or account changes.

Next design prepared: [local validation/credential boundary](../architecture/p2-validation-boundary.md).
It proposes four read workers plus two tenant validators, with no Snowflake
credentials in the API. Rushikesh approved the design including the two extra
validator identities. First [offline boundary slice](p2-worker-boundary-checklist.md)
is implemented: asymmetric assertions, fresh injected membership/replay guards
and canonical summary-only validator handler, with 34 new tests. Peer transport,
delegation, restart-safe replay, packaging/secret custody and live SQL/isolation
remain open. Nothing is provisioned or live; P2 remains open.

Next offline increment adds a token-verifying summary broker, fresh PostgreSQL
membership adapter, internal-user UUID subjects and immutable tenant/disclosure
routing. Broker delivery rechecks session/membership and validates response
scope. Seventeen additional disposable-database/fake-source tests pass; latest
API total is **196**, root regression **145**, with Ruff/format/whitespace checks
passing. This in-process summary composition is not the read-worker delegation
or authenticated transport implementation. No HTTP startup integration, live
source access, persistent identities, push or website deployment was added.

The website must remain unchanged per Rushikesh's latest instruction. Completing
offline tests does not waive these gates or authorise P3, public deployment,
new grants, account-wide restrictions or reuse of human OAuth in a server.

## Gates that remain open

- [ ] Five target-user interviews and reconciliation of workflow findings.
- [ ] Customer identity/SSO deployment, real-data privacy/security/residency gates.
- [ ] Pilot integration format and owner-agreed quality/latency thresholds.
- [ ] Production service authentication and database-enforced tenant isolation.
- [ ] Backup/restore, incident response and operational launch readiness.

These are not waived by synthetic-alpha permission. No real patient data,
customer rollout, autonomous denial or unsupported executable rule activation.
Policy activation continues to require explicit human approval.

## Verification and delivery checkpoint

- Latest offline integration checkpoint: root **145**, API/PostgreSQL **145**,
  client **41**, source API-to-UI **15**, normal browser **23** tests pass. Typecheck/lint/production
  build, isolated domain wheel and contract regeneration without drift pass.
  The test stack uses loopback ports 8003/3003 and a disposable PostgreSQL schema;
  no source-alpha tenants were seeded into the persistent sandbox. Graceful
  shutdown cleanup was verified after fixing Uvicorn signal replay; the three
  earlier disposable test schemas were removed explicitly, and the latest run
  leaves zero. Fixtures can recreate them; no sandbox volume/data was removed.
  Production-mode source routes return 404 even with the contract-test flag set.
  The normal local stack also verifies both source routes return 404; its web
  container was rebuilt and is healthy without enabling the contract-test flag.
  No Snowflake/AI, grants, push, remote CI or website deployment ran.

- Latest client increment: **41 no-network client tests pass**; client/web
  typecheck and lint pass, as does the web production build. No source route
  was enabled or connected. Canonical API/domain and database behaviour are
  unchanged; their Python suites were not rerun for this increment.
  Local web Docker rebuild/readiness and all **22 browser regressions** pass
  with the new locked client dependencies. No remote CI run is claimed.

- Latest presentation increment: **22 browser tests pass**, web typecheck/lint
  and production build pass. Local-only fixture route returns 404 in production
  mode in the prior checkpoint; its environment/auth guards are unchanged.
  Clause filter/title/ID matching, reset, page-link attributes and mobile layout
  are now covered. Desktop screenshot visually inspected. This tests presentation,
  not real source API/UI or service isolation.
  Python/API suites were not rerun for this frontend-only increment.

- Root regression: **145 passed** after domain-packaging regressions; root/API
  lint, API formatting and git whitespace checks pass.
- Targeted metadata/inspection boundary suite: **39 passed** this checkpoint.
- API/PostgreSQL suite: **145 passed** after the v2 source-adapter increment,
  including 44 new repository/HTTP tests. This supersedes the earlier unavailable-Docker
  test attempt. Local PostgreSQL was started for disposable test schemas, then
  stopped with its data volume retained. No volume was deleted.
- Isolated domain wheel: byte identity with all four canonical modules, frozen
  schema and missing/invalid-state smoke pass without the legacy package,
  Snowflake, Streamlit or FastAPI installed. API Docker build and non-root image
  smoke pass with network disabled for the smoke. The normal image has no
  Snowflake/Streamlit runtime dependency. API OpenAPI regenerated with no drift.
- Generated v2 OpenAPI/TypeScript contracts and web typecheck pass. All previous
  paths and component schemas are unchanged. New source routes authenticate but
  return 503 unless a repository is injected explicitly in local/test. No default
  connection, source UI/login or staging/production activation is enabled.
- Updated API Docker build and network-disabled non-root v2 schema smoke pass.
- Browser/UI and remote CI have not been rerun for this backend increment.
- Remote CI: last verified passing `d3623da`; newer local commits are not covered
  by that run. Recheck the branch before reporting an ahead count or pushing.
- Python source authentication now completed. All three independent history
  comparisons pass. GOL001's saved decision validates and matches the snapshot;
  GOL024/GOL027 have no saved decision rows, so full decision parity is open.
- All three cases have 35 scoped product-clause references. Counts are not proof
  of narrative grounding or retrieved clause text. No source backfill/AI ran.
- Final warehouse check: CIQ_WH SUSPENDED, zero clusters/running/queued queries.
- Public demo and authenticated Streamlit remain separate from the local product
  alpha. Product source integration has not been deployed.
- Preserve the untracked submission video; do not include it in product commits.

### Approved missing-recommendation scope revision — 19 October

Rushikesh approved an explicit missing-recommendation state rather than source
backfill. P2 must faithfully show an absent recommendation for GOL024/GOL027;
it must not reproduce the demo QUERY/REFER as live decisions. This revises the
original expectation of three matching saved decisions, not the remaining
source, isolation, clinical-disclosure or UI integration gates.

- [x] Pure-Python immutable SAVED/MISSING source observations and offline tests.
- [x] Missing state has only validated context and the supplied estimate; no
  invented outcome/payable/calculation/query/referral. Invalid saved rows and
  ambiguous reads remain errors, never missing-state fallback.
- [x] Explicit shared-domain package boundary (`cashlessiq-domain`).
- [x] Versioned source-read API with tested opt-in adapter; v1 is unchanged.
- [ ] UI distinguishes no saved recommendation from QUERY/REFER, source error
  and zero payable; end-to-end coverage with separate source-alpha tenants.
  Local fixture presentation is implemented; real source-alpha integration and
  its live owner/clinical-access tests remain open. The isolated real-HTTP fake-
  gateway integration now tests both tenant scopes and all three roles, not
  Snowflake enforcement or live parity. The fixture preview is explicitly
  labelled, authenticated and unavailable outside local/local-auth mode.

The existing v1 API requires an outcome, so it is unchanged. The v2 adapter uses
the new observation, but HTTP reads stay disabled by default and the UI is not
integrated. The first source view omits raw clinical prose and calculation text;
full financial trace/citation display remains open. Live repository verification
subsequently passed as recorded below. No source writes, AI calls, deployment or
historical schema changes ran.

### Live repository verification — 19 October

One operator connection explicitly used CIQ_PRODUCT_READER with secondary roles
disabled. The actual repository composed the metadata and inspection gateways;
two queue reads and three detail reads made five bounded metadata SELECTs and
twelve bounded inspection SELECTs. All three cases matched the frozen seven-field
metadata baseline and independent member/history constants, including conditions.
The frozen files were comparison inputs only, never source fallback.

GOL001's saved recommendation passed fresh canonical/citation validation and
matched outcome/claimed/payable. GOL024/GOL027 returned only the approved MISSING
state, without invented outcome/payable. Each detail contained 35 validated,
scoped clause-register references; this does not prove retrieved text/narrative
grounding. No source writes, AI, grants, persistent identity seeds, HTTP/UI
activation or deployment ran. This check exercises the repository directly,
not authenticated browser parity. Source identity/PUBLIC and UI gates remain open.
Final SHOW under the reader role confirmed CIQ_WH SUSPENDED, zero started
clusters/running/queued queries, X-Small and 60-second auto-suspend unchanged.
Incremental dollars and current trial balance were not measured.

## Latest offline increment — restart-aware replay

- [x] Optional same-host atomic replay ledger and authority integration, not
  imported into startup. Eleven new tests cover concurrent spawned processes,
  retained consumption after restart, shared capacity, expiry and fail-closed
  missing/corrupt/locked/full storage. No raw tokens or source payloads persisted.
- [x] 207 API/PostgreSQL tests, 145 root tests, root/API lint and API formatting
  pass. Existing local stack only; test schemas/files are disposable.
- [ ] Read-worker delegation, authenticated private peer transport, lifecycle/
  secret mounts, exact Snowflake isolation package and live acceptance remain.
  The replay candidate requires retained shared local state and lifecycle review;
  it is not distributed-host or deployed isolation. Default replay is unchanged.

No Snowflake/AI use, source activation, new credentials/grants, push or deployment.
The two-day credit plan is committed; actual balance/expiry remain unverified.

### Subsequent offline delegation increment

Broker-authenticated requests can now take a fixed read-relay -> tenant-validator
path in disposable tests. The broker signs separate audience/operation-bound
parent/summary capabilities with identical subject, tenant, disclosure, case and
lifetime, plus a parent nonce binding. Readers hold no signing key and forward
the enclosed summary capability unchanged. Reader and validator independently
consume replay guards and check fresh membership; broker checks again on delivery.

The endpoint checks a fixed reader/disclosure pairing against **injected fake
peer context**, not real TLS authentication. Real transport, remote membership,
packaging and credential isolation remain open. This relay returns summary only,
not a complete queue/detail read worker or approved financial-trace projection.
All HTTP startup, source/UI activation and public v2 contracts remain unchanged.

Latest verification: **255 API/PostgreSQL tests and 145 root tests** pass; root/API
lint, API formatting and whitespace checks pass. The increment adds 32 delegation
tests and reruns 16 existing broker scenarios through the delegated path. Web/
browser/build/remote CI were not rerun for these internal-only changes. No
Snowflake/AI calls, keys saved to disk, grants, provisioning, push or deployment.

## Latest transport checkpoint

The two local worker hops now have an explicitly constructed mTLS transport
candidate: required client certificates, explicit CA, IP SAN verification,
certificate pins/URI identities and certificate-derived peer context. Twenty-three
real loopback TLS tests pass, including both-hop composition, missing/foreign/
untrusted/expired/wrong-purpose credentials, spoofed headers, malformed requests,
replay and generic failure handling. Temporary test PKI is deleted by fixtures.

Latest backend total: **278 API/PostgreSQL tests**, plus **145 root tests**, with
root/API lint, API formatting and whitespace checks passing. Web/browser/build/
remote CI were not rerun for this internal-only increment. No Snowflake/AI calls,
real credentials, grants, source activation, ordinary startup, push or deployment.

This closes loopback peer authentication, not deployed isolation. Remote
membership, separate packaging/mounts, CA/signing-key custody/rotation, replay
lifecycle and exact Snowflake/live acceptance gates remain. See the
[transport checkpoint](../architecture/p2-worker-transport.md). Next: authoritative
remote membership and worker packaging preparation; do not give workers general
operational DB credentials or activate human OAuth as a shortcut.

## Latest membership checkpoint

The narrow authoritative membership service/client now passes loopback mTLS tests
without giving workers general DB credentials. Certificate identity pins the
tenant; UUID/nonce-bound responses contain only the fresh current role or null.
Revocation, lookup outages and medical downgrade deny before delivery. Both tenant
scopes/all roles compose with fake source inputs; no source endpoint was activated.

Latest verification: **312 API/PostgreSQL tests**, **145 root tests**, root/API
lint, API formatting and whitespace checks. Web/browser/build/remote CI not rerun
for this internal-only change. No Snowflake spend, real credentials, grants, push,
ordinary startup or deployment. See [evidence/limits](../architecture/p2-worker-membership.md).

Next: separate worker/membership packaging, private network and mount-isolation
tests, then reviewed secret/replay lifecycle and exact Snowflake package. P2 is
not complete; the live product path and public website remain unchanged.

## Latest packaging checkpoint

A separate minimal worker artifact now builds without API startup, DB modules or
Snowflake connector. The default image refuses activation. An explicit test-only
image passed eight-container/14-private-network checks: permitted edges work;
forbidden peers fail by hostname/direct IP; non-root/read-only/dummy-secret mount
boundaries hold. All disposable resources were cleaned up; normal local stack and
website are untouched. See [packaging evidence/limits](../architecture/p2-worker-packaging.md).

312 API/PostgreSQL and 145 root tests remain green. No Snowflake/AI, real keys,
service provisioning, live source activation, push or deployment. Deployment is
paused again at the owner's request. Next: actual container mTLS using temporary
PKI, trusted membership-service packaging/DB policy and secret/replay lifecycle.
The topology probes are not application handlers; P2 remains incomplete.

## Latest private-container transport checkpoint — 21 October

Four disposable containers now exercise the canonical delegated relay/validator
and remote membership adapters over exact private IPs with pinned temporary mTLS
identities. The synthetic SAVED summary is correct; replay, wrong identity,
cross-tenant/direct-hop access and revoked/unavailable membership deny. Per-role
read-only test key mounts hold; the eight-container topology/package smoke also
passes. See [scope/evidence/limits](../architecture/p2-worker-container-mtls.md).

342 API/PostgreSQL and 145 root tests pass; lint/format/whitespace pass and public
OpenAPI is unchanged. Disposable resources are removed. No website/normal startup,
Snowflake/AI use, real keys/grants, push or P3. This supersedes the container-mTLS
next action above, not the broader live-acceptance gates. Next: retained replay
volume/restart lifecycle using disposable keys, then trusted membership-service
packaging and narrow DB access review. P2 remains in progress.

## Latest retained replay checkpoint — 21 October

The disposable private-mTLS harness now has an explicit retained-volume variant.
Both validator and reader container restarts reject their original consumed
capabilities while still unexpired; fresh capabilities succeed afterward. Exact
per-authority mounts, file ownership/modes, hash/expiry-only contents and refused
reinitialization are checked. Missing state denies requests and listener startup
without recreating the file or falling back to memory. All test volumes are
removed after the run. See [evidence/limits](../architecture/p2-worker-replay-lifecycle.md).

342 backend and 145 root tests remain green. No production code/API/startup,
real credentials, Snowflake/AI, push, deployment or P3 changes. This closes the
offline container restart test, **not** production replay/key recovery policy.
Next: separately packaged trusted membership service and narrow DB policy, using
bounded disposable tests; retain the remaining P2 live/isolation/evidence gates.

## Latest membership package checkpoint — 21 October

Separate locked membership wheel and narrow DB adapter are implemented locally.
The adapter uses only role/ID/active columns in a fresh schema-qualified read-only
transaction with statement/lock timeouts. Artifact checks exclude API/auth/broker/
models/Snowflake and default startup refuses activation. Twenty new disposable-
schema/mocked tests pass; backend **362**, root **145**. See
[DB boundary and review proposal](../architecture/p2-membership-db-boundary.md).

This is not dedicated-principal privilege or container DB isolation acceptance:
tests use the existing local test admin connection. No persistent role/grant,
credential, source activation, Snowflake/AI, deployment or P3. Next: separately
package the membership container and verify column-grant/DB-network denial in a
disposable environment; exact production provisioning stays separately gated.
No push or remote CI is claimed.

## Latest membership container/DB checkpoint — 21 October

The membership image and disposable PostgreSQL restricted-principal test pass.
Real point lookup succeeds; 18 forbidden reads/writes/DDL/admin/function actions
fail by grants even in read-write transactions. Committed role downgrade and
user/tenant/membership deactivation are observed; required-grant revocation and
DB outage deny without missing-state fallback. Private pair networks and exact
per-service read-only secret mounts exclude DB drivers/credentials/reachability
from reader/validator containers. Default membership image refuses startup and
excludes its probe. All test resources/data/credentials are discarded; normal DB
and website unchanged. See [scope/evidence/limits](../architecture/p2-membership-container-db.md).

This is a disposable mirrored schema, not production grant acceptance. DB TLS,
real secret custody and actual mTLS-server/DB composition remain open. Next:
compose pinned membership transport with the restricted DB lookup, then continue
the remaining P2 security/source/evidence gates. No Snowflake/AI, persistent
provisioning, deployment, push or P3.

## Latest lifecycle/configuration review — 21 October

The [runtime lifecycle proposal](../architecture/p2-runtime-lifecycle.md) now
specifies the next offline fixed DB factory, material-by-service ownership,
maintenance-window rotation and lost-replay-state recovery. It identifies a
remaining clock-jump/rollback hazard: expiry pruning plus later backward time is
not protected by the current ledger. Trusted clock enforcement/recovery must be
implemented and negatively tested before activation; no automatic protection is
claimed. Stop-and-restart rotation matches the current single-key/static-pin
implementation; hot reload and zero-downtime renewal are not assumed.

Next bounded implementation: strict membership-only connection configuration and
fixed verified-TLS factory, with dummy inputs, no startup wiring and no real
secrets or network calls. Then reuse disposable DB acceptance and combine it with
retained replay. Exact encrypted secret-store/delivery and production readiness
remain separate review/approval gates. This is a documentation checkpoint only;
prior test counts are unchanged, not rerun. No Snowflake/AI, spend, provisioning,
deployment, push or P3.

## Spend guardrails

Latest recovery checkpoint, 21 October: a private ignored metadata/rebuild bundle
has been captured and integrity-verified. Eleven explicit bounded statements
(three source SELECTs) completed in 25.062 seconds with five retained query IDs.
Counts remain 2/0/0 saved rows and 35 clause references per case. The archived
canonical code passed 127 tests from a separate restored tree with no Snowflake
calls; working-tree root regression is now 155 passed. Final warehouse check is
SUSPENDED/zero clusters/running/queued. See [scope and evidence](recovery-checkpoint.md).
This is not raw-source/full database recovery, fresh decision validation or P2
exit. No runtime/API/UI activation, new credentials/grants, deployment or push.
Next: review the remaining raw recovery/live-definition disclosure scope before
expanding exports; continue offline security prerequisites if that scope is not
approved. Exact balance/expiry and live isolation gates remain unresolved.

The [bounded replay-input export scope](recovery-export-scope.md) is now reviewed
and written: staged GOL001 then GOL024/GOL027, 14 source SELECTs total, private
latest-decision JSON/condition inputs only after explicit persistence approval.
No new source reads or exports ran for this review. Live definitions/rules/grants
are excluded; the current reader does not have POLICY_RULE access. Exporter
implementation, payload guards, capture and offline replay were subsequently
completed after approval: **175 root tests pass**, including 20 exporter tests.
Stage A (12.698s) and B (9.136s) used 14 source SELECTs / 38 explicit statements;
GOL001 SAVED and GOL024/GOL027 MISSING independently replay successfully offline.
Restricted inputs are private/ignored, not committed or publicly uploaded.
See [evidence and limitations](recovery-inputs-evidence.md). No AI, grants,
source writes, runtime activation, deployment or push; P2 remains open.

21 October live checkpoint: the explicit reader/NONE connection works; eight
metadata statements confirm 13 direct grants/eight visible source tables and
suspended CIQ_WH/two visible pools. The reader reports `resource_monitor=null`,
unlike the historical CIQ_RM baseline. Source reads/exports are paused pending
targeted administrative confirmation, not an automatic monitor/grant repair.
The subsequent owner-supplied ACCOUNTADMIN/NONE report resolves this discrepancy:
CIQ_RM exists and is attached; quota 10 warehouse credits/month, 2.27 used,
notifications 50/75%, suspend 90%. No repair was made. Search returned no visible
rows, not proof of absence/suspension. See the
[inventory, limitations and bounded CoCo prompt](snowflake-expiry-inventory.md).
No source-row reads, AI, account changes or deployment ran. Exact expiry/balance
and incremental cost remain unverified; no recovery export is yet claimed.

After that confirmation, a local reader/NONE batch ran three bounded source
SELECTs: case metadata, saved-row counts and clause-reference counts for exactly
GOL001/TPA001 and GOL024/GOL027/TPA003. All expected pairs were returned;
GOL001 has two saved rows, the other cases zero, and all have 35 clause refs.
No raw decision/clinical data was read and no new canonical validation pass is
claimed. See [captured observations and limits](snowflake-expiry-source-evidence.md).
This is supervised evidence, not a coherent snapshot or API/UI/service acceptance.

Latest planning baseline: **$195 remaining and two days until expiry**, reported
by Rushikesh on 21 October, not independently verified. There is no budget for
purchasing credits afterward. Prioritize bounded source verification and private
synthetic recovery/evidence capture before further offline infrastructure work;
do not wait for every worker gate to close before preserving permitted evidence.
Use the [revised sprint budget](snowflake-budget.md): maximum $145 ordinary work
plus $50 reserve. This supersedes earlier $203/four-day and $205/18-day estimates.
Necessary bounded reads are approved; service/credential/grant packages and live
activation retain their separate exact approval gates.
Do not upgrade or incur out-of-pocket charges. Do not start agents, extraction,
search or Streamlit just to use expiring credits. Confirm exact expiry and
balance before larger batches; historical billing lags.
After expiry, continue local fixture/domain/API/UI development with live source
routes disabled. Local tests do not close outstanding live isolation gates.
No purchase, upgrade, real secret provisioning or deployment is authorized by
this budget update. No Snowflake calls were made for the planning checkpoint.

## Latest local delivery — 21 October

The prior 51 commits were pushed with owner approval; remote/local `main` matched
`1f81e76` at that checkpoint. No remote CI success is claimed for that push.

The next offline P2 increment implements the inactive fixed membership DB
connection factory: immutable/redacted configuration, single private endpoint,
fixed TLS policy, fresh connections and generic denial. Ambient `PG*` settings
deny before connection rather than being silently interpreted. **55 new offline
tests and 175 root tests pass**, with an added CI step for the new suite.
Repository Ruff, changed-file formatting and whitespace checks pass. A fresh
non-editable membership wheel includes the exact factory source and preserves
API/auth/Snowflake exclusions; the default executable still refuses activation.
The packaging check now bypasses cached local wheels after detecting one that
omitted the newly added module. Full API/DB/browser and remote CI were not rerun.
See [implementation limitations and next acceptance](../architecture/p2-runtime-lifecycle.md).
Normal startup, public UI and API contracts are unchanged. No Snowflake spend,
real credential reads, service/grant changes, deployment or P3 work.
Subsequent disposable restricted PostgreSQL/TLS acceptance now uses the fixed
factory inside the running membership service. TLS-1.3/empty-search-path,
hostname/CA/missing-CA, hostile ambient configuration, trust restoration,
disclosure/deactivation/grant changes and outage checks pass. Root **175**,
factory **55** and API/PostgreSQL **362** tests pass; lint/format/whitespace checks
pass. [Evidence and limits](../architecture/p2-membership-db-tls.md) record the
initial assertion-format correction and successful rerun. No Snowflake, normal
runtime activation, browser/build/remote CI, push or deployment for this step.
The combined retained replay/fixed-factory TLS test now passes using
`make product-worker-replay-tls`: unexpired restart replay rejection, restored
trust, disclosure/deactivation/grant changes, paused-DB outage/resume and
missing-ledger delivery/startup denial in one disposable environment. No reset
under an old signing key is attempted. The initial tmpfs DB stop/start harness
failure and corrected successful run are recorded in the
[replay lifecycle evidence](../architecture/p2-worker-replay-lifecycle.md).
All owned test resources were removed; **175 root / 55 factory / 362 API/DB**
tests and lint/format/whitespace checks pass. No normal activation, real secrets,
Snowflake, website deployment or remote CI claim.
Offline signing-generation acceptance now adds **18 cases**, covering both
tenants/all three roles and healthy/missing/corrupt ledgers. Unused, unexpired
old parent/child signatures deny after new-key construction; absent replacement
state denies even fresh signatures until explicit test-only provisioning.
Damaged state is preserved; healthy ledgers are retained; fresh new-generation
requests and restart replay rejection pass. **380 API/DB and 175 root tests**
pass, with lint/format/whitespace checks. See the
[scope and operational limits](../architecture/p2-runtime-lifecycle.md#offline-signing-generation-recovery-acceptance--21-october).
This is an offline primitive test, not container rotation, a recovery controller
or clock-safety implementation. No Snowflake, real secrets, runtime/website
activation or remote CI claims. Next: container-level signing-generation
acceptance and clock-safety design/negative tests, then secret-delivery/readiness/
deadline gates. Live isolation/evidence/P2 exit remain open.

The subsequent healthy container signing-transition increment adds
`make product-worker-generation-tls`: both authorities stop before test signing
trust changes, healthy replay files remain byte-identical, unused/unexpired old
parent and child deny independently, and new-key requests succeed. Existing
new-key restart replay, DB-TLS, trust, revocation, outage/resume and missing-state
checks are composed in the same disposable environment. See
[evidence and limitations](../architecture/p2-worker-replay-lifecycle.md#healthy-signing-generation-transition--21-october).
The initial dynamic-address invariant failure was corrected by explicitly
reserving test addresses before certificates/listeners, not weakening trust.
The corrected full container run passes and cleans up; **175 root / 380 API/DB /
55 factory** tests and lint/format/whitespace checks pass. Browser/frontend-build/remote
CI were not rerun. This increment is committed locally, not deployed or pushed.
Next: lost-state container recovery and reviewed clock-safety design, followed
by custody/readiness/deadline controls. P2 remains open; no normal/public
activation, Snowflake/AI, real credentials or P3.

The next disposable recovery acceptance adds `make product-worker-recovery-tls`.
Reader loss and validator corruption deny independently under old trust; both
authority processes stop before the new signing generation is installed. New
fixed-path ledger absence refuses startup; explicit UID-10001/no-capability
provisioning creates new files only, after mounted new trust is verified.
Fresh SAVED and unexpired old-parent/child rejection, restart replay, DB-TLS/
revocation/outage and unchanged original damaged evidence all pass. The first
initializer permission failure and corrected passing run are recorded in
[recovery evidence](../architecture/p2-worker-replay-lifecycle.md#lostcorrupt-state-container-recovery-candidate--21-october).
Root **175**, API/DB **380**, factory **55**, lint/format/whitespace pass. No
production recovery controller or corrupt-content startup detection is claimed.
Next is reviewed durable clock safety, followed by actual custody, readiness,
deadlines/shutdown and generation control. Snowflake isolation, governed evidence,
live API/UI and P2 exit remain open. No deployment, source/AI spend or P3.

## References

Latest checkpoint: the seven increments through `7c761e2` are pushed; later
local commits have not been pushed. The owner approved offline clock-safety
design/implementation. The [inactive guard and signed-path tests](../architecture/p2-clock-safety.md#offline-implementation-checkpoint--21-october)
now pass: **449 API/PostgreSQL tests (69 new clock cases)** and **175 root tests**,
repository lint, changed-file formatting and whitespace checks. Separate broker/
authority files preserve high-water and unsafe latches, serialize replay and
deny unsafe authorization/delivery across both tenants/all roles. Healthy and
unsafe separate-process restart cases pass with fake host time/health.

No real health provider/operational thresholds, container clock-domain proof,
worker packaging, readiness/recovery controller or service wiring is claimed.
Default startup/public UI/contracts and legacy ledger are unchanged; no browser,
frontend build, container or remote CI rerun in this increment. Next is the
host-health/provider and boot/suspend contract plus bounded container packaging
acceptance, then custody/readiness/deadlines. Snowflake isolation, governed
evidence and live API/UI acceptance remain open. No Snowflake/AI, secrets,
deployment or P3; completion estimate remains P2 ~60%, overall 35–40%.

The subsequent [clock-domain/artifact probe](../architecture/p2-clock-safety.md#disposable-linux-clock-domainartifact-checkpoint--21-october)
passes in two disposable network-free Linux containers with retained state:
shared boot/monotonic domain, restart replay rejection and sticky unsafe latch.
The normal artifact includes the exact guard source, excludes the test probe/API
startup and still refuses activation. Health is explicitly fake; this is not
signed/mTLS clock composition or deployment-host synchronization/suspend proof.
Both successful test runs cleaned up their owned containers/volume. Root **175**,
API/DB **449**, lint/format/whitespace checks pass. No source/AI spend, normal
runtime activation, public change, browser/build/remote CI, deployment or P3.

The next opt-in pre-bind clock-readiness candidate adds **18 tests**: both
summary listener variants deny missing/corrupt/legacy/version/generation/latch/
health/rollback failures before socket binding. Healthy loopback bind/close
requires a successful clock check and performs no source work. Full **467
API/DB** and **175 root** tests, lint/format/whitespace and isolated membership
wheel/activation-refusal checks pass. Membership Docker now copies the clock
module required by its canonical worker dependency. No normal startup change.
The [provider review](../architecture/p2-clock-health-review.md) records Linux
suspend and synchronization-evidence limits; real host-health/delivery policy,
full custody/readiness/deadlines and private signed-clock composition remain
open. No real provider, threshold, paid service, deployment or P3 is selected.
Existing combined replay/DB-TLS regression passed on sequential rerun with exact
cleanup; the first run's unexplained initial delegated-request denial is retained
in the [clock checkpoint](../architecture/p2-clock-safety.md#opt-in-pre-bind-clock-readiness--21-october),
not represented as a diagnosed/fixed defect. It does not prove guarded private
clock/mTLS composition. No security check or timeout was relaxed.

The subsequent [guarded two-hop loopback mTLS checkpoint](../architecture/p2-clock-safety.md#signed-two-hop-loopback-mtls-composition--21-october)
adds **42 cases** across both tenants/all roles. Actual signed parent/child,
clock-checked listeners, durable guard/replay and both TLS hops now compose in
one test. Truthful SAVED/MISSING and replay denial pass; unsafe clocks prevent
reads or delivery at the selected broker/reader/validator boundary. A healthy
sample cannot clear the retained latch. **509 API/DB** and **175 root** tests,
lint/format/whitespace checks pass. Normal startup/runtime code did not change;
only the shared disposable test PKI was expanded. Health, app identity/membership
and source data are still fake. This closes the loopback composition test gap,
not real host health/suspend or private-container/custody/controller/live-source
acceptance. No container/browser/build/remote CI rerun, Snowflake/AI, deployment,
push or P3 for this increment. P2 remains open.

Next decision: review the [bounded host-health prototype](../architecture/p2-clock-health-proposal.md).
The proposed Linux/Chrony collector and separately signed, boot/suspend-aware
evidence require a new explicit contract and versioned state before integration.
The earlier guard approval did not authorize operating a collector or creating
real trust material. This proposal requests offline-only implementation with
fake/recorded source input and temporary keys; no daemon installation, host
purchase, production thresholds, Snowflake spend or deployment. Current tests
remain **509 API/DB / 175 root**, not rerun for this documentation-only step.
Completion estimate stays unchanged; no real provider is claimed.

The owner subsequently approved the offline host-health prototype. Its first
[parser/signature checkpoint](../architecture/p2-clock-health-proposal.md#first-implementation-checkpoint--21-october)
adds **81 offline cases** using fake pinned-format daemon responses and temporary
independent keys. Strict bounds/source allowlists, exact upward uncertainty
rounding, signature/header/duplicate-key and domain/freshness checks pass.
Full **590 API/DB** and **175 root** tests, lint/format/whitespace checks pass.
No process/clock/file/key discovery or source access is implemented. The result
is explicitly stateless and has no v1 guard-health adapter; persisted epoch/
sequence/conflict/latch handling, bounded collection and provider/TLS integration
are next. Real host/daemon/policy/custody and activation remain separate. No
worker packaging/container/browser/build/remote CI rerun, Snowflake/AI,
deployment, push or P3. P2 remains open; completion estimate unchanged.

- [Migration sequence](../architecture/migration-plan.md)
- [P0 decisions](phase-p0-checklist.md)
- [P1 evidence and research deferral](phase-p1-checklist.md)
- [P2 evidence](phase-p2-checklist.md)
- [Snowflake integration](../architecture/snowflake-read-integration.md)
- [Budget](snowflake-budget.md)
