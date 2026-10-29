"""Daily preview accounting uses fictional snapshots and never starts Docker/GCP."""

import copy
import json
import stat
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from scripts import gcp_preview_usage as usage

FIXTURE = Path(__file__).parent / "fixtures/gcp-preview/running.json"
HISTORICAL = "historical_snapshot_only"


def snapshot(start="2026-10-31T04:00:00Z", observed="2026-10-31T05:00:00Z", *, stopped=False):
    value = json.loads(FIXTURE.read_text())
    value["observed_at"] = observed
    vm = value["instance"]
    vm["lastStartTimestamp"] = start
    vm["resourceStatus"]["scheduling"]["terminationTimestamp"] = (
        usage.instant(start) + timedelta(hours=4)
    ).isoformat()
    if stopped:
        vm["status"] = "TERMINATED"
        vm.pop("resourceStatus")
        vm["networkInterfaces"][0]["accessConfigs"][0].pop("natIP")
    return value


def record(ledger=None, *, stopped=False, **times):
    return usage.observe(
        ledger, snapshot(stopped=stopped, **times), "stopped" if stopped else "running", HISTORICAL
    )


def report(ledger, at="2026-10-31T05:00:00Z"):
    return usage.report(ledger, usage.instant(at))


def test_first_session_and_repeat_reads_do_not_reset_or_double_count():
    ledger = record()
    ledger = record(ledger, observed="2026-10-31T05:30:00Z")
    result = report(ledger, "2026-10-31T05:30:00Z")
    assert len(ledger["sessions"]) == 1
    assert result["accounted_today_seconds"] == 5400
    assert result["remaining_today_seconds"] == 9000
    assert usage.instant(result["stop_by"]) == usage.instant("2026-10-31T08:00:00Z")
    assert not result["stop_now"]


def test_restart_gets_only_the_unused_daily_allowance():
    ledger = record()
    ledger = record(ledger, stopped=True, observed="2026-10-31T06:00:00Z")
    # A later stopped observation does not charge time already known to be stopped.
    ledger = record(ledger, stopped=True, observed="2026-10-31T06:30:00Z")
    ledger = record(ledger, start="2026-10-31T07:00:00Z", observed="2026-10-31T07:30:00Z")
    result = report(ledger, "2026-10-31T07:30:00Z")
    assert result["accounted_today_seconds"] == 9000
    assert result["remaining_today_seconds"] == 5400
    assert usage.instant(result["stop_by"]) == usage.instant("2026-10-31T09:00:00Z")
    assert usage.instant(ledger["sessions"][-1]["automatic_stop_deadline"]) == usage.instant(
        "2026-10-31T11:00:00Z"
    )


def test_open_session_keeps_counting_after_assumed_automatic_stop():
    result = report(record(), "2026-10-31T09:00:00Z")
    assert result["accounted_today_seconds"] == 18000
    assert result["remaining_today_seconds"] == 0
    assert result["stop_now"]
    assert result["session_open"]


def test_stop_receipt_closes_conservatively_at_observation_not_an_assumed_deadline():
    ledger = record(record(), stopped=True, observed="2026-10-31T08:15:00Z")
    result = report(ledger, "2026-10-31T09:00:00Z")
    assert result["accounted_today_seconds"] == 15300
    assert not result["session_open"]
    assert result["stop_by"] is None


def test_india_midnight_splits_usage_and_does_not_erase_prior_day():
    ledger = record(start="2026-10-31T17:30:00Z", observed="2026-10-31T18:00:00Z")
    before = report(ledger, "2026-10-31T18:00:00Z")
    assert usage.instant(before["stop_by"]) == usage.instant("2026-10-31T18:30:00Z")
    ledger = record(
        ledger, start="2026-10-31T17:30:00Z", stopped=True, observed="2026-10-31T19:30:00Z"
    )
    after = report(ledger, "2026-10-31T19:30:00Z")
    assert after["day"] == "2026-11-01"
    assert after["accounted_seconds_by_day"] == {"2026-10-31": 3600, "2026-11-01": 3600}
    assert after["remaining_today_seconds"] == 10800
    ledger = record(ledger, start="2026-11-01T04:00:00Z", observed="2026-11-01T05:00:00Z")
    assert report(ledger, "2026-11-01T05:00:00Z")["accounted_today_seconds"] == 7200


def test_fractional_seconds_round_usage_up_once_per_day():
    ledger = record(start="2026-10-31T04:00:00.9Z", observed="2026-10-31T05:00:00Z")
    result = report(ledger)
    assert result["accounted_today_seconds"] == 3600
    assert result["remaining_today_seconds"] == 10800


