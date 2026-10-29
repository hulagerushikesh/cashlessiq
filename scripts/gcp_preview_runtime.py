"""Operate the approved, synthetic GCP VM stack; no GCP API or billing calls.

This runs on the preview VM after its resources and images have been approved.
The owner-preview helper first creates independent credentials and sets the
exact HTTPS origin. This helper only accepts registry SHA-256 image digests.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from scripts import check_gcp_preview_plan, owner_preview

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env.owner-preview.local"
COMPOSE_FILES = check_gcp_preview_plan.COMPOSE_FILES
IMAGE_KEYS = ("CIQ_PREVIEW_API_IMAGE", "CIQ_PREVIEW_WEB_IMAGE")


def expected_image(service: str, value: str) -> str:
    registry = json.loads(check_gcp_preview_plan.PLAN.read_text())["build"]["registry"]
    pattern = rf"{re.escape(registry)}/{service}@sha256:[0-9a-f]{{64}}"
    if not re.fullmatch(pattern, value):
        raise ValueError(f"{service} must use an exact SHA-256 digest in {registry}")
    return value


def read_private_environment() -> dict[str, str]:
    # The shared helper checks regular-file type, symlinks and mode 0600.
    values = owner_preview.read_settings(ENV_FILE)
    lines = ENV_FILE.read_text().splitlines()
    keys = [line.split("=", 1)[0] for line in lines]
    if len(keys) != len(set(keys)) or any("=" not in line for line in lines):
        raise ValueError("Preview environment has duplicate or malformed entries")
    return values


def validate() -> dict[str, str]:
    values = read_private_environment()
    required = {
        "CIQ_DB_PASSWORD",
        "CIQ_LOCAL_AUTH_SECRET",
        "CIQ_WEB_ORIGIN",
        "CIQ_PREVIEW_PASSWORD_HASH",
        *IMAGE_KEYS,
    }
    if not required.issubset(values) or any(not values[key] for key in required):
        raise ValueError("Preview secrets, exact HTTPS origin and both image digests are required")
    owner_preview.validate_origin(values["CIQ_WEB_ORIGIN"])
    expected_image("api", values[IMAGE_KEYS[0]])
    expected_image("web", values[IMAGE_KEYS[1]])
    if not re.fullmatch(r"\$2[aby]\$14\$[./A-Za-z0-9]{53}", values["CIQ_PREVIEW_PASSWORD_HASH"]):
        raise ValueError("Owner password must have the expected bcrypt hash")
    return values


def set_images(api_image: str, web_image: str, *, replace: bool = False) -> None:
    expected_image("api", api_image)
    expected_image("web", web_image)
    values = read_private_environment()
    for key, image in zip(IMAGE_KEYS, (api_image, web_image), strict=True):
        if values.get(key) and values[key] != image and not replace:
            raise ValueError(
                "Existing image digest differs; pass --replace after reviewing revision"
            )
    content = ENV_FILE.read_text()
    content = "\n".join(
        line for line in content.splitlines() if line.split("=", 1)[0] not in IMAGE_KEYS
    )
    content += f"\n{IMAGE_KEYS[0]}={api_image}\n{IMAGE_KEYS[1]}={web_image}\n"
    # Replace the private file atomically and keep it private if interrupted.
    with tempfile.NamedTemporaryFile(
        mode="w", dir=ENV_FILE.parent, prefix=".ciq-preview-", delete=False
    ) as file:
        temporary = Path(file.name)
        os.chmod(temporary, 0o600)
        file.write(content)
    try:
        os.replace(temporary, ENV_FILE)
    finally:
        temporary.unlink(missing_ok=True)
    print("Exact API and web image digests saved in the private VM environment.")


def compose_command(*args: str) -> list[str]:
    command = ["docker", "compose", "--env-file", str(ENV_FILE)]
    for file in COMPOSE_FILES:
        command.extend(("-f", file))
    return [*command, *args]


def compose_environment(values: dict[str, str]) -> dict[str, str]:
    env = os.environ.copy()
    env.update(values)
    return env


def check() -> dict[str, str]:
    values = validate()
    env = compose_environment(values)
    config = json.loads(
        subprocess.run(
            compose_command("config", "--format", "json"),
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )
    if config["name"] != "cashlessiq-owner-preview":
        raise ValueError("Unexpected Compose project name")
    services = config["services"]
    if set(services) != {"db", "migrate", "api", "web", "gateway"}:
        raise ValueError("Unexpected service in preview composition")
    if not (
        services["api"]["image"] == services["migrate"]["image"] == values[IMAGE_KEYS[0]]
        and services["web"]["image"] == values[IMAGE_KEYS[1]]
    ):
        raise ValueError("Resolved images differ from approved exact digests")
    if (
        any(
            services[name]["environment"]["CIQ_SYNTHETIC_WORKFLOWS"] != "true"
            for name in ("migrate", "api", "web")
        )
        or services["api"]["environment"]["CIQ_LOCAL_EMBEDDED_WORKER"] != "true"
    ):
        raise ValueError("Synthetic workflows and local worker must be enabled")
    if any(services[name].get("ports") for name in ("db", "migrate", "api", "web")):
        raise ValueError("Backend port published by resolved composition")
    ports = services["gateway"]["ports"]
    if (
        len(ports) != 1
        or ports[0]["host_ip"] != "127.0.0.1"
        or ports[0]["published"] != "3080"
        or ports[0]["target"] != 8080
    ):
        raise ValueError("Gateway must publish only loopback port 3080")
    if config["networks"]["preview"]["internal"] is not True:
        raise ValueError("Backend network must stay internal")
    expected_mib = {"db": 256, "migrate": 256, "api": 512, "web": 512, "gateway": 128}
    for name, mib in expected_mib.items():
        if int(services[name]["mem_limit"]) != mib * 1024 * 1024:
            raise ValueError(f"Unexpected {name} memory ceiling")
    for name in ("db", "migrate", "api", "web"):
        if set(services[name]["networks"]) != {"preview"}:
            raise ValueError(f"Unexpected {name} network")
    if set(services["gateway"]["networks"]) != {"preview", "entry"}:
        raise ValueError("Unexpected gateway network")
    print("Private GCP runtime configuration passed; no container or cloud resource started.")
    return env


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("set-images", "check", "up", "restart-web", "down", "status")
    )
    parser.add_argument("--api-image")
    parser.add_argument("--web-image")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    if args.action == "set-images":
        if not args.api_image or not args.web_image:
            parser.error("set-images requires --api-image and --web-image")
        set_images(args.api_image, args.web_image, replace=args.replace)
    elif args.action == "check":
        check()
    else:
        if args.action == "up":
            environment = check()
            operation = ("up", "--no-build", "--pull", "always", "--detach", "--wait")
        elif args.action == "restart-web":
            environment = check()
            operation = (
                "up",
                "--no-build",
                "--pull",
                "never",
                "--no-deps",
                "--detach",
                "--wait",
                "web",
            )
        elif args.action == "down":
            environment = compose_environment(read_private_environment())
            operation = ("down",)
        else:
            environment = compose_environment(read_private_environment())
            operation = ("ps", "--all")
        subprocess.run(compose_command(*operation), cwd=ROOT, env=environment, check=True)


if __name__ == "__main__":
    main()
