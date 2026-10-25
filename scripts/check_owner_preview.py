"""Real gateway/production-app smoke checks against a disposable CI stack."""

import base64
import json
import re
import subprocess
from http.cookies import SimpleCookie
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from scripts.owner_preview import CREDENTIALS, read_settings

BASE = "http://127.0.0.1:3080"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def main() -> None:
    settings = read_settings()
    password = CREDENTIALS.read_text().split("Password: ", 1)[1].strip()
    basic = "Basic " + base64.b64encode(f"owner:{password}".encode()).decode()
    opener = build_opener(NoRedirect())
    checks = 0

    def request(path, status, *, auth=None, cookie=None, origin=None, form=None):
        nonlocal checks
        headers = {}
        if auth is not None:
            headers["Authorization"] = auth
        if cookie is not None:
            headers["Cookie"] = cookie
        if origin is not None:
            headers["Origin"] = origin
        data = urlencode(form).encode() if form is not None else None
        try:
            response = opener.open(Request(BASE + path, data=data, headers=headers), timeout=10)
        except HTTPError as error:
            response = error
        with response:
            body = response.read().decode()
            assert response.status == status, (path, response.status, status)
            assert response.headers.get("Cache-Control") == "no-store", path
            assert "noindex" in response.headers.get("X-Robots-Tag", ""), path
            if status == 401:
                assert response.headers.get("WWW-Authenticate", "").startswith("Basic ")
                assert "GOL001" not in body and "Choose your review" not in body
            checks += 1
            return response.headers, body

    for path in ["/", "/login", "/cases", "/cases/GOL001", "/source-preview", "/source-cases"]:
        request(path, 401)
        request(path, 401, auth="Basic " + base64.b64encode(b"owner:wrong").decode())
    for auth in ["Basic invalid", "Bearer fictional", ""]:
        request("/login", 401, auth=auth)
    request("/auth/login", 401, origin=settings["CIQ_WEB_ORIGIN"], form={"profile": "processor"})
    _, login = request("/login", 200, auth=basic)
    assert "Choose your review perspective" in login
    asset = re.search(r'(?:src|href)="(/_next/static/[^"?]+)', login)
    assert asset is not None, "Production page must link built static assets"
    request(asset.group(1), 401)
    request(asset.group(1), 200, auth=basic)
    request("/cases/GOL001", 307, auth=basic)
    request(
        "/auth/login",
        403,
        auth=basic,
        origin="https://foreign.invalid",
        form={"profile": "processor"},
    )
    request("/auth/login", 403, auth=basic, form={"profile": "processor"})

    for role in ["processor", "medical_officer", "auditor"]:
        headers, _ = request(
            "/auth/login",
            303,
            auth=basic,
            origin=settings["CIQ_WEB_ORIGIN"],
            form={"profile": role},
        )
        assert headers["Location"] == settings["CIQ_WEB_ORIGIN"] + "/"
        cookies = SimpleCookie(headers["Set-Cookie"])
        session = cookies["ciq_session"]
        assert session["secure"] and session["httponly"] and session["samesite"].lower() == "strict"
        cookie = f"ciq_session={session.value}"
        _, case = request("/cases/GOL001", 200, auth=basic, cookie=cookie)
        assert "95,000" in case
        assert ("Acute appendicitis" in case) == (role == "medical_officer")
        # An application session never substitutes for the outer owner password.
        request("/cases/GOL001", 401, cookie=cookie)
        request(
            "/auth/logout",
            403,
            auth=basic,
            cookie=cookie,
            origin="https://foreign.invalid",
            form={},
        )
        headers, _ = request(
            "/auth/logout",
            303,
            auth=basic,
            cookie=cookie,
            origin=settings["CIQ_WEB_ORIGIN"],
            form={},
        )
        assert headers["Location"] == settings["CIQ_WEB_ORIGIN"] + "/login"
        assert SimpleCookie(headers["Set-Cookie"])["ciq_session"]["max-age"] == "0"

    config = json.loads(
        subprocess.run(
            [
                "docker",
                "compose",
                "--env-file",
                ".env.owner-preview.local",
                "-f",
                "compose.owner-preview.yml",
                "-f",
                "compose.preview-small.yml",
                "config",
                "--format",
                "json",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    )
    assert config["name"] == "cashlessiq-owner-preview"
    for service, values in config["services"].items():
        if service != "gateway":
            assert not values.get("ports"), service
            assert set(values["networks"]) == {"preview"}, service
    assert config["networks"]["preview"]["internal"] is True
    expected_mib = {"db": 256, "migrate": 256, "api": 256, "web": 512, "gateway": 128}
    for service, mib in expected_mib.items():
        assert config["services"][service]["mem_limit"] == mib * 1024 * 1024, service
    ports = config["services"]["gateway"]["ports"]
    assert len(ports) == 1 and ports[0]["host_ip"] == "127.0.0.1" and ports[0]["target"] == 8080
    print(
        f"Owner-preview acceptance: {checks} HTTP checks passed; "
        "only gateway loopback is published."
    )
    # Report only task-owned runtime metrics, never configuration or environments.
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            ".env.owner-preview.local",
            "-f",
            "compose.owner-preview.yml",
            "-f",
            "compose.preview-small.yml",
            "stats",
            "--no-stream",
            "--format",
            "json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    rows = [json.loads(line) for line in result.stdout.splitlines() if line]
    assert len(rows) == 4, "Expected the four running preview services"
    for row in rows:
        print(f"Runtime footprint: {row['Name']} | {row['MemUsage']} | CPU {row['CPUPerc']}")


if __name__ == "__main__":
    main()
