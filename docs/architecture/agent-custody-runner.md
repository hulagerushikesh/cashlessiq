# One-shot synthetic custody process

24 November 2026. Source preparation only; no automatic service, migration,
deployed activation, Snowflake/provider access or paid cloud action.

The manually launched `ciq_api.agent_custody_runner` replaces custody's test-only
interactive helper in the two app-to-result acceptance journeys. It constructs
one original `FakeCustodySubmission` and calls `run()` once: independent receipt
verification, checkpoint/prepare, issue, bounded canned exchange, then validated
publication. Stage failure ends the process. No queue scan, recovery, retry,
owner connection, direct journal, permission creation or human decision exists.

## Operator delivery and startup

After a confirmed [clinical claim](agent-claim-runner.md), the trusted operator
must separately assign that exact operation in the protected custody registry.
A claim receipt and private startup plan do not grant that authority.

The operator supplies `/run/ciq-agent-custody/custody.json`: strict protocol
`ciq-fake-custody-v1`, database/login names and original OIDs, private password,
receipt schema, request ID, reserved claim, fake epoch pin and distinct receipt
server UID. The claim version is a strict positive bounded integer; pending or
final operation states are rejected. Hosts, DSNs, socket/command selectors,
tenant/actor/grant selection, retry flags and candidate fields are forbidden.

The bounded 8 KiB file must be owned by the runtime UID, single-link, regular and
mode `0600`. Descriptor-relative opening walks every absolute ancestor without
symlinks, requiring root/runtime ownership and no group/other write. Nonblocking
opening rejects FIFOs before reading; duplicate JSON keys and nonobjects fail.
Missing files fail without provisioning, creation, repair or fallback.

The installed environment launches with `-I -B -m ciq_api.agent_custody_runner`,
no arguments/stdin and the clinical runner's same nonroot Linux identity,
capability, NoNewPrivs and clean-environment checks. Core dumps are disabled and
a 35-second alarm bounds the process. The supervisor must independently bound
resources and kill/reap the entire owned process hierarchy, including a separately
sessioned transport; the runner is not a service manager or production sandbox.

Only fixed loopback PostgreSQL at `127.0.0.1:5432` is constructed, with NullPool,
three-second connect, five-second statement, two-second lock and eight-second
idle transaction timeouts. Every physical connection requires the original
database/login names and OIDs, equal current/session identity, nonadmin NOINHERIT
LOGIN, no memberships in either direction and no database ownership. This reuses
the clinical identity guard; full effective-ACL installation auditing remains
separate. There is no owning-application DB fallback.

The receipt endpoint is fixed `/run/ciq-agent-receipts/ipc/peer.sock`. The existing
client validates safe server-owned ancestors and both kernel UIDs before any
protocol payload; fake epoch/full retained history and independent SQL authority
remain mandatory. It cannot provision/reset the journal. The receipt process
still needs its own production startup/supervision and durable storage policy.

## Fixed canned child and publication

Only `sys.executable -I -B -m ciq_api.agent_canned_exchange` can be launched.
The existing bounded transport clears environment/inherited descriptors, limits
request/reply/time, permits one exchange and kills/reaps its owned process group.
No executable, fixture path or credential can be selected by an input field.

The canned child reads only fixed `/run/ciq-agent-custody/candidate.json`, a
private operator-supplied synthetic candidate bounded to 128,000 bytes, under
the same descriptor/file checks. It checks the typed bounded request, duplicate
keys, current deadline and exact operation `run_id`, then returns that candidate
in the existing request-hash-bound envelope. It performs no provider call or
independent source observation. The candidate is deliberately untrusted: only
the original custody coordinator's later fresh scope, deterministic money and
owned citation checks can publish it. Missing or invalid output after issue
retains the uncertain attempt; it never refunds or retries.

The child shares custody's trusted UID and installed API environment. Although
no credentials are passed, this is **not** protection from hostile child code
reading same-UID credentials or contacting the DB. It is a canned-only rehearsal,
not replacement evidence for the separate transport-isolation suite or live
provider containment. Root and runtime UIDs remain trusted file owners.

Only a confirmed publication emits `fake_custody_published` and exit 0. Every
failure emits fixed `fake_custody_unavailable` and exit 1, without credential,
clinical output, driver detail or traceback. Lost success output is uncertainty;
relaunch cannot reconstruct pending issue/candidate authority or repeat work.

## Verification and remaining activation

Offline checks cover strict selectors/claims, private files and ancestors,
fixed engine/peer/child construction, original-instance sequencing, disposal,
output redaction and operation/deadline-bound canned responses. Actual Linux
CI replaces both successful and invalid-money HTTP journeys with the packaged
custody module. Eight pre-attempt faults cover replaced DB/login OIDs, public
plan, environment injection, wrong UID, root, wrong peer UID and revoked custody
assignment. A missing canned file after durable issue stays held across relaunch.
The existing combined suite grows from 28 to 37 scenarios; resource limits and
owned cleanup requirements remain unchanged.

Accepted code `a8742855715c909804015537fed93fc618151125` passes
[product CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/45321964685)
and [private-preview CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/45321964801).
All 37 combined cases pass in 175.28s, with owned containers/image removed.
The separate ledger job passes 476 baseline checks, fourteen owner-fixture
encrypted restores, 313 restricted commands, 53 installation/retirement checks
and 27 restricted restores. Product passes 2,528 API checks (29 expected skips,
two existing warnings), 69 client checks, 26 browser checks, fifteen source UI
checks and eighteen MVP journeys. Preview passes eighteen journeys plus saved
workflow reopening after restart (6.4s) and encrypted restore (6.0s). Both stack
cleanup steps succeed. All 59 new offline checks and repository Ruff also pass;
the earlier focused custody/claim regression selection passes 272 checks before
three additional directory cases were added and passed in the 59-case run.

There is no Compose/systemd entry, worker registration, production credential
installer or runtime-bundle deployment. Next integrate bounded trusted operator
and receipt-process supervision, quiescence/secret rotation and explicit restore
reauthorization. Governed Snowflake source/provider status and usage remain later
gates, followed by a separately approved GCP build and joint testing window.
