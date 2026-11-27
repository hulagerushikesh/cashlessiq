"""Retained single-call faults with dummy pins and no provider/cloud/Docker I/O."""

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from ciq_api import agent_single_call_journal as journal

NOW = datetime(2026, 11, 27, 14, tzinfo=UTC)
RAW = b'{"synthetic":"PRIVATE raw provider response"}'
USAGE = journal.ReportedTokenUsage(input_tokens=100, output_tokens=None)


@pytest.fixture
def pin():
    return journal.ReviewedCallPin(
        grant_id=uuid4(), database_id=uuid4(), epoch_id=uuid4(), operation_id=uuid4(),
        submission_id=uuid4(), approval_sha256="a" * 64, binding_sha256="b" * 64,
        request_sha256="c" * 64, config_sha256="d" * 64, source_sha256="e" * 64,
        provider_identity_sha256="f" * 64, hostname="reviewed-account.snowflakecomputing.com",
        starts_at=NOW, ends_at=NOW + timedelta(hours=1), reserved_units=20,
        provider_seconds=8, max_tokens=256,
    )


@pytest.fixture
def retained(tmp_path, pin):
    return journal.SingleCallJournal.provision(tmp_path / "retained", pin)


def denied(call):
    with pytest.raises(ValueError, match=f"^{journal.ERROR}$") as caught:
        call()
    assert caught.value.__suppress_context__


def reopen(retained, pin):
    return journal.SingleCallJournal(retained.directory, pin)


def test_one_issue_one_observation_and_all_units_remain_held(retained, pin):
    ready = retained.status()
    assert ready.phase == "ready" and ready.reserved_units == 20 and ready.uncertain_units == 0
    assert ready.issued_at is None and ready.reported_usage is None
    assert retained.issue(now=NOW) is None  # No serializable dispatch ticket.
    issued = reopen(retained, pin).status()
    assert issued.phase == "issued" and issued.uncertain_units == 20 and issued.reserved_units == 0
    assert issued.issued_at == NOW and issued.provider_run_id is None
    retained.observe(RAW, provider_run_id="opaque-provider-id", usage=USAGE)
    observed = reopen(retained, pin).status()
    assert observed.phase == "observed" and observed.uncertain_units == 20
    assert observed.response_sha256 == hashlib.sha256(RAW).hexdigest()
    assert observed.reported_usage == USAGE and observed.provider_run_id == "opaque-provider-id"
    assert RAW not in retained.path.read_bytes()
    for call in (lambda: reopen(retained, pin).issue(now=NOW),
                 lambda: retained.observe(RAW, provider_run_id="replacement", usage=USAGE)):
        denied(call)
    assert retained.status() == observed


@pytest.mark.parametrize("field", [
    "grant_id", "database_id", "epoch_id", "operation_id", "submission_id",
    "approval_sha256", "binding_sha256", "request_sha256", "config_sha256",
    "source_sha256", "provider_identity_sha256", "hostname", "starts_at", "ends_at",
    "reserved_units", "provider_seconds", "max_tokens",
])
def test_changed_approval_or_scope_cannot_adopt_history(retained, pin, field):
    value = getattr(pin, field)
    if field.endswith("_id"):
        value = uuid4()
    elif field.endswith("sha256"):
        value = "0" * 64
    elif field == "hostname":
        value = "other-account.snowflakecomputing.com"
    elif field.endswith("_at"):
        value += timedelta(seconds=1)
    else:
        value = {"reserved_units": 21, "provider_seconds": 7, "max_tokens": 257}[field]
    changed = pin.model_copy(update={field: value})
    other = reopen(retained, changed)
    denied(other.status)
    denied(lambda: other.issue(now=NOW + timedelta(seconds=5)))
    assert retained.status().phase == "ready"


@pytest.mark.parametrize("field,value", [
    ("reserved_units", True), ("reserved_units", 0), ("reserved_units", "20"),
    ("provider_seconds", True), ("provider_seconds", 9), ("provider_seconds", 1.0),
    ("max_tokens", 255), ("max_tokens", 16_001), ("max_tokens", "256"),
    ("request_sha256", "A" * 64), ("protocol", "fake-only"),
    ("hostname", "localhost"), ("hostname", "https://account.snowflakecomputing.com"),
    ("starts_at", NOW.replace(tzinfo=None)), ("ends_at", NOW),
    ("ends_at", NOW + timedelta(hours=4, microseconds=1)),
])
def test_invalid_even_unsafely_constructed_pins_fail_before_files(tmp_path, pin, field, value):
    denied(lambda: journal.SingleCallJournal.provision(
        tmp_path / "absent", pin.model_copy(update={field: value}),
    ))
    assert not (tmp_path / "absent").exists()


@pytest.mark.parametrize("when", [NOW - timedelta(microseconds=1), NOW + timedelta(hours=1),
                                  NOW + timedelta(hours=1, seconds=-12),
                                  NOW.replace(tzinfo=None), "2026-11-27T14:00:00Z", True])
