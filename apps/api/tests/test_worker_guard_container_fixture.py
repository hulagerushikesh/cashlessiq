"""Frozen-time disposable topology helper; no Docker, auth or source connection."""

import importlib.util
import json
from hashlib import sha256
from pathlib import Path

import pytest

from ciq_api.source_alpha import SOURCE_TENANTS
from ciq_api.worker_authority import ISSUER
from ciq_api.worker_guard_health import VerifiedGuardClaims
from ciq_api.worker_guard_state import GuardStateDenied


@pytest.fixture
def topology_fixture(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[2] / "worker/tests/guard_mtls_fixture.py"
    spec = importlib.util.spec_from_file_location("guard_mtls_test_fixture", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "STATE", tmp_path / "used.sqlite")
    monkeypatch.setattr(module, "PUBLIC", tmp_path / "public.json")
    monkeypatch.setattr(module.os, "chown", lambda *_: None)
    return module


@pytest.mark.parametrize("role", ["reader", "validator"])
@pytest.mark.parametrize(
    "action", ["consume", "reinitialize", "latch", "missing", "corrupt", "health"]
)
def test_explicit_container_fixture_is_fail_closed(topology_fixture, role, action):
    f = topology_fixture
    f.initialize(role)
    guard, evidence = f.load()
    audience = "reader:0:nonclinical" if role == "reader" else "validator:0"
    namespace = sha256(f"{ISSUER}\0{audience}\0{SOURCE_TENANTS[0].tenant_id}".encode()).hexdigest()
    assert guard._config.authority == namespace
    assert guard._config.assertion_generation == f.GENERATION
    assert set(json.loads(f.PUBLIC.read_text())) == {"public", "config", "evidence"}
    assert "PRIVATE KEY" not in f.PUBLIC.read_text()
    claims = VerifiedGuardClaims(
        authority=namespace, assertion_generation=f.GENERATION, nonce="a" * 64, iat=1000, exp=1030
    )
    assert guard.observe(evidence).permits(claims)
    if action == "consume":
        guard.consume_verified(evidence, claims)
        reopened, evidence = f.load()
        assert reopened.observe(evidence).permits(claims)  # Not an expiry-based denial.
        with pytest.raises(GuardStateDenied):
            reopened.consume_verified(evidence, claims)
        assert len(reopened.inspect()[1]) == 1
    elif action == "reinitialize":
        before = f.STATE.read_bytes(), f.PUBLIC.read_bytes()
        with pytest.raises(FileExistsError):
            f.initialize(role)
        assert before == (f.STATE.read_bytes(), f.PUBLIC.read_bytes())
    else:
        if action == "missing":
            f.STATE.unlink()
        elif action == "corrupt":
            f.STATE.write_bytes(b"disposable corruption")
        elif action == "latch":
            guard, evidence = f.load(unsafe=True)
        else:

            def evidence():
                return "invalid signed health"

        with pytest.raises(GuardStateDenied):
            guard.observe(evidence)
        if action == "missing":
            assert not f.STATE.exists()
        elif action == "corrupt":
            assert f.STATE.read_bytes() == b"disposable corruption"
        else:
            reopened, evidence = f.load()
            with pytest.raises(GuardStateDenied):
                reopened.observe(evidence)
