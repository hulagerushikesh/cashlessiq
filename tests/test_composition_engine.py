"""Actual bounded subprocesses/fake CLI, no Docker connection or daemon mutation."""

import json
import os
import socket
import sys
import tempfile
import time
from pathlib import Path

import pytest

from scripts.bounded_composition_actor import ActorDenied
from scripts.composition_engine import Engine


@pytest.fixture
def rig(tmp_path):
    config = tmp_path / "config"
    config.mkdir(mode=0o700)
    short = tempfile.TemporaryDirectory(prefix="ciq-eng-", dir="/tmp")
    endpoint = Path(short.name) / "engine.sock"
    listener = socket.socket(socket.AF_UNIX)
    listener.bind(str(endpoint))
    binary = tmp_path / "fake-docker"

    def make(code, *, budget=1_000_000_000):
        binary.write_text(f"#!{sys.executable}\n" + code + "\n")
        binary.chmod(0o700)
        return Engine(
            binary=str(binary),
            socket=str(endpoint),
            config=config,
            commands=(("inspect", "owned"), ("start", "owned"), ("stop", "owned")),
            deadline_ns=time.monotonic_ns() + 10_000_000_000,
            budget_ns=budget,
        )

    yield make, config, endpoint
    listener.close()
    short.cleanup()


def test_explicit_endpoint_config_empty_environment_and_inactive_construction(rig, monkeypatch):
    make, config, endpoint = rig
    monkeypatch.setenv("DOCKER_HOST", "tcp://private-unapproved-endpoint")
    engine = make(
        "import json,os,sys; print(json.dumps({'args':sys.argv[1:], 'env':dict(os.environ)}))"
    )
    assert not engine.fenced
    observed = json.loads(engine("inspect", "owned"))
    assert observed["args"] == [
        "--host",
        "unix://" + str(endpoint),
        "--config",
        str(config),
        "inspect",
        "owned",
    ]
    assert "DOCKER_HOST" not in observed["env"]
    assert "HOME" not in observed["env"]


@pytest.mark.parametrize(
    "code",
    [
        "import time; time.sleep(30)",
        "import sys; print('private-detail'); sys.exit(1)",
        "print('x'*40000)",
        "import os; os.write(1,b'\\xff')",
        "import time; print('printed-but-not-complete',flush=True); time.sleep(30)",
        "print('\\x01'*15000)",
    ],
)
def test_blocked_failed_overflow_and_malformed_cli_latch_admission(rig, code, capsys):
    make, _, _ = rig
    engine = make(code, budget=500_000_000)
    started = time.monotonic()
    with pytest.raises(ActorDenied, match="outcome unknown"):
        engine("start", "owned")
    assert engine.fenced and time.monotonic() - started < 3
    with pytest.raises(ActorDenied):
        engine("start", "owned")
    assert capsys.readouterr() == ("", "")


def test_latched_channel_allows_only_independent_inspection_and_containment(rig):
    make, _, _ = rig
    engine = make("import sys; sys.exit(1)")
    with pytest.raises(ActorDenied):
        engine("start", "owned")
    # Replace trusted fake executable ONLY in this test; runtime CLI is trusted.
    make("print('confirmed')")
    assert engine("inspect", "owned") == "confirmed\n"
    assert engine("stop", "owned") == "confirmed\n"
    with pytest.raises(ActorDenied):
        engine("start", "owned")


@pytest.mark.parametrize(
    "change", ["nonempty", "mode", "symlink", "not-socket", "expired", "unlisted"]
)
def test_preflight_denies_before_cli_exec(rig, tmp_path, change):
    make, config, endpoint = rig
    marker = tmp_path / "executed"
    engine = make(f"from pathlib import Path; Path({str(marker)!r}).touch()")
    args = ("inspect", "owned")
    if change == "nonempty":
        (config / "config.json").write_text("{}")
    elif change == "mode":
        config.chmod(0o755)
    elif change == "symlink":
        config.rename(tmp_path / "retained")
        config.symlink_to(tmp_path / "retained", target_is_directory=True)
    elif change == "not-socket":
        endpoint.unlink()
        endpoint.touch()
    elif change == "expired":
        engine.deadline_ns = time.monotonic_ns()
    else:
        args = ("inspect", "foreign")
    with pytest.raises(ActorDenied):
        engine(*args)
    assert engine.fenced and not marker.exists()


@pytest.mark.parametrize(
    "command", [("exec", "owned"), ("system", "prune"), ("rm", "owned"), ("pull", "image")]
)
def test_out_of_scope_operations_rejected_at_construction(rig, command):
    make, _, _ = rig
    engine = make("pass")
    with pytest.raises(ActorDenied):
        Engine(
            binary=engine.binary,
            socket=engine.socket,
            config=engine.config,
            commands=(command,),
            deadline_ns=engine.deadline_ns,
        )


def test_command_limit_and_bools_rejected(rig):
    make, _, _ = rig
    engine = make("pass")
    with pytest.raises(ActorDenied):
        Engine(
            binary=engine.binary,
            socket=engine.socket,
            config=engine.config,
            commands=(("inspect", "owned"),),
            deadline_ns=True,
        )
    assert os.path.isabs(engine.binary)


def test_dynamic_container_ids_require_registration_in_exact_declared_slots(rig):
    make, _, _ = rig
    base = make("print('bounded')")
    engine = Engine(
        binary=base.binary,
        socket=base.socket,
        config=base.config,
        commands=(("inspect", "{incarnation}"), ("start", "{incarnation}")),
        deadline_ns=base.deadline_ns,
    )
    cid = "a" * 64
    engine.permit_incarnation(cid)
    assert engine("inspect", cid) == "bounded\n"
    with pytest.raises(ActorDenied):
        engine("inspect", "b" * 64)
    assert engine.fenced
    # Registration cannot reset a fenced admission channel.
    engine.permit_incarnation("b" * 64)
    with pytest.raises(ActorDenied):
        engine("start", cid)
    assert engine("inspect", cid) == "bounded\n"


@pytest.mark.parametrize("cid", ["a" * 12, "sha256:" + "a" * 64, "foreign", True])
def test_invalid_dynamic_registration_fences_without_io(rig, cid):
    make, _, _ = rig
    engine = make("pass")
    with pytest.raises(ActorDenied):
        engine.permit_incarnation(cid)
    assert engine.fenced
