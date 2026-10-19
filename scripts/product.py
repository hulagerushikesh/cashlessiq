"""Local stack launcher; generated secrets stay in an ignored, owner-only file."""

from __future__ import annotations

import argparse
import os
import secrets
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env.product.local"


def local_environment() -> dict[str, str]:
    if not ENV_FILE.exists():
        descriptor = os.open(ENV_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(
                f"CIQ_DB_PASSWORD={secrets.token_hex(24)}\n"
                f"CIQ_LOCAL_AUTH_SECRET={secrets.token_hex(32)}\n"
            )
    return dict(line.split("=", 1) for line in ENV_FILE.read_text().splitlines() if line)


def run(*command: str, env: dict[str, str] | None = None) -> None:
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["up", "down", "status", "logs", "test-api"])
    action = parser.parse_args().action
    private = local_environment()
    compose = (
        "docker",
        "compose",
        "--env-file",
        str(ENV_FILE),
        "-f",
        "compose.product.yml",
    )
    if action == "up":
        run(*compose, "up", "--build", "--detach", "--wait", "--wait-timeout", "240")
        print("CashlessIQ local workspace: http://localhost:3000")
        print("API readiness: http://localhost:8000/health/ready")
    elif action == "down":
        run(*compose, "down")
        print("Local services stopped. PostgreSQL data volume retained.")
    elif action == "status":
        run(*compose, "ps", "--all")
    elif action == "logs":
        run(*compose, "logs", "--tail", "60", "api", "web", "migrate")
    else:
        env = os.environ | {
            "TEST_DATABASE_URL": (
                f"postgresql+psycopg://ciq:{private['CIQ_DB_PASSWORD']}@127.0.0.1:55432/cashlessiq"
            ),
        }
        run("uv", "run", "--project", "apps/api", "pytest", "apps/api/tests", env=env)


if __name__ == "__main__":
    main()
