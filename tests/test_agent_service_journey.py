"""Offline guards and fresh readiness evidence; no service/DB/host mutations."""

from types import SimpleNamespace

import pytest

from scripts import test_agent_service_journey as runner


def service_fixture(units):
    service = runner.Services(units, SimpleNamespace(check=lambda: None))
    service.delivered.update(service.units)
    return service


@pytest.mark.parametrize("result,passed", [(0, 0), (0, 2), (0, 4), (1, 3), (0, 3)])
def test_acceptance_requires_three_actual_passes_and_success_not_quiet_summary(result, passed):
    if result == 0 and passed == 3:
        runner.acceptance(result, passed)
    else:
        with pytest.raises(RuntimeError, match="private diagnostics withheld"):
            runner.acceptance(result, passed)


@pytest.mark.parametrize("fault", ["journey", "controller", "database"])
def test_journey_opt_in_and_exact_database_precede_host_access(monkeypatch, fault):
    for key, value, bad in (
        ("CIQ_AGENT_SERVICE_JOURNEY_TEST", "1", "journey"),
        ("CIQ_AGENT_CONTROLLER_TEST", "1", "controller"),
        ("TEST_DATABASE_URL", runner.EXPECTED, "database"),
    ):
        monkeypatch.setenv(key, "wrong" if fault == bad else value)
    monkeypatch.setattr(runner.packages, "guard", lambda: pytest.fail("Host was accessed"))
    with pytest.raises(SystemExit, match="exact opted-in disposable database"):
        runner.guard()


@pytest.mark.parametrize("state,empty", [("active", True), ("inactive", False)])
def test_start_refuses_previous_live_invocation(monkeypatch, state, empty):
    service = service_fixture([("claim", "owned")])
    monkeypatch.setattr(runner.policy, "value", lambda *_: state)
    monkeypatch.setattr(runner.quiescence, "verify_stopped", lambda _: None)
    monkeypatch.setattr(runner.policy, "empty", lambda _: empty)
    monkeypatch.setattr(runner.policy, "run", lambda *_: pytest.fail("Service was started"))
    with pytest.raises(RuntimeError, match="not quiescent"):
        service.start("claim")


@pytest.mark.parametrize("invocation", ["", "old", "a" * 32])
def test_start_requires_new_exact_invocation_id(monkeypatch, invocation):
    service = service_fixture([("claim", "owned")])
    service.invocations["claim"] = "a" * 32
    monkeypatch.setattr(runner.policy, "value", lambda _, key: (
        "inactive" if key == "ActiveState" else invocation
    ))
    monkeypatch.setattr(runner.quiescence, "verify_stopped", lambda _: None)
    monkeypatch.setattr(runner.policy, "empty", lambda _: True)
    monkeypatch.setattr(runner.policy, "run", lambda *_: None)
    with pytest.raises(RuntimeError, match="invocation identity"):
        service.start("claim")


@pytest.mark.parametrize("state,records", [
    ("failed", ["fake_receipt_ready"]),  # Old readiness cannot override current exit.
    ("active", ["PRIVATE"]),
    ("active", ["fake_receipt_ready", "fake_receipt_unavailable"]),
])
def test_readiness_denies_dead_or_unexpected_private_output(monkeypatch, capsys, state, records):
    service = service_fixture([("receipt", "owned")])
    service.invocations["receipt"] = "b" * 32
    monkeypatch.setattr(runner.policy, "value", lambda *_: state)
    monkeypatch.setattr(runner.packages, "logs", lambda invocation: records)
    with pytest.raises(RuntimeError) as error:
        service.receipt_ready()
    assert "PRIVATE" not in str(error.value) and capsys.readouterr() == ("", "")


def test_readiness_waits_for_current_invocation_marker_not_type_exec(monkeypatch):
    service = service_fixture([("receipt", "owned")])
    service.invocations["receipt"] = "c" * 32
    monkeypatch.setattr(runner.policy, "value", lambda *_: "active")
    replies = iter([[], ["fake_receipt_ready"]])
    seen = []

    def logs(invocation):
        seen.append(invocation)
        return next(replies)

    def wait(predicate, bound):
        assert bound == 6 and predicate() is False and predicate() is True

    monkeypatch.setattr(runner.packages, "logs", logs)
    monkeypatch.setattr(runner.policy, "wait_for", wait)
    service.receipt_ready()
    assert seen == ["c" * 32, "c" * 32]


@pytest.mark.parametrize("failure", ["stop", "evidence"])
def test_cleanup_checks_all_owned_units_and_preserves_files_on_uncertain_stop(monkeypatch, failure):
    service = service_fixture([("claim", "owned-claim"), ("receipt", "owned-receipt")])
    stopped = []

    def run(*args):
        stopped.append(args[-1])
        if args[-1] == "owned-receipt" and failure == "stop":
            raise RuntimeError("PRIVATE")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(runner.policy, "run", run)
    verified = []

    def verify(unit):
        verified.append(unit)
        if unit == "owned-receipt":
            raise ValueError("PRIVATE")

    monkeypatch.setattr(runner.quiescence, "verify_stopped", verify)
    with pytest.raises(RuntimeError, match="fixtures retained") as error:
        service.stop()
    assert "PRIVATE" not in str(error.value) and stopped == ["owned-receipt", "owned-claim"]
    assert verified == (["owned-claim"] if failure == "stop" else ["owned-receipt", "owned-claim"])
