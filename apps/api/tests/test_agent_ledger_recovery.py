"""Populated, encrypted PostgreSQL restore on an explicitly supplied CI service.

Never starts Docker or contacts a provider. Ordinary API runs skip this suite;
the dedicated public CI job supplies its disposable PostgreSQL container ID.
"""

import hashlib
import json
import os
import re
import subprocess
from contextlib import contextmanager
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from test_agent_ledger import (
    ACTOR,
    NOW,
    TENANT_ID,
    balance,
    payload,
    replacement_grant,
    reserve,
    rows,
    submission,
)
from test_agent_ledger import (
    setup as setup,
)

from ciq_api.agent_contracts import AgentContractError
from ciq_api.agent_ledger import FakeAgentLedger
from ciq_api.agent_ledger_models import AgentAttempt, AgentComparison, AgentOperation
from ciq_api.review_models import ReviewCase

pytestmark = pytest.mark.skipif(
    not os.environ.get("CIQ_AGENT_RECOVERY_CONTAINER"),
    reason="Populated restore requires the explicit disposable CI PostgreSQL service",
)


def service_command(container, *args, **kwargs):
    try:
        return subprocess.run(
            ["docker", "exec", "-i", container, *args],
            check=True,
            timeout=90,
            stderr=subprocess.PIPE,
            **kwargs,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        raise RuntimeError("Disposable ledger recovery command failed") from None


@pytest.fixture
def recovery_service():
    from scripts.check_mvp_recovery import require_restart_permission

    # Check before any Docker mutation; setting an environment variable on a Mac
    # is insufficient to make this suite operate on local containers/databases.
    require_restart_permission("preview")
    container = os.environ["CIQ_AGENT_RECOVERY_CONTAINER"]
    if not re.fullmatch(r"[a-f0-9]{64}", container):
        raise ValueError("Expected the exact disposable CI service container ID")
    result = subprocess.run(
        ["docker", "inspect", container],
        check=True,
        timeout=10,
        capture_output=True,
    )
    inspected = json.loads(result.stdout)
    assert len(inspected) == 1
    row = inspected[0]
    assert row["Id"] == container
    assert row["State"]["Running"]
    assert row["Config"]["Image"] == "postgres:17-bookworm"
    assert any(p["HostPort"] == "5432" for p in row["NetworkSettings"]["Ports"]["5432/tcp"])
    assert "POSTGRES_PASSWORD=ciq-disposable-agent-ledger" in row["Config"]["Env"]
    return container


@contextmanager
def snapshot(engine):
    url = engine.url
    assert (url.host, url.port, url.username) == ("127.0.0.1", 5432, "postgres")
    assert url.database == "postgres" or re.fullmatch(
        r"ciq_agent_restore_[a-f0-9]{24}", url.database
    )
    assert url.password == "ciq-disposable-agent-ledger"
    with engine.connect() as db:
        schema = db.scalar(text("SELECT current_schema()"))
    assert re.fullmatch(r"test_[a-f0-9]{32}", schema)
    with psycopg.connect(
        host=url.host,
        port=url.port,
        user=url.username,
        password=url.password,
        dbname=url.database,
        options=(
            "-c statement_timeout=30000 -c lock_timeout=3000 "
            "-c idle_in_transaction_session_timeout=120000 -c timezone=UTC"
        ),
    ) as db:
        db.execute("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY")
        yield db, schema


@contextmanager
def restored_database(s, container, directory):
    from scripts.check_mvp_recovery import recovered_transfer_dump, verify_manifest
    from scripts.mvp_recovery_probe import table_manifest
    from scripts.verify_mvp_backup import digest_file, verify_package

    directory.mkdir(mode=0o700)
    dump = directory / "current.dump"
    # Hash and dump the same exported read-only snapshot. Source schema is never
    # modified, migrated, truncated or used as the restore destination.
    with snapshot(s.engine) as (db, schema):
        expected = table_manifest(db, schema)
        snapshot_id = db.execute("SELECT pg_export_snapshot()").fetchone()[0]
        with dump.open("xb") as output:
            dump.chmod(0o600)
            service_command(
                container,
                "pg_dump",
                "-U",
                "postgres",
                "-d",
                "postgres",
                "--format=custom",
                "--no-owner",
                "--no-privileges",
                "--lock-wait-timeout=5s",
                f"--schema={schema}",
                f"--snapshot={snapshot_id}",
                stdout=output,
            )
    descriptor = directory / "verified.json"
    descriptor.write_text(
        json.dumps(
            {
                "schema": "0004_agent_ledger",
                "tables": expected,
                "dump": {
                    "file": "current.dump",
                    "bytes": dump.stat().st_size,
                    "sha256": digest_file(dump),
                },
            }
        )
    )
    descriptor.chmod(0o600)
    assert len(verify_package(directory)["tables"]) == 21
    for table in ("agent_execution_grant", "agent_operation", "agent_attempt", "agent_comparison"):
        assert expected[table]["rows"] > 0
    database = "ciq_agent_restore_" + uuid4().hex[:24]
    service_command(container, "createdb", "-U", "postgres", "-T", "template0", database)
    engine = create_engine(
        s.engine.url.set(database=database), connect_args={"options": f"-csearch_path={schema}"}
    )
    try:
        with recovered_transfer_dump(directory, expected) as decrypted:
            assert decrypted != dump
            assert digest_file(decrypted) == digest_file(dump)
            with decrypted.open("rb") as source:
                service_command(
                    container,
                    "pg_restore",
                    "-U",
                    "postgres",
                    "--no-owner",
                    "--no-privileges",
                    "--exit-on-error",
                    "-d",
                    database,
                    stdin=source,
                    stdout=subprocess.PIPE,
                )
        assert not decrypted.exists()
        with snapshot(engine) as (db, restored_schema):
            verify_manifest(expected, table_manifest(db, restored_schema))
        yield SimpleNamespace(**{**vars(s), "engine": engine, "ledger": FakeAgentLedger(engine)})
    finally:
        engine.dispose()
        service_command(container, "dropdb", "-U", "postgres", "--force", database)
    # No application/ledger mutation in the restored DB may affect the original.
    with snapshot(s.engine) as (db, schema):
        verify_manifest(expected, table_manifest(db, schema))


def receipt_digest(s):
    """No clinical rows, permits or output bodies appear in assertion reports."""
    digest = hashlib.sha256()
    for model in (AgentAttempt, AgentComparison):
        with Session(s.engine) as db:
            values = db.execute(
                text(
                    f"SELECT row_to_json(t)::text FROM {model.__tablename__} t "
                    'ORDER BY row_to_json(t)::text COLLATE "C"'
                )
            ).scalars()
            for value in values:
                data = value.encode()
                digest.update(len(data).to_bytes(8, "big"))
                digest.update(data)
    return digest.hexdigest()


@pytest.mark.parametrize(
    "state",
    [
        "reserved",
        "claimed",
        "submitting",
        "unknown",
        "rejected",
        "published",
        "superseded",
        "expired",
    ],
)
def test_populated_encrypted_restore_retains_receipts_and_forbids_resubmission(
    recovery_service, setup, tmp_path, state
):
    s = setup
    baseline = submission(s, 0)
    s.ledger.publish_fake_result(baseline, payload(baseline))
    subject = reserve(s, 1)
    permit = claim = None
    if state not in {"reserved", "expired"}:
        claim = s.ledger.claim(TENANT_ID, ACTOR, subject.operation_id)
    if state not in {"reserved", "claimed", "expired"}:
        permit = s.ledger.begin_submission(TENANT_ID, ACTOR, claim)
    pending = reserve(s, 2)
    if state == "published":
        s.ledger.publish_fake_result(permit, payload(permit))
    elif state == "rejected":
        s.ledger.publish_fake_result(permit, b"invalid fake output")
    elif state == "superseded":
        with Session(s.engine) as db, db.begin():
            review = db.get(ReviewCase, (TENANT_ID, "REQ-FAKE-1"))
            review.version += 1
        s.ledger.publish_fake_result(permit, payload(permit))
    elif state in {"unknown", "expired"}:
        s.clock[0] = NOW + timedelta(seconds=120)
        s.ledger.recover_expired(TENANT_ID, subject.operation_id)
    before_balance, before_receipts = balance(s), receipt_digest(s)
    before_attempts = {(a.id, a.submission_id) for a in rows(s, AgentAttempt)}
    with restored_database(s, recovery_service, tmp_path / "backup") as restored:
        assert balance(restored) == before_balance
        assert receipt_digest(restored) == before_receipts
        assert {(a.id, a.submission_id) for a in rows(restored, AgentAttempt)} == before_attempts
        # Even while its old lease is valid, a durable submitted attempt cannot
        # obtain a second permit after a full dump/decrypt/restore.
        if permit:
            with pytest.raises(AgentContractError):
                restored.ledger.begin_submission(TENANT_ID, ACTOR, claim)
        s.clock[0] = NOW + timedelta(seconds=121)
        expected_state = {"reserved": "expired", "claimed": "expired", "submitting": "unknown"}.get(
            state, state
        )
        recovered = restored.ledger.recover_expired(TENANT_ID, subject.operation_id)
        assert recovered.state == expected_state
        assert restored.ledger.recover_expired(TENANT_ID, subject.operation_id) == recovered
        assert restored.ledger.recover_expired(TENANT_ID, pending.operation_id).state == "expired"
        baseline_result = restored.ledger.recover_expired(TENANT_ID, baseline.operation_id)
        assert baseline_result.state == "published"
        # Changing grant, correlation or review version must not repurchase a run.
        replacement = restored.ledger.create_fake_grant(TENANT_ID, s.spec)
        assert reserve(restored, 1, grant_id=replacement) == recovered
        assert reserve(restored, 1) == recovered
        # A restored result still fences cross-version attempts under a new
        # grant; a changed digest is not permission to repurchase baseline work.
        for changes, grant_changes in (
            ({"config_digest": "c" * 64}, {"config": "c" * 64}),
            ({"source_digest": "c" * 64}, {"source": "c" * 64}),
        ):
            changed_grant = replacement_grant(restored, **grant_changes)
            with pytest.raises(AgentContractError, match="mapping_replacement_requires_review"):
                reserve(restored, 0, grant_id=changed_grant, **changes)
        with pytest.raises(AgentContractError):
            restored.ledger.claim(TENANT_ID, ACTOR, subject.operation_id)
        if permit:
            with pytest.raises(AgentContractError):
                restored.ledger.publish_fake_result(permit, payload(permit))
        assert receipt_digest(restored) == before_receipts
        assert {(a.id, a.submission_id) for a in rows(restored, AgentAttempt)} == before_attempts
        # Unknown allowance is still held, while unsubmitted expired work is released.
        uncertain = expected_state == "unknown"
        consumed = 20 if expected_state in {"published", "rejected", "superseded"} else 10
        assert balance(restored) == (3, int(uncertain), 0, consumed, 10 if uncertain else 0)
        # Restoring post-data triggers, unique keys and FK constraints matters as
        # much as restoring rows. These statements must fail in fresh transactions.
        for statement in (
            "DELETE FROM agent_attempt",
            "DELETE FROM agent_operation",
            "DELETE FROM agent_execution_grant",
            "DELETE FROM agent_comparison",
            "UPDATE agent_operation SET state='reserved', version=version+1",
            "UPDATE agent_execution_grant SET mode='live'",
            "UPDATE agent_comparison SET candidate='{}'",
            "INSERT INTO agent_attempt SELECT tenant_id, gen_random_uuid(), operation_id, "
            "attempt_number, gen_random_uuid(), fence_id, submitted_at FROM agent_attempt",
        ):
            with pytest.raises(DBAPIError), restored.engine.begin() as db:
                db.execute(text(statement))
        with pytest.raises(DBAPIError) as rejected, Session(restored.engine) as db, db.begin():
            db.add(
                AgentComparison(
                    tenant_id=TENANT_ID,
                    operation_id=pending.operation_id,
                    attempt_id=baseline.attempt_id,
                    candidate={},
                    published_at=NOW,
                )
            )
        assert rejected.value.orig.sqlstate == "23503"  # Exact operation/attempt FK.
        assert receipt_digest(restored) == before_receipts
        assert all(op.state != "submitting" for op in rows(restored, AgentOperation))
        with restored.engine.connect() as db:
            for table in ("review_audit", "review_outbox", "analytics_event"):
                assert db.scalar(text(f"SELECT count(*) FROM {table}")) == 0


@pytest.mark.parametrize("already_claimed", [False, True])
def test_restore_can_finish_unsubmitted_work_once_before_its_deadline(
    recovery_service, setup, tmp_path, already_claimed
):
    s = setup
    baseline = submission(s, 0)
    s.ledger.publish_fake_result(baseline, payload(baseline))
    subject = reserve(s, 1)
    claim = s.ledger.claim(TENANT_ID, ACTOR, subject.operation_id) if already_claimed else None
    reserve(s, 2)
    with restored_database(s, recovery_service, tmp_path / "backup") as restored:
        # The restored grant and original deadline remain in force. An operation
        # with no persisted attempt can complete its first submission; restoration
        # must not silently drop it or grant a new 120-second execution window.
        assert restored.ledger.recover_expired(TENANT_ID, subject.operation_id).state == "reserved"
        claim = claim or restored.ledger.claim(TENANT_ID, ACTOR, subject.operation_id)
        permit = restored.ledger.begin_submission(TENANT_ID, ACTOR, claim)
        with pytest.raises(AgentContractError, match="automatic_retry_forbidden"):
            restored.ledger.begin_submission(TENANT_ID, ACTOR, claim)
        result = restored.ledger.publish_fake_result(permit, payload(permit))
        assert result.state == "published"
        assert restored.ledger.publish_fake_result(permit, payload(permit)) == result
        assert reserve(restored, 1) == result
        assert len(rows(restored, AgentAttempt)) == len(rows(restored, AgentComparison)) == 2
        assert balance(restored) == (3, 1, 10, 20, 0)
