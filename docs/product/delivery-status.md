# Product delivery — owner dashboard

Updated 3 November 2026. This page summarizes the current product plan; the
[progress index](progress.md) and phase checklists retain detailed evidence.
Hackathon submission is finished and is not counted as product delivery.

### Restricted custody checkpoint and single-use issue — 3 November

Prepared the [inactive fake custody transaction path](../architecture/agent-custody-submission.md).
A separate custody login can checkpoint only an exact operator-bound operation,
using the pinned clinical principal and fresh clinical locks. Independent full
history verification, the protected checkpoint and external prepare stay on one
custody transaction. Original-process pending state is created only after local
commit; issue independently rechecks history/scope and consumes one retained
external marker. Restart, failed/ambiguous commit, replay, changed bindings,
revoked access and expired locks fail conservatively without refunds. No I/O
permit is returned and no transport/provider is dispatched.

The **31 new offline checks** pass in a combined **452-check** suite. Dedicated
CI passes **181 actual-login cases**, including **35 new custody cases**, the
existing 476 agent checks and all fourteen encrypted recoveries. Those recoveries
still use the owning fixture path; restricted dispatch/publication/recovery
integration and authenticated process/peer custody remain the next work.
Revision `9010fe9` passes
[full product CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41617111433)
and [private preview CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41617111576):
1,027 root, 2,099 API (nineteen expected skips), 72 membership, 58 client,
26 browser, 15 source UI and all eighteen MVP journeys. Catalog, transport
isolation, process containment, contracts/types/lint/build and owned cleanup pass.
The preview separately passes eighteen journeys, matched encrypted 22-table
restoration and both saved-workflow browser reopenings, with successful owned
fresh-volume/stack cleanup. No route, worker, startup or deployed image activates this
package. GCP is freshly verified TERMINATED with its 1,800-second STOP and Docker
Desktop is off; no paid build/run or source/provider call was made.

### Independent restricted receipt observation — 3 November

Prepared the [fake receipt observer](../architecture/agent-receipt-observer.md)
with a separate authenticated database login, protected default-disabled epoch
binding and a no-argument history command. It reads the entire bounded epoch,
including cases outside the clinical controller's allowlist, then compares the
shared canonical checkpoint identities against retained fake custody while the
epoch lock remains held. Runtime has no direct table access or history reset;
clinical controller cannot invoke this observer. Oversized/missing/contradictory
history, expiry and wrong identities fail closed. A successful observation returns
no ticket or execution permission.

All **67 new checks** pass: 30 offline and 37 actual-login cases. The combined
offline suite passes 421 checks; dedicated CI passes all 146 restricted-login
cases, the existing 476 agent checks and fourteen populated encrypted recoveries.
The latter still use the owner-connected execution path, rather than a restricted
submission service. Revision `499a6c7` passes
[full product CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41612481036)
and [private preview CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41612481048):
1,027 root, 2,068 API (eighteen expected skips), 72 membership, 58 client,
26 browser, 15 source UI and all eighteen MVP journeys. Catalog, transport
isolation, process containment, contracts/types/lint/build and owned cleanup pass.
The preview separately passes eighteen journeys, encrypted 22-table restoration
and both saved-workflow browser reopenings, with fresh-volume/stack cleanup.

The next step is a custody-controlled restricted checkpoint/issue transaction
path, followed by private publication and conservative recovery. Independent
source capture, authenticated process/secret custody and live-provider integration
remain later gates. No API, worker, executor or startup enables the new observer.
The product's synthetic MVP and tested private hosting remain complete; live agent
and customer/real-data readiness are separate unfinished milestones.

No deployed schema, roles, binding, image or source was changed. A fresh read-only
3 November check confirms GCP is TERMINATED with its existing 1,800-second STOP.
No paid build/run, Snowflake call or local Docker startup was performed.

### Restricted fake reservation and leases — 3 November

Prepared the [reservation/lease capability](../architecture/agent-controller-reservation.md)
after the restricted capture step. A protected, disabled-by-default operator scope
pins the exact login, case, fake grant, epoch, snapshot and configuration. Runtime
commands can hold approved fake allowance and claim/heartbeat an unsubmitted
operation without direct table access. Concurrent duplicates hold allowance once;
leases retain the original deadline and reject stale versions/fences. The command
path cannot submit, publish, refund, create a grant or reset cost history.

All **50 new actual restricted-login cases** pass, together with the existing
59 capture cases, 476 agent checks and fourteen populated encrypted recoveries.
The latter still use the owner-level ledger and do not establish restricted
submission/recovery integration. **27 new offline checks** pass (391 combined
offline agent/contract/controller cases). Revision `a5a0e87` passes
[full product CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41582984895)
and [private preview CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41582984446):
1,027 root, 2,038 API (seventeen expected skips), 72 membership, 58 client,
26 browser, 15 source UI and all eighteen MVP journeys. Catalog, transport
isolation, process containment, contracts/types/lint/build and owned cleanup pass.
The preview separately passes eighteen journeys, encrypted 22-table restoration
and both saved-workflow browser reopenings. The earlier fixture was corrected to
respect immutable approval/operation identities; no safeguard was removed.

