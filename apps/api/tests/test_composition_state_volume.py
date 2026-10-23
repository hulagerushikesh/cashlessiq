"""State helper host semantics only; no Docker mount or Linux UID claim."""

import importlib.util
import io
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from test_worker_guard_container_fixture import topology_fixture as topology_fixture

from ciq_api.worker_guard_health import VerifiedGuardClaims
from ciq_api.worker_guard_state import GuardStateDenied

PATH = Path(__file__).resolve().parents[2] / "worker/tests/composition_state_volume.py"
SPEC = importlib.util.spec_from_file_location("composition_state_volume", PATH)
helper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helper)


def frame(fixture, role="broker"):
    return json.dumps(dict(version=1, role=role, generation=fixture.GENERATION)).encode()


@pytest.fixture
def volume(topology_fixture, tmp_path):
    root = tmp_path / "volume"
    root.mkdir(mode=0o700)
    return root, topology_fixture


@pytest.mark.parametrize(
    "role",
    [
        "broker",
        "validator-0",
        "validator-1",
        "reader-0-clinical",
        "reader-0-nonclinical",
        "reader-1-clinical",
        "reader-1-nonclinical",
    ],
)
def test_independent_state_probe_retains_spent_replay(volume, role):
    root, fixture = volume
    body = frame(fixture, role)
    assert helper.initialize(root, body, fixture)["state"] == "INITIALIZED"
    owner = os.getuid(), os.getgid()
    assert helper.verify(root, body, fixture, owner=owner)["state"] == "VERIFIED"
    guard, evidence = fixture.load(directory=root)
    claims = VerifiedGuardClaims(
        authority=fixture.authority_for(role),
        assertion_generation=fixture.GENERATION,
        nonce="a" * 64,
        iat=1000,
        exp=1030,
    )
    guard.consume_verified(evidence, claims)
    assert helper.verify(root, body, fixture, owner=owner)["role"] == role
    reopened, evidence = fixture.load(directory=root)
    with pytest.raises(GuardStateDenied):
        reopened.consume_verified(evidence, claims)
    before = {p.name: p.read_bytes() for p in root.iterdir()}
    with pytest.raises(helper.StateVolumeDenied):
        helper.initialize(root, body, fixture)
    assert before == {p.name: p.read_bytes() for p in root.iterdir()}


@pytest.mark.parametrize(
    "damage",
    [
        "missing",
        "corrupt",
        "extra",
        "symlink",
        "hardlink",
        "mode",
        "owner",
        "role",
        "latched",
        "signature",
    ],
)
def test_probe_never_initializes_or_repairs(volume, damage):
    root, fixture = volume
    body = frame(fixture)
    helper.initialize(root, body, fixture)
    state = root / "used.sqlite"
    owner = os.getuid(), os.getgid()
    if damage == "missing":
        state.unlink()
    elif damage == "corrupt":
        state.write_bytes(b"corrupt disposable SQLite")
    elif damage == "extra":
        (root / "unexpected").touch()
    elif damage == "symlink":
        state.rename(root.parent / "original")
        state.symlink_to(root.parent / "original")
    elif damage == "hardlink":
        os.link(state, root.parent / "linked")
    elif damage == "mode":
        state.chmod(0o644)
    elif damage == "owner":
        owner = owner[0] + 1, owner[1]
    elif damage == "role":
        body = frame(fixture, "validator-0")
    elif damage == "latched":
        guard, evidence = fixture.load(directory=root, unsafe=True)
        with pytest.raises(GuardStateDenied):
            guard.observe(evidence)
    else:
        public = root / "public-guard.json"
        value = json.loads(public.read_text())
        value["evidence"] = "not signed"
        public.chmod(0o600)
        public.write_text(json.dumps(value))
        public.chmod(0o400)
    fixture.initialize = Mock(side_effect=AssertionError("No repair"))
    with pytest.raises(helper.StateVolumeDenied):
        helper.verify(root, body, fixture, owner=owner)
    fixture.initialize.assert_not_called()
    if damage == "missing":
        assert not state.exists()
    if damage == "corrupt":
        assert state.read_bytes() == b"corrupt disposable SQLite"