def test_outside_window_or_too_little_remaining_time_cannot_issue(retained, when):
    denied(lambda: retained.issue(now=when))
    assert retained.status().phase == "ready"


def test_equivalent_timezone_pins_and_last_full_window_are_canonical(retained, pin):
    local = timezone(timedelta(hours=5, minutes=30))
    equivalent = pin.model_copy(update={"starts_at": pin.starts_at.astimezone(local),
                                        "ends_at": pin.ends_at.astimezone(local)})
    other = reopen(retained, equivalent)
    other.issue(now=pin.ends_at - timedelta(seconds=13))
    assert retained.status().phase == "issued"


def test_two_independent_callers_compete_for_one_committed_issue(retained, pin):
    def issue(_):
        try:
            reopen(retained, pin).issue(now=NOW)
            return True
        except ValueError as error:
            assert str(error) == journal.ERROR
            return False

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(issue, range(2))) == [False, True]
    assert retained.status().uncertain_units == 20


@pytest.mark.parametrize("phase", ["before-issue", "after-issue", "after-observe"])
def test_actual_process_exit_preserves_dispatch_fence(retained, pin, phase):
    # Dummy test delivery only; no runtime accepts path/config through argv.
    code = f"""
import os, sys
sys.path.insert(0, {str(Path(journal.__file__).resolve().parents[1])!r})
from pathlib import Path
from datetime import datetime
from ciq_api.agent_single_call_journal import SingleCallJournal, ReviewedCallPin, ReportedTokenUsage
pin = ReviewedCallPin.model_validate_json(sys.stdin.buffer.read())
journal = SingleCallJournal(Path({str(retained.directory)!r}), pin)
if {phase!r} != 'before-issue':
    journal.issue(now=datetime.fromisoformat({NOW.isoformat()!r}))
if {phase!r} == 'after-observe':
    journal.observe({RAW!r}, provider_run_id='dummy-provider',
                    usage=ReportedTokenUsage(input_tokens=None, output_tokens=0))
os._exit(23)
"""
    result = subprocess.run((sys.executable, "-I", "-B", "-c", code),
                            input=pin.model_dump_json().encode(), capture_output=True,
                            timeout=5, env={"LANG": "C.UTF-8"})
    assert result.returncode == 23 and not result.stdout and not result.stderr
    other = reopen(retained, pin)
    if phase == "before-issue":
        assert other.status().phase == "ready"
        other.issue(now=NOW)
    else:
        denied(lambda: other.issue(now=NOW))
    assert other.status().uncertain_units == 20


def test_failure_after_issue_commit_cannot_dispatch_or_refund(retained, pin, monkeypatch):
    original = retained._connection

    @contextmanager
    def lose_ack():
        with original() as db:
            yield db
        raise OSError("PRIVATE lost commit acknowledgment")

    monkeypatch.setattr(retained, "_connection", lose_ack)
    dispatched = []

    def run():
        retained.issue(now=NOW)
        dispatched.append(True)

    denied(run)
    assert not dispatched
    denied(lambda: reopen(retained, pin).issue(now=NOW))
    assert reopen(retained, pin).status().uncertain_units == 20


def test_uncommitted_issue_rolls_back_and_never_dispatches(retained, monkeypatch):
    original = retained._connection

    @contextmanager
    def fail_before_commit():
        with original() as db:
            yield db
            raise OSError("PRIVATE failure before commit")

    monkeypatch.setattr(retained, "_connection", fail_before_commit)
    denied(lambda: retained.issue(now=NOW))
    monkeypatch.setattr(retained, "_connection", original)
    assert retained.status().phase == "ready"


@pytest.mark.parametrize("fault", ["missing", "empty", "directory-mode", "file-mode",
                                  "hardlink", "symlink", "fifo", "oversize", "corrupt"])
def test_lost_or_unsafe_retention_never_becomes_fresh_authority(retained, pin, fault):
    retained.issue(now=NOW)
    if fault == "missing":
        retained.path.unlink()
    elif fault == "empty":
        retained.path.write_bytes(b"")
    elif fault == "directory-mode":
        retained.directory.chmod(0o755)
    elif fault == "file-mode":
        retained.path.chmod(0o644)
    elif fault == "hardlink":
        os.link(retained.path, retained.directory / "second-name")
    elif fault == "symlink":
        target = retained.directory / "original"
        retained.path.rename(target)
        retained.path.symlink_to(target)
    elif fault == "fifo":
        retained.path.unlink()
        os.mkfifo(retained.path, 0o600)
    else:
        retained.path.write_bytes(b"x" * (262_145 if fault == "oversize" else 128))
    denied(reopen(retained, pin).status)
    denied(lambda: reopen(retained, pin).issue(now=NOW))
    denied(lambda: journal.SingleCallJournal.provision(retained.directory, pin))
    assert not retained.path.exists() if fault == "missing" else retained.path.exists()