def test_missing_stop_receipt_rejects_restart_without_changing_existing_ledger():
    ledger = record()
    original = copy.deepcopy(ledger)
    with pytest.raises(ValueError, match="Missing STOP"):
        record(ledger, start="2026-10-31T06:00:00Z", observed="2026-10-31T06:30:00Z")
    assert ledger == original


def test_stopped_observation_cannot_hide_unrecorded_restart():
    with pytest.raises(ValueError, match="Unrecorded VM start"):
        record(
            record(), stopped=True, start="2026-10-31T06:00:00Z", observed="2026-10-31T06:30:00Z"
        )


def test_restart_cannot_overlap_recorded_stop_upper_bound():
    ledger = record(record(), stopped=True, observed="2026-10-31T06:00:00Z")
    with pytest.raises(ValueError, match="overlapping restart"):
        record(ledger, start="2026-10-31T05:30:00Z", observed="2026-10-31T06:30:00Z")


@pytest.mark.parametrize("stopped", [False, True])
def test_old_observation_is_rejected(stopped):
    with pytest.raises(ValueError, match="predates"):
        record(record(), stopped=stopped, observed="2026-10-31T04:30:00Z")


def test_initial_stopped_state_cannot_claim_a_zero_usage_baseline():
    with pytest.raises(ValueError, match="first RUNNING"):
        record(stopped=True)


def test_closed_start_cannot_be_reopened_by_a_stale_running_state():
    ledger = record(record(), stopped=True)
    with pytest.raises(ValueError, match="already closed"):
        record(ledger)


def test_changed_deadline_rejected_instead_of_silently_extending_time():
    value = snapshot(observed="2026-10-31T05:15:00Z")
    value["instance"]["resourceStatus"]["scheduling"]["terminationTimestamp"] = (
        "2026-10-31T07:00:00Z"
    )
    with pytest.raises(ValueError, match="deadline changed"):
        usage.observe(record(), value, "running", HISTORICAL)


@pytest.mark.parametrize("change", ["replacement", "live", "wrong-project", "stopping", "no-id"])
def test_different_vm_evidence_or_unverified_state_is_rejected(change):
    value = snapshot()
    evidence = HISTORICAL
    if change == "replacement":
        value["instance"]["id"] = "9999999999999999999"
    elif change == "live":
        evidence = "live_read_only"
    elif change == "wrong-project":
        value["instance"]["selfLink"] = value["instance"]["selfLink"].replace(
            "cashlessiq-dev-rush", "other"
        )
    elif change == "stopping":
        value["instance"]["status"] = "STOPPING"
    else:
        value["instance"].pop("id")
    with pytest.raises((ValueError, KeyError)):
        usage.observe(record(), value, "running", evidence)


@pytest.mark.parametrize(
    "damage", ["project", "budget", "tz", "empty", "future", "missing-stop", "overlap"]
)
def test_corrupt_or_incompatible_history_cannot_grant_remaining_time(damage):
    ledger = record(record(), stopped=True)
    ledger = record(ledger, start="2026-10-31T06:00:00Z", observed="2026-10-31T06:30:00Z")
    if damage == "project":
        ledger["project_id"] = "atlas-rag-rush"
    elif damage == "budget":
        ledger["daily_limit_seconds"] = 28800
    elif damage == "tz":
        ledger["timezone"] = "UTC"
    elif damage == "empty":
        ledger["sessions"] = []
    elif damage == "future":
        ledger["sessions"][0]["stopped_observed_at"] = "2027-01-01T00:00:00Z"
    elif damage == "missing-stop":
        ledger["sessions"][0]["stopped_observed_at"] = None
    else:
        ledger["sessions"][1]["started_at"] = "2026-10-31T04:30:00Z"
    with pytest.raises(ValueError):
        report(ledger, "2026-10-31T06:30:00Z")


def test_report_rejects_clock_rollback_and_requires_explicit_timezone():
    ledger = record()
    with pytest.raises(ValueError):
        report(ledger, "2026-10-31T04:30:00Z")
    with pytest.raises(ValueError):
        usage.report(ledger, usage.instant("2026-10-31T06:30:00Z").replace(tzinfo=None))


def call(monkeypatch, path, *arguments):
    monkeypatch.setattr(sys, "argv", ["usage", *arguments, "--ledger", str(path)])
    usage.main()


def freeze(monkeypatch, at):
    class Clock(datetime):
        @classmethod
        def now(cls, tz):
            return usage.instant(at)

    monkeypatch.setattr(usage, "datetime", Clock)


