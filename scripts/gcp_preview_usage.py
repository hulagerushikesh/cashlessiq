"""Account for observed preview sessions across restarts; never start or stop a VM.

Run this from one persistent operator checkout, including after every STOP.
The local ledger is an operator aid, not a billing meter or enforced cloud cap.
An unclosed session keeps counting until TERMINATED is actually observed.
"""

from __future__ import annotations

import argparse
import copy
import fcntl
import json
import math
import os
import subprocess
import tempfile
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.check_gcp_preview_instance import PROJECT, live_snapshot, timestamp, verify
from scripts.check_gcp_preview_plan import PLAN

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER = ROOT / "output/gcp-preview/usage.json"
ZONE = ZoneInfo("Asia/Kolkata")
LIMIT = 14400
EVIDENCE = {"live_read_only", "historical_snapshot_only"}


def instant(value: object) -> datetime:
    return timestamp(value).astimezone(UTC)


def validate(ledger: dict) -> None:
    """Reject damaged/incompatible history rather than silently resetting usage."""
    if (
        ledger["version"] != 1
        or ledger["project_id"] != PROJECT
        or ledger["timezone"] != ZONE.key
        or ledger["daily_limit_seconds"] != LIMIT
        or ledger["evidence"] not in EVIDENCE
        or not isinstance(ledger["instance_id"], str)
        or not ledger["instance_id"].isdigit()
        or not ledger["sessions"]
    ):
        raise ValueError("Invalid usage ledger identity or policy")
    previous = None
    last_observed = instant(ledger["observed_at"])
    for index, session in enumerate(ledger["sessions"]):
        start = instant(session["started_at"])
        end = instant(session["stopped_observed_at"]) if session["stopped_observed_at"] else None
        deadline = instant(session["automatic_stop_deadline"])
        if (
            start > last_observed
            or (previous is not None and start < previous)
            or not 0 < (deadline - start).total_seconds() <= LIMIT
            or (end is not None and not start <= end <= last_observed)
            or (end is None and index != len(ledger["sessions"]) - 1)
        ):
            raise ValueError("Usage ledger has overlapping, incomplete or inconsistent sessions")
        previous = end


def observe(ledger: dict | None, snapshot: dict, expected: str, evidence: str) -> dict:
    """Only verified VM states may add history. Missing STOP receipts fail closed."""
    plan = json.loads(PLAN.read_text())
    if plan["operating_policy"]["daily_testing_budget_seconds"] != LIMIT:
        raise ValueError("Usage policy differs from the reviewed four-hour daily limit")
    checked = verify(snapshot, expected)
    observed = instant(checked["observed_at"])
    started = instant(snapshot["instance"]["lastStartTimestamp"])
    instance_id = snapshot["instance"]["id"]
    if evidence not in EVIDENCE or not isinstance(instance_id, str) or not instance_id.isdigit():
        raise ValueError("Missing VM identity or evidence mode")
    if started > observed:
        raise ValueError("VM start is later than its observation")
    if ledger is None:
        if expected != "running":
            raise ValueError("Initialize at the first RUNNING observation, not after a stopped run")
        result = {
            "version": 1,
            "project_id": PROJECT,
            "instance_id": instance_id,
            "timezone": ZONE.key,
            "daily_limit_seconds": LIMIT,
            "evidence": evidence,
            "observed_at": observed.isoformat(),
            "sessions": [],
        }
    else:
        validate(ledger)
        if ledger["evidence"] != evidence or ledger["instance_id"] != instance_id:
            raise ValueError("Cannot mix historical/live evidence or a replaced VM in this ledger")
        if observed < instant(ledger["observed_at"]):
            raise ValueError("Observation predates the last usage receipt")
        result = copy.deepcopy(ledger)

    sessions = result["sessions"]
    last = sessions[-1] if sessions else None
    if last and started == instant(last["started_at"]):
        if expected == "running":
            if last["stopped_observed_at"]:
                raise ValueError("RUNNING observation reuses an already closed VM start")
            if instant(last["automatic_stop_deadline"]) != instant(
                checked["automatic_stop_deadline"]
            ):
                raise ValueError("Automatic STOP deadline changed during the recorded session")
        elif last["stopped_observed_at"] is None:
            # Conservative upper bound: STOPPING and assumed timer expiry are not receipts.
            last["stopped_observed_at"] = observed.isoformat()
    elif expected == "stopped":
        raise ValueError("Unrecorded VM start; reconcile history before claiming remaining time")
    else:
        if last and (
            last["stopped_observed_at"] is None or started < instant(last["stopped_observed_at"])
        ):
            raise ValueError("Missing STOP receipt or overlapping restart; reconcile usage history")
        sessions.append(
            {
                "started_at": started.isoformat(),
                "stopped_observed_at": None,
                "automatic_stop_deadline": checked["automatic_stop_deadline"],
            }
        )
    result["observed_at"] = observed.isoformat()
    validate(result)
    return result