The next step is independently authenticated receipt/admission verification and
restricted checkpoint, issue, publication and conservative recovery commands.
A caller-supplied "journal checked" flag/digest is insufficient. This reservation
package does not replace the existing owner-connected fake executor/ledger.
Independent source capture and provider/credential integration follow. Synthetic
MVP workflows and tested private hosting remain complete; live agent and
customer/real-data readiness remain separate unfinished milestones.

No deployed migration, role, binding, image or source was changed. A read-only
3 November check confirms GCP is TERMINATED with its existing 1,800-second STOP.
No paid build/run, Snowflake call or local Docker startup was performed.

### Current scope and controller capture — 3 November

The complete **synthetic MVP workflow set** is implemented: request intake and
fact correction, deterministic background assessment, human review, audit/outbox,
PDF quarantine/extraction, policy regression/approval/activation and access controls.
Private GCP hosting and the stable hostname were tested on 2 November. They stay
offline between approved windows. This is not completion of live agent integration
or customer/real-data readiness; the [scope table](#how-much-is-finished) distinguishes them.

Prepared the [principal-bound controller capture](../architecture/agent-controller-capture.md):
a database login-bound exact case allowlist/window, fresh clinical locks and
selected policy projection, with shared strict Python validation. The runtime
receives one function capability and no clinical/ledger table grants. Tests use
real restricted PostgreSQL logins on disposable CI: all **59 pass**, alongside
the existing 476 agent checks and fourteen populated encrypted recoveries.
Thirteen new offline client checks also pass. Revision `89586d4` passes
[full product CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41576247892)
and [private preview CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41576247912):
1,027 root, 2,011 API (sixteen expected skips), 72 membership, 58 client, 26 browser,
15 source UI and all eighteen MVP journeys. Catalog, transport isolation,
containment, contracts/types/lint/build and owned cleanup passed. The preview
separately passed all eighteen journeys, encrypted 22-table restoration and both
saved-workflow browser reopenings. Earlier superseded runs were cancelled after
correcting two test collection/name-resolution assumptions; they are not the
accepted revision.
No production role/binding or migration is installed. The existing ledger's write
methods still use their owner-level test connection; the later reservation-only
extension above does not replace that execution path.
Independent source capture, provider execution, live custody/credentials and
approved live comparison/clinical UI acceptance follow.

A new read-only check on 3 November confirms GCP is TERMINATED with its existing
1,800-second STOP backstop. No new paid build/run, Snowflake call or local Docker
startup was performed. Existing deployed images and data are unchanged.

### Default-closed fake admission and old-backup quarantine — 2 November

Implemented the [fake admission gate](../architecture/agent-admission-quarantine.md).
Migration `0005_agent_admission` creates an immutable fake epoch anchor without a
default row. Ordinary ledger construction cannot admit work. Explicit disposable
provisioning binds an empty ledger to a separate private SQLite test journal;
missing, changed or closed custody denies admission. Exact checkpoint history and
single-use issue markers persist before fake child I/O; restart never reconstructs
permission. Cross-store commit failures retain uncertainty and have no reset path. Expired
reservations also keep allowance when independent history cannot be verified;
a stale backup is not evidence that no attempt occurred.

Added 27 offline journal checks, 22 PostgreSQL gate cases and four encrypted
restore cases whose backups precede a later checkpoint/issue/publication/quarantine.
The original ten populated recoveries now include all 22 tables. Actual-child
checks also require the independently committed issue marker before startup.
Revision `93abcdd` passes [full product CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41459570300)
and [private preview CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41459570298).
The dedicated job passed **476 agent checks** and **all fourteen populated encrypted
recoveries**. Full CI passed **1,027 root**, **1,998 API** (fifteen expected skips),
72 membership, 58 client, 26 browser, 15 source UI and all eighteen MVP journeys;
catalog, transport isolation/owned cleanup, contracts/types/lint/build and process
containment also passed. The private preview separately passed all eighteen
journeys, encrypted **22-table recovery** and both saved-workflow browser reopenings.
A final recovery review added refusal to release expired reservation allowance
when history is unverified; that fix is included in the accepted revision.
Earlier superseded full runs were cancelled and are not the accepted revision.

The controller still has an owner-level test connection. Next restrict its database
commands and accounting permissions, then finish independent source capture and
the bounded provider adapter. The SQLite adapter is fake-only; live independent
receipt custody, secrets and reviewed reconciliation remain unconfigured. No route,
worker or service activates this seam. No GCP build/start, Snowflake usage or local
Docker startup was performed; the old deployed images/schema remain unchanged.

### Inactive fake executor and transport isolation — 2 November

Implemented a [bounded fake process executor](../architecture/agent-executor-boundary.md)
with **56 offline protocol/process tests** and **13 additional PostgreSQL tests**.
The durable submission checkpoint commits before child startup. Exact request,
attempt/submission IDs, mapping/configuration pins and the effective lease are
bound across IPC; returned candidates still pass fresh clinical scope and rule
validation before private storage. No human review/final amount is changed.
Child crashes, timeout, bad framing and excessive output retain uncertain
allowance and cannot obtain another coordinator submission.

The stdlib-only fake image has no database/provider SDK, network or database
credential in its disposable container test. Separate numeric identities and
exact read-only dummy mounts deny access to the other component's identity;
read-only root, dropped capabilities and resource/namespace limits are inspected.
All invocation-owned containers and the image are removed. The harness refuses
execution outside its explicit Linux CI job before contacting Docker. Ordinary
Mac checks do not start local containers. The canned fixture tests framing and
isolation, not independent source capture, actual credentials or provider parity.

The controller still uses a schema-owning test connection. Next implement narrow
controller database commands with protected accounting and fresh scope locks,
then restore quarantine/external receipt handling. Independently captured source
mapping, governed source identities, a supported bounded provider adapter and
separately approved live golden comparisons/clinical UI acceptance remain.
No API route or worker activates this fake seam; no production role or secret
was provisioned and no schema migration was added.

Revision `ad38848` passes [full product CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41434111010)
and [private preview CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41434110762).
The dedicated job passed **427 checks** (146 contract, 122 mapping, 90 original
ledger, 56 process/protocol and 13 process/ledger integration), followed by all
ten populated encrypted recovery cases. The separate container job passed and
removed all owned resources. Full CI passed 1,026 root, 1,949 API (eleven expected
skips), 72 membership, 58 client, 26 browser and 15 source UI checks, plus catalog,
contracts/types/lint/build/containment and all eighteen MVP journeys. The preview
also passed all eighteen journeys, encrypted 21-table restore and both saved
workflow browser reopenings. A process-reaping observation race in the new test
was corrected before this acceptance; the bounded descendant-cleanup assertion
remains enforced. Earlier superseded runs are not the accepted revision.

A read-only GCP check confirms the VM remains TERMINATED with its 1,800-second
STOP backstop. No new GCP build/run, Snowflake call, live grant or Mac Docker
startup was performed. Existing deployed images and data remain unchanged.

### Inactive source validation and replacement protection — 2 November

Implemented the [versioned mapping validator](../architecture/agent-source-mapping.md)
and **122 offline checks**. Existing golden IDs and captured product snapshots
have separate namespaces; tenant, request, policy/rules/evidence, source capture,
registry and tool/search definition drift fail closed. Strict integer money and
explicit nulls are retained. The validation receipt grants no execution authority;
independent source capture, governed privileges and transport remain unconnected.

The fake-only ledger now has **90 PostgreSQL tests**, adding eighteen cases for
changed mapping/configuration replacements, unresolved input amendments, concurrent
admission and rechecking old reservations at the submission boundary. Completed
or uncertain work cannot be repurchased by changing a digest/grant. Only an
expired, never-submitted reservation can be replaced under a new exact fake grant.
The ten populated encrypted recovery cases also reject changed-digest attempts
against a retained published result. No schema migration or live activation was added.

Prepared the [clinical executor boundary package](../architecture/agent-executor-boundary.md):
separate controller/transport identities, database capabilities, secret custody,
restore quarantine and a concrete denial-test matrix. It is a review package;
no service, principal, credential or grant was provisioned. Next implement the
disposable database/process boundary, then independently captured source mapping
and a provider adapter with reviewed checkpoint/lookup and latency budgets.
Stale-backup reconciliation and separately approved live golden comparisons remain.

Revision `3436411` passes [full product CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41425980997)
and [private preview CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41425980837).
The dedicated job passed **358 agent checks** (146 contract, 122 mapping and 90
ledger), followed by all ten populated encrypted recovery cases. Full CI passed
1,026 root checks, 1,880 API checks (eleven expected skips), 35 catalog, 72 membership,
58 client, 26 browser and 15 source UI checks, plus all eighteen MVP journeys.
The private preview separately passed 37 HTTP checks, all eighteen MVP journeys,
encrypted 21-table recovery and both saved-workflow browser reopenings. Types,
lint, build, contract drift, containment and owned cleanup also passed.
A fresh read-only GCP check confirms the VM is TERMINATED with a 1,800-second
STOP backstop and no external IPv4. No paid build/run, Snowflake call or local
Docker startup was needed; existing deployed images and retained data are unchanged.

### Populated agent recovery completed; source mapping prepared — 2 November

Revision `ac48b19` passes
[full product CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41423257127)
and [private preview CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41423257133).
The dedicated agent job passed 218 existing checks and **ten populated encrypted
recovery cases**. Each backup restores all 21 tables, including nonempty grant,
operation, attempt and comparison records. Stable submission IDs, private results,
allowance accounting, database guards and no-resubmission behaviour survive the
restore; valid unsubmitted work can finish once within its original deadline.
The original schema remains unchanged and temporary restored databases are removed.
See the [recovery details](../architecture/agent-run-ledger.md).

Full CI also passes 1,026 root checks, 1,740 API checks (the ten CI-only restores
are skipped here and run in their dedicated job), all 18 MVP journeys in each
workflow, and encrypted preview recovery/browser reopening on the restored volume.
Types, lint, build, contract drift, containment and owned cleanup pass.

Prepared the [source mapping review](../architecture/agent-source-mapping.md)
from repository definitions: legacy and product request/policy IDs, policy
versions, evidence hashes, strict monetary/null handling and remaining-cover
snapshots require explicit mapping. No source transport or permissions are applied.
Next implement offline mapping fixtures and prepare the clinical execution
boundary, then review the bounded provider adapter/latency budget. Recovery from
a backup older than an actual submission needs reconciliation or quarantine
before live execution. Live golden comparison and joint human acceptance remain.

No GCP build/start, Snowflake call or operator Mac Docker start was needed.
A read-only cloud check confirms the VM remains TERMINATED with its 1,800-second
STOP backstop. Existing deployed images/data and the closed usage ledger remain
unchanged; the private hostname stays offline between approved windows.

### Named hostname tested; fake-only agent ledger implemented — 2 November

The owner approved a new 30-minute GCP window using the existing accepted images.
`cashlessiq-test.hulage.in` now reaches the owner-gated app with the correct HTTPS
origin: all **18 deployed browser journeys** and **35 direct HTTPS checks** pass.
The smoke harness now waits for role-switch sign-in navigation before making a
shared-cookie request. The public fixed-example demo remains independent. See
the [named-host receipt](gcp-named-host-2026-11-02.md); the private site is expected
to be offline between approved windows under the stop-between-tests policy.
The VM was verified TERMINATED at **14:58:06 IST**, with no external IP or
reserved addresses. This second session used about 15 observed minutes; today's
conservative recorded total is 2,780 seconds (about 46 minutes), with no open
session. DNS/token/origin configuration and the database volume are retained.

The [inactive fake-only ledger](../architecture/agent-run-ledger.md) now has four
PostgreSQL tables, owned foreign keys, stable operation identity, atomic allowance
reservation and submission checkpoints, renewable fenced leases, conservative
unknown accounting and atomic private comparison publication. Its 72 database
fault/concurrency checks and the earlier 146 contract checks pass in disposable
CI. The migration cannot admit live grants; no route/worker/provider adapter is
connected. Source/CI changes do not upgrade the existing cloud app/database.

Revision `2433424` passes [full product CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41419930718)
and [private preview CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41419930694):
1,026 root checks, 1,740 API checks, the separate 218 agent checks, all browser/MVP
journeys, encrypted 21-table recovery and both saved-workflow browser reopenings.
Contract drift, types, lint, build, containment and owned cleanup pass. Agent
tables were empty in that preview run; separate populated recovery is recorded above.

For the current synthetic app, deployment and workflow acceptance are established
by the checks above and the earlier manual owner session. Further testing follows
each change. Agent integration is still a separate milestone: governed identities/
database privileges, request-policy-evidence transport, remote checkpoint/lookup
and timeout budget, stale-backup reconciliation/quarantine, explicitly approved live golden
comparisons, clinical display and joint human acceptance remain. Production and
real-data gates remain separate; a project-wide testing percentage would hide
these materially different scopes.

### Inactive agent contract and offline fault tests — 2 November

The [v1 agent comparison contract](../architecture/agent-comparison-contract.md)
now binds the selected request/policy/evidence/review versions and validates
strict monetary lines and exact owned citations against the shared rules core.
The policy payload excludes other requests' regression examples. The fake-only
lifecycle checks stale scopes, closed reviews, lost fences and deadlines;
uncertain responses block automatic second attempts in the simulation.

All 146 offline contract tests pass, including the thirty canonical examples
and full equivalence between the existing and selected-policy calculation
entry points. The existing root regression also passes (1,018 checks, three
skips), together with repository Python lint and whitespace checks.
This is not live agent parity or durable duplicate-call protection.
No agent route, live adapter, schema migration or embedded-worker wiring was
added; GCP and Snowflake execution remain inactive. Remaining work includes the
durable run-ledger/lease/cost implementation and governed source-version mapping.
The [durable-stage proposal](../architecture/agent-run-ledger-design.md) records
the operation key, durable submission checkpoint, conservative reconciliation,
publication transaction and crash/concurrency acceptance matrix. It is design
only; the next implementation uses a fake gateway and disposable PostgreSQL.

Revision `2878ff7` passes [full product CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41415294397)
and [private preview CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41415294434):
1,668 API checks (one skip, two existing warnings), 1,018 root checks (three
skips), 72 membership, 35 catalog, 58 client, 26 browser, 15 source UI and all
18 MVP journeys. The owner preview separately passed all 18 journeys, restored
and matched 17 tables, then reopened the saved workflow after restart and fresh
restore. Contracts/types/lint/build, containment and cleanup passed. A fresh
GCP read confirmed the VM remains TERMINATED; no new paid build/run was opened.
The existing deployed image remains unchanged; the inactive agent contract is
source/CI preparation only.

### Stable address configured; agent integration next — 2 November

The owner signed in to Cloudflare. The dedicated `cashlessiq-private-test`
managed tunnel and proxied CNAME `cashlessiq-test.hulage.in` are saved, routing
only that hostname to the password-protected loopback gateway on port 3080.
No connector or GCP VM was started; the new hostname is not yet end-to-end tested.
The public prototype remains at `cashlessiq.hulage.in`. The selected first-level
test hostname avoids the deeper-subdomain certificate issue in the earlier
suggestion. See the [configuration and next-window handoff](stable-private-domain.md).

The deployed rules/workflows do not yet call the retained Cortex Agent. The
[integration sequence](../architecture/product-agent-integration.md) records
request/policy version mapping, governed identities, input/output validation,
uncertain paid-call handling and the current 60-second job lease versus the
legacy agent's 120-second execution budget. Offline preparation does not close
live-source gates or authorize paid execution.

Revision `aaecef5` passes [full product regression](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41389177084)
and [private preview CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41389176994):
58 client checks, all existing API/browser/MVP checks, owner gate and encrypted
17-table recovery with both browser reopenings. DNS/TLS reach Cloudflare;
HTTP 530 is expected while its connector is inactive. The public demo still
returns 200, and a fresh read confirms the GCP VM remains TERMINATED with no
external IPv4 or reserved addresses. No new GCP image was built or paid run opened.

### First GCP test completed; VM stopped — 2 November

The owner tested the private preview and requested another engineering browser
pass. All 18 deployed checks passed in one uninterrupted 4.8-minute run, without
retries, using a 240-second overall ceiling and unchanged action/navigation
limits. This includes the long journey that needed an isolated rerun during the
initial deployment. A separate manual UI journey verified missing diagnosis and
procedure → QUERY with no calculation → reviewer information request → corrected
facts → INR 95,000 reassessment → resumed and completed review, with five audit
versions. Processor access hid clinical details and the clinical correction note.
No blocking defect was observed in these checks; this is synthetic testing,
not production or load acceptance.

All steady containers were healthy with zero restarts/OOM state. During the
additional four-minute sample, minimum estimated host available RAM was
1,041.4 MiB and swap use stayed zero. No second build, resize or local Docker
was needed. The tunnel and app were shut down, retaining the database volume.
At **09:34:46 IST**, a live read verified the VM was **TERMINATED**, with no
assigned external IPv4, no active STOP deadline and zero reserved addresses.
The preserved usage ledger records 1,901 seconds (about 32 minutes) for today,
with the session closed. Disk/image/source retention continues; the temporary
preview is offline. See the [2 November receipts](gcp-first-run-2026-11-02.md).

### GCP billing linked; build and test next — 1 November

The owner approved the first bounded cloud test: billing linkage, one build,
at most four hours of VM use and retained disk/image/source storage. Google
rejected the billing link with `Cloud billing quota exceeded`; a fresh read
confirmed billing was disabled at that checkpoint. Five other projects are linked to the only
open billing account. No build or VM was started, and Docker stayed off.
At the owner's explicit request, the agent submitted the quota-increase form
for one additional billing-linked project. Google confirmed submission and
said a reply typically takes about two business days. Google subsequently
approved the request at 17:14 IST, with up to one hour for propagation. The
agent verified the approval email. After the owner asked to check again, the
approved billing link succeeded at approximately 21:08 IST; an independent read
confirmed billing enabled on Firebase Payment. At that checkpoint no build or VM had started. Offline Compose and
package/checksum checks pass; actual cloud acceptance was still outstanding.
Keep the existing dedicated project; no additional project is needed. The [first-run handoff](gcp-first-run-2026-11-01.md) records the
approval, exact failure, submission receipt, prepared inputs and next step. Earlier statements
below that paid actions were unapproved describe their historical checkpoints.

### Policy wording uploads preserve proposals — 1 November

Uploading optional policy wording previously navigated away from the authoring
page and discarded an already-started proposal. Confirmed wording uploads now
stay on that page, update only the extraction panel and clear only the upload
controls. The proposal fields, edited clauses/rules/examples, command ID and
selected source remain mounted. A confirmed upload receives a fresh command ID
for another file; a failed or uncertain response keeps the file and original ID
for an identical retry. An unavailable progress read is reported separately from
the confirmed upload. No draft values are written to browser storage.

Requested progress reads now survive a hidden/offline pause even when the last
loaded data was complete, while retaining the two-minute observation bound.
Local types, lint and all 55 client checks pass. Revision `7940886` passes the
[private preview run](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41277424414):
37 HTTP gate checks, all 18 MVP browser journeys, encrypted recovery matching
17 tables, browser reopening after restart/fresh-volume restoration and owned
cleanup. The new real-upload journey verifies retained authoring edits, repeated
uploads, selected wording and the final saved proposal. The lost-response test
commits an identical upload through authenticated HTTP before dropping the
browser response, then confirms that retry creates no duplicate document.
[Full product regression](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41277424482)
also passes at that revision: 1,018 root checks (three skips), 1,522 API checks
(one skip, two existing warnings), 72 membership, 35 catalog, 55 client, 26
browser, 15 source UI and all 18 MVP browser journeys, plus contracts, types,
lint, build, containment and owned cleanup. The runtime bundle below is unchanged;
the next separately approved API/web image build must use `7940886` or a later
accepted revision. Docker remains off and paid GCP actions remain unapproved.
The planned 31 October date has passed; the sequence below is the
handoff for the next owner-approved testing window, not evidence of deployment.

### Daily usage accounting prepared — 29 October

The GCP handoff now includes a persistent operator usage ledger: verified start
and completed-stop receipts, cumulative allowance across restarts, India workday
boundaries and an earlier `stop_by` deadline when some of the four hours have
already been used. Unclosed sessions continue counting until STOP is observed.
Missing receipts, replaced VMs, reversed time and mixed historical/live evidence
fail without replacing prior history. This is conservative local accounting,
not a billing meter or a cloud-enforced cap. No actual VM history, Docker start
or paid action was performed. Revision `3735e6f` passes 88 focused offline
usage/instance/package/measurement tests, repository Ruff and the Compose-only
preflight. The full
[product run](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40910782084)
passes 1,018 root checks (three skips), 1,522 API checks (one skip, two existing
warnings), 72 membership, 35 catalog, 51 client, 26 browser, 15 source UI and all
16 MVP browser checks, plus contracts/types/lint/build/containment and cleanup. The
[private preview run](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40910782236)
passes 37 gate checks, all 16 MVP browser journeys, encrypted recovery matching
all 17 tables, both recovery browser checks and owned cleanup.

The refreshed minimal runtime archive is
`output/gcp-preview/cashlessiq-gcp-preview-3735e6f18f93.tar.gz`, SHA-256
`5233ca09a9ba10d9e825b793caeb1a1587b3c754357593241f4b4d69b65f2cea`.
Checksum/manifest verification and a fresh temporary extraction pass the instance
checker and historical usage record/status commands. That temporary ledger was
removed; no actual cloud-usage ledger was initialized. This replaces the earlier
runtime archive for the next handoff, while application behavior remains the
accepted workflow baseline below.

### Saturday testing preparation — 29 October

The owner selected **Saturday, 31 October** for joint testing and GCP use.
Engineering continues with Docker off and cloud spending unapproved until the
specific cost/window decision. The [Saturday sequence](saturday-testing-2026-10-31.md)
covers the remaining operational acceptance without repeating earlier owner tests.

A new usability increment updates read panels for assessments, supporting PDFs,
policy regressions and policy wording without reloading forms. Pending work has
bounded foreground checks; hidden/offline tabs pause, failures stop checking and
specific jobs have inspect/retry pages. Form entries and action versions remain
mounted. New tests exercise these limits, role projections, worker completion
races and browser form preservation. Final code `1adafa8` passes both
[full product CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40906659813)
and [private preview CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40906659753).
Acceptance includes 982 root tests (three skips), 1,522 API (one skip), 72
membership, 35 catalog, 51 client, 26 browser, 15 source UI and all 16 MVP browser
checks, plus contracts/types/lint/build/containment. The preview also passes
encrypted restore matching all 17 tables, browser reopening after restart and
fresh-volume restoration, and owned cleanup. Successful-save browser checks now
wait for document navigation, avoiding stale results during a pending save.
The status query reads only metadata and adds no SQL deprecation warnings.

The accepted runtime archive is
`output/gcp-preview/cashlessiq-gcp-preview-1adafa88fbe7.tar.gz`, SHA-256
`a744de8e39ffce1ba51207d406df81ceb9b9c56b8d56c452c4d0623a313c75de`.
Its checksum, manifest and fresh temporary extraction pass the offline checker
and sampler import. It supersedes the older engineering archive below for this
handoff; it still contains no application source, credentials or owner media.
No Docker or paid GCP resource has been started. Actual GCP access, host fitness
and off-machine backup custody remain operational checks, not completed work.

### GCP handoff checks accepted in CI — 29 October

Final engineering revision `dd459e8` passes
[full product CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40841606501)
and [private preview CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40841606646).
Product checks include 982 root tests (three skips), 1,521 API tests (one skip),
72 membership, 35 catalog, 41 client, 26 browser, 15 source UI and 13 MVP browser
checks, plus contracts/types/lint/build and containment. The preview passes all
13 MVP journeys, encrypted fresh-volume recovery, browser reopening after
restart and restore, and owned cleanup. All 52 focused instance/measurement/
package checks also pass locally without starting Docker.

Twelve preview samples report individual container highs of database 48.2 MiB,
API 97.5 MiB, web 99.3 MiB and gateway 15.6 MiB, totaling 260.7 MiB before
rounding (the highs need not be simultaneous). The Linux **CI runner**, with
15,983.9 MiB usable RAM, reports a minimum available-memory estimate of
13,648.5 MiB and zero initial/sampled swap use. These validate host sampling;
they do not establish fitness of the proposed 2 GiB VM or capture short peaks.

The minimal runtime archive at `output/gcp-preview/cashlessiq-gcp-preview-dd459e823f93.tar.gz`
has SHA-256 `11c61c2bc61cdc0b1f79db9efc571b6f6b5ee04dde49b26d807444d073faefa5`.
Its checksum and file manifest pass, and a fresh temporary extraction runs the
offline instance check and sampler import. It includes no credentials, app
source or owner video. No local Docker or paid cloud resource was started.
The next operational milestone is the first explicitly approved four-hour GCP
test: actual host fitness, remote HTTPS, access controls, recovery and completed
VM shutdown. Billing approval and real off-machine backup custody remain open.

### Whole-host memory observation prepared — 29 October

The foreground preview sampler now has an explicit `--include-host` mode for
Linux: usable RAM, the minimum sampled `MemAvailable` estimate, initial swap
use and its sampled high, alongside the existing container observations. Missing
or malformed required counters fail rather than silently claiming evidence;
unavailable Linux counters prevent the wrapped command from starting. Browser
CI enables the mode, and the minimal runtime bundle includes it for the actual
VM. The operator guide has a bounded two-minute sample during cross-device
testing. All 51 focused measurement/instance/package checks pass locally; this
does not establish a whole-VM fit before a real approved GCP run. No local
Docker or cloud resource was started.

### Read-only GCP start/stop acceptance — 29 October

The operator now has a checker for the actual reviewed instance and its
four-hour STOP deadline, and a separate stopped-state acceptance requiring
`TERMINATED` with no assigned external IP or reserved external address in the
dedicated project. Wrong projects/sizes, longer timers, attached resource
policies, transitional/suspended states and retained external addresses fail.
Its live mode uses only fixed-project describe/list calls with prompts disabled;
offline fixtures are explicitly labelled historical and never contact GCP.
The [operator sequence](../../deploy/gcp-preview/README.md) includes both checks.
All 37 focused instance/runtime/package checks pass locally, along with Ruff and
the Compose-only preflight. No Docker daemon, cloud API, VM or paid build was
started for this work. Cumulative daily hours, disk/image retention costs and
firewall/IAM acceptance still need operator verification during an approved run.

The preceding four-hour plan at `27ade5c` passed both
[full product CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40814433252)
and [private preview CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40814433298).
The new checker is prepared and offline-tested; no actual GCP VM is claimed.

### On-demand four-hour GCP policy — 29 October

The owner selected active testing only: finish code/builds before starting the
VM, use at most four hours total per working day, and stop early when done.
The current plan and operator sequence use a four-hour automatic STOP, with no
automatic daily start. Each restart resets that timer, so cumulative daily use
must be tracked separately. Billing linkage and provisioning still require
explicit approval; no paid resources have been started. Docker stays off on
the Mac. This supersedes the earlier eight-hour proposal recorded below.

### GCP private test handoff prepared — 29 October

A minimal runtime bundle and VM helper now connect the accepted CI revision to
the proposed first cloud run. The bundle lists and hashes only the four Compose
files, Caddy gateway, plan and runtime helpers. The helper refuses mutable image
tags and wrong-project digests, checks the private configuration and full
synthetic composition, and uses prebuilt images. The
[operator sequence](../../deploy/gcp-preview/README.md) covers the four-hour
STOP, tunnel, memory acceptance and cleanup. Local checks exercise the helper
without creating GCP resources. Billing remains disabled; the first paid test
still requires an approved spend and test window.
The earlier `f377278` bundle below used the superseded eight-hour plan; use a
new bundle from the committed four-hour plan for deployment.
The committed `f377278` bundle was extracted into a fresh temporary directory
and passed its own Compose-only runtime check. Its SHA-256 is
`343f85e93c26258da7327f938aff2570dea1a98fc26ae7a2b0a2154ddf4153c6`.
[Private owner preview CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40806424789)
and [product foundation CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40806424644)
both passed at that revision. This is package and disposable-CI evidence, not
an actual GCP VM or remote HTTPS acceptance.

### GCP MVP composition corrected — 28 October

The first GCP preview must include the synthetic MVP overlay as well as the
owner gateway, small-runtime and GCP image overlays. A no-cloud preflight now
checks the complete Compose configuration, exact digest placeholders, workflow
flags, loopback-only gateway and effective memory ceilings. The API/embedded
worker needs 512 MiB, making the steady container ceiling **1,408 MiB** on the
proposed 2 GiB VM. The first remote run still needs a current cost review,
explicit billing/provisioning approval and observed host-memory acceptance;
no GCP resource was started or charged by this correction.
The [private preview run](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40700195977)
passed the new preflight, full MVP browser workflow and encrypted fresh-volume
recovery at `f402286`. The separate
[product foundation run](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40700195755)
passed its database, API and browser jobs at the same revision.

### Encrypted-to-volume CI integration — 28 October

The disposable owner-preview recovery now decrypts a verified GPG backup with
a separate temporary private keyring and restores the decrypted dump into its
second, empty PostgreSQL volume. Its browser check reopens the saved synthetic
workflow from that volume. The [private preview run](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40693580097)
passed the complete workflow, encrypted restore, both recovery browser checks
and owned cleanup at `c4b5fcc`. The separate
[product foundation run](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40693580136)
passed its database, API and browser jobs. This remains same-runner testing,
not off-machine custody or a GCP deployment.

### Encrypted transfer preparation — 27 October

The verified synthetic backup can now be wrapped in a single private GPG file
for an owner-selected recipient key, then decrypted into a new directory with
archive-entry and manifest checks. This is an offline helper: no key was created
for the owner, no backup was uploaded, and no different-host recovery is claimed.
An ephemeral local test key encrypted and decrypted the current 17-table
synthetic backup; the recovered package passed independent verification and the
temporary key and copy were removed.
The [recovery guide](mvp-recovery-rehearsal.md) includes the exact transfer and
verification commands. The recipient key, off-machine destination and an actual
retrieval/recovery exercise remain to be chosen and performed.
The [full product CI run](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40514442472)
passed at `0323f7c`, including root, database, API and browser workflow checks.

### Current backup integrity — 27 October

New synthetic MVP backups bind the verified table inventory to the exact dump
bytes with a SHA-256 digest. A standalone, Docker-free command checks a private
copied backup before it is considered for restore. The current local database
again restored and matched all 17 tables; a private copy of its new backup
passed offline verification and the owner app remained available. This detects
accidental copy damage. External encrypted custody and recovery on another host
remain unverified; no GCP or Snowflake action was taken.
The [private preview run](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40511629064)
and [full product run](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40511628981)
both passed for `80fe291`.

### Current data recovery check — 26 October

The [current-MVP recovery rehearsal](mvp-recovery-rehearsal.md) now makes a
consistent private backup of the existing synthetic database, restores it into
a temporary database, and compares all table contents and schema columns.
The local owner app stays available. Disposable preview CI also exercises a
database/application restart and reopens the saved workflow in a browser. It now
restores the same backup into an independent, empty PostgreSQL volume in a
second disposable preview and reopens that workflow there too.
This is a private testing recovery check; GCP remains preparation only.
The [accepted preview run](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40330569264)
passed all 17 table comparisons, the restart check and both fresh-browser
recovery checks. [Full product CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40331362155)
passed at `a64f8d1`, including 916 root, 1,521 API, 26 browser, 15 source UI
and 13 MVP browser checks. These are same-runner, synthetic recovery checks;
off-machine backup custody is still unverified.

### Current: easier synthetic testing — 26 October

Owner feedback exposed missing workflow navigation and confusing inactive-policy
intake. Those routes, role-specific links and errors are fixed. The next usability
batch at `7c1ea94` replaces JSON editing with normal controls for policy clauses,
supported rule parameters, regression examples and request fact corrections.
Failed saves retain entries in the open form; these are not durable drafts.
Policy/request lists now provide tenant-scoped search and previous/next pages.

Local verification passes 13 MVP browser, 26 existing browser, 41 client and 24
focused MVP API tests, plus types, lint, Ruff and generated contracts. The agent
also verified rejection/correction/retry in the actual app browser. See the
[current UI testing report](ui-testing-2026-10-26.md) for the evidence and limits.
The fresh [production preview](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40277868633)
passes all 37 gate checks and all 13 MVP browser tests on the standalone server.
The [full product run](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40277868637)
also passes: 913 root, 1,521 API, 72 membership, 35 catalog, 41 client,
26 existing browser, 15 source UI and all 13 MVP browser tests, plus
contracts/types/lint/build/containment.

Local synthetic testing remains ready. GCP, billing, live data and paid gateways
remain unactivated; the owner can focus on usability rather than repeating the
technical test suite.

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

### Earlier checkpoint: local two-person testing; GCP preparation only — 25 October

Local navigation follow-up: filtered queue links now carry the bounded reference,
recommendation and page into case detail, and “Back to case queue” restores that
context. Unknown case IDs have a workspace recovery page with a queue link,
without a substitute recommendation. Existing browser journeys now check the
filtered round trip and unknown-case recovery. Local lint/types pass; all 26
browser checks passed against the refreshed local app (34.7 seconds, one worker).
The development composition now mounts only `apps/web/src` read-only, so source
edits reload without image builds. Only the existing web container was replaced
using its existing development image, with builds/pulls/dependency changes
disabled. API, database and Redis container IDs are unchanged; web remains healthy
and loopback-only. No second stack or cloud resource was started.
Implementation `8aa2511` passed
[full product CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40185775870)
and the [37-check production preview](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40185775770).

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

The earlier 35–40% estimate described the read-only checkpoint and is no longer
current. The synthetic MVP workflow set is implemented and tested. Readiness for
real data or customers is a separate milestone; a percentage would obscure the
external approvals and validation still required.

| Phase | Finished for private synthetic testing | Still required before real operation |
| --- | --- | --- |
| P0: product direction | Approved initial scope, architecture and policy | Validate assumptions with design partners |
| P1: foundation | Frontend/API/database, seven roles, membership, contracts and CI | Deferred user interviews before customer rollout |
| P2: case/source reads | Golden case workspace and complete eight-service synthetic physical acceptance | Approved governed live sources and operational custody |
| P3: reviewer workflow | Assignment, comments, human actions, version conflicts, immutable audit and transactional outbox | Domain-owner acceptance and authorised external analytics delivery; local projection is working |
| P4: assessment jobs | Durable asynchronous rules assessment, leases, recovery, retries, dead-letter handling and validated persistence | Authorised live AI/search gateways and operational service monitoring |
| P5: ingestion/policies | Synthetic PDF extraction, input history, supported rules/clauses, regression, second-person approval, activation and rollback | Real-data storage/retention, malware scanning, OCR and customer policy validation |
| P6: migration completion | Prototype remains independently available | Parallel reconciliation and retirement after a real integration is proven |

## Earlier accepted local baseline — 25 October

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

These remain governed live-source exit gates. The owner's later expanded scope
authorized synthetic P3–P5 workflows while those real-source gates stay open;
their implementation does not imply a P2 production exit.

## Deployment and next decision

The private GCP app and [stable hostname](stable-private-domain.md) passed
synthetic testing on 2 November. The existing e2-small VM is stopped; local Docker
stays off. `cashlessiq-test.hulage.in` is expected to be offline between approved
windows. The public `cashlessiq.hulage.in` fixed-example demo remains independent.
The old temporary tunnel address is retired.

The deployed app still uses revision `79408862a15454565f09744edd90c25b3d4df1d4`
and schema `0003_mvp`. Subsequent agent engineering exists in source/disposable
CI and is inactive. A new image build, migration rehearsal and VM test need a
concrete approval of charges/window before deployment; previous paid windows are
closed. No larger VM is assumed necessary.

Continue offline/disposable engineering on controller commands/accounting,
independent source capture, provider transport and live custody. Then present the
exact synthetic cases, tools/configuration, credential scopes, attempts, latency
budget and expected charges for a bounded comparison and joint human test.
Customer identity/OIDC, real-data privacy/storage, operational custody and
design-partner acceptance remain separate release gates.

The owner reports adding Snowflake payment information on 25 October; account
status, balance and current resource usage have not been independently checked.
Ask before payment-related actions or new spend, including warehouse/query and
AI/serverless usage. Continued development uses synthetic fixtures without
depending on paid access. Preserve existing private recovery evidence; if
the source is unavailable, use labeled fixtures for development and report
unavailability truthfully. No bulk AI calls or credit-burning work is planned.
