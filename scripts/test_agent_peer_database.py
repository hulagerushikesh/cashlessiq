"""Combined dummy PostgreSQL/UID acceptance, explicit disposable Linux CI only."""

import json
import os
import signal
import subprocess
import sys
import time
from uuid import uuid4

from test_agent_receipt_peer import docker, interrupted, summary

CAPS = {"SETUID", "SETGID", "CHOWN", "DAC_OVERRIDE", "FOWNER", "KILL"}


def inspect(identifier):
    return json.loads(docker("inspect", identifier).stdout)[0]


def common():
    return [
        "--read-only", "--cap-drop", "ALL",
        *(value for cap in sorted(CAPS) for value in ("--cap-add", cap)),
        "--security-opt", "no-new-privileges", "--user", "0:0",
        "--memory", "512m", "--cpus", "1", "--pids-limit", "128",
        "--ulimit", "nofile=256:256",
    ]


def isolated(config, network, tmpfs):
    host = config["HostConfig"]
    assert host["NetworkMode"] == network and not host["PortBindings"]
    assert host["ReadonlyRootfs"] and not host["Privileged"]
    assert host["PidMode"] != "host" and host["IpcMode"] != "host"
    assert not host["Binds"]
    assert not any(m["Type"] != "tmpfs" for m in config["Mounts"])
    assert set(host["Tmpfs"]) == set(tmpfs)
    assert config["Config"]["User"] == "0:0"
    assert {c.removeprefix("CAP_") for c in host["CapDrop"]} == {"ALL"}
    assert {c.removeprefix("CAP_") for c in host["CapAdd"]} == CAPS
    assert "no-new-privileges" in host["SecurityOpt"]
    assert host["Memory"] == 512 * 1024 * 1024 and host["PidsLimit"] == 128
    assert host["NanoCpus"] == 1_000_000_000
    assert host["Ulimits"] == [{"Name": "nofile", "Hard": 256, "Soft": 256}]


def main():
    if (
        sys.platform != "linux" or os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("GITHUB_REPOSITORY") != "hulagerushikesh/cashlessiq"
        or os.environ.get("CIQ_AGENT_PEER_DATABASE_TEST") != "1"
    ):
        raise SystemExit("Combined peers require the explicit disposable CI job")
    signal.signal(signal.SIGTERM, interrupted)
    name = "ciq-peer-db-" + uuid4().hex[:16]
    image, owned = name + ":test", []
    try:
        docker("build", "-f", "deploy/agent-controller/peer-database-test.Dockerfile",
               "-t", image, ".", timeout=180)
        docker("pull", "postgres:17-bookworm", timeout=120)
        # PG and the test supervisor share only this network-free loopback
        # namespace. No host port, external bridge, Docker socket or data mount.
        pg = docker(
            "create", "--name", name + "-pg", *common(), "--network", "none",
            "--tmpfs", "/var/lib/postgresql/data:rw,nosuid,nodev,noexec,size=192m,mode=755",
            "--tmpfs", "/var/run/postgresql:rw,nosuid,nodev,noexec,size=4m,mode=777",
            "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=16m,mode=1777",
            "--env", "POSTGRES_PASSWORD=ciq-disposable-agent-ledger",
            "--env", "PGDATA=/var/lib/postgresql/data", "postgres:17-bookworm",
        ).stdout.decode().strip()
        owned.append(pg)
        isolated(inspect(pg), "none", ("/var/lib/postgresql/data", "/var/run/postgresql", "/tmp"))
        docker("start", pg)
        end = time.monotonic() + 35
        while docker("exec", pg, "pg_isready", "-h", "127.0.0.1", "-U", "postgres",
                     check=False).returncode:
            if time.monotonic() >= end:
                raise RuntimeError("Disposable combined database readiness timed out")
            time.sleep(0.5)
        identifier = docker(
            "create", "--name", name, *common(), "--network", "container:" + pg,
            "--tmpfs", "/run:rw,nosuid,nodev,noexec,size=32m,mode=755",
            "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=64m,mode=1777",
            "--env", "GITHUB_ACTIONS=true",
            "--env", "GITHUB_REPOSITORY=hulagerushikesh/cashlessiq",
            "--env", "CIQ_AGENT_CONTROLLER_TEST=1",
            "--env", "CIQ_AGENT_RECEIPT_PEER_TEST=1",
            "--env", "CIQ_AGENT_PEER_DATABASE_TEST=1",
            "--env", "TEST_DATABASE_URL=postgresql+psycopg://postgres:"
            "ciq-disposable-agent-ledger@127.0.0.1:5432/postgres", image,
        ).stdout.decode().strip()
        owned.append(identifier)
        isolated(inspect(identifier), "container:" + pg, ("/run", "/tmp"))
        try:
            result = docker("start", "-a", identifier, check=False, timeout=240)
        except subprocess.TimeoutExpired as exc:
            summary(exc.stdout or b"")
            raise RuntimeError("Combined peer acceptance timed out") from None
        passed = summary(result.stdout)
        state = inspect(identifier)["State"]
        if (
            result.returncode or state["Running"] or state["ExitCode"] != 0
            or state["OOMKilled"] or state["Error"] or passed != 11
        ):
            raise RuntimeError("Combined peer acceptance failed")
        assert inspect(pg)["State"]["Running"] and not inspect(pg)["State"]["OOMKilled"]
        print("PASS: restricted PostgreSQL, separate receipt peer and bounded fake child")
    finally:
        failures = []
        for identifier in reversed(owned):
            if docker("rm", "-f", identifier, check=False).returncode:
                failures.append("container")
        if docker("image", "rm", image, check=False).returncode:
            failures.append("image")
        if failures:
            raise RuntimeError("Owned combined-peer cleanup incomplete")
        print("PASS: invocation-owned database, peer containers and image removed")


if __name__ == "__main__":
    main()