def test_offline_cli_initializes_only_explicitly_and_never_calls_gcp(tmp_path, monkeypatch, capsys):
    def forbidden():
        pytest.fail("Historical accounting contacted GCP")

    monkeypatch.setattr(usage, "live_snapshot", forbidden)
    path = tmp_path / "usage.json"
    args = ("record", "--expect", "running", "--snapshot", str(FIXTURE))
    with pytest.raises(SystemExit) as error:
        call(monkeypatch, path, *args)
    assert error.value.code == 1
    assert not path.exists()
    call(monkeypatch, path, *args, "--initialize-no-earlier-usage")
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    original = path.read_bytes()
    with pytest.raises(SystemExit) as error:
        call(monkeypatch, path, *args, "--initialize-no-earlier-usage")
    assert error.value.code == 1
    assert path.read_bytes() == original
    output = capsys.readouterr().out
    assert HISTORICAL in output
    assert "not a billing meter or cloud cap" in output
    assert "192.0.2.10" not in output
    call(monkeypatch, path, "status", "--at", "2026-10-29T05:30:00Z")
    assert path.read_bytes() == original


def test_failed_record_preserves_file_and_redacts_input(tmp_path, monkeypatch, capsys):
    path = tmp_path / "usage.json"
    usage.save(path, record())
    original = path.read_bytes()
    bad = tmp_path / "snapshot.json"
    bad.write_text(
        json.dumps(snapshot(start="2026-10-31T06:00:00Z", observed="2026-10-31T06:30:00Z"))
    )
    with pytest.raises(SystemExit) as error:
        call(monkeypatch, path, "record", "--expect", "running", "--snapshot", str(bad))
    assert error.value.code == 1
    assert path.read_bytes() == original
    assert "reconcile" in capsys.readouterr().err
    assert not list(tmp_path.glob("tmp*"))


def test_live_read_is_explicit_and_uses_only_existing_read_only_reader(
    tmp_path, monkeypatch, capsys
):
    value = snapshot()

    freeze(monkeypatch, "2026-10-31T05:00:01Z")
    monkeypatch.setattr(usage, "live_snapshot", lambda: value)
    path = tmp_path / "usage.json"
    call(
        monkeypatch,
        path,
        "record",
        "--expect",
        "running",
        "--live",
        "--initialize-no-earlier-usage",
    )
    assert json.loads(path.read_text())["evidence"] == "live_read_only"
    assert "live_read_only" in capsys.readouterr().out


@pytest.mark.parametrize("at", ["2026-10-31T05:02:01Z", "2026-10-31T04:59:59Z"])
def test_stale_or_future_live_snapshot_does_not_write_ledger(tmp_path, monkeypatch, at):
    freeze(monkeypatch, at)
    monkeypatch.setattr(usage, "live_snapshot", snapshot)
    path = tmp_path / "usage.json"
    with pytest.raises(SystemExit) as error:
        call(
            monkeypatch,
            path,
            "record",
            "--expect",
            "running",
            "--live",
            "--initialize-no-earlier-usage",
        )
    assert error.value.code == 1
    assert not path.exists()


def test_valid_over_budget_stop_is_saved_before_warning_exit(tmp_path, monkeypatch, capsys):
    path = tmp_path / "usage.json"
    usage.save(path, record())
    value = tmp_path / "stopped.json"
    value.write_text(json.dumps(snapshot(stopped=True, observed="2026-10-31T08:30:00Z")))
    with pytest.raises(SystemExit) as error:
        call(monkeypatch, path, "record", "--expect", "stopped", "--snapshot", str(value))
    assert error.value.code == 2
    assert json.loads(path.read_text())["sessions"][0]["stopped_observed_at"]
    assert '"remaining_today_seconds": 0' in capsys.readouterr().out


def test_atomic_write_failure_leaves_existing_ledger_intact(tmp_path, monkeypatch):
    path = tmp_path / "usage.json"
    usage.save(path, record())
    original = path.read_bytes()

    def fail(*args):
        raise OSError("fictional disk failure")

    monkeypatch.setattr(usage.os, "replace", fail)
    with pytest.raises(OSError):
        usage.save(path, record(record(), stopped=True))
    assert path.read_bytes() == original
    assert sorted(item.name for item in tmp_path.iterdir()) == ["usage.json"]


def test_concurrent_command_cannot_overwrite_another_receipt(tmp_path, monkeypatch):
    path = tmp_path / "usage.json"
    usage.save(path, record())
    original = path.read_bytes()
    with path.with_suffix(".json.lock").open("a") as lock:
        usage.fcntl.flock(lock, usage.fcntl.LOCK_EX | usage.fcntl.LOCK_NB)
        with pytest.raises(SystemExit) as error:
            call(monkeypatch, path, "record", "--expect", "running", "--snapshot", str(FIXTURE))
    assert error.value.code == 1
    assert path.read_bytes() == original


def test_over_limit_previous_day_remains_visible_after_midnight():
    ledger = record(record(), stopped=True, observed="2026-10-31T08:30:00Z")
    result = report(ledger, "2026-11-01T04:00:00Z")
    assert result["remaining_today_seconds"] == 14400
    assert result["past_days_over_limit"] == ["2026-10-31"]
