"""Offline checkpoint controls; no Snowflake connection or credential use."""

import io
import json
import subprocess
import tarfile
from pathlib import Path

import pytest

from scripts import recovery_checkpoint as checkpoint


def results():
    rows = [[{"ROLE": "CIQ_PRODUCT_READER", "SECONDARY_ROLES": '{"value":""}'}]]
    for _ in range(3):
        rows.append(
            [
                {"REQUEST_ID": request, "TPA_ID": owner}
                for request, owner in sorted(checkpoint.PAIRS)
            ]
        )
    rows.append([{"name": "CIQ_WH", "state": "STARTED"}])
    batch = [[]]
    for index, group in enumerate(rows):
        batch.extend((group, [{"CAPTURED_QUERY_ID": f"query-{index}"}]))
    return batch


def test_fixed_batch_budget_and_scope():
    sql = checkpoint.batch_sql()
    assert sql.count(";") == 11
    assert "STATEMENT_TIMEOUT_IN_SECONDS=30" in sql
    assert "STATEMENT_QUEUED_TIMEOUT_IN_SECONDS=15" in sql
    for forbidden in ("CLINICAL_NOTE", "DECISION_JSON", "DATA_AGENT_RUN", "CREATE ", "GRANT "):
        assert forbidden not in sql
    assert len(checkpoint.validate_capture(results())) == 5


@pytest.mark.parametrize("failure", ["role", "secondary", "owner", "duplicate", "id", "count"])
def test_unexpected_capture_denies(failure):
    batch = results()
    if failure == "role":
        batch[1][0]["ROLE"] = "ACCOUNTADMIN"
    elif failure == "secondary":
        batch[1][0]["SECONDARY_ROLES"] = '{"value":"ALL"}'
    elif failure == "owner":
        batch[3][0]["TPA_ID"] = "TPA999"
    elif failure == "duplicate":
        batch[3][1] = batch[3][0]
    elif failure == "id":
        batch[2] = []
    else:
        batch.pop()
    with pytest.raises(ValueError):
        checkpoint.validate_capture(batch)


def test_cli_bounded_explicit_and_no_retry(monkeypatch):
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, json.dumps(results()), "")

    monkeypatch.setattr(checkpoint.subprocess, "run", run)
    evidence = checkpoint.run_capture()
    assert evidence["statements"] == 11
    assert len(calls) == 1
    command, options = calls[0]
    assert command[command.index("--role") + 1] == "CIQ_PRODUCT_READER"
    assert command[command.index("--secondary-roles") + 1] == "NONE"
    assert options["timeout"] == 180
    assert options["capture_output"] is True


def test_archive_verify_offline_tamper_and_private_modes(tmp_path, monkeypatch):
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w") as archive:
        entry = tarfile.TarInfo("src/example.py")
        archive.addfile(entry, io.BytesIO(b""))

    def git(command, **kwargs):
        if "diff" in command:
            return b""
        return "revision\n" if "rev-parse" in command else data.getvalue()

    monkeypatch.setattr(checkpoint.subprocess, "check_output", git)
    monkeypatch.setattr(checkpoint, "run_capture", lambda: pytest.fail("Offline must not connect"))
    destination = tmp_path / "private"
    checkpoint.create_checkpoint(destination)
    checkpoint.verify_checkpoint(destination)
    assert destination.stat().st_mode & 0o777 == 0o700
    assert all(item.stat().st_mode & 0o777 == 0o600 for item in destination.iterdir())
    (destination / "evidence.json").write_text("tampered")
    with pytest.raises(ValueError, match="Integrity"):
        checkpoint.verify_checkpoint(destination)


def test_dirty_sources_refused_before_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(checkpoint.subprocess, "check_output", lambda *a, **k: b"diff")
    target = tmp_path / "not-created"
    with pytest.raises(ValueError, match="Commit"):
        checkpoint.create_checkpoint(target)
    assert not Path(target).exists()
