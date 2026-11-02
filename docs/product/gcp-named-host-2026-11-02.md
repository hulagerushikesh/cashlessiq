# Named private hostname acceptance — 2 November 2026

The owner approved a new test window of at most 30 minutes on the existing
e2-small VM, reusing the accepted images without another build or larger VM.
The quoted estimate was roughly US$0.01–0.02 VM/IP plus traffic/logs/tax and
existing retained storage; it was explicitly not a hard billing cap.

## Initial state and bounded startup

At 09:00 UTC, `https://cashlessiq-test.hulage.in` returned Cloudflare 530 and
`ciq-private-test` was TERMINATED. The DNS/tunnel configuration was present;
there was no running connector. This was expected offline behaviour under the
owner's stop-between-tests policy.

The existing cumulative ledger showed 1,901 seconds of observed use for the
day with its earlier session closed. The VM's maximum duration was shortened
from four hours to **1,800 seconds with STOP**, with no automatic restart or
scheduled start. The fixed-project live checker and usage ledger accept a
stricter bounded duration without increasing the four-hour daily ceiling.
The new automatic deadline was **09:43:11.847 UTC / 15:13:11.847 IST**.

The existing deployment remained revision `7940886`, using the original
accepted immutable web/API image digests. No source, new ledger migration or
agent executor was deployed. Startup initially reported expired registry-login
authentication while checking private image pulls; Docker used the already
cached exact images and all four steady services became healthy. No replacement
build, image tag substitution or extra access grant was used.

## Named connector and origin

The dedicated connector token was transferred privately through IAP, installed
as root-owned mode 0600 under root-owned mode-0700 `/etc/cashlessiq-preview`,
and its temporary transferred copy removed. It was never printed or placed in
process arguments, source archives or Git. Its ignored operator copy remains
private for later authorized operation.

The manually started service uses systemd `LoadCredential` and `--token-file`.
The installed template's SHA-256 matched
`c75c05e2ac282da19f94643a4ced25e2b034749304d3a6af3ef1770ddccb034e`;
`systemd-analyze verify` passed. `UnitFileState=static`, with no boot enablement,
no automatic restart, 128 MiB memory limit and 25% CPU quota. Its four-hour
process backstop does not override the VM's stricter 30-minute STOP. Readiness
reported four tunnel connections; metrics remained on `127.0.0.1:20241`.

The app origin was set to the exact `https://cashlessiq-test.hulage.in` address
and applied to the web service. Anonymous loopback access returned 401 before
the connector started. HTTPS then reached the password gate with `no-store`,
`noindex` and Cloudflare `DYNAMIC` response status. The public fixed-example
`https://cashlessiq.hulage.in` independently remained HTTP 200.

## Acceptance observations

Thirty-five direct HTTPS checks passed for anonymous/wrong-password rejection,
protected deep links and built assets, foreign/missing-origin mutations, exact
redirects, Secure/HttpOnly/SameSite=Strict session cookies, three-role clinical
projection, outer owner-gate enforcement even with an app session, sign-out
and no-cache headers. The verifier supplied an explicit client User-Agent;
browser acceptance is recorded separately. No credential or session cookie was
printed or retained in its JSON receipt.

The initial browser run passed 17 of 18 checks. The role-switch test navigated
to a policy before the sign-in navigation had completed, then its shared request
context received 401. Adding explicit sign-out/sign-in URL assertions made the
isolated check pass in 15 seconds. This is a smoke-harness synchronization fix,
not a deployed app change. The complete subsequent run passed **all 18 checks
in 4.5 minutes**, with one worker, no retries and traces disabled. A final
1440×1000 processor workspace screenshot was saved and visually inspected;
request, policy-library and background-job navigation was visible.

A one-time runtime read during testing showed all four steady services healthy;
gateway/API/web/database host ports remained unpublished except for the gateway
at `127.0.0.1:3080`. Sampled container use was approximately 22/100/153/69 MiB,
and the connector used about 66 MiB. The host reported 1,182 MiB available and
zero swap. These are individual observations, not peak/load guarantees.

Ignored operator receipts are under `output/gcp-preview/`: `named-host-browser.log`,
`named-host-progress-navigation.log`, `named-host-browser-accepted.log`,
`named-host-https-checks.json`, `named-host-runtime-checks.txt` and the preserved
usage ledger. Browser traces were disabled. The operator Mac's Docker stayed off.

## Completed shutdown

The connector was stopped, and Compose removed the app containers/networks
without deleting the retained database volume. The VM was explicitly stopped
before the automatic deadline. At **09:28:06 UTC / 14:58:06 IST**, the fixed-project
live checker verified TERMINATED, no active deadline, no assigned external IPv4
and zero reserved external addresses. The retained schedule remains 1,800-second
STOP; the connector remains a manual-only static service.

The usage ledger closed this session at 09:28:09 UTC. Its observed interval was
09:13:30.693–09:28:09.716 UTC, approximately **880 seconds rounded up** (about
15 minutes). Both recorded sessions total **2,780 seconds** today (about
46 minutes), conservatively rounded and not a billing meter. Remaining daily
allowance does not authorize another window. Retained disk/image/source costs
continue. The private hostname returned HTTP 530 after shutdown, as expected;
the independent public demo still returned HTTP 200.

Additional ignored receipts: `named-host-stopped.json`,
`named-host-usage-closed.txt`, `named-host-runtime-down.txt` and the inspected
`named-host-workspace.png`. No cloud build, resize, paid Snowflake/agent call,
scheduled start or local Docker run occurred.

## Source/CI acceptance, separate from the existing cloud images

Source revision `2433424` passes
[product CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41419930718)
and [owner preview CI](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41419930694).
Product acceptance includes 1,026 root checks (three skips), 1,740 API checks
(one skip, two existing warnings), 72 membership, 35 catalog, 58 client,
26 browser, 15 source UI and 18 MVP journeys. The separate PostgreSQL 17 job
passes all 218 agent checks (146 contract + 72 durable-ledger).

The production-server preview also passes 37 gateway/role/origin/cookie checks,
all 18 MVP journeys, encrypted restore matching 21 tables, and saved-workflow
browser reopening after both restart and fresh-volume restoration. Both
workflows removed their disposable resources. The four new agent tables were
empty in that recovery run; populated-ledger recovery remains a pre-live gate.
These CI images were not uploaded to GCP. Its retained database is still at the
existing app's schema; future deployment needs a separately approved build/run.
