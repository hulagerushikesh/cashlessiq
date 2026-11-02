# Stable private test address

2 November 2026. DNS and the remotely managed tunnel are configured; the
connector is inactive. The application has not been tested through this
hostname. GCP remains stopped and the earlier temporary address is offline.

## Address and observed Cloudflare state

| Purpose | Address / configuration |
| --- | --- |
| Public fixed-example prototype | `https://cashlessiq.hulage.in` |
| Private synthetic workspace | `https://cashlessiq-test.hulage.in` |
| Dedicated tunnel | `cashlessiq-private-test` |
| Tunnel ID | `9f1f851b-df11-4f03-b7d9-5020ff5ac164` |
| Published application | Exact hostname, all paths, `http://127.0.0.1:3080` |
| DNS | Proxied CNAME to `9f1f851b-df11-4f03-b7d9-5020ff5ac164.cfargotunnel.com` |

The owner signed in to Cloudflare. The dashboard showed a Free, full-setup
`hulage.in` zone, twelve existing DNS records and no account tunnels. A dedicated
tunnel was created within the displayed existing capacity. Its exact-host
published application was saved; Cloudflare's success receipt confirmed the
CNAME creation. No connector, VM, build, paid add-on or subscription was started.
The public prototype's existing DNS was not edited.

Use the first-level `cashlessiq-test.hulage.in` hostname. The earlier suggested
`test.cashlessiq.hulage.in` is deeper than normal Universal SSL coverage in a
full-setup zone. No Advanced Certificate Manager purchase is needed for the
selected hostname. An unauthenticated HTTPS HEAD request on 2 November succeeded
with normal certificate verification and returned HTTP 530 while the connector
was inactive. This establishes DNS/TLS reachability to Cloudflare, not application
authentication or end-to-end acceptance. The public demo still returned HTTP 200.
See [Cloudflare's certificate limits](https://developers.cloudflare.com/ssl/edge-certificates/universal-ssl/limitations/).

Read-only dashboard inspection found one Worker route,
`cashlessiq.hulage.in/*` -> `falling-dust-f1ed`, and one disabled redirect from
that same public hostname to the original Snowflake console. Neither matches
the new sibling hostname. The Rules overview showed no origin/rewrite,
configuration, cache or response-header rules; legacy Page Rules showed none.
The DNS table confirmed the new proxied tunnel alongside the unchanged public
demo record. Recheck these scopes before a later approved run; this inspection
does not prove future configuration or live private-response caching behaviour.

The operator receipt is ignored at `output/gcp-preview/named-tunnel-route.png`.
The dedicated connector token was saved directly to a mode-0600 ignored
`output/gcp-preview/tunnel-token.txt`, without printing it. It is not an account
API token or account-wide certificate. Do not commit it, include it in archives,
pass it as a command argument, or expose the connector-install panel in receipts.

## Next approved testing window

Domain configuration does not authorize another paid GCP run. Agree the next
window first, preserve the usage ledger and reuse the accepted image digests.
No new app image is required just to set this origin or start a named connector.
The browser harness change runs on the operator machine.

1. Inspect Cloudflare routes that can match this hostname: Worker routes,
   redirects, origin rewrites and cache rules. The public prototype may use
   hostname-specific rules; do not widen or repurpose them. Confirm the new
   hostname reaches the dedicated tunnel and authenticated responses are not
   cached. Leave paid cache, routing, load-balancing and certificate add-ons off.
2. After separately approved VM startup, run the existing live instance check
   and record the start in the preserved daily usage ledger. Set a stop deadline
   using the remaining daily allowance, not a fresh four-hour entitlement.
3. Transfer only the dedicated token through IAP to the dedicated VM. Use a
   private temporary file, never a command-line token. Every gcloud invocation
   must explicitly select `--project=cashlessiq-dev-rush`. Install the token as
   root-owned mode 0600 at `/etc/cashlessiq-preview/tunnel-token` inside a
   root-owned mode-0700 directory. Remove the temporary transferred copy.
4. Copy the accepted
   `deploy/gcp-preview/ciq-preview-tunnel.service.example` to
   `/etc/systemd/system/ciq-preview-tunnel.service`. This template is deliberately
   outside the existing runtime bundle's file allowlist: transfer it separately
   from the accepted revision, compare its SHA-256 and run
   `systemd-analyze verify` on the VM before installing/starting it. Keep the
   pinned, checksum-verified `cloudflared` binary already installed there.
   Run `systemctl daemon-reload`; do not enable the unit at boot. Ensure the old
   transient quick-tunnel unit is stopped and unloaded before using that name.
5. Set the exact origin and apply it to only the web service:

   ```sh
   python3 -m scripts.owner_preview set-origin --origin https://cashlessiq-test.hulage.in
   python3 -m scripts.gcp_preview_runtime up
   python3 -m scripts.gcp_preview_runtime restart-web
   python3 -m scripts.gcp_preview_runtime check
   ```

   `up` uses the accepted digests with no build. Check local anonymous `/login`
   rejection (401) at the loopback gateway before starting the connector. The
   current owner password remains required on every route. The application
   continues to use synthetic role selection behind this owner gate.
6. Manually start `ciq-preview-tunnel.service`. The service reads its token via
   systemd `LoadCredential` and `cloudflared --token-file`, with no secret in
   process arguments. It has no boot enablement, no restart policy, a four-hour
   process ceiling, 128 MiB ceiling and 25% CPU quota. The process ceiling is
   only a backstop: it neither stops the VM nor enforces cumulative daily use.
7. Verify valid HTTPS, anonymous/wrong-password rejection, protected assets,
   Secure cookies, same-origin mutations, sign-out, role/clinical restrictions,
   deep links and no exposure of ports 3000/8000/5432. Confirm the public demo
   still works independently. If Cloudflare Access is added later, verify its
   identity/service-token flow separately; the current browser harness supports
   the existing owner basic-auth gate, not an Access login bypass.
8. Run the existing deployed tests only with exact double opt-in:

   ```sh
   MVP_BASE_URL=https://cashlessiq-test.hulage.in \
   MVP_APPROVED_GCP_ORIGIN=https://cashlessiq-test.hulage.in \
   MVP_OWNER_PASSWORD_FILE=/absolute/private/path/owner-password.txt \
   npm run test:mvp -- --workers=1 --trace=off --timeout=240000
   ```

   This prepares a permitted test target; environment variables are not spend
   approval. The public prototype, sibling subdomains and arbitrary remote hosts
   remain rejected by the harness.
9. When testing ends, stop the connector, stop the app while retaining its DB
   volume, stop the VM, verify TERMINATED/no external IP/reservations, and close
   the usage receipt. Keep DNS and the inactive tunnel for the next session.
   An offline hostname can show a Cloudflare error while the VM is stopped;
   do not restart paid infrastructure to hide that expected state.

Rollback is to stop the connector and restore the previously accepted exact
origin if a new quick-tunnel window is separately chosen. Remove only this
dedicated hostname route/CNAME if abandoning it. Do not point a CNAME at the old
temporary `trycloudflare.com` URL, change the public demo record or reuse an
unrelated application's tunnel.

References: [managed tunnel setup](https://developers.cloudflare.com/tunnel/get-started/),
[token-file and runtime flags](https://developers.cloudflare.com/tunnel/reference/run-parameters/).

## Offline verification

All 58 client checks, TypeScript checks, lint and `git diff --check` passed.
The origin guard covers both exact approved custom-host and quick-tunnel
targets, and rejects the public demo, siblings, suffix lookalikes, HTTP, ports,
paths, query/fragment and missing approval/credentials. No browser/server was
started for these client checks. The service template parses and its manual
start, token-file and bounded-runtime settings were inspected; actual systemd
execution remains a VM acceptance step. A fresh read-only GCP check at
04:32:19 UTC confirmed TERMINATED, no active deadline/external IPv4 and no
reserved addresses. No new runtime usage session was opened.

Revision `aaecef5` also passes both remote CI runs:

- [Private preview 41389176994](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41389176994):
  owner/asset/role/origin/cookie checks, all 18 MVP browser journeys, encrypted
  restoration matching all 17 tables, saved-review reopening after restart and
  on a fresh restored volume, and owned cleanup.
- [Product regression 41389177084](https://github.com/hulagerushikesh/cashlessiq/actions/runs/41389177084):
  1,018 root checks (three skips), 1,522 API checks (one skip, two existing
  warnings), 72 membership, 35 catalog, 58 client, 26 browser, 15 source UI and
  all 18 MVP journeys, plus contracts, types, lint, build, containment and cleanup.

These are disposable-runner checks. They do not establish live application
acceptance through the inactive custom-host tunnel, Cortex integration or a
new accepted GCP image. The existing deployed image digests remain unchanged.
