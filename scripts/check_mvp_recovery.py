"""Back up the current synthetic MVP and verify an isolated restore.

The active database is read only throughout. Optional service restart acceptance
and fresh-volume acceptance are limited to disposable GitHub Actions preview stacks.
"""

import argparse
import hashlib
import json
import os
import re
import select
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

from scripts.verify_mvp_backup import verify_package

ROOT = Path(__file__).resolve().parents[1]
PROBE = (ROOT / "scripts/mvp_recovery_probe.py").read_text()
FRESH_PROJECT = "cashlessiq-recovery-ci"


def command(args, **kwargs):
    try:
        return subprocess.run(
            args, check=True, cwd=ROOT, timeout=120, stderr=subprocess.PIPE, **kwargs
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        raise RuntimeError("Recovery command failed; private artifacts retained") from None


def compose_prefix(stack):
    if stack not in {"product", "preview"}:
        raise ValueError("Unknown recovery stack")
    name = "product" if stack == "product" else "owner-preview"
    args = ["docker", "compose", "--env-file", f".env.{name}.local", "-f", f"compose.{name}.yml"]
    if stack == "preview":
        args += ["-f", "compose.preview-small.yml"]
    return args


def owned_containers(stack):
    ids = {}
    for service in ("db", "api"):
        cid = command([*compose_prefix(stack), "ps", "-q", service], stdout=subprocess.PIPE)
        cid = cid.stdout.decode().strip()
        if not re.fullmatch(r"[a-f0-9]{64}", cid):
            raise ValueError("Expected one running recovery container")
        row = json.loads(command(["docker", "inspect", cid], stdout=subprocess.PIPE).stdout)[0]
        labels = row["Config"]["Labels"]
        if (
            row["Id"] != cid
            or not row["State"]["Running"]
            or labels.get("com.docker.compose.project")
            != f"cashlessiq-{'product' if stack == 'product' else 'owner-preview'}"
            or labels.get("com.docker.compose.service") != service
            or labels.get("com.docker.compose.project.working_dir") != str(ROOT)
        ):
            raise ValueError("Recovery container ownership mismatch")
        ids[service] = cid
    return ids


def read_frame(process):
    deadline, data = time.monotonic() + 120, b""
    while b"\n" not in data:
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not select.select([process.stdout], [], [], remaining)[0]:
            raise RuntimeError("Snapshot probe timed out")
        chunk = os.read(process.stdout.fileno(), 65536)
        if not chunk or len(data) + len(chunk) > 65536:
            raise RuntimeError("Invalid snapshot probe response")
        data += chunk
    return json.loads(data)


def probe_command(api, target):
    return ["docker", "exec", "-i", api, "/app/apps/api/.venv/bin/python", "-c", PROBE, target]


def verify_manifest(expected, actual):
    if not expected or expected != actual:
        raise RuntimeError(
            "Restored MVP table inventory or contents do not match the backup snapshot"
        )


def backup(ids, directory):
    process = subprocess.Popen(
        probe_command(ids["api"], "source"),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        cwd=ROOT,
    )
    try:
        frame = read_frame(process)
        snapshot = frame["snapshot"]
        if not re.fullmatch(r"[A-F0-9]+-[A-F0-9]+-[0-9]+", snapshot):
            raise ValueError("Invalid exported snapshot identifier")
        path = directory / "current.dump"
        with path.open("xb") as output:
            path.chmod(0o600)
            command(
                [
                    "docker",
                    "exec",
                    ids["db"],
                    "pg_dump",
                    "-U",
                    "ciq",
                    "-d",
                    "cashlessiq",
                    "--format=custom",
                    "--no-owner",
                    "--no-privileges",
                    "--lock-wait-timeout=5s",
                    f"--snapshot={snapshot}",
                ],
                stdout=output,
            )
        if not 0 < path.stat().st_size <= 100 * 1024**2:
            raise ValueError("Backup size limit")
        with path.open("rb") as source:
            if source.read(5) != b"PGDMP":
                raise ValueError("Expected PostgreSQL custom backup")
        process.communicate(b"release\n", timeout=10)
        if process.returncode != 0:
            raise RuntimeError("Snapshot transaction failed")
        return path, frame
    finally:
        if process.poll() is None:
            # Closing stdin releases the server transaction even if docker exec is interrupted.
            process.stdin.close()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)


