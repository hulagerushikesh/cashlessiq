# Private owner preview from the existing Mac

**Current decision:** the owner subsequently selected a dedicated GCP target
for an independent preview. [The small testing plan](gcp-private-testing.md)
records that local Docker is sufficient and a duplicate local stack is not
required. The instructions below retain the earlier Mac-specific option.

25 October 2026. Rushikesh selected **this Mac first, without hosting spend**.
He has already tested the current local app and explained it to two friends.
This package prepares the next delivery step; it does not require repeating that
general walkthrough, and does not claim an online deployment.

## What this package changes

`compose.owner-preview.yml` is a separate project and database volume. It does
not replace the app on localhost:3000 or reuse its database/auth secrets. The
web container uses a built, non-root Next.js standalone server instead of
`next dev`. Standalone output is enabled only for that Docker build target;
the existing development and source-contract test paths keep their defaults.

Only the gateway publishes a port, **127.0.0.1:3080**. The web, API and database
are on an internal Docker network with no published ports. Caddy requires the
owner password on every path, including login, case pages, assets and auth
POSTs. An app session does not bypass this outer gate. Owner credentials are
stripped before forwarding requests; responses are no-store and noindex.

The role selector remains synthetic identity for fictional data, behind that
separate owner gate. `CIQ_ENVIRONMENT=local` is deliberate and is not permission
to expose the normal local stack. Live-source routes stay disabled. This is not
customer identity, a production deployment or P2 live-source acceptance.

## Start and stop, when Mac headroom permits

Run from the repository root. `prepare` and `up` use the existing Mac headroom
gate before Docker hashing/build/start. Elevated pressure must defer them; do
not stop unrelated workloads or raise Docker limits to force a pass.

1. Prepare independent credentials with a temporary, non-serving origin:

   ```sh
   python3 -m scripts.owner_preview prepare --origin https://pending.invalid
   python3 -m scripts.owner_preview up
   ```

   The generated password is in `output/owner-preview/owner-password.txt`, mode
   0600, ignored by Git. Username: `owner`. Independent DB/auth secrets and the
   bcrypt hash are in `.env.owner-preview.local`, also ignored and mode 0600.
   Do not print either file into logs or paste credentials into a URL. Preparation
   refuses existing files instead of replacing secrets. Partial preparation is
   retained for inspection, not automatically retried or deleted.

2. Verify the loopback gateway: an unauthenticated request to
   `http://127.0.0.1:3080/login` must return 401. In a local browser, supply the
   generated owner credentials and confirm the role selector loads. Sign-in
   redirects are not usable until the actual HTTPS origin is configured.

3. With an installed `cloudflared` binary, start a temporary tunnel **only to
   the verified gateway**, never localhost:3000 or :8000:

   ```sh
   ./output/owner-preview/tools/cloudflared tunnel --url http://127.0.0.1:3080
   ```

   The native arm64 binary has been prepared locally from official release
   `2026.10.3`, with the release asset SHA-256 verified before extraction;
   `--version` succeeds. The ignored `tools/verified-release.json` records its
   provenance and checksums. It is not a global installation.

   This creates an outbound tunnel and prints its temporary HTTPS hostname. No
   router port forwarding, domain purchase, paid hosting or account signup is
   part of this package. A tunnel binary is not installed by the preview helper.

4. Configure the exact HTTPS origin printed by the tunnel, without a trailing
   slash, then apply it to the preview web container:

   ```sh
   python3 -m scripts.owner_preview set-origin --origin https://REPLACE-WITH-ASSIGNED-HOST.trycloudflare.com
   python3 -m scripts.owner_preview up
   ```

   Replace the placeholder with the actual lowercase hostname. The helper
   rejects HTTP, credentials, ports, paths, query strings and fragments. Origins
   determine login/logout checks, redirect targets and Secure session cookies;
   they are not accepted dynamically from request forwarding headers.

5. Before calling the remote preview usable, verify the HTTPS URL in a separate
   browser session: anonymous login/case/asset requests receive the owner
   challenge; wrong credentials fail; correct credentials allow the synthetic
   sign-in; all three roles load their permitted cases; foreign-origin POSTs
   fail; session cookies have Secure/HttpOnly/SameSite=Strict; sign-out clears
   the app session. Keep this a targeted delivery check, not another general
   product walkthrough. Never introduce real records or documents.

6. Stop the tunnel process first (Ctrl-C in its terminal), then:

   ```sh
   python3 -m scripts.owner_preview down
   ```

   Only the separate preview project is stopped; its fictional database is
   retained. The existing localhost:3000 stack is unaffected. Do not add `-v` or
   delete credentials as an ordinary stop operation. To revoke remote access,
   stop the tunnel; app sign-out does not erase a browser's cached Basic Auth.

## Engineering evidence and remaining delivery checks

The dedicated `Private owner preview` workflow builds the actual production
image on a standard public Linux runner, starts a fresh fictional database and
gateway, and checks password denial, protected static assets, all three roles,
origin rejection, HTTPS redirect/Secure-cookie headers, logout, and the absence
of published backend ports. It also checks non-root runtime and that web source
files are absent from the standalone runtime image. Its HTTP checks use the
loopback gateway with an explicit HTTPS origin; they do not attest a live tunnel
or a browser's end-to-end TLS session. CI removes only its disposable project
and volumes, and publishes no image, credential or deployment artifact.

Local policy tests cover invalid-origin denial before Docker, preserving
existing credentials, deferring under low headroom and private settings files.
Implementation `536e1b5` passed [private-preview CI 40165607337](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40165607337):
37 HTTP checks, built non-root standalone runtime and disposable cleanup all
passed. [Full product CI 40165607340](https://github.com/hulagerushikesh/cashlessiq/actions/runs/40165607340)
also passed: 885 root tests (three CI skips), 72 membership, 41 client, 1,469
backend, 26 browser, 15 source UI and 35 catalog cases, plus lint, types,
contracts, build and containment. All 15 new preview policy tests passed locally.

A fresh Mac resource check deferred startup: pressure 2, load 12.18 on eight
CPUs and about 1.29 GiB estimated Docker headroom (less than the required 2 GiB).
No local preview secrets were generated, and no additional containers or tunnel
were started.
The original app remains healthy. Actual Mac/tunnel acceptance remains open;
CI success is not an online deployment.

Mac sleep, shutdown, network loss or stopping the tunnel makes the remote
preview unavailable. Its hostname changes on a new quick-tunnel session, so
the origin must be updated. There is no uptime promise. Any future paid action
still requires Rushikesh's approval.

Implementation follows the official [Next.js standalone and monorepo tracing
documentation](https://nextjs.org/docs/app/api-reference/config/next-config-js/output),
[Caddy Basic Auth](https://caddyserver.com/docs/caddyfile/directives/basic_auth)
and [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).
Basic Auth must travel over HTTPS remotely. Quick Tunnels are intended for
testing, have no uptime guarantee and do not require an account or domain.
