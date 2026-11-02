"""Offline independent fake custody: filesystem and crash-consistency contract."""

import os
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from pydantic import ValidationError

from ciq_api.agent_admission import (
    ERROR,
    FakeCheckpoint,
    FakeEpochPin,
    FakeReceiptJournal,
)
from ciq_api.agent_contracts import AgentContractError


def receipt(**changes):
    return FakeCheckpoint(
        **{
            "tenant_id": uuid4(), "request_id": "SYN-RECEIPT",
            "operation_id": uuid4(), "submission_id": uuid4(), "digest": "a" * 64,
            **changes,
        }
    )


@pytest.fixture
def journal(tmp_path):
    return FakeReceiptJournal.provision(
        tmp_path / "custody", FakeEpochPin(database_id=uuid4(), epoch_id=uuid4()),
    )


def closed(call):
    with pytest.raises(AgentContractError, match=f"^{ERROR}$"):
        call()


def test_reopen_persists_issued_tombstone_and_never_initializes_again(journal):
    first = receipt()
    journal.check(())
    journal.prepare(first)
    reopened = FakeReceiptJournal(journal.directory, journal.pin)
    reopened.check((first,))
    reopened.issue(first)
    FakeReceiptJournal(journal.directory, journal.pin).check((first,))
    closed(lambda: journal.issue(first))
    closed(lambda: journal.prepare(first))
    closed(lambda: FakeReceiptJournal.provision(journal.directory, journal.pin))
    journal.check((first,))


@pytest.mark.parametrize("phase", ["prepared", "issued"])
def test_missing_local_history_is_quarantined_even_after_restart(journal, phase):
    first = receipt()
    journal.prepare(first)
    if phase == "issued":
        journal.issue(first)
    reopened = FakeReceiptJournal(journal.directory, journal.pin)
    closed(lambda: reopened.check(()))
    reopened.check((first,))


@pytest.mark.parametrize("field", [
    "tenant_id", "request_id", "operation_id", "submission_id", "digest",
])
def test_contradictory_local_history_is_never_a_match(journal, field):
    first = receipt()
    journal.prepare(first)
    value = {"request_id": "SYN-OTHER", "digest": "b" * 64}.get(field, uuid4())
    altered = FakeCheckpoint.model_validate({**first.model_dump(), field: value})
    closed(lambda: journal.check((altered,)))
    closed(lambda: journal.issue(altered))
    journal.issue(first)


@pytest.mark.parametrize("selector", ["database_id", "epoch_id", "mode"])
def test_caller_cannot_select_new_epoch_or_live_mode(journal, selector):
    values = {**journal.pin.model_dump(), selector: "live" if selector == "mode" else uuid4()}
    if selector == "mode":
        with pytest.raises(ValidationError):
            FakeEpochPin.model_validate(values)
    else:
        different = FakeReceiptJournal(journal.directory, FakeEpochPin.model_validate(values))
        closed(lambda: different.check(()))
        closed(lambda: different.prepare(receipt()))
    journal.check(())


def test_terminal_quarantine_never_reopens_with_old_pin(journal):
    first = receipt()
    journal.prepare(first)
    journal.quarantine()
    reopened = FakeReceiptJournal(journal.directory, journal.pin)
    for action in (
        lambda: reopened.check((first,)), lambda: reopened.prepare(receipt()),
        lambda: reopened.issue(first), reopened.quarantine,
    ):
        closed(action)


@pytest.mark.parametrize("phase", ["prepare", "issue"])
def test_concurrent_controllers_get_at_most_one_permission(journal, phase):
    first = receipt()
    if phase == "issue":
        journal.prepare(first)

    def command():
        try:
            other = FakeReceiptJournal(journal.directory, journal.pin)
            getattr(other, phase)(first)
            return "ok"
        except AgentContractError as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: command(), range(2))) == sorted(["ok", ERROR])
    journal.check((first,))


@pytest.mark.parametrize("phase", ["prepared", "issued"])
def test_abrupt_process_exit_does_not_erase_committed_receipt(journal, phase):
    # Pin/path are synthetic trusted test config, no credentials/clinical input.
    script = """
import os, sys
from pathlib import Path
from ciq_api.agent_admission import FakeReceiptJournal, FakeEpochPin, FakeCheckpoint
j = FakeReceiptJournal(Path(sys.argv[1]), FakeEpochPin.model_validate_json(sys.argv[2]))
r = FakeCheckpoint.model_validate_json(sys.argv[3])
j.prepare(r)
if sys.argv[4] == 'issued': j.issue(r)
os._exit(7)
"""
    first = receipt()
    result = subprocess.run([
        sys.executable, "-c", script, str(journal.directory), journal.pin.model_dump_json(),
        first.model_dump_json(), phase,
    ], capture_output=True, timeout=10)
    assert result.returncode == 7 and result.stdout == result.stderr == b""
    reopened = FakeReceiptJournal(journal.directory, journal.pin)
    reopened.check((first,))
    if phase == "issued":
        closed(lambda: reopened.issue(first))
    else:
        reopened.issue(first)


