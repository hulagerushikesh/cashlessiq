"""Actual small disposable processes; no Docker, credentials or user services."""

import sys

import pytest

from scripts.bounded_composition_actor import ActorDenied, BoundedActor


def actor(code, *, budget=2_000_000_000):
    return BoundedActor((sys.executable, "-I", "-c", code), budget_ns=budget, grace_ns=300_000_000)


def test_inactive_constructor_and_one_use_result():
    task = actor('print(\'{"status":"synthetic-only"}\', flush=True)')
    assert not task.used and not task.fenced
    assert task.execute() == {"status": "synthetic-only"}
    assert task.actor_reaped and task.watcher_reaped
    with pytest.raises(ActorDenied):
        task.execute()


@pytest.mark.parametrize(
    "code",
    [
        "import time; time.sleep(30)",
        "import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(30)",
        "import time; print('{\"late\":true}',flush=True); time.sleep(30)",
        'print(\'{"duplicate":1,"duplicate":2}\',flush=True)',
        'print("x"*40000,flush=True)',
        'print(\'{"first":1}\\n{"second":2}\',flush=True)',
        (
            "import time; print('{\"first\":1}',flush=True); time.sleep(.02); "
            "print('{\"second\":2}',flush=True)"
        ),
        "print('{\"invalid\":NaN}',flush=True)",
        "import sys; print('{\"bad_exit\":true}',flush=True); sys.exit(1)",
    ],
)
def test_watchdog_denies_blocked_late_malformed_and_failed_actor(code, capsys):
    task = actor(code, budget=500_000_000)
    with pytest.raises(ActorDenied, match="outcome unknown"):
        task.execute()
    assert task.fenced and task.watcher_reaped
    with pytest.raises(ActorDenied):
        task.execute()
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize(
    "field,value",
    [
        ("budget_ns", True),
        ("budget_ns", 0),
        ("budget_ns", 30_000_000_000),
        ("grace_ns", True),
        ("grace_ns", 0),
        ("command", ["python"]),
        ("command", ("",)),
    ],
)
def test_invalid_policy_never_launches(field, value, monkeypatch):
    from unittest.mock import Mock

    import scripts.bounded_composition_actor as implementation

    launch = Mock()
    monkeypatch.setattr(implementation.subprocess, "Popen", launch)
    options = dict(
        command=(sys.executable, "-I", "-c", "pass"), budget_ns=1_000_000_000, grace_ns=300_000_000
    )
    options[field] = value
    with pytest.raises(ActorDenied):
        BoundedActor(**options)
    launch.assert_not_called()


def test_outer_bound_kills_a_stalled_watcher_itself(tmp_path, monkeypatch):
    import scripts.bounded_composition_actor as implementation

    watcher = tmp_path / "stalled_watcher.py"
    watcher.write_text(
        "import signal,time\nsignal.signal(signal.SIGTERM,signal.SIG_IGN)\ntime.sleep(30)\n"
    )
    monkeypatch.setattr(implementation, "Path", lambda _: watcher)
    task = actor("pass", budget=100_000_000)
    with pytest.raises(ActorDenied):
        task.execute()
    assert task.fenced and task.watcher_reaped and not task.actor_reaped


def test_unknown_sigchld_handler_denies_before_process_creation(monkeypatch):
    from unittest.mock import Mock

    import scripts.bounded_composition_actor as implementation

    task = actor("pass")
    launch = Mock()
    monkeypatch.setattr(implementation.subprocess, "Popen", launch)
    monkeypatch.setattr(implementation.signal, "getsignal", lambda _: implementation.signal.SIG_IGN)
    with pytest.raises(ActorDenied):
        task.execute()
    launch.assert_not_called()


@pytest.mark.parametrize("failure", ["kill", "wait"])
def test_cleanup_uncertainty_denies_without_raw_syscall_error(monkeypatch, failure):
    import subprocess
    from unittest.mock import Mock

    import scripts.bounded_composition_actor as implementation

    task = actor("pass")
    child = Mock(pid=999999)
    child.stdin.closed = False
    monkeypatch.setattr(implementation.subprocess, "Popen", Mock(return_value=child))
    monkeypatch.setattr(implementation, "_write", Mock())
    monkeypatch.setattr(
        implementation,
        "_line",
        Mock(return_value=dict(state="completed", actor_reaped=True, value={"test": "only"})),
    )
    kill = Mock(side_effect=PermissionError("private OS detail") if failure == "kill" else None)
    monkeypatch.setattr(implementation.os, "killpg", kill)
    if failure == "wait":
        child.wait.side_effect = subprocess.TimeoutExpired("test-only", 0.1)
    with pytest.raises(ActorDenied, match="outcome unknown"):
        task.execute()
    assert task.fenced and task.used
    if failure == "kill":
        child.kill.assert_called_once_with()
    else:
        assert not task.watcher_reaped