def restore(ids, path, expected):
    database = "ciq_rehearsal_" + uuid4().hex[:24]
    command(["docker", "exec", ids["db"], "createdb", "-U", "ciq", "-T", "template0", database])
    try:
        with path.open("rb") as source:
            command(
                [
                    "docker",
                    "exec",
                    "-i",
                    ids["db"],
                    "pg_restore",
                    "-U",
                    "ciq",
                    "--no-owner",
                    "--no-privileges",
                    "--exit-on-error",
                    "-d",
                    database,
                ],
                stdin=source,
                stdout=subprocess.PIPE,
            )
        result = command(probe_command(ids["api"], database), stdout=subprocess.PIPE)
        verify_manifest(expected, json.loads(result.stdout)["manifest"])
    finally:
        command(["docker", "exec", ids["db"], "dropdb", "-U", "ciq", database])


def require_restart_permission(stack):
    if (
        stack != "preview"
        or sys.platform != "linux"
        or os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("RUNNER_OS") != "Linux"
        or os.environ.get("GITHUB_REPOSITORY") != "hulagerushikesh/cashlessiq"
    ):
        raise ValueError("Service restart rehearsal is limited to disposable GitHub CI preview")


def fresh_compose_prefix():
    return [
        "docker",
        "compose",
        "-p",
        FRESH_PROJECT,
        "--env-file",
        ".env.owner-preview.local",
        "-f",
        "compose.owner-preview.yml",
        "-f",
        "compose.preview-small.yml",
        "-f",
        "compose.mvp.yml",
    ]


def fresh_preview_env():
    return {
        **os.environ,
        "CIQ_PREVIEW_PORT": "3081",
        "CIQ_WEB_ORIGIN": "http://127.0.0.1:3081",
    }


