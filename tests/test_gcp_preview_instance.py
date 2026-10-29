"""VM billing safeguards use fictional Compute responses, never a live cloud VM."""

import copy
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import check_gcp_preview_instance as checker

FIXTURE = Path(__file__).parent / "fixtures/gcp-preview/running.json"


@pytest.fixture
def snapshot():
    return json.loads(FIXTURE.read_text())


def stopped(snapshot):
    result = copy.deepcopy(snapshot)
    result["instance"]["status"] = "TERMINATED"
    result["instance"].pop("terminationTimestamp")
    result["instance"]["networkInterfaces"][0]["accessConfigs"][0].pop("natIP")
    return result


def test_running_reports_stop_deadline_without_printing_ip(snapshot):
    report = checker.verify(snapshot, "running")
    assert report["automatic_stop_deadline"] == "2026-10-29T08:00:00+00:00"
    assert report["external_ipv4_present"] is True
    assert "192.0.2.10" not in json.dumps(report)


def test_stopped_accepts_only_terminated_without_external_ip(snapshot):
    report = checker.verify(stopped(snapshot), "stopped")
    assert report["state"] == "TERMINATED"
    assert report["external_ipv4_present"] is False
    with pytest.raises(ValueError, match="TERMINATED"):
        checker.verify(snapshot, "stopped")


def test_integer_duration_and_omitted_stopped_access_configs_are_valid(snapshot):
    snapshot = stopped(snapshot)
    snapshot["instance"]["scheduling"]["maxRunDuration"] = {"seconds": 14400}
    snapshot["instance"]["networkInterfaces"][0].pop("accessConfigs")
    assert checker.verify(snapshot, "stopped")["external_ipv4_present"] is False


@pytest.mark.parametrize("state", ["STOPPING", "SUSPENDED", "PROVISIONING", "STAGING"])
def test_transitional_and_suspended_states_are_not_a_stop_receipt(snapshot, state):
    snapshot = stopped(snapshot)
    snapshot["instance"]["status"] = state
    with pytest.raises(ValueError, match="TERMINATED"):
        checker.verify(snapshot, "stopped")


@pytest.mark.parametrize("field", ["selfLink", "zone", "machineType"])
def test_never_accepts_same_named_resources_from_another_project(snapshot, field):
    snapshot["instance"][field] = snapshot["instance"][field].replace(
        "cashlessiq-dev-rush", "atlas-rag-rush"
    )
    with pytest.raises(ValueError):
        checker.verify(snapshot, "running")


@pytest.mark.parametrize(
    "change",
    [
        {"maxRunDuration": {"seconds": "28800"}},
        {"maxRunDuration": {"seconds": "14400", "nanos": 1}},
        {"maxRunDuration": {}},
        {"instanceTerminationAction": "DELETE"},
        {"terminationTime": "2026-10-30T08:00:00Z"},
    ],
)
def test_missing_or_changed_backstop_is_rejected(snapshot, change):
    snapshot["instance"]["scheduling"].update(change)
    with pytest.raises((ValueError, KeyError)):
        checker.verify(snapshot, "running")


@pytest.mark.parametrize(
    "deadline", [None, "2026-10-29T04:30:00Z", "2026-10-29T12:00:00Z", "2026-10-29T08:00:00"]
)
def test_missing_expired_long_or_timezone_free_deadline_fails(snapshot, deadline):
    snapshot["instance"]["terminationTimestamp"] = deadline
    with pytest.raises(ValueError):
        checker.verify(snapshot, "running")


@pytest.mark.parametrize("state", ["running", "stopped"])
def test_reserved_even_unattached_external_address_rejected(snapshot, state):
    if state == "stopped":
        snapshot = stopped(snapshot)
    snapshot["addresses"] = [{"addressType": "EXTERNAL"}]
    with pytest.raises(ValueError, match="reserved"):
        checker.verify(snapshot, state)


def test_stopped_rejects_retained_ip_and_active_deadline(snapshot):
    bad = stopped(snapshot)
    bad["instance"]["networkInterfaces"][0]["accessConfigs"][0]["natIP"] = "192.0.2.10"
    with pytest.raises(ValueError, match="still reports an external"):
        checker.verify(bad, "stopped")
    bad = stopped(snapshot)
    bad["instance"]["terminationTimestamp"] = "2026-10-29T08:00:00Z"
    with pytest.raises(ValueError, match="active termination"):
        checker.verify(bad, "stopped")


@pytest.mark.parametrize("change", ["network", "subnetwork", "ipv6", "policy", "size"])
def test_unreviewed_size_network_or_restart_policy_rejected(snapshot, change):
    instance = snapshot["instance"]
    interface = instance["networkInterfaces"][0]
    if change in {"network", "subnetwork"}:
        interface[change] = interface[change].replace("cashlessiq-dev-rush", "other-project")
    elif change == "ipv6":
        interface["stackType"] = "IPV4_IPV6"
    elif change == "policy":
        instance["resourcePolicies"] = ["unreviewed-schedule"]
    else:
        instance["machineType"] = instance["machineType"].replace("e2-small", "e2-standard-8")
    with pytest.raises(ValueError):
        checker.verify(snapshot, "running")


def test_live_reader_only_describes_and_lists_in_fixed_project(snapshot, monkeypatch):
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        assert kwargs["env"]["CLOUDSDK_CORE_DISABLE_PROMPTS"] == "1"
        assert kwargs["timeout"] == 30
        result = snapshot["instance"] if "describe" in command else []
        return SimpleNamespace(stdout=json.dumps(result))

    monkeypatch.setattr(checker.subprocess, "run", run)
    checker.live_snapshot()
    assert len(commands) == 2
    assert commands[0][:5] == ["gcloud", "--quiet", "compute", "instances", "describe"]
    assert commands[1][:5] == ["gcloud", "--quiet", "compute", "addresses", "list"]
    assert all("--project=cashlessiq-dev-rush" in command for command in commands)
    assert "metadata" not in " ".join(commands[0])
    assert not any(word in {"start", "stop"} for c in commands for word in c)


def test_permission_error_does_not_attempt_to_enable_or_create(snapshot, monkeypatch):
    calls = []

    def fail(command, **kwargs):
        calls.append(command)
        raise subprocess.CalledProcessError(1, command, stderr="private cloud diagnostic")

    monkeypatch.setattr(checker.subprocess, "run", fail)
    monkeypatch.setattr(sys, "argv", ["check", "--expect", "running", "--live"])
    with pytest.raises(SystemExit) as result:
        checker.main()
    assert result.value.code == 1
    assert len(calls) == 1


def test_offline_cli_is_explicitly_historical_and_does_not_call_cloud(monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        pytest.fail("Offline snapshot tried to contact GCP")

    monkeypatch.setattr(checker.subprocess, "run", forbidden)
    monkeypatch.setattr(sys, "argv", ["check", "--expect", "running", "--snapshot", str(FIXTURE)])
    checker.main()
    output = capsys.readouterr().out
    assert "historical_snapshot_only" in output
    assert "Disk/image charges and daily runtime remain separate" in output


def test_cli_explains_failed_state_without_dumping_snapshot(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["check", "--expect", "stopped", "--snapshot", str(FIXTURE)])
    with pytest.raises(SystemExit) as result:
        checker.main()
    assert result.value.code == 1
    output = capsys.readouterr().err
    assert "Expected TERMINATED" in output
    assert "192.0.2.10" not in output