@pytest.mark.parametrize("fault", [
    "missing", "garbled", "oversize", "file_public", "directory_public",
    "file_symlink", "directory_symlink",
])
def test_unavailable_or_unsafe_custody_is_fixed_error_and_not_auto_created(journal, fault):
    if fault == "missing":
        journal.path.unlink()
    elif fault == "garbled":
        journal.path.write_bytes(b"private malformed clinical bytes")
    elif fault == "oversize":
        journal.path.write_bytes(b"x" * (256 * 1024 + 1))
    elif fault == "file_public":
        journal.path.chmod(0o644)
    elif fault == "directory_public":
        journal.directory.chmod(0o755)
    elif fault == "file_symlink":
        original = journal.path.with_suffix(".original")
        journal.path.rename(original)
        journal.path.symlink_to(original)
    else:
        original = journal.directory.with_suffix(".original")
        journal.directory.rename(original)
        journal.directory.symlink_to(original, target_is_directory=True)
    closed(lambda: journal.check(()))
    closed(lambda: journal.prepare(receipt()))
    if fault == "missing":
        assert not journal.path.exists()


def test_receipt_inventory_is_bounded_and_contains_no_clinical_bodies(journal):
    receipts = tuple(receipt(request_id=f"SYN-{i}") for i in range(30))
    for item in receipts:
        journal.prepare(item)
    closed(lambda: journal.prepare(receipt(request_id="SYN-31")))
    journal.check(receipts)
    assert journal.path.stat().st_mode & 0o777 == 0o600
    assert journal.directory.stat().st_mode & 0o777 == 0o700
    with sqlite3.connect(journal.path) as db:
        assert [r[1] for r in db.execute("PRAGMA table_info(receipt)")] == [
            "tenant_id", "request_id", "operation_id", "submission_id", "digest", "state",
        ]
    assert b"facts_json" not in journal.path.read_bytes()
    assert b"policy_json" not in journal.path.read_bytes()


def test_sqlite_guards_reject_receipt_reset_or_epoch_change(journal):
    first = receipt()
    journal.prepare(first)
    for sql in (
        "DELETE FROM receipt", "UPDATE receipt SET digest='b'",
        "UPDATE identity SET epoch_id='other'", "DELETE FROM identity",
    ):
        with pytest.raises(sqlite3.IntegrityError), sqlite3.connect(journal.path) as db:
            db.execute(sql)
    journal.issue(first)
    with pytest.raises(sqlite3.IntegrityError), sqlite3.connect(journal.path) as db:
        db.execute("UPDATE receipt SET state='prepared'")
    journal.check((first,))


def test_missing_external_receipt_is_not_evidence_of_zero_usage(journal):
    closed(lambda: journal.check((receipt(),)))
    assert os.stat(journal.path).st_size > 0


def test_checkpoint_digest_uses_instants_not_database_session_timezone():
    from datetime import UTC, datetime, timedelta, timezone
    from types import SimpleNamespace

    from ciq_api.agent_admission import checkpoint
    from ciq_api.agent_ledger_models import AgentExecutionGrant, AgentOperation

    now = datetime(2026, 11, 2, 10, 0, 0, 123456, tzinfo=UTC)
    op = SimpleNamespace(
        id=uuid4(), tenant_id=uuid4(), actor_id=uuid4(), grant_id=uuid4(),
        request_id="SYN-TIMEZONE", operation_key="a" * 64, snapshot={"synthetic": True},
        config_digest="b" * 64, source_digest="c" * 64,
        created_at=now, deadline=now + timedelta(seconds=120),
    )
    grant = SimpleNamespace(
        id=op.grant_id, mode="fake-only", approval_ref="fake only",
        starts_at=now, ends_at=now + timedelta(minutes=10),
        case_limit=1, concurrency_limit=1, unit_limit=10, units_per_attempt=10,
    )
    attempt = SimpleNamespace(
        id=uuid4(), tenant_id=op.tenant_id, operation_id=op.id,
        submission_id=uuid4(), fence_id=uuid4(), submitted_at=now,
    )
    db = SimpleNamespace(get=lambda model, _: {
        AgentOperation: op, AgentExecutionGrant: grant,
    }[model])
    expected = checkpoint(db, attempt)
    for target in (timezone(timedelta(hours=5, minutes=30)), timezone(timedelta(hours=-7))):
        for obj, fields in (
            (op, ("created_at", "deadline")), (grant, ("starts_at", "ends_at")),
            (attempt, ("submitted_at",)),
        ):
            for name in fields:
                setattr(obj, name, getattr(obj, name).astimezone(target))
        assert checkpoint(db, attempt) == expected
    attempt.submitted_at = now.replace(tzinfo=None)
    closed(lambda: checkpoint(db, attempt))
