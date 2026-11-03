"""Explicit disposable CI only. No host mounts, credentials or local activation."""

import os
import re
import signal
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def docker(*args, check=True, timeout=30):
    result = subprocess.run(["docker", *args], cwd=ROOT, capture_output=True, timeout=timeout)
    if check and result.returncode:
        raise RuntimeError("Disposable receipt-peer Docker operation failed")
    return result


def interrupted(_signal, _frame):
    raise SystemExit("Interrupted; cleaning owned fake receipt peer resources")


def main():
    if (
        sys.platform != "linux" or os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("GITHUB_REPOSITORY") != "hulagerushikesh/cashlessiq"
        or os.environ.get("CIQ_AGENT_RECEIPT_PEER_TEST") != "1"
    ):
        raise SystemExit("Receipt peer isolation requires the explicit disposable CI job")
    signal.signal(signal.SIGTERM, interrupted)
    name = "ciq-receipt-peer-" + uuid4().hex[:16]
    image, identifier = name + ":test", None
    try:
        docker("build", "-f", "deploy/agent-controller/receipt-peer-test.Dockerfile",
               "-t", image, ".", timeout=180)
        identifier = docker(
            "create", "--name", name, "--label", f"ciq.receipt-peer-test={name}",
            "--network", "none", "--read-only", "--cap-drop", "ALL",
            # Only the trusted disposable supervisor changes UID/owns fixture
            # files and kills/reaps children. No privilege is granted to peers.
            "--cap-add", "SETUID", "--cap-add", "SETGID", "--cap-add", "CHOWN",
            "--cap-add", "DAC_OVERRIDE", "--cap-add", "FOWNER", "--cap-add", "KILL",
            "--security-opt", "no-new-privileges", "--user", "0:0",
            "--memory", "512m", "--cpus", "1", "--pids-limit", "128",
            "--ulimit", "nofile=256:256",
            "--tmpfs", "/run:rw,nosuid,nodev,noexec,size=32m,mode=755",
            "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=64m,mode=1777",
            "--env", "GITHUB_ACTIONS=true",
            "--env", "GITHUB_REPOSITORY=hulagerushikesh/cashlessiq",
            "--env", "CIQ_AGENT_RECEIPT_PEER_TEST=1", image,
        ).stdout.decode().strip()
        result = docker("start", "-a", identifier, check=False, timeout=180)
        # Test data are synthetic, but emit only counts/fixed failure labels.
        output = result.stdout.decode(errors="replace")
        for line in output.splitlines():
            if re.fullmatch(r"\d+ passed(?:, \d+ warnings?)? in [0-9.]+s", line.strip()):
                print(line.strip())
            elif line.startswith(("FAILED ", "ERROR ")):
                print(line.split(" - ", 1)[0])
        if result.returncode:
            raise RuntimeError("Disposable receipt peer acceptance failed")
        print("PASS: independent receipt peers and invocation-owned process/file cleanup")
    finally:
        failures = []
        if identifier is not None and docker("rm", "-f", identifier, check=False).returncode:
            failures.append("container")
        if docker("image", "rm", image, check=False).returncode:
            failures.append("image")
        if failures:
            raise RuntimeError("Owned receipt-peer cleanup incomplete")
        print("PASS: invocation-owned receipt peer container/image removed")


if __name__ == "__main__":
    main()
