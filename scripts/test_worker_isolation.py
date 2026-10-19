"""Build disposable worker test image and verify dummy mounts/private topology.

Explicit local Docker test only; no Compose changes, secrets from environment,
Snowflake, real credentials or normal service activation. Removes only resources
created by this invocation, retaining existing product containers and volumes.
"""

import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
ROLES = (
    "broker",
    "read1nonclinical",
    "read1medical",
    "read3nonclinical",
    "read3medical",
    "validator1",
    "validator3",
    "membership",
)


def docker(*arguments, capture=True):
    result = subprocess.run(
        ["docker", *arguments],
        cwd=ROOT,
        text=True,
        check=True,
        stdout=subprocess.PIPE if capture else None,
    )
    return result.stdout.strip() if capture else None


def main():
    prefix = f"ciq-isolation-{uuid4().hex[:12]}"
    image = f"{prefix}:test"
    candidate = f"{prefix}:candidate"
    containers, networks = [], []
    adjacency = {role: set() for role in ROLES}
    edges = []
    for tenant in (1, 3):
        for disclosure in ("nonclinical", "medical"):
            reader = f"read{tenant}{disclosure}"
            edges.extend((("broker", reader), (reader, f"validator{tenant}")))
        for worker in (f"read{tenant}nonclinical", f"read{tenant}medical", f"validator{tenant}"):
            edges.append((worker, "membership"))
    try:
        docker(
            "build",
            "--target",
            "candidate",
            "-f",
            "apps/worker/Dockerfile",
            "-t",
            candidate,
            ".",
            capture=False,
        )
        docker(
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--entrypoint",
            "python",
            candidate,
            "-c",
            "import importlib.util; from ciq_api import worker_membership; "
            "assert importlib.util.find_spec('ciq_worker_runtime.isolation_probe') is None; "
            "assert importlib.util.find_spec('ciq_api.main') is None; "
            "assert importlib.util.find_spec('sqlalchemy') is None; "
            "assert importlib.util.find_spec('snowflake') is None",
        )
        docker(
            "build",
            "--target",
            "isolation-test",
            "-f",
            "apps/worker/Dockerfile",
            "-t",
            image,
            ".",
            capture=False,
        )
        role_networks = {role: [] for role in ROLES}
        for index, (left, right) in enumerate(edges):
            network = docker(
                "network",
                "create",
                "--internal",
                "--label",
                f"cashlessiq.isolation-test={prefix}",
                f"{prefix}-edge{index}",
            )
            networks.append(network)
            role_networks[left].append(network)
            role_networks[right].append(network)
            adjacency[left].add(right)
            adjacency[right].add(left)
        with TemporaryDirectory(prefix="ciq-dummy-mounts-") as directory:
            root = Path(directory)
            for role in ROLES:
                dummy = root / role
                dummy.touch(mode=0o444)
                dummy.chmod(0o600)
                dummy.write_text(f"dummy-only:{role}")
                dummy.chmod(0o444)
                arguments = [
                    "create",
                    "--name",
                    f"{prefix}-{role}",
                    "--network",
                    role_networks[role][0],
                    "--network-alias",
                    role,
                    "--label",
                    f"cashlessiq.isolation-test={prefix}",
                    "--read-only",
                    "--cap-drop",
                    "ALL",
                    "--security-opt",
                    "no-new-privileges",
                    "--user",
                    "10001:10001",
                    "--memory",
                    "128m",
                    "--cpus",
                    "0.5",
                    "--pids-limit",
                    "32",
                    "--tmpfs",
                    "/tmp:rw,noexec,nosuid,size=8m,mode=1777",
                    "--mount",
                    f"type=bind,src={dummy},dst=/run/ciq/identity,readonly",
                ]
                if role in {"broker", "membership"}:
                    destination = "broker-signing-key" if role == "broker" else "membership-db"
                    arguments += [
                        "--mount",
                        f"type=bind,src={dummy},dst=/run/ciq/{destination},readonly",
                    ]
                identifier = docker(*arguments, image, "serve", role)
                containers.append(identifier)
            ids = dict(zip(ROLES, containers, strict=True))
            for role in ROLES:
                for network in role_networks[role][1:]:
                    docker("network", "connect", "--alias", role, network, ids[role])
            for identifier in containers:
                docker("start", identifier)
            inspected = {
                role: json.loads(docker("inspect", identifier))[0]
                for role, identifier in ids.items()
            }
            addresses = {
                role: [net["IPAddress"] for net in config["NetworkSettings"]["Networks"].values()]
                for role, config in inspected.items()
            }
            # Inspect real engine configuration, not just desired CLI arguments.
            for role, identifier in ids.items():
                config = inspected[role]
                host = config["HostConfig"]
                assert host["ReadonlyRootfs"] and host["CapDrop"] == ["ALL"]
                assert "no-new-privileges" in host["SecurityOpt"]
                assert config["Config"]["User"] == "10001:10001"
                assert not host["PortBindings"] and not config["Config"].get("ExposedPorts")
                assert all(not mount["RW"] for mount in config["Mounts"] if mount["Type"] == "bind")
                assert all(
                    json.loads(docker("network", "inspect", network))[0]["Internal"]
                    for network in config["NetworkSettings"]["Networks"]
                    if network != "none"
                )
                docker(
                    "exec",
                    identifier,
                    "python",
                    "-m",
                    "ciq_worker_runtime.isolation_probe",
                    "check",
                    role,
                    json.dumps(addresses),
                    *sorted(adjacency[role]),
                    capture=False,
                )
            print(
                "PASS: eight containers, 14 internal pair networks, no host ports; "
                "dummy secrets only"
            )
    finally:
        failures = []
        for command in (
            *[("rm", "-f", identifier) for identifier in reversed(containers)],
            *[("network", "rm", network) for network in reversed(networks)],
            ("image", "rm", image),
            ("image", "rm", candidate),
        ):
            result = subprocess.run(["docker", *command], capture_output=True, text=True)
            if result.returncode and "No such" not in result.stderr:
                failures.append(command[0])
        if failures:
            raise RuntimeError(f"Test cleanup incomplete for {prefix}: {failures}")


if __name__ == "__main__":
    main()
