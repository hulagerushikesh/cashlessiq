"""Local stack launcher; generated secrets stay in an ignored, owner-only file."""

from __future__ import annotations

import argparse
import os
import secrets
import subprocess
import sys
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


def run(*command: str, env: dict[str, str] | None = None, timeout: int | None = None) -> None:
    subprocess.run(command, cwd=ROOT, env=env, check=True, timeout=timeout)


def require_local_headroom() -> None:
    if sys.platform == "darwin":
        from scripts.check_product_host import require_headroom

        require_headroom()


def start(compose: tuple[str, ...], *, timeout: int | None = None) -> None:
    require_local_headroom()
    run(*compose, "up", "--build", "--detach", "--wait", "--wait-timeout", "240", timeout=timeout)


def stop(compose: tuple[str, ...]) -> None:
    run(*compose, "down", timeout=120)


def test_environment(private: dict[str, str]) -> dict[str, str]:
    env = os.environ | {
        "TEST_DATABASE_URL": (
            f"postgresql+psycopg://ciq:{private['CIQ_DB_PASSWORD']}@127.0.0.1:55432/cashlessiq"
        ),
    }
    env.pop("VIRTUAL_ENV", None)
    return env


def test_session(compose: tuple[str, ...], private: dict[str, str]) -> None:
    """Run bounded API/browser checks and attempt to stop our stack on failure."""
    require_local_headroom()
    try:
        start(compose, timeout=600)
        run(
            "uv",
            "run",
            "--project",
            "apps/api",
            "pytest",
            "apps/api/tests",
            env=test_environment(private),
            timeout=900,
        )
        run("npm", "run", "test:browser", timeout=600)
    finally:
        stop(compose)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=["up", "down", "status", "logs", "test-api", "test-source-ui", "test-session"],
    )
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
        start(compose)
        print("CashlessIQ local workspace: http://localhost:3000")
        print("API readiness: http://localhost:8000/health/ready")
    elif action == "down":
        stop(compose)
        print("Local services stopped. PostgreSQL data volume retained.")
    elif action == "test-session":
        test_session(compose, private)
        print("Bounded local checks passed. CashlessIQ services stopped; data retained.")
    elif action == "status":
        run(*compose, "ps", "--all")
    elif action == "logs":
        run(*compose, "logs", "--tail", "60", "api", "web", "migrate")
    else:
        env = test_environment(private)
        if action == "test-source-ui":
            run("npm", "run", "build", env=env)
            run("npm", "run", "test:source-ui", env=env)
        else:
            run("uv", "run", "--project", "apps/api", "pytest", "apps/api/tests", env=env)


if __name__ == "__main__":
    main()