@pytest.mark.parametrize(
    "body",
    [
        b"",
        b"x" * 4097,
        b"{}",
        b"[]",
        b'{"version":1,"version":1,"role":"broker","generation":"disposable-v3-generation"}',
        b'{"version":true,"role":"broker","generation":"disposable-v3-generation"}',
        b'{"version":1,"role":"reader","generation":"disposable-v3-generation"}',
        b'{"version":1,"role":"membership","generation":"disposable-v3-generation"}',
        b'{"version":1,"role":"broker","generation":"wrong"}',
    ],
)
def test_bad_request_has_no_filesystem_effect(volume, body):
    root, fixture = volume
    fixture.initialize = Mock(side_effect=AssertionError("No initialization"))
    with pytest.raises(helper.StateVolumeDenied):
        helper.initialize(root, body, fixture)
    fixture.initialize.assert_not_called()
    assert not list(root.iterdir())


def test_partial_initialization_is_retained_and_blocks_new_attempt(volume):
    root, fixture = volume
    calls = []

    def partial(*args, **kwargs):
        calls.append(args)
        (root / "used.sqlite").write_bytes(b"partial")
        raise OSError("fictional interruption")

    fixture.initialize = partial
    for _ in range(2):
        with pytest.raises(helper.StateVolumeDenied):
            helper.initialize(root, frame(fixture), fixture)
    assert len(calls) == 1 and (root / "used.sqlite").read_bytes() == b"partial"


@pytest.mark.parametrize("mode,uid", [("initialize", 10001), ("verify", 0), ("reset", 0)])
def test_cli_denies_wrong_mode_or_identity_before_filesystem(
    topology_fixture, monkeypatch, capsys, mode, uid
):
    monkeypatch.setitem(sys.modules, "guard_mtls_fixture", topology_fixture)
    monkeypatch.setattr(sys, "argv", ["state-helper", mode])
    monkeypatch.setattr(os, "geteuid", lambda: uid)
    monkeypatch.setattr(os, "getegid", lambda: uid)
    monkeypatch.setattr(helper, "initialize", Mock(side_effect=AssertionError("No I/O")))
    monkeypatch.setattr(helper, "verify", Mock(side_effect=AssertionError("No I/O")))
    assert helper.main() == 1
    assert capsys.readouterr() == ("", "Disposable state volume denied\n")
    helper.initialize.assert_not_called()
    helper.verify.assert_not_called()


@pytest.mark.parametrize("mode,uid", [("initialize", 0), ("verify", 10001)])
def test_cli_fixed_path_bounded_input_and_redacted_receipt(
    topology_fixture, monkeypatch, capsys, mode, uid
):
    monkeypatch.setitem(sys.modules, "guard_mtls_fixture", topology_fixture)
    monkeypatch.setattr(sys, "argv", ["state-helper", mode])
    monkeypatch.setattr(os, "geteuid", lambda: uid)
    monkeypatch.setattr(os, "getegid", lambda: uid)
    body = frame(topology_fixture)
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(body)))
    result = dict(state=mode.upper(), role="broker", generation=topology_fixture.GENERATION)
    operation = Mock(return_value=result)
    monkeypatch.setattr(helper, mode, operation)
    assert helper.main() == 0
    assert json.loads(capsys.readouterr().out) == result
    args, kwargs = operation.call_args
    assert args == (Path("/var/lib/ciq-replay"), body, topology_fixture)
    assert kwargs == ({} if uid == 0 else {"owner": (10001, 10001)})


def test_state_helper_build_context_excludes_credentials_and_normal_entrypoint():
    base = Path(__file__).resolve().parents[1]
    dockerfile = (base / "Dockerfile.state-test").read_text()
    context = (base / "Dockerfile.state-test.dockerignore").read_text().splitlines()
    assert context == [
        "**",
        "!apps/",
        "!apps/worker/",
        "!apps/worker/tests/",
        "!apps/worker/tests/composition_state_volume.py",
    ]
    assert "ARG CIQ_BROKER_TEST_IMAGE\nFROM ${CIQ_BROKER_TEST_IMAGE}" in dockerfile
    assert "USER 10001:10001" in dockerfile
    assert '"/opt/ciq-composition/composition_state_volume.py"' in dockerfile
    assert "CMD []" in dockerfile
