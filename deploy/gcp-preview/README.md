# First private GCP test: operator sequence

This is a disposable, fictional-data test for the owner and engineering agent.
The dedicated project is `cashlessiq-dev-rush`. Billing is disabled and paid
deployment is not authorized as of 29 October 2026. Do not run the paid steps
until the owner approves the exact cost, billing account and test window.

## Prepare offline before approval

1. Accept a single committed Git revision with the full product and private
   preview CI jobs green. Run `python3 -m scripts.check_gcp_preview_plan`.
2. After committing the runtime files, run
   `python3 -m scripts.package_gcp_preview create`. It refuses an uncommitted
   change to any packaged file. The ignored archive in `output/gcp-preview/`
   contains only the four Compose files, gateway configuration, plan and the
   three runtime helpers. It contains no application source, owner video or
   credential. Verify it with
   `python3 -m scripts.package_gcp_preview verify PATH_TO_ARCHIVE`.
3. Record the accepted commit, archive SHA-256, proposed four-hour run window
   and an updated charge estimate. Get the owner's explicit approval before
   linking billing, enabling paid services, building or creating resources.

## Execute only after the spend decision

1. Specify `--project=cashlessiq-dev-rush` for **every** GCP CLI action; the
   machine's default project is unrelated. Link only the approved billing
   account. Set a cost alert, remembering it is not a hard cap. Create the
   reviewed network, IAP SSH rule, Artifact Registry repository and two service
   accounts: a builder with repository write and log write access, and a VM
   identity with repository read access. Do not grant project-wide Editor.
2. Submit `cloudbuild.yml` from the accepted revision using the builder
   identity. Record the registry SHA-256 digest for each pushed image. A mutable
   tag is not accepted by the runtime helper. Do not build on the VM.
   Complete and accept the build before starting the VM. Keep it off during
   coding, build failures and time away from testing; reuse accepted digests
   until the code changes.
3. Create the reviewed e2-small Debian VM with a 20 GiB standard disk and only
   IAP SSH ingress. Set `--max-run-duration=4h
   --instance-termination-action=STOP` when creating it. Verify those fields on
   the created instance before proceeding. Stopping releases the ephemeral IP;
   the disk and retained images continue to accrue storage cost.
4. Install Docker Engine and its Compose plugin on the VM. Transfer the small
   archive and `.sha256` file through IAP SSH, compare its SHA-256, and extract
   into a private working directory. Run the commands below from that directory
   as the dedicated preview operator. Never copy the local development `.env`,
   source data, backup keys or owner credentials to the VM.

   ```sh
   python3 -m scripts.owner_preview prepare --origin https://pending.invalid
   python3 -m scripts.gcp_preview_runtime set-images \
     --api-image 'us-central1-docker.pkg.dev/cashlessiq-dev-rush/ciq-preview/api@sha256:REPLACE_WITH_64_HEX' \
     --web-image 'us-central1-docker.pkg.dev/cashlessiq-dev-rush/ciq-preview/web@sha256:REPLACE_WITH_64_HEX'
   python3 -m scripts.gcp_preview_runtime check
   python3 -m scripts.gcp_preview_runtime up
   ```

   `prepare` creates the private owner password and separate local database/auth
   secrets. The runtime check resolves all four Compose files and refuses a
   tag, a wrong project, an exposed backend port or a non-loopback gateway.
   `up` uses `--no-build` and pulls the exact accepted API/web digests.
5. Confirm that `curl -s -o /dev/null -w '%{http_code}'
   http://127.0.0.1:3080/login` returns `401` on the VM. Download a pinned
   Linux amd64 `cloudflared` from its [official release](https://github.com/cloudflare/cloudflared/releases/tag/2026.10.5),
   verify its published SHA-256, then run its quick tunnel to **only**
   `http://127.0.0.1:3080`. The 2026.10.5 `cloudflared-linux-amd64` digest is
   `e1bc0cf084fd9e590554fe769a86b1db46701c3f847a43d902f7b974a4e16298`.
   Record the generated HTTPS hostname; do not tunnel port 3000 or 8000.
6. Set the exact assigned origin and restart only the web service. Substitute
   the actual `https://...trycloudflare.com` hostname for `HTTPS_ORIGIN`:

   ```sh
   python3 -m scripts.owner_preview set-origin --origin HTTPS_ORIGIN
   python3 -m scripts.gcp_preview_runtime restart-web
   python3 -m scripts.gcp_preview_runtime check
   ```

   Keep the owner password out of logs and URLs.
7. From a separate browser session, check anonymous denial, wrong-password
   denial, the three synthetic roles, request/policy/reviewer workflows, secure
   cookies, sign-out and the absence of exposed backend ports. Measure host
   memory under use. If the 2 GiB VM is unhealthy, stop this run and review a
   larger VM and its price before changing size. Confirm the four-hour STOP
   setting is present, and verify the VM stops by that deadline if the run lasts
   that long. Stop early whenever testing finishes: stop the tunnel, then run
   `python3 -m scripts.gcp_preview_runtime down` and stop the VM. Retain or
   delete the fictional disk and images according to the agreed storage plan.

The initial GCP run establishes only private synthetic access and resource
fitness. It does not authorize real patient data or customer traffic.

Use at most four hours of total VM runtime per working day unless a longer
window is separately approved. There is no automatic daily start. Each start
resets the VM runtime limit, so the operator must track the day's cumulative
runtime and stop sooner after a restart. The per-start limit is not a daily
spend cap. Stopping containers alone does not stop VM billing: verify the GCP
instance is `TERMINATED` and its ephemeral external IPv4 has been released.
