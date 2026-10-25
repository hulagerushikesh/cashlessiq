"""Manage only the separate synthetic owner preview; never starts a tunnel."""

from __future__ import annotations

import argparse
import os
import re
import secrets
import stat
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env.owner-preview.local"
CREDENTIALS = ROOT / "output/owner-preview/owner-password.txt"
CADDY_IMAGE = "caddy:2-alpine"


def validate_origin(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or len(parsed.netloc) > 253
        or not re.fullmatch(
            r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
            r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?",
            parsed.netloc,
        )
        or "." not in parsed.netloc
        or any((parsed.path, parsed.query, parsed.fragment))
    ):
        raise ValueError("Use an exact HTTPS hostname origin, without a path or port")
    return value


def require_local_headroom() -> None:
    if sys.platform == "darwin":
        from scripts.check_product_host import require_headroom

        require_headroom()


def private_write(path: Path, content: str) -> None:
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as file:
        file.write(content)


def read_settings() -> dict[str, str]:
    if (
        ENV_FILE.is_symlink()
        or not ENV_FILE.is_file()
        or stat.S_IMODE(ENV_FILE.stat().st_mode) != 0o600
    ):
        raise ValueError("Preview environment must be a private regular file with mode 0600")
    values = dict(line.split("=", 1) for line in ENV_FILE.read_text().splitlines() if line)
    return {key: value.strip("'") for key, value in values.items()}


def compose(*args: str) -> None:
    subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            str(ENV_FILE),
            "-f",
            "compose.owner-preview.yml",
            *args,
        ],
        cwd=ROOT,
        check=True,
    )


def prepare(origin: str) -> None:
    validate_origin(origin)
    if ENV_FILE.exists() or ENV_FILE.is_symlink() or CREDENTIALS.exists():
        raise ValueError("Preview configuration already exists; refusing to replace credentials")
    require_local_headroom()
    password = secrets.token_urlsafe(32)
    hashed = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--interactive",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            # The official Caddy binary has this file capability; omitting it
            # from Docker's bounding set can prevent exec before hashing starts.
            "--cap-add",
            "NET_BIND_SERVICE",
            "--security-opt",
            "no-new-privileges",
            CADDY_IMAGE,
            "caddy",
            "hash-password",
        ],
        input=password + "\n",
        text=True,
        capture_output=True,
        timeout=60,
        check=True,
    ).stdout.strip()
    if not re.fullmatch(r"\$2[aby]\$14\$[./A-Za-z0-9]{53}", hashed):
        raise ValueError("Password hashing did not return the expected bcrypt hash")
    CREDENTIALS.parent.mkdir(parents=True, exist_ok=True)
    private_write(CREDENTIALS, f"Username: owner\nPassword: {password}\n")
    private_write(
        ENV_FILE,
        f"CIQ_DB_PASSWORD={secrets.token_hex(24)}\n"
        f"CIQ_LOCAL_AUTH_SECRET={secrets.token_hex(32)}\n"
        f"CIQ_WEB_ORIGIN={origin}\n"
        # Single quotes prevent Compose from interpolating bcrypt's dollar signs.
        f"CIQ_PREVIEW_PASSWORD_HASH='{hashed}'\n",
    )
    print(f"Prepared separate preview credentials: {CREDENTIALS}")
    print("No preview stack or tunnel has been started.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "set-origin", "up", "down", "status"])
    parser.add_argument("--origin")
    args = parser.parse_args()
    if args.action in {"prepare", "set-origin"}:
        if not args.origin:
            parser.error("--origin is required")
        validate_origin(args.origin)
    if args.action == "prepare":
        prepare(args.origin)
    elif args.action == "set-origin":
        settings = read_settings()
        old = f"CIQ_WEB_ORIGIN={settings['CIQ_WEB_ORIGIN']}\n"
        ENV_FILE.write_text(ENV_FILE.read_text().replace(old, f"CIQ_WEB_ORIGIN={args.origin}\n"))
        print("Preview origin updated; restart only the preview web service to apply it.")
    elif args.action == "up":
        validate_origin(read_settings()["CIQ_WEB_ORIGIN"])
        require_local_headroom()
        compose("up", "--build", "--detach", "--wait", "--wait-timeout", "240")
        print("Owner gateway: http://127.0.0.1:3080 (remote access requires an HTTPS tunnel)")
    else:
        compose(*(["down"] if args.action == "down" else ["ps", "--all"]))


if __name__ == "__main__":
    # `python -m scripts.owner_preview` keeps the shared Mac resource gate importable.
    main()
