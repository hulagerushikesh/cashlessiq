"""Inactive fake receipt custody outside the product PostgreSQL backup.

Explicit disposable engineering only. SQLite FULL commits model independently
retained receipts; same-host files are NOT production custody, authentication or
protection against their owner/host administrator. No live mode or reset/release
API. Losing either side fails closed. No path/epoch is accepted through IPC.
"""

import os
import sqlite3
import stat
from contextlib import contextmanager
from datetime import UTC
from pathlib import Path
from typing import Literal
from urllib.parse import quote
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ciq_api.agent_contracts import AgentContractError, Digest, ImmutableContract, Label
from ciq_api.agent_ledger_models import (
    AgentAdmissionEpoch,
    AgentAttempt,
    AgentExecutionGrant,
    AgentOperation,
)
from ciq_api.assessment import fingerprint

MAX_RECEIPTS = 30
ERROR = "agent_admission_quarantined"


def _closed():
    raise AgentContractError(ERROR) from None


class FakeEpochPin(ImmutableContract):
    mode: Literal["fake-only"] = "fake-only"
    database_id: UUID
    epoch_id: UUID


class FakeCheckpoint(ImmutableContract):
    """Only identities and an exact local receipt digest, never clinical bodies."""

    tenant_id: UUID
    request_id: Label
    operation_id: UUID
    submission_id: UUID
    digest: Digest

    def values(self):
        return (
            str(self.tenant_id), self.request_id, str(self.operation_id),
            str(self.submission_id), self.digest,
        )