def report(ledger: dict, at: datetime) -> dict:
    validate(ledger)
    if at.tzinfo is None or at < instant(ledger["observed_at"]):
        raise ValueError("Report time must include a timezone and follow the latest observation")
    day = at.astimezone(ZONE).date()
    tomorrow = datetime.combine(day + timedelta(days=1), time(), ZONE)
    intervals: dict[str, float] = {}
    for session in ledger["sessions"]:
        start = instant(session["started_at"])
        end = instant(session["stopped_observed_at"]) if session["stopped_observed_at"] else at
        while start < end:
            date = start.astimezone(ZONE).date()
            next_day = datetime.combine(date + timedelta(days=1), time(), ZONE)
            finish = min(end, next_day)
            key = date.isoformat()
            intervals[key] = intervals.get(key, 0) + (finish - start).total_seconds()
            start = finish
    # Round usage up, never grant an extra second because of fractional timestamps.
    seconds = {key: math.ceil(value) for key, value in sorted(intervals.items())}
    used = seconds.get(day.isoformat(), 0)
    remaining = max(0, LIMIT - used)
    current = ledger["sessions"][-1]
    open_session = current["stopped_observed_at"] is None
    stop_by = (
        min(
            at + timedelta(seconds=remaining), tomorrow, instant(current["automatic_stop_deadline"])
        )
        if open_session
        else None
    )
    return {
        "project_id": PROJECT,
        "evidence": ledger["evidence"],
        "timezone": ZONE.key,
        "day": day.isoformat(),
        "as_of": at.isoformat(),
        "last_observed_at": ledger["observed_at"],
        "basis": "recorded_observations_only",
        "accounted_seconds_by_day": seconds,
        "daily_limit_seconds": LIMIT,
        "accounted_today_seconds": used,
        "remaining_today_seconds": remaining,
        "session_open": open_session,
        "stop_by": stop_by.astimezone(ZONE).isoformat() if stop_by else None,
        "stop_now": open_session and (remaining == 0 or stop_by <= at),
        "past_days_over_limit": [
            key for key, value in seconds.items() if key < day.isoformat() and value > LIMIT
        ],
    }


def save(path: Path, ledger: dict) -> None:
    """Replace only a complete serialized ledger, with the caller holding its lock."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(ledger, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    record = commands.add_parser("record", help="Append a verified running/stopped receipt")
    record.add_argument("--expect", choices=("running", "stopped"), required=True)
    source = record.add_mutually_exclusive_group(required=True)
    source.add_argument("--live", action="store_true", help="Only describe/list GCP state")
    source.add_argument(
        "--snapshot", type=Path, help="Fictional/historical input; never cloud evidence"
    )
    record.add_argument(
        "--initialize-no-earlier-usage",
        action="store_true",
        help="First run only: operator confirms there is no unrecorded earlier VM runtime",
    )
    status = commands.add_parser("status", help="Report local history without contacting GCP")
    status.add_argument("--at", help="Explicit historical report timestamp, including timezone")
    for command in (record, status):
        command.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    args = parser.parse_args()
    try:
        path = args.ledger
        if args.action == "status":
            ledger = json.loads(path.read_text())
            result = report(ledger, instant(args.at) if args.at else datetime.now(UTC))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            # One persistent operator ledger. Concurrent commands cannot lose a receipt.
            with path.with_suffix(path.suffix + ".lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                exists = path.exists()
                if exists == args.initialize_no_earlier_usage:
                    raise ValueError(
                        "Initialize only a new ledger, explicitly confirming no earlier usage"
                    )
                ledger = json.loads(path.read_text()) if exists else None
                snapshot = live_snapshot() if args.live else json.loads(args.snapshot.read_text())
                now = datetime.now(UTC)
                if (
                    args.live
                    and not 0 <= (now - instant(snapshot["observed_at"])).total_seconds() <= 120
                ):
                    raise ValueError("Live observation is stale or in the future")
                ledger = observe(
                    ledger,
                    snapshot,
                    args.expect,
                    "live_read_only" if args.live else "historical_snapshot_only",
                )
                result = report(ledger, now if args.live else instant(snapshot["observed_at"]))
                save(path, ledger)
        print(json.dumps(result, indent=2))
        print("Recorded runtime is a conservative upper bound, not a billing meter or cloud cap.")
        print(
            "Only recorded starts/stops are covered. Keep one ledger; never reset it for a new day."
        )
        print("No VM is started/stopped. Disk, image and other charges remain separate.")
        print("Local status cannot detect an unrecorded start or authorize another testing window.")
        if (
            result["stop_now"]
            or result["accounted_today_seconds"] > LIMIT
            or result["past_days_over_limit"]
        ):
            parser.exit(2, "Usage needs operator attention; valid observations were retained.\n")
    except (KeyError, TypeError, ValueError, OSError, subprocess.SubprocessError):
        parser.exit(
            1,
            "Usage record failed; preserve the ledger and reconcile history before restarting.\n",
        )


if __name__ == "__main__":
    main()
