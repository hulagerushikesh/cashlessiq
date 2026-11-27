"""Offline launch-order/fencing controls. These do not prove host containment."""

from dataclasses import replace

import pytest

from ciq_api import agent_single_call_supervisor as supervisor


class Host:
    def __init__(self):
        self.calls, self.live, self.observations = [], set(), {}
        self.allowed = self.clean = True
        self.fault = None

    def check(self):
        return self.allowed

    def quiescent(self, role):
        self.calls.append(("quiet", role))
        return role not in self.live

    def start(self, role):
        self.calls.append(("start", role))
        self.live.add(role)
        incarnation = str(supervisor.ROLES.index(role) + 1) * 32
        self.observations[role] = supervisor.Observation(
            incarnation, True, None, supervisor.READY[role], b"",
        )
        if self.fault == role:
            raise RuntimeError("PRIVATE start ACK lost")
        return incarnation

    def observe(self, role):
        self.calls.append(("observe", role))
        current = self.observations[role]
        if "custody" in self.live:
            return replace(current, running=False, exit_code=0)
        return current

    def stop(self, role):
        self.calls.append(("stop", role))
        self.live.discard(role)
        return self.clean


@pytest.fixture
def setup(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(supervisor, "monotonic", lambda: now[0])
    monkeypatch.setattr(supervisor, "time", lambda: now[0] + 1000)
    monkeypatch.setattr(supervisor, "sleep", lambda seconds: now.__setitem__(0, now[0] + seconds))
    host = Host()
    return host, supervisor.SingleCallSupervisor(host), now


def test_original_peer_readiness_before_custody_and_all_exits_before_delivery(setup):
    host, launch, _ = setup
    assert launch.run() == supervisor.SupervisionResult("published", True)
    assert [r for command, r in host.calls if command == "start"] == list(supervisor.ROLES)
    assert [r for command, r in host.calls if command == "stop"] == list(reversed(supervisor.ROLES))
    assert not host.live
    before = host.calls.copy()
    with pytest.raises(ValueError, match=supervisor.ERROR):
        launch.run()
    assert host.calls == before


@pytest.mark.parametrize("role", supervisor.ROLES)
def test_partial_start_ack_failure_stops_possibly_allocated_role_without_retry(setup, role):
    host, launch, _ = setup
    host.fault = role
    assert launch.run().outcome == "unavailable"
    started = [r for command, r in host.calls if command == "start"]
    assert started == list(supervisor.ROLES[:supervisor.ROLES.index(role) + 1])
    assert [r for command, r in host.calls if command == "stop"] == list(reversed(started))
    assert not host.live


@pytest.mark.parametrize("role", supervisor.ROLES)
def test_existing_service_is_never_adopted_or_stopped(setup, role):
    host, launch, _ = setup
    host.live.add(role)
    assert launch.run() == supervisor.SupervisionResult("unavailable", True)
    assert not any(c in ("start", "stop") for c, _ in host.calls)
    assert host.live == {role}


@pytest.mark.parametrize("fault", [
    "wrong-incarnation", "extra-output", "stderr", "too-large", "failure", "missing-marker",
    "boolean-exit", "wrong-running", "running-with-code", "wrong-type",
])
def test_untrusted_or_failed_invocation_observation_denies_publication(setup, fault):
    host, launch, _ = setup
    original = host.observe

    def observe(role):
        current = original(role)
        if role != "custody":
            return current
        changes = {
            "wrong-incarnation": {"incarnation": "f" * 32},
            "extra-output": {"stdout": b"PRIVATE payload"},
            "stderr": {"stderr": b"PRIVATE diagnostic"},
            "too-large": {"stdout": b"x" * 129},
            "failure": {"exit_code": 1},
            "missing-marker": {"stdout": b""},
            "boolean-exit": {"exit_code": False},
            "wrong-running": {"running": 0},
            "running-with-code": {"running": True, "exit_code": 0},
        }
        return {} if fault == "wrong-type" else replace(current, **changes[fault])

    host.observe = observe
    result = launch.run()
    assert result == supervisor.SupervisionResult("unavailable", True)
    assert "PRIVATE" not in repr(result) and not host.live


@pytest.mark.parametrize("phase", ["receipt", "provider"])
def test_readiness_timeout_never_starts_custody(setup, phase):
    host, launch, now = setup
    original = host.observe

    def observe(role):
        value = original(role)
        return replace(value, stdout=b"") if role == phase else value

    host.observe = observe
    assert launch.run().outcome == "unavailable"
    assert ("start", "custody") not in host.calls and not host.live
    assert 3 <= now[0] - 100 < 3.1


@pytest.mark.parametrize("fault", ["exit", "lost-marker", "revoked"])
def test_earlier_peer_loss_or_consent_revocation_fences_later_launch(setup, fault):
    host, launch, _ = setup
    original = host.observe

    def observe(role):
        value = original(role)
        if role == "receipt" and "provider" in host.live:
            if fault == "revoked":
                host.allowed = False
            return replace(value, **({"running": False, "exit_code": 0} if fault == "exit"
                                    else {"stdout": b""} if fault == "lost-marker" else {}))
        return value

    host.observe = observe
    assert launch.run().outcome == "unavailable"
    assert ("start", "custody") not in host.calls and not host.live


@pytest.mark.parametrize("fault", ["backwards", "wall-backwards", "wall-drift", "gap", "nan"])
def test_clock_fault_after_launch_still_cleans_every_owned_role(setup, monkeypatch, fault):
    host, launch, now = setup
    original = host.observe

    def observe(role):
        value = original(role)
        if role == "custody":
            if fault == "wall-backwards":
                monkeypatch.setattr(supervisor, "time", lambda: 1000.0)
            elif fault == "wall-drift":
                monkeypatch.setattr(supervisor, "time", lambda: 1101.1)
            else:
                now[0] = {"backwards": 99.0, "gap": 102.1, "nan": float("nan")}[fault]
        return value

    host.observe = observe
    assert launch.run().outcome == "unavailable"
    assert [r for command, r in host.calls if command == "stop"] == list(reversed(supervisor.ROLES))
    assert not host.live


@pytest.mark.parametrize("fault", ["false", "exception", "still-live", "interrupt"])
def test_unconfirmed_stop_quarantines_and_attempts_other_owned_stops(setup, fault):
    host, launch, _ = setup
    original = host.stop

    def stop(role):
        result = original(role)
        if role == "custody":
            if fault == "exception":
                raise RuntimeError("PRIVATE cleanup failure")
            if fault == "interrupt":
                raise KeyboardInterrupt
            if fault == "still-live":
                host.live.add(role)
            return False if fault == "false" else result
        return result

    host.stop = stop
    assert launch.run() == supervisor.SupervisionResult("quarantined", False)
    assert [r for command, r in host.calls if command == "stop"] == list(reversed(supervisor.ROLES))


def test_cancellation_preserved_after_all_owned_cleanup(setup):
    host, launch, _ = setup
    original = host.observe

    def observe(role):
        if role == "custody":
            raise KeyboardInterrupt
        return original(role)

    host.observe = observe
    with pytest.raises(KeyboardInterrupt):
        launch.run()
    assert not host.live and len([c for c in host.calls if c[0] == "stop"]) == 3


@pytest.mark.parametrize("fault", ["false", "boolean-impostor", "exception"])
def test_preflight_failure_consumes_entry_without_any_start(setup, fault):
    host, launch, _ = setup

    def check():
        if fault == "exception":
            raise ValueError("PRIVATE preflight details")
        return 1 if fault == "boolean-impostor" else False

    host.check = check
    assert launch.run() == supervisor.SupervisionResult("unavailable", True)
    assert not host.calls
    with pytest.raises(ValueError, match=supervisor.ERROR):
        launch.run()


@pytest.mark.parametrize("identifier", [None, "", "f" * 31, "F" * 32, 123, "1" * 32])
def test_bad_or_reused_process_identity_cleans_even_an_unacknowledged_start(setup, identifier):
    host, launch, _ = setup
    original = host.start

    def start(role):
        actual = original(role)
        return identifier if role == "provider" else actual

    host.start = start
    assert launch.run().outcome == "unavailable"
    assert ("start", "custody") not in host.calls and not host.live


def test_success_marker_is_not_delivery_until_all_original_processes_exit(setup):
    host, launch, now = setup
    original = host.observe

    def observe(role):
        value = original(role)
        return replace(value, running=True, exit_code=None) if role == "provider" else value

    host.observe = observe
    assert launch.run() == supervisor.SupervisionResult("unavailable", True)
    assert 30 <= now[0] - 100 < 30.1 and not host.live


def test_acknowledged_ready_output_cannot_disappear_after_custody_launch(setup):
    host, launch, _ = setup
    original = host.observe

    def observe(role):
        value = original(role)
        if role == "receipt" and "custody" in host.live:
            return replace(value, running=True, exit_code=None, stdout=b"")
        return value

    host.observe = observe
    assert launch.run().outcome == "unavailable"
    assert not host.live
