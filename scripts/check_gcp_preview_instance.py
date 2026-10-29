"""Read-only acceptance of a running or stopped private preview VM.

Default operation uses a saved, historical JSON snapshot. Explicit --live uses
only gcloud describe/list, with prompts disabled and the project fixed. It never
enables an API, provisions resources, starts/stops a VM or changes billing.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from scripts.check_gcp_preview_plan import PLAN

PROJECT = "cashlessiq-dev-rush"
INSTANCE_FIELDS = (
    "selfLink,name,status,zone,machineType,scheduling,networkInterfaces,"
    "resourcePolicies,lastStartTimestamp,terminationTimestamp"
)


class PreviewCheckError(ValueError):
    """A safe, operator-facing validation failure without captured cloud output."""


def resource(value: object) -> str:
    """Accept only Compute v1 resource links, never suffix-only project matches."""
    if not isinstance(value, str):
        raise PreviewCheckError("Missing Compute resource identity")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or parsed.netloc not in {"www.googleapis.com", "compute.googleapis.com"}
        or not parsed.path.startswith("/compute/v1/")
        or parsed.query
        or parsed.fragment
    ):
        raise PreviewCheckError("Unexpected Compute resource identity")
    return parsed.path.removeprefix("/compute/v1/")


def timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise PreviewCheckError("Missing VM start, stop deadline or observation timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise PreviewCheckError("VM timestamps must include a timezone")
    return parsed


def verify(snapshot: dict, expected: str) -> dict:
    if expected not in {"running", "stopped"}:
        raise PreviewCheckError("Expected state must be running or stopped")
    plan = json.loads(PLAN.read_text())
    if plan["project_id"] != PROJECT:
        raise PreviewCheckError("Preview plan targets the wrong project")
    zone = plan["zone"]
    name = plan["instance"]["name"]
    base = f"projects/{PROJECT}"
    identity = f"{base}/zones/{zone}/instances/{name}"
    instance = snapshot["instance"]
    if instance["name"] != name or resource(instance["selfLink"]) != identity:
        raise PreviewCheckError("Wrong preview instance or project")
    if resource(instance["zone"]) != f"{base}/zones/{zone}":
        raise PreviewCheckError("Wrong preview zone")
    machine = plan["instance"]["machine_type"]
    if resource(instance["machineType"]) != f"{base}/zones/{zone}/machineTypes/{machine}":
        raise PreviewCheckError("VM size differs from the reviewed preview plan")
    state = "RUNNING" if expected == "running" else "TERMINATED"
    if instance["status"] != state:
        raise PreviewCheckError(f"Expected {state}; VM has not reached the required state")

    schedule = instance["scheduling"]
    duration = schedule["maxRunDuration"]
    maximum = plan["instance"]["max_run_duration_seconds"]
    if (
        str(duration["seconds"]) != str(maximum)
        or str(duration.get("nanos", 0)) != "0"
        or schedule["instanceTerminationAction"] != "STOP"
        or schedule.get("terminationTime")
    ):
        raise PreviewCheckError("VM must retain the reviewed four-hour duration with STOP")
    if instance.get("resourcePolicies"):
        raise PreviewCheckError("Unexpected VM resource policy; review possible scheduled startup")

    interfaces = instance["networkInterfaces"]
    if len(interfaces) != 1:
        raise PreviewCheckError("Preview must have one private network interface")
    interface = interfaces[0]
    if (
        resource(interface["network"]) != f"{base}/global/networks/{plan['network']['name']}"
        or resource(interface["subnetwork"])
        != f"{base}/regions/{plan['region']}/subnetworks/{plan['network']['subnet']}"
        or interface.get("stackType", "IPV4_ONLY") != "IPV4_ONLY"
        or interface.get("ipv6AccessConfigs")
        or interface.get("ipv6Address")
    ):
        raise PreviewCheckError("Unexpected preview network or IPv6 configuration")
    configs = interface.get("accessConfigs", [])
    if len(configs) > 1 or any(c.get("type") != "ONE_TO_ONE_NAT" for c in configs):
        raise PreviewCheckError("Unexpected external access configuration")
    external = [c["natIP"] for c in configs if c.get("natIP")]
    if expected == "running" and len(external) != 1:
        raise PreviewCheckError("Running preview requires its planned ephemeral IPv4")
    if expected == "stopped" and external:
        raise PreviewCheckError("Stopped preview still reports an external IPv4")
    # This is a dedicated project. Even an unattached reserved address can keep
    # charging after STOP, so do not accept any external reservation in it.
    addresses = snapshot["addresses"]
    if not isinstance(addresses, list) or any(
        not isinstance(address, dict) or address.get("addressType") != "INTERNAL"
        for address in addresses
    ):
        raise PreviewCheckError("Dedicated project has a reserved or unclassified external address")

    observed = timestamp(snapshot["observed_at"])
    deadline = None
    if expected == "running":
        started = timestamp(instance["lastStartTimestamp"])
        deadline = timestamp(instance["terminationTimestamp"])
        if not (
            started <= observed < deadline and 0 < (deadline - started).total_seconds() <= maximum
        ):
            raise PreviewCheckError(
                "VM automatic stop deadline is missing, expired or exceeds four hours"
            )
    elif instance.get("terminationTimestamp"):
        raise PreviewCheckError("Stopped VM still reports an active termination deadline")

    return {
        "project_id": PROJECT,
        "instance": name,
        "state": state,
        "machine_type": machine,
        "max_run_duration_seconds": maximum,
        "termination_action": "STOP",
        "automatic_stop_deadline": deadline.isoformat() if deadline else None,
        "external_ipv4_present": bool(external),
        "reserved_external_addresses": 0,
        "observed_at": observed.isoformat(),
    }


def read_gcloud(*arguments: str, fields: str) -> object:
    environment = os.environ.copy()
    environment["CLOUDSDK_CORE_DISABLE_PROMPTS"] = "1"
    result = subprocess.run(
        [
            "gcloud",
            "--quiet",
            "compute",
            *arguments,
            f"--project={PROJECT}",
            f"--format=json({fields})",
        ],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return json.loads(result.stdout)


def live_snapshot() -> dict:
    plan = json.loads(PLAN.read_text())
    if plan["project_id"] != PROJECT:
        raise PreviewCheckError("Preview plan targets the wrong project")
    instance = read_gcloud(
        "instances",
        "describe",
        plan["instance"]["name"],
        f"--zone={plan['zone']}",
        fields=INSTANCE_FIELDS,
    )
    addresses = read_gcloud("addresses", "list", fields="addressType")
    return {
        "instance": instance,
        "addresses": addresses,
        "observed_at": datetime.now(UTC).isoformat(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expect", required=True, choices=("running", "stopped"))
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--live", action="store_true", help="Only read current GCP state")
    source.add_argument("--snapshot", type=Path, help="Historical JSON; makes no cloud calls")
    args = parser.parse_args()
    try:
        snapshot = live_snapshot() if args.live else json.loads(args.snapshot.read_text())
        report = verify(snapshot, args.expect)
    except PreviewCheckError as error:
        parser.exit(1, f"Preview VM check failed: {error}.\n")
    except (KeyError, TypeError, ValueError, OSError, subprocess.SubprocessError):
        # Do not print captured cloud output, metadata or local credentials.
        parser.exit(
            1, "Preview VM check failed; inspect state, permissions and the reviewed plan.\n"
        )
    report["evidence"] = "live_read_only" if args.live else "historical_snapshot_only"
    print(json.dumps(report, indent=2))
    print("This check changes no resource. Disk/image charges and daily runtime remain separate.")


if __name__ == "__main__":
    main()
