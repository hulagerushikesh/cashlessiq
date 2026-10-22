"""Explicit disposable Linux acceptance; no product services, credentials or network."""

import json
import shutil
import subprocess
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "Dockerfile": ROOT / "scripts/supervisor-container/Dockerfile",
    "offline_supervisor.py": ROOT / "apps/api/src/ciq_api/offline_supervisor.py",
    "supervisor_probe.py": ROOT / "scripts/supervisor_probe.py",
}
CASES = {
    "lifecycle",
    "partial_start",
    "readiness_loss",
    "unknown_termination",
    "blocked_controller",
}


def main():
    prefix = f"ciq-supervisor-{uuid4().hex[:12]}"
    image = f"{prefix}:test"
    end = time.monotonic() + 900

    def docker(*args, timeout=60, cleanup=False):
        # Reserve the final minute for exact owned-resource cleanup.
        deadline = end if cleanup else end - 60
        budget = min(timeout, 10 if cleanup else timeout, deadline - time.monotonic())
        if budget <= 0:
            raise TimeoutError("Disposable acceptance budget exceeded")
        return subprocess.run(
            ["docker", *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=budget,
            cwd=ROOT,
        ).stdout.strip()

    try:
        with TemporaryDirectory(prefix="ciq-supervisor-build-") as temporary:
            for name, source in SOURCES.items():
                shutil.copyfile(source, Path(temporary) / name)
            docker("build", "--network=none", "-t", image, temporary, timeout=300)
        docker(
            "create",
            "--name",
            prefix,
            "--label",
            f"cashlessiq.supervisor-test={prefix}",
            "--network",
            "none",
            "--read-only",
            "--user",
            "10001:10001",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--memory",
            "128m",
            "--cpus",
            "1",
            "--pids-limit",
            "64",
            image,
        )
        inspected = json.loads(docker("inspect", prefix))[0]
        host = inspected["HostConfig"]
        assert host["NetworkMode"] == "none" and host["ReadonlyRootfs"]
        assert host["CapDrop"] == ["ALL"] and not host["Privileged"]
        assert inspected["Config"]["User"] == "10001:10001"
        assert not inspected["Mounts"] and not host["PortBindings"]
        docker("start", prefix)
        result = json.loads(docker("wait", prefix, timeout=120))
        logs = docker("logs", prefix)
        if result != 0:
            raise AssertionError(
                "Disposable process acceptance failed; inspect test implementation"
            )
        reports = [json.loads(row) for row in logs.splitlines()]
        assert len(reports) == len(CASES)
        assert {r["case"] for r in reports} == CASES
        assert all(r["status"] == "PASS" for r in reports)
        print(logs)
        print(f"{prefix}: PASS network-free non-root process containment; test-only")
    finally:
        # Exact unique name only; never prune unrelated Docker resources.
        print(f"{prefix}: cleanup scope container={prefix} image={image}")
        names = docker(
            "ps",
            "-a",
            "--filter",
            f"name=^{prefix}$",
            "--format",
            "{{.Names}}",
            cleanup=True,
        )
        if names:
            assert names == prefix
            docker("rm", "-f", prefix, cleanup=True)
        if docker("image", "ls", "-q", image, cleanup=True):
            docker("image", "rm", image, cleanup=True)
        assert not docker(
            "ps",
            "-a",
            "--filter",
            f"name=^{prefix}$",
            "--format",
            "{{.Names}}",
            cleanup=True,
        )
        print(f"{prefix}: owned test container/image removed; base/build cache may remain")


if __name__ == "__main__":
    main()
