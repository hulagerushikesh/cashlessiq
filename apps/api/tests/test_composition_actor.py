"""Actual actor/watcher processes around the eight-role fake-engine adapter.

No Docker, membership DB, TLS listener, secret material or physical acceptance.
"""

import pytest
from composition_actor_fixture import FakeCompositionAttempt
from composition_actor_fixture import implementation as actor
from test_composition_launcher import plan


def test_invalid_actor_policy_preserves_reservations_without_start(tmp_path):
    attempt = FakeCompositionAttempt(plan())
    with pytest.raises(actor.ActorDenied):
        attempt.execute("healthy", tmp_path / "reached", budget_ns=True)
    assert attempt.fenced and attempt.active == 1 and len(attempt.pending) == 8
    assert attempt.task is None and not list(tmp_path.iterdir())


@pytest.mark.parametrize("mode", ["healthy", "partial"])
def test_bounded_case_returns_only_after_model_and_fake_cleanup(tmp_path, mode):
    attempt = FakeCompositionAttempt(plan())
    result = attempt.execute(mode, tmp_path / "reached", budget_ns=5_000_000_000)
    assert result == dict(
        mode=mode,
        state="STOPPED" if mode == "healthy" else "FENCED",
        owned=8 if mode == "healthy" else 1,
        stopped=8 if mode == "healthy" else 1,
        active=0,
        deliveries=1 if mode == "healthy" else 0,
    )
    assert attempt.task.actor_reaped and attempt.task.watcher_reaped and not attempt.task.fenced
    assert attempt.active == 0 and not attempt.pending
    assert attempt.fenced is (mode == "partial")


@pytest.mark.parametrize("mode", ["blocked-create", "blocked-stop", "late"])
def test_watchdog_interrupts_actual_blocked_launcher_callbacks_and_rejects_late_result(
    tmp_path, mode, capsys
):
    # Reserve all exact names outside the actor BEFORE any callback. Process
    # termination never confirms Docker-resource absence; retain these UNKNOWN.
    attempt = FakeCompositionAttempt(plan())
    marker = tmp_path / "reached"
    with pytest.raises(actor.ActorDenied):
        attempt.execute(mode, marker, budget_ns=3_000_000_000)
    assert marker.read_text() == mode  # Callback reached, not an import/startup timeout.
    assert attempt.fenced and attempt.task.fenced and attempt.task.watcher_reaped
    assert attempt.active == 1 and len(attempt.pending) == 8
    assert all(state == "UNKNOWN" for state in attempt.pending.values())
    with pytest.raises(actor.ActorDenied):
        attempt.execute("healthy", tmp_path / "second", budget_ns=3_000_000_000)
    assert capsys.readouterr() == ("", "")
