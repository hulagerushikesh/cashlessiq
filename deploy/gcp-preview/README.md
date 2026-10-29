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
   runtime helpers. It contains no application source, owner video or
   credential. Verify it with
   `python3 -m scripts.package_gcp_preview verify PATH_TO_ARCHIVE`.
   Exercise the VM acceptance checker with fictional data:

   ```sh
   python3 -m scripts.check_gcp_preview_instance --expect running \
     --snapshot tests/fixtures/gcp-preview/running.json
   ```

   This prints `historical_snapshot_only`; it is not cloud deployment evidence.
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
   From the operator's checkout, run the read-only acceptance check:

   ```sh
   python3 -m scripts.check_gcp_preview_instance --expect running --live
   ```

   It checks the dedicated project/instance, zone, reviewed machine type,
   four-hour duration and STOP action, active automatic-stop deadline, expected
   network/subnet, IPv4-only access and absence of attached resource policies or
   reserved external addresses. It uses only `gcloud compute instances describe`
   and `gcloud compute addresses list`, with the project fixed and prompts off.
   A missing API, absent VM or permission error fails without enabling or
   creating anything. The displayed deadline is for this start, not a daily cap.
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
   memory under use. The bundle includes a bounded foreground sampler. On the
   VM, sample during a two-minute browser test from the other device:

   ```sh
   python3 -m scripts.measure_preview_resources --include-host -- \
     python3 -c 'import time; time.sleep(120)'
   ```

   It starts no containers. It reports service highs, Linux usable RAM, minimum
   estimated available RAM and initial/maximum observed swap use. Run this on
   the VM host, not inside a container. The Linux `MemAvailable` estimate
   includes reclaimable cache (see the [Linux counter definitions](https://docs.kernel.org/filesystems/proc.html#meminfo));
   raw `MemFree` is not a capacity verdict. Observe
   responsiveness, restarts and OOM events separately. Samples miss short peaks
   and this browser-only window excludes startup; a larger CI host's numbers
   cannot prove this VM fits. The foreground sampler exits with its command;
   it does not create a scheduled monitor or extend the VM window.
   If the 2 GiB VM is unhealthy, stop this run and review a
   larger VM and its price before changing size. Confirm the four-hour STOP
   setting is present, and verify the VM stops by that deadline if the run lasts
   that long. Stop early whenever testing finishes: stop the tunnel, then run
   `python3 -m scripts.gcp_preview_runtime down` and stop the VM. Retain or
   delete the fictional disk and images according to the agreed storage plan.
   Confirm completion from the operator's checkout:

   ```sh
   python3 -m scripts.check_gcp_preview_instance --expect stopped --live
   ```

   `STOPPING`, `SUSPENDED` and containers-down do not pass. Acceptance requires
   `TERMINATED`, no assigned external IP, no active stop deadline and no reserved
   external address in the dedicated project, including unattached reservations.
   If the VM is still stopping, wait briefly and rerun the read-only check.

The initial GCP run establishes only private synthetic access and resource
fitness. It does not authorize real patient data or customer traffic.

Use at most four hours of total VM runtime per working day unless a longer
window is separately approved. There is no automatic daily start. Each start
resets the VM runtime limit, so the operator must track the day's cumulative
runtime and stop sooner after a restart. The per-start limit is not a daily
spend cap. Stopping containers alone does not stop VM billing: verify the GCP
instance is `TERMINATED` and its ephemeral external IPv4 has been released.

The checker records only the state observed during its two reads. It does not
stop a VM, prevent a later start, enforce cumulative daily hours, inventory all
other billable services, or verify firewall/IAM/disk settings. Those remain
operator acceptance steps. Saved snapshots are historical evidence only; use
`--live` at the beginning and end of the actual approved run. The implementation
follows Google's [VM time-limit semantics](https://docs.cloud.google.com/compute/docs/instances/limit-vm-runtime)
and [Compute instance fields](https://docs.cloud.google.com/compute/docs/reference/rest/v1/instances).
