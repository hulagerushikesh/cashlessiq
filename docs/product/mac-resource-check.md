# Mac headroom checkpoint — 23 October 2026

Owner approved the disposable eight-role service-composition batch and requested
a Mac configuration/load check first. The implementation approval remains valid;
the heavy run is deferred for resource headroom, not waiting for another approval.

## Read-only observations

| Observation | Result |
| --- | --- |
| Physical memory / CPU | 8 GiB / 8 CPUs |
| Docker allocation | About 3.82 GiB / 8 CPUs |
| Disk available | About 117 GiB |
| Running product services | Four; all healthy before and after the check |
| Current container memory | About 1.06 GiB total at the automated check |
| Mac pressure observation | `kern.memorystatus_vm_pressure_level = 2`, not normal (`1`) |
| Swap allocated/in use | About 8.56 GiB in the automated check |

Swap occupancy alone does not measure current swapping or prove an application
leak; this Mac has long uptime. The immediate refusal is the pressure observation.
Disk space and estimated Docker headroom passed. No guarantee against future
pressure, overheating, host pause or competing processes follows from a sample.

## Implemented safety check

```sh
make product-host-check
```

`scripts/check_product_host.py` uses bounded read-only observations only: selected
Mac sysctl metrics, one-minute load, local disk free space, selected Docker info
fields and container memory totals. No container names/environments, credentials
or complete Docker inspection/configuration are printed. Each external command
has a four-second timeout. Unsupported platforms, failed/malformed observations
and changing container counts refuse rather than guessing.

Conservative **local test** policy: normal Mac pressure, at least 8 GiB physical
memory, two host/Docker CPUs, one-minute load no higher than 75% of CPU count,
12 GiB free disk, 3 GiB Docker allocation and 2 GiB estimated Docker headroom.
These are proposed test-start margins, not operational clock-health policy,
benchmarked capacity or a promise that the full run will fit.

Exit `0` means only the sampled preflight passed. Exit `2` means defer (Make
reports a nonzero target); it is not a product failure. There is no force flag,
auto-tuning, restart, cleanup/prune, process termination or daemon startup.
The future composition runner must invoke `require_headroom()` before allocation
and between stages, retain per-container CPU/memory/PID limits and a bounded
watchdog/cleanup budget. This standalone command is **not** a running monitor or
an already-integrated enforcement layer around existing test targets.

## Outcome and next action

Actual invocation returned DEFER at pressure level 2 and created no containers.
The proposed eight-canonical-service composition is **not implemented or run**
in this checkpoint. No acceptance claim or P2 percentage increase is made.

Owner can close unused applications normally and rerun the check. Do not kill
unfamiliar processes, clear caches/swap, increase Docker memory or change Mac
settings just to pass. If needed, separately arrange a temporary pause of the
local sandbox for the integration run; it was left running here. A passing
preflight permits resuming the already-approved implementation/run, not live
Snowflake access, operational credential creation or public deployment.

Verification: **25 new mocked resource-check tests; all 238 root tests pass**,
repository Ruff, changed-file format and whitespace checks pass. No container
build, backend/PostgreSQL suite, browser suite or source test rerun locally.
Historical local-alpha checks remain recorded separately. Remote CI for this
new commit is not yet claimed complete. No Snowflake/AI spending, host setting
changes, encrypted-image creation, account changes or P3 work.