def test_observation_requires_original_issue_and_retains_unknown_tokens(retained):
    denied(lambda: retained.observe(RAW, provider_run_id="dummy", usage=USAGE))
    retained.issue(now=NOW)
    retained.observe(RAW, provider_run_id="dummy", usage=USAGE)
    assert retained.status().reported_usage.output_tokens is None
    assert retained.status().uncertain_units == 20


@pytest.mark.parametrize("raw,provider_id,usage", [
    (b"", "dummy", USAGE), (b"x" * 384_001, "dummy", USAGE),
    (bytearray(RAW), "dummy", USAGE), (RAW, "", USAGE), (RAW, "x" * 201, USAGE),
    (RAW, "dummy\nPRIVATE", USAGE), (RAW, "dummy", {"input_tokens": 1}),
    (RAW, "dummy", USAGE.model_copy(update={"input_tokens": True})),
    (RAW, "dummy", USAGE.model_copy(update={"output_tokens": -1})),
], ids=["empty", "oversize", "mutable", "empty-id", "long-id", "newline", "dict",
         "bool", "negative"])
def test_bad_observation_cannot_release_or_replace_issue(retained, raw, provider_id, usage):
    retained.issue(now=NOW)
    denied(lambda: retained.observe(raw, provider_run_id=provider_id, usage=usage))
    assert retained.status().phase == "issued" and retained.status().uncertain_units == 20


@pytest.mark.parametrize("sql", [
    "DELETE FROM single_call", "UPDATE single_call SET pin='replacement'",
    "UPDATE single_call SET phase='ready',issued_at=NULL",
    "UPDATE single_call SET issued_at='2026-11-28T14:00:00+00:00'",
])
def test_sql_guards_preserve_original_issued_history(retained, sql):
    retained.issue(now=NOW)
    with sqlite3.connect(retained.path) as db, pytest.raises(sqlite3.IntegrityError):
        db.execute(sql)
    assert retained.status().phase == "issued"


def test_retention_file_contains_only_pins_and_accounting(retained, pin):
    retained.issue(now=NOW)
    retained.observe(RAW, provider_run_id="dummy", usage=USAGE)
    with sqlite3.connect(retained.path) as db:
        tables = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        row = db.execute("SELECT * FROM single_call").fetchone()
    assert tables == [("single_call",)] and json.loads(row[1])["grant_id"] == str(pin.grant_id)
    assert RAW not in retained.path.read_bytes()


def test_two_observers_cannot_replace_original_response_association(retained, pin):
    retained.issue(now=NOW)

    def observe(index):
        try:
            reopen(retained, pin).observe(RAW, provider_run_id=f"dummy-{index}", usage=USAGE)
            return index
        except ValueError as error:
            assert str(error) == journal.ERROR
            return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(observe, range(2)))
    winner = [result for result in results if result is not None]
    assert len(winner) == 1
    assert retained.status().provider_run_id == f"dummy-{winner[0]}"
    assert retained.status().uncertain_units == 20


def test_observation_commit_ack_loss_preserves_marker_without_reissue(retained, pin, monkeypatch):
    retained.issue(now=NOW)
    original = retained._connection

    @contextmanager
    def lose_ack():
        with original() as db:
            yield db
        raise OSError("PRIVATE lost observation acknowledgment")

    monkeypatch.setattr(retained, "_connection", lose_ack)
    denied(lambda: retained.observe(RAW, provider_run_id="dummy", usage=USAGE))
    other = reopen(retained, pin)
    assert other.status().phase == "observed" and other.status().uncertain_units == 20
    denied(lambda: other.issue(now=NOW))
    denied(lambda: other.observe(RAW, provider_run_id="replacement", usage=USAGE))


@pytest.mark.parametrize("symlink", [False, True])
def test_provision_never_adopts_existing_or_dangling_directory(tmp_path, pin, symlink):
    path = tmp_path / "owner"
    if symlink:
        path.symlink_to(tmp_path / "absent")
    else:
        path.mkdir()
        (path / "preserve").write_bytes(b"PRIVATE owner file")
    denied(lambda: journal.SingleCallJournal.provision(path, pin))
    assert (path.is_symlink() if symlink
            else (path / "preserve").read_bytes() == b"PRIVATE owner file")


def test_failed_provision_preserves_committed_file_for_review(tmp_path, pin, monkeypatch):
    path = tmp_path / "retained"

    def fail(_):
        raise OSError("PRIVATE parent fsync failed")

    monkeypatch.setattr(journal.os, "fsync", fail)
    denied(lambda: journal.SingleCallJournal.provision(path, pin))
    assert (path / "single-call.sqlite3").is_file()
    denied(lambda: journal.SingleCallJournal.provision(path, pin))
