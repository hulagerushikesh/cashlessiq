"""Disposable real SQLite state + staged test material; no Docker/source I/O."""

import json
import os
from unittest.mock import Mock

import pytest
from composition_state_fixture import States, StatesDenied
from test_composition_launcher import FakeDocker, Launcher
from test_composition_material import materials as materials
from test_worker_guard_container_fixture import topology_fixture as topology_fixture
from test_worker_guard_mtls import assertion_key as assertion_key
from test_worker_transport import pki as pki

from ciq_api.worker_guard_health import VerifiedGuardClaims
from ciq_api.worker_guard_state import GuardStateDenied


@pytest.fixture
def prepared(materials, topology_fixture, tmp_path):
    plan, staged = materials
    root = tmp_path / "states"
    root.mkdir(mode=0o700)
    states = States(plan, root, topology_fixture)
    assert states.initialize()
    return states, staged


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_all_seven_states_match_material_and_preserve_replay_after_reload(prepared):
    states, staged = prepared
    assert states.verify(staged)
    assert len(list(states.root.iterdir())) == 7
    for role in states.roles:
        guard, evidence = states.fixture.load(directory=states.path(role))
        claims = VerifiedGuardClaims(
            authority=states.fixture.authority_for(role),
            assertion_generation=states.plan.generation,
            nonce="a" * 64,
            iat=1000,
            exp=1030,
        )
        guard.consume_verified(evidence, claims)
        assert states.verify(staged)
        reopened, evidence = states.fixture.load(directory=states.path(role))
        with pytest.raises(GuardStateDenied):
            reopened.consume_verified(evidence, claims)
    before = snapshot(states.root)
    with pytest.raises(StatesDenied):
        states.initialize()
    assert snapshot(states.root) == before
    # A new owner-side object does not grant permission to initialize over state.
    other = States(states.plan, states.root, states.fixture)
    with pytest.raises(StatesDenied):
        other.initialize()
    assert snapshot(states.root) == before


@pytest.mark.parametrize(
    "damage",
    [
        "missing",
        "corrupt",
        "extra",
        "symlink",
        "hardlink",
        "mode",
        "generation",
        "swapped",
        "latched",
        "material",
        "membership-state",
    ],
)
def test_state_gate_denies_without_reinitializing_or_repairing(prepared, damage):
    states, staged = prepared
    directory = states.path("broker")
    state, public = directory / "used.sqlite", directory / "public-guard.json"
    if damage == "missing":
        state.unlink()
    elif damage == "corrupt":
        state.write_bytes(b"fictional damaged sqlite")
    elif damage == "extra":
        (directory / "unexpected").touch()
    elif damage == "symlink":
        state.rename(directory / "original")
        state.symlink_to(directory / "original")
    elif damage == "hardlink":
        os.link(state, states.root.parent / "linked-state")
    elif damage == "mode":
        state.chmod(0o644)
    elif damage == "generation":
        raw = json.loads(public.read_text())
        raw["config"]["assertion_generation"] = "wrong-generation"
        public.chmod(0o600)
        public.write_text(json.dumps(raw))
        public.chmod(0o400)
    elif damage == "swapped":
        other = states.path("validator-0")
        temp = states.root / "temporary"
        directory.rename(temp)
        other.rename(directory)
        temp.rename(other)
    elif damage == "latched":
        guard, evidence = states.fixture.load(directory=directory, unsafe=True)
        with pytest.raises(GuardStateDenied):
            guard.observe(evidence)
    elif damage == "material":
        (staged["broker"].root / "unexpected").touch(mode=0o400)
    else:
        (states.root / "membership-state").mkdir(mode=0o700)
    before = snapshot(states.root)
    initializer = states.fixture.initialize
    states.fixture.initialize = Mock(side_effect=AssertionError("No repair"))
    try:
        with pytest.raises(StatesDenied):
            states.verify(staged)
        states.fixture.initialize.assert_not_called()
        assert snapshot(states.root) == before
    finally:
        states.fixture.initialize = initializer


def test_partial_initialization_retains_files_and_denies_retry(
    materials, topology_fixture, tmp_path
):
    plan, _ = materials
    root = tmp_path / "partial"
    root.mkdir(mode=0o700)
    states = States(plan, root, topology_fixture)
    original = topology_fixture.initialize
    calls = []

    def fail(role, **kwargs):
        calls.append(role)
        if len(calls) == 2:
            raise RuntimeError("fictional failure")
        return original(role, **kwargs)

    topology_fixture.initialize = fail
    with pytest.raises(StatesDenied):
        states.initialize()
    before = snapshot(root)
    assert before and len(calls) == 2
    with pytest.raises(StatesDenied):
        states.initialize()
    assert snapshot(root) == before and len(calls) == 2


def test_seven_state_gate_is_required_by_launcher_preflight(prepared):
    states, staged = prepared
    engine = FakeDocker(states.plan)

    def check(role, descriptor):
        return descriptor == states.plan.descriptor(role) and states.verify(staged)

    launcher = Launcher(
        states.plan,
        engine=engine,
        material_check=check,
        auxiliaries={"db": "d" * 64, "controller": "e" * 64},
    )
    assert launcher.verify(launcher.services)
    (states.path("validator-1") / "used.sqlite").unlink()
    assert not launcher.verify(launcher.services)
    assert not any(call[0] in {"create", "start"} for call in engine.calls)