class FakeReceiptJournal:
    """Fixed file, bounded transactions, no auto-create on reopen, no retry/reset.

    This adapter is for disposable tests, not a chosen live receipt service. Its
    configured directory and epoch pin belong to the trusted harness, never a
    browser, model, transport envelope or restored product backup.
    """

    def __init__(self, directory: Path, pin: FakeEpochPin):
        self.directory = Path(directory)
        self.pin = FakeEpochPin.model_validate(pin.model_dump())
        self.path = self.directory / "fake-receipts.sqlite3"

    @classmethod
    def provision(cls, directory: Path, pin: FakeEpochPin):
        journal = cls(directory, pin)
        try:
            journal.directory.mkdir(mode=0o700)  # Existing custody is never replaced.
            fd = os.open(journal.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            os.close(fd)
            with journal._connection() as db:
                db.executescript("""
CREATE TABLE identity (
 id INTEGER PRIMARY KEY CHECK(id=1), database_id TEXT NOT NULL, epoch_id TEXT NOT NULL,
 mode TEXT NOT NULL CHECK(mode='fake-only'), state TEXT NOT NULL CHECK(state IN ('active','closed'))
);
CREATE TABLE receipt (
 tenant_id TEXT NOT NULL, request_id TEXT NOT NULL,
 operation_id TEXT NOT NULL UNIQUE, submission_id TEXT PRIMARY KEY,
 digest TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('prepared','issued')),
 UNIQUE(tenant_id, request_id)
);
CREATE TRIGGER identity_guard BEFORE UPDATE ON identity
WHEN OLD.state != 'active' OR NEW.state != 'closed'
 OR NEW.id != OLD.id OR NEW.database_id != OLD.database_id
 OR NEW.epoch_id != OLD.epoch_id OR NEW.mode != OLD.mode
BEGIN SELECT RAISE(ABORT,'immutable_identity'); END;
CREATE TRIGGER identity_delete BEFORE DELETE ON identity
BEGIN SELECT RAISE(ABORT,'immutable_identity'); END;
CREATE TRIGGER receipt_delete BEFORE DELETE ON receipt
BEGIN SELECT RAISE(ABORT,'immutable_receipt'); END;
CREATE TRIGGER receipt_guard BEFORE UPDATE ON receipt
WHEN OLD.state != 'prepared' OR NEW.state != 'issued'
 OR NEW.tenant_id != OLD.tenant_id OR NEW.request_id != OLD.request_id
 OR NEW.operation_id != OLD.operation_id OR NEW.submission_id != OLD.submission_id
 OR NEW.digest != OLD.digest
BEGIN SELECT RAISE(ABORT,'immutable_receipt'); END;
""")
                db.execute(
                    "INSERT INTO identity VALUES(1,?,?,?,'active')",
                    (str(pin.database_id), str(pin.epoch_id), pin.mode),
                )
            # SQLite syncs its transaction; also persist the newly created name.
            fd = os.open(journal.directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
            return journal
        except (OSError, sqlite3.Error):
            _closed()

    @contextmanager
    def _connection(self):
        db = None
        try:
            for path, kind, permissions in (
                (self.directory, stat.S_ISDIR, 0o700), (self.path, stat.S_ISREG, 0o600),
            ):
                details = path.lstat()
                if (
                    not kind(details.st_mode) or stat.S_IMODE(details.st_mode) != permissions
                    or details.st_uid != os.getuid()
                ):
                    _closed()
            if self.path.stat().st_size > 256 * 1024:
                _closed()
            # mode=rw is essential: missing custody must not become an empty DB.
            db = sqlite3.connect(
                f"file:{quote(str(self.path.resolve()), safe='/')}?mode=rw", uri=True, timeout=1,
            )
            db.execute("PRAGMA trusted_schema=OFF")
            db.execute("PRAGMA journal_mode=DELETE")
            db.execute("PRAGMA synchronous=FULL")
            db.execute("PRAGMA max_page_count=64")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except (OSError, sqlite3.Error):
            _closed()
        finally:
            if db is not None:
                db.close()  # Rollback on any uncommitted failure.

    def _identity(self, db):
        if db.execute("SELECT * FROM identity").fetchall() != [(
            1, str(self.pin.database_id), str(self.pin.epoch_id), "fake-only", "active",
        )]:
            _closed()

    def check(self, expected: tuple[FakeCheckpoint, ...]):
        with self._connection() as db:
            self._identity(db)
            actual = db.execute(
                "SELECT tenant_id,request_id,operation_id,submission_id,digest "
                "FROM receipt LIMIT 31"
            ).fetchall()
            if len(actual) > MAX_RECEIPTS or sorted(actual) != sorted(c.values() for c in expected):
                _closed()

    def prepare(self, checkpoint: FakeCheckpoint):
        checkpoint = FakeCheckpoint.model_validate(checkpoint.model_dump())
        with self._connection() as db:
            self._identity(db)
            if db.execute("SELECT count(*) FROM receipt").fetchone()[0] >= MAX_RECEIPTS:
                _closed()
            # Unique case/operation/submission IDs fence new grants, amended input,
            # mappings and reconstructed local rows. No unused-receipt refund API.
            db.execute("INSERT INTO receipt VALUES(?,?,?,?,?,'prepared')", checkpoint.values())

    def issue(self, checkpoint: FakeCheckpoint):
        checkpoint = FakeCheckpoint.model_validate(checkpoint.model_dump())
        with self._connection() as db:
            self._identity(db)
            changed = db.execute(
                "UPDATE receipt SET state='issued' WHERE tenant_id=? AND request_id=? "
                "AND operation_id=? AND submission_id=? AND digest=? AND state='prepared'",
                checkpoint.values(),
            ).rowcount
            if changed != 1:
                _closed()
        # Persist 'issued' BEFORE fake child I/O. An exit here sacrifices this
        # allowance; a new process can never obtain a second issue permission.

    def quarantine(self):
        """Terminal close only. No clear, rotate, reconcile or reset operation."""
        with self._connection() as db:
            self._identity(db)
            db.execute("UPDATE identity SET state='closed' WHERE id=1")


def checkpoint(db, attempt: AgentAttempt) -> FakeCheckpoint:
    op = db.get(AgentOperation, (attempt.tenant_id, attempt.operation_id))
    grant = db.get(AgentExecutionGrant, (op.tenant_id, op.grant_id)) if op else None
    if not op or not grant or grant.mode != "fake-only":
        _closed()
    return checkpoint_from_material(op, grant, attempt)


def checkpoint_from_material(op, grant, attempt) -> FakeCheckpoint:
    """Shared canonical preimage for owner fixtures and restricted observation.

    The caller must independently obtain/validate these rows. This pure hash
    function does not authenticate supplied material or authorize any action.
    """
    # Immutable source fields only: state/counters/leases may legitimately move.
    # Include approval window/allowance and captured snapshot HASH, not its body.
    def instant(value):
        if value.tzinfo is None or value.utcoffset() is None:
            _closed()
        return value.astimezone(UTC).isoformat()

    body = {
        "version": 1, "tenant": str(op.tenant_id), "actor": str(op.actor_id),
        "request": op.request_id, "operation": str(op.id), "key": op.operation_key,
        "snapshot_digest": fingerprint(op.snapshot), "config": op.config_digest,
        "source": op.source_digest, "created": instant(op.created_at),
        "deadline": instant(op.deadline), "grant": str(grant.id),
        "approval_digest": fingerprint(grant.approval_ref),
        "window": [instant(grant.starts_at), instant(grant.ends_at)],
        "limits": [grant.case_limit, grant.concurrency_limit, grant.unit_limit,
                   grant.units_per_attempt],
        "attempt": str(attempt.id), "submission": str(attempt.submission_id),
        "fence": str(attempt.fence_id), "submitted": instant(attempt.submitted_at),
    }
    return FakeCheckpoint(
        tenant_id=op.tenant_id, request_id=op.request_id, operation_id=op.id,
        submission_id=attempt.submission_id, digest=fingerprint(body),
    )


class FakeAdmissionGate:
    def __init__(self, journal: FakeReceiptJournal):
        self.journal = journal

    @classmethod
    def provision_empty_for_tests(cls, engine, directory: Path):
        """Explicit fake operator action. Never called by migration/route/startup.

        Can initialize only a database with no operations/attempts/admitted units.
        Partial bootstrap failure leaves custody unusable rather than overwriting
        it. This is not approval for any provider, identity or paid service.
        """
        with Session(engine) as db, db.begin():
            db.execute(text("LOCK TABLE agent_admission_epoch IN EXCLUSIVE MODE"))
            if (
                db.get(AgentAdmissionEpoch, 1)
                or db.scalar(select(AgentOperation.id).limit(1))
                or db.scalar(select(AgentAttempt.id).limit(1))
                or db.scalar(select(AgentExecutionGrant.id).where(
                    (AgentExecutionGrant.admitted != 0) | (AgentExecutionGrant.in_flight != 0)
                    | (AgentExecutionGrant.reserved_units != 0)
                    | (AgentExecutionGrant.consumed_units != 0)
                    | (AgentExecutionGrant.uncertain_units != 0)
                ).limit(1))
            ):
                _closed()
            pin = FakeEpochPin(database_id=uuid4(), epoch_id=uuid4())
            journal = FakeReceiptJournal.provision(directory, pin)
            db.add(AgentAdmissionEpoch(id=1, **pin.model_dump()))
        return cls(journal)

    def check(self, db):
        # All admission writers serialize BEFORE acquiring clinical/grant locks.
        anchor = db.scalar(select(AgentAdmissionEpoch).where(
            AgentAdmissionEpoch.id == 1,
        ).with_for_update())
        pin = self.journal.pin
        if not anchor or (anchor.mode, anchor.database_id, anchor.epoch_id) != (
            "fake-only", pin.database_id, pin.epoch_id,
        ):
            _closed()
        attempts = list(db.scalars(select(AgentAttempt).limit(MAX_RECEIPTS + 1)))
        if len(attempts) > MAX_RECEIPTS:
            _closed()
        self.journal.check(tuple(checkpoint(db, a) for a in attempts))

    def prepare(self, db, attempt):
        self.journal.prepare(checkpoint(db, attempt))

    def issue(self, db, attempt):
        self.journal.issue(checkpoint(db, attempt))
