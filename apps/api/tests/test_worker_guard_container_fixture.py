"""Frozen-time disposable topology helper; no Docker, auth or source connection."""

import importlib.util
import json
from hashlib import sha256
from pathlib import Path

import pytest

from ciq_api.offline_supervisor import ROLES
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


@pytest.mark.parametrize("role", sorted(ROLES - {"membership"}))
def test_all_supervisor_authorities_have_independent_retained_state(
    topology_fixture, tmp_path, role
):
    f = topology_fixture
    assert set(f.SERVICE_BINDINGS) == ROLES - {"membership"}
    directory = tmp_path / role
    directory.mkdir()
    generation = "disposable-composition-1"
    f.initialize(role, directory=directory, generation=generation)
    guard, evidence = f.load(directory=directory)
    if role == "broker":
        expected = "broker"
    else:
        pieces = role.split("-")
        index = int(pieces[1])
        audience = f"validator:{index}"
        if pieces[0] == "reader":
            disclosure = "medical" if pieces[2] == "clinical" else "nonclinical"
            audience = f"reader:{index}:{disclosure}"
        expected = sha256(
            f"{ISSUER}\0{audience}\0{SOURCE_TENANTS[index].tenant_id}".encode()
        ).hexdigest()
    assert guard._config.authority == expected
    assert guard._config.assertion_generation == generation
    assert (directory.stat().st_mode & 0o777) == 0o700
    assert ((directory / "used.sqlite").stat().st_mode & 0o777) == 0o600
    public = directory / "public-guard.json"
    assert (public.stat().st_mode & 0o777) == 0o400
    assert set(json.loads(public.read_text())) == {"public", "config", "evidence"}
    assert "PRIVATE KEY" not in public.read_text()
    claims = VerifiedGuardClaims(
        authority=expected, assertion_generation=generation, nonce="b" * 64, iat=1000, exp=1030
    )
    guard.consume_verified(evidence, claims)
    reopened, evidence = f.load(directory=directory)
    with pytest.raises(GuardStateDenied):
        reopened.consume_verified(evidence, claims)
    before = {p.name: p.read_bytes() for p in directory.iterdir()}
    with pytest.raises(FileExistsError):
        f.initialize(role, directory=directory, generation="disposable-composition-2")
    assert before == {p.name: p.read_bytes() for p in directory.iterdir()}


@pytest.mark.parametrize("damage", ["missing", "corrupt", "public-only"])
def test_composition_state_is_not_repaired(topology_fixture, tmp_path, damage):
    f = topology_fixture
    directory = tmp_path / "broker-state"
    directory.mkdir()
    f.initialize("broker", directory=directory)
    state = directory / "used.sqlite"
    if damage in {"missing", "public-only"}:
        state.unlink()
    else:
        state.write_bytes(b"disposable broken SQLite")
    before = {p.name: p.read_bytes() for p in directory.iterdir()}
    if damage == "public-only":
        with pytest.raises(FileExistsError):
            f.initialize("broker", directory=directory)
    else:
        guard, evidence = f.load(directory=directory)
        with pytest.raises(GuardStateDenied):
            guard.observe(evidence)
    assert before == {p.name: p.read_bytes() for p in directory.iterdir()}


@pytest.mark.parametrize(
    "role", ["membership", "reader-2-clinical", "reader-0-medical", "validator-2", "", None, []]
)
def test_unknown_composition_role_refuses_before_writes(topology_fixture, tmp_path, role):
    with pytest.raises(ValueError, match="Unknown disposable authority role"):
        topology_fixture.initialize(role, directory=tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_composition_authority_names_are_unique(topology_fixture):
    f = topology_fixture
    assert len({f.authority_for(role) for role in f.SERVICE_BINDINGS}) == 7


def test_one_service_cannot_consume_another_services_claim(topology_fixture, tmp_path):
    f = topology_fixture
    roles = sorted(ROLES - {"membership"})
    for role in roles:
        directory = tmp_path / role
        directory.mkdir()
        f.initialize(role, directory=directory)
    for role in roles:
        guard, evidence = f.load(directory=tmp_path / role)
        for other in set(roles) - {role}:
            claims = VerifiedGuardClaims(
                authority=f.authority_for(other),
                assertion_generation=f.GENERATION,
                nonce="c" * 64,
                iat=1000,
                exp=1030,
            )
            with pytest.raises(GuardStateDenied):
                guard.consume_verified(evidence, claims)
        # Foreign claims do not spend this service's nonce or latch its state.
        claims = claims.model_copy(update={"authority": f.authority_for(role)})
        guard.consume_verified(evidence, claims)
