"""Local engineering checks must not strand a product stack."""

import subprocess

import pytest

from scripts import product


def test_headroom_failure_never_reaches_docker(monkeypatch):
    monkeypatch.setattr(product.sys, "platform", "darwin")

    def unavailable():
        raise RuntimeError("insufficient headroom")

    def unexpected(*args, **kwargs):
        pytest.fail("Docker must not run when Mac headroom is insufficient")

    monkeypatch.setattr("scripts.check_product_host.require_headroom", unavailable)
    monkeypatch.setattr(product, "run", unexpected)
    with pytest.raises(RuntimeError, match="headroom"):
        product.start(("docker", "compose"))


@pytest.mark.parametrize("failed_stage", ["start", "api", "browser"])
def test_session_stops_owned_stack_on_failure(monkeypatch, failed_stage):
    calls = []
    monkeypatch.setattr(product, "require_local_headroom", lambda: None)

    def start(compose, *, timeout=None):
        calls.append(("start", timeout))
        if failed_stage == "start":
            raise subprocess.CalledProcessError(1, "docker compose up")

    def run(*command, env=None, timeout=None):
        stage = "api" if command[0] == "uv" else "browser"
        calls.append((stage, timeout))
        if failed_stage == stage:
            raise subprocess.TimeoutExpired(stage, timeout)

    def stop(compose):
        calls.append(("stop", None))

    monkeypatch.setattr(product, "start", start)
    monkeypatch.setattr(product, "run", run)
    monkeypatch.setattr(product, "stop", stop)
    with pytest.raises((subprocess.CalledProcessError, subprocess.TimeoutExpired)):
        product.test_session(("docker", "compose"), {"CIQ_DB_PASSWORD": "disposable"})
    assert calls[-1] == ("stop", None)
    assert calls[0] == ("start", 600)


def test_session_stops_after_success(monkeypatch):
    calls = []
    monkeypatch.setattr(product, "require_local_headroom", lambda: None)
    monkeypatch.setattr(product, "start", lambda *args, **kwargs: calls.append("start"))
    monkeypatch.setattr(product, "run", lambda *args, **kwargs: calls.append(args[0]))
    monkeypatch.setattr(product, "stop", lambda *args: calls.append("stop"))
    product.test_session(("docker", "compose"), {"CIQ_DB_PASSWORD": "disposable"})
    assert calls == ["start", "uv", "npm", "stop"]