def require_empty_fresh_project():
    containers = command(
        [
            "docker",
            "ps",
            "-a",
            "-q",
            "--filter",
            f"label=com.docker.compose.project={FRESH_PROJECT}",
        ],
        stdout=subprocess.PIPE,
    ).stdout.strip()
    volume = subprocess.run(
        ["docker", "volume", "inspect", f"{FRESH_PROJECT}_owner-preview-db"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=10,
        check=False,
    )
    if containers or volume.returncode == 0:
        raise ValueError("Fresh recovery project or volume already exists")


def fresh_volume_preview(path, expected):
    """Restore to a new PostgreSQL volume and launch an independent CI preview."""
    require_restart_permission("preview")
    require_empty_fresh_project()
    prefix, env = fresh_compose_prefix(), fresh_preview_env()
    try:
        # Compose's default build-image names contain the project name. Reuse
        # images already built for the original preview; never build or pull.
        for service in ("api", "web"):
            source = (
                command(
                    [*compose_prefix("preview"), "images", "-q", service],
                    stdout=subprocess.PIPE,
                    env=os.environ,
                )
                .stdout.decode()
                .strip()
            )
            if not re.fullmatch(r"(?:sha256:)?[a-f0-9]{12,64}", source):
                raise ValueError("Expected one existing preview image")
            command(["docker", "tag", source, f"{FRESH_PROJECT}-{service}:latest"])
        command(
            [
                *prefix,
                "up",
                "--no-build",
                "--pull",
                "never",
                "--no-deps",
                "--detach",
                "--wait",
                "--wait-timeout",
                "90",
                "db",
            ],
            stdout=subprocess.PIPE,
            env=env,
        )
        db = command([*prefix, "ps", "-q", "db"], stdout=subprocess.PIPE, env=env)
        db = db.stdout.decode().strip()
        if not re.fullmatch(r"[a-f0-9]{64}", db):
            raise ValueError("Expected one fresh recovery database container")
        row = json.loads(command(["docker", "inspect", db], stdout=subprocess.PIPE).stdout)[0]
        mounts = row["Mounts"]
        if (
            row["Config"]["Labels"].get("com.docker.compose.project") != FRESH_PROJECT
            or row["Config"]["Labels"].get("com.docker.compose.service") != "db"
            or len(mounts) != 1
            or mounts[0].get("Name") != f"{FRESH_PROJECT}_owner-preview-db"
            or mounts[0].get("Destination") != "/var/lib/postgresql/data"
        ):
            raise ValueError("Fresh recovery database/volume ownership mismatch")
        # Recreate only the new project's initial database from template0,
        # matching the temporary-DB restore path. No application is running.
        command(["docker", "exec", db, "dropdb", "-U", "ciq", "cashlessiq"])
        command(["docker", "exec", db, "createdb", "-U", "ciq", "-T", "template0", "cashlessiq"])
        with path.open("rb") as source:
            command(
                [
                    "docker",
                    "exec",
                    "-i",
                    db,
                    "pg_restore",
                    "-U",
                    "ciq",
                    "--no-owner",
                    "--no-privileges",
                    "--exit-on-error",
                    "-d",
                    "cashlessiq",
                ],
                stdin=source,
                stdout=subprocess.PIPE,
            )
        result = command(
            [
                *prefix,
                "run",
                "--rm",
                "--no-deps",
                "-T",
                "api",
                "/app/apps/api/.venv/bin/python",
                "-c",
                PROBE,
                "fresh",
            ],
            stdout=subprocess.PIPE,
            env=env,
        )
        verify_manifest(expected, json.loads(result.stdout)["manifest"])
        command(
            [
                *prefix,
                "up",
                "--no-build",
                "--pull",
                "never",
                "--no-deps",
                "--detach",
                "--wait",
                "--wait-timeout",
                "120",
                "api",
                "web",
                "gateway",
            ],
            stdout=subprocess.PIPE,
            env=env,
        )
        print("Fresh PostgreSQL volume restored; recovered preview ready on loopback 3081.")
    except Exception:
        # This project is CI-only and was verified absent before creation.
        command([*prefix, "down", "--volumes"], stdout=subprocess.PIPE, env=env)
        raise


def restart_preview():
    # No local entry point reaches this mutation without the explicit CI-only guard.
    require_restart_permission("preview")
    prefix = [*compose_prefix("preview"), "-f", "compose.mvp.yml"]
    command([*prefix, "stop", "gateway", "web", "api"], stdout=subprocess.PIPE)
    try:
        # With application writers stopped, compare a stable checkpoint across a DB restart.
        # The stopped API cannot probe; use a one-off API container on the same private network.
        def checkpoint():
            result = command(
                [
                    *prefix,
                    "run",
                    "--rm",
                    "--no-deps",
                    "-T",
                    "api",
                    "/app/apps/api/.venv/bin/python",
                    "-c",
                    PROBE,
                    "checkpoint",
                ],
                stdout=subprocess.PIPE,
            )
            return json.loads(result.stdout)

        before = checkpoint()
        if not before.get("sample"):
            raise ValueError("Expected completed synthetic browser workflow before restart")
        command([*prefix, "stop", "db"], stdout=subprocess.PIPE)
        command(
            [
                *prefix,
                "up",
                "--no-build",
                "--pull",
                "never",
                "--no-deps",
                "--detach",
                "--wait",
                "--wait-timeout",
                "90",
                "db",
            ],
            stdout=subprocess.PIPE,
        )
        verify_manifest(before["manifest"], checkpoint()["manifest"])
        sample = ROOT / "output/owner-preview/recovery-checkpoint.json"
        with sample.open("x") as output:
            sample.chmod(0o600)
            json.dump(before["sample"], output)
        print("Database restart preserved all MVP tables; browser checkpoint prepared.")
    finally:
        command(
            [
                *prefix,
                "up",
                "--no-build",
                "--pull",
                "never",
                "--no-deps",
                "--detach",
                "--wait",
                "--wait-timeout",
                "90",
                "db",
            ],
            stdout=subprocess.PIPE,
        )
        command(
            [
                *prefix,
                "up",
                "--no-build",
                "--pull",
                "never",
                "--no-deps",
                "--detach",
                "--wait",
                "--wait-timeout",
                "120",
                "api",
                "web",
                "gateway",
            ],
            stdout=subprocess.PIPE,
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stack", choices=["product", "preview"], default="product")
    parser.add_argument("--restart-preview-ci", action="store_true")
    parser.add_argument("--fresh-volume-preview-ci", action="store_true")
    args = parser.parse_args()
    if args.restart_preview_ci or args.fresh_volume_preview_ci:
        require_restart_permission(args.stack)
    ids = owned_containers(args.stack)
    directory = ROOT / "output/mvp-recovery" / uuid4().hex
    directory.mkdir(parents=True, mode=0o700)
    path, frame = backup(ids, directory)
    restore(ids, path, frame["manifest"])
    with path.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    with (directory / "verified.json").open("x") as output:
        os.chmod(output.name, 0o600)
        json.dump(
            {
                "schema": "0003_mvp",
                "tables": frame["manifest"],
                "dump": {"file": "current.dump", "bytes": path.stat().st_size, "sha256": digest},
            },
            output,
            indent=2,
        )
    verify_package(directory)
    print(f"Current MVP backup restored and matched {len(frame['manifest'])} tables.")
    print(f"Private backup retained: {path}")
    if args.restart_preview_ci:
        restart_preview()
    if args.fresh_volume_preview_ci:
        fresh_volume_preview(path, frame["manifest"])


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError):
        print("MVP recovery rehearsal failed; source database was not restored or replaced.")
        raise SystemExit(1) from None
