"""Bounded, network-free clock-domain/restart test; never real clock-health acceptance."""

import argparse
import hashlib
import json
import subprocess
from contextlib import suppress
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def docker(*arguments, timeout=60):
    return subprocess.run(
        ["docker", *arguments],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
        timeout=timeout,
    ).stdout.strip()


def main(*, unified=False):
    prefix = f"ciq-clock-{uuid4().hex[:12]}"
    image = f"{prefix}:test"
    candidate = f"{prefix}:candidate"
    volume = f"{prefix}-state"
    module = "worker_guard_authority" if unified else "worker_clock"
    expected_hash = hashlib.sha256(
        (ROOT / f"apps/api/src/ciq_api/{module}.py").read_bytes()
    ).hexdigest()
    probe_name = "guard_probe" if unified else "clock_probe"
    containers = [f"{prefix}-one", f"{prefix}-two"]
    created = []
    volume_created = False

    def probe(container, operation):
        return docker(
            "exec", container, "python", "-m", f"ciq_worker_runtime.{probe_name}", operation
        )

    try:
        test_target = "guard-test" if unified else "clock-test"
        for target, tag in ((test_target, image), ("candidate", candidate)):
            docker(
                "build",
                "--target",
                target,
                "-f",
                "apps/worker/Dockerfile",
                "-t",
                tag,
                ".",
                timeout=300,
            )
        docker("volume", "create", "--label", f"cashlessiq.clock-test={prefix}", volume)
        volume_created = True
        docker(
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--user",
            "0:0",
            "--cap-drop",
            "ALL",
            "--cap-add",
            "CHOWN",
            "--security-opt",
            "no-new-privileges",
            "--mount",
            f"type=volume,src={volume},dst=/state",
            "--entrypoint",
            "python",
            image,
            "-m",
            f"ciq_worker_runtime.{probe_name}",
            "initialize",
        )
        for name in containers:
            created.append(name)  # Register before creation; cleanup is exact, never broad prune.
            docker(
                "run",
                "-d",
                "--name",
                name,
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
                "0.5",
                "--pids-limit",
                "32",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,size=8m",
                "--mount",
                f"type=volume,src={volume},dst=/state",
                "--entrypoint",
                "sleep",
                image,
                "240",
            )
            inspect = json.loads(docker("inspect", name))[0]
            assert inspect["HostConfig"]["NetworkMode"] == "none"
            assert inspect["HostConfig"]["ReadonlyRootfs"] is True
            assert inspect["Config"]["User"] == "10001:10001"
            assert not inspect["HostConfig"]["PortBindings"]
        first = json.loads(probe(containers[0], "consume"))
        second = json.loads(probe(containers[1], "replay"))
        docker("restart", containers[0])
        third = json.loads(probe(containers[0], "replay"))
        assert first["boot"] == second["boot"] == third["boot"]
        assert first["mono_ns"] <= second["mono_ns"] <= third["mono_ns"]
        assert first["wall_ns"] <= second["wall_ns"] <= third["wall_ns"]
        if unified:
            assert first["boottime_ns"] <= second["boottime_ns"] <= third["boottime_ns"]
            assert all(value["boottime_ns"] >= value["mono_ns"] for value in (first, second, third))
        assert probe(containers[1], "latch") == "Guard denied as required"
        docker("restart", containers[0])
        assert probe(containers[0], "deny") == "Guard denied as required"
        assert probe(containers[1], "deny") == "Guard denied as required"
        # Inspect the normal artifact without activating any service or mounting state.
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
            "import importlib.util,hashlib,sys; from pathlib import Path; "
            "import importlib; clock=importlib.import_module('ciq_api.'+sys.argv[2]); "
            "assert hashlib.sha256(Path(clock.__file__).read_bytes()).hexdigest()==sys.argv[1]; "
            "assert importlib.util.find_spec('ciq_worker_runtime.clock_probe') is None; "
            "assert importlib.util.find_spec('ciq_worker_runtime.guard_probe') is None; "
            "assert importlib.util.find_spec('ciq_api.main') is None; "
            "assert all(importlib.util.find_spec(n) is None for n in "
            "('sqlalchemy','psycopg','fastapi','snowflake','ciq_api.worker_guard_broker')); "
            "import ciq_api.worker_guard_health,ciq_api.worker_guard_transport",
            expected_hash,
            module,
        )
        try:
            docker("run", "--rm", "--network", "none", "--read-only", candidate)
        except subprocess.CalledProcessError as error:
            assert error.returncode == 1
            assert "Worker activation unavailable" in error.stderr
        else:
            raise AssertionError("Default worker unexpectedly activated")
        label = "v3 " if unified else ""
        print(f"{prefix}: PASS {label}clock-domain/restart/latch/artifact; fake health only")
    finally:
        failures = []
        for name in created:
            try:
                docker("rm", "-f", name)
            except subprocess.CalledProcessError:
                # A failed create may not have made a container; inspect before reporting.
                if docker("ps", "-a", "--filter", f"name=^{name}$", "--format", "{{.Names}}"):
                    failures.append(name)
        if volume_created:
            try:
                docker("volume", "rm", volume)
            except subprocess.CalledProcessError:
                failures.append(volume)
        for tag in (image, candidate):
            with suppress(subprocess.CalledProcessError):
                docker("image", "rm", tag)
        if failures:
            raise RuntimeError(f"Review exact test cleanup failures: {failures}")
        print(f"{prefix}: owned test containers/volume removed; build cache may remain")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unified-guard", action="store_true")
    main(unified=parser.parse_args().unified_guard)
