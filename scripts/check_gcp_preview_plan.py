"""Check the private GCP MVP composition without contacting GCP or starting Docker."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "deploy/gcp-preview/plan.json"
MIB = 1024 * 1024
COMPOSE_FILES = (
    "compose.owner-preview.yml",
    "compose.preview-small.yml",
    "compose.mvp.yml",
    "compose.gcp-preview.yml",
)


def check() -> None:
    plan = json.loads(PLAN.read_text())
    assert plan["project_id"] == "cashlessiq-dev-rush"
    assert plan["project_billing_enabled"] is False
    assert plan["cloud_deployment_authorized"] is False
    assert plan["runtime"]["compose_files"] == list(COMPOSE_FILES)
    assert plan["instance"]["max_run_duration_seconds"] == 14400
    assert plan["instance"]["termination_action"] == "STOP"

    assert plan["operating_policy"]["daily_testing_budget_seconds"] == 14400
    assert plan["operating_policy"]["automatic_daily_start"] is False

    registry = plan["build"]["registry"]
    api_image = f"{registry}/api@sha256:{'a' * 64}"
    web_image = f"{registry}/web@sha256:{'b' * 64}"
    env = os.environ.copy()
    env.update(
        CIQ_DB_PASSWORD="offline-preflight-only",
        CIQ_LOCAL_AUTH_SECRET="offline-preflight-only",
        CIQ_WEB_ORIGIN="https://preview.example.test",
        CIQ_PREVIEW_PASSWORD_HASH="offline-preflight-only",
        CIQ_PREVIEW_API_IMAGE=api_image,
        CIQ_PREVIEW_WEB_IMAGE=web_image,
    )
    command = ["docker", "compose"]
    for file in COMPOSE_FILES:
        command.extend(("-f", file))
    command.extend(("config", "--format", "json"))
    config = json.loads(
        subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    )
    services = config["services"]
    assert set(services) == {"db", "migrate", "api", "web", "gateway"}
    assert services["migrate"]["image"] == services["api"]["image"] == api_image
    assert services["web"]["image"] == web_image
    for service in ("migrate", "api", "web"):
        assert services[service]["environment"]["CIQ_SYNTHETIC_WORKFLOWS"] == "true"
    assert services["api"]["environment"]["CIQ_LOCAL_EMBEDDED_WORKER"] == "true"

    expected_mib = {"db": 256, "migrate": 256, "api": 512, "web": 512, "gateway": 128}
    for service, mib in expected_mib.items():
        assert int(services[service]["mem_limit"]) == mib * MIB, service
    steady_mib = sum(expected_mib[name] for name in expected_mib if name != "migrate")
    assert plan["runtime"]["steady_container_memory_ceiling_mib"] == steady_mib

    for name, service in services.items():
        if name != "gateway":
            assert not service.get("ports"), name
            assert set(service["networks"]) == {"preview"}, name
    assert config["networks"]["preview"]["internal"] is True
    ports = services["gateway"]["ports"]
    assert len(ports) == 1
    assert ports[0]["host_ip"] == "127.0.0.1" and ports[0]["published"] == "3080"
    assert ports[0]["target"] == 8080
    print(f"GCP MVP composition preflight passed; steady container ceiling {steady_mib} MiB.")
    print("No cloud API, build, container start or paid resource was used.")


if __name__ == "__main__":
    check()
