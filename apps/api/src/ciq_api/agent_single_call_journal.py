"""Inactive retained single-call bookkeeping, never a live execution permit.

Trusted provisioning only; no runner, IPC, route, provider or fake-ledger import.
This journal must remain outside product backups under separately protected
custody. Its owner/parent paths, host and retained history are trusted. Replacing
or rolling back this journal defeats its fence; no claim of off-host durability.
"""

import hashlib
import json
import os
import sqlite3
import stat
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import quote
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from ciq_api.agent_contracts import Digest, ImmutableContract, canonical_json
from ciq_api.agent_https_process import MAX_PROCESS_SECONDS
from ciq_api.agent_https_transport import MAX_RESPONSE_BYTES, SinglePostHTTPS

ERROR = "single_call_journal_unavailable"
_COUNT = Annotated[int, Field(strict=True, ge=0, le=1_000_000_000)]


def _require(value):
    if not value:
        raise ValueError(ERROR)


def _instant(value):
    _require(type(value) is datetime and value.tzinfo is not None and value.utcoffset() is not None)
    return value.astimezone(UTC).isoformat()


class ReviewedCallPin(ImmutableContract):
    """Operator-supplied reviewed pins, not authenticated approval evidence.

    An approval hash cannot verify owner consent. A future protected issuer must
    establish that consent, current clinical authority and these exact pins.
    Units are conservative admission counters, not currency or a billing cap.
    """

    protocol: Literal["prepared-single-provider-call-v1"] = "prepared-single-provider-call-v1"
    grant_id: UUID
    database_id: UUID
    epoch_id: UUID
    operation_id: UUID
    submission_id: UUID
    approval_sha256: Digest
    binding_sha256: Digest
    request_sha256: Digest
    config_sha256: Digest
    source_sha256: Digest
    provider_identity_sha256: Digest
    hostname: str
    starts_at: AwareDatetime = Field(strict=True)
    ends_at: AwareDatetime = Field(strict=True)
    reserved_units: Annotated[int, Field(strict=True, ge=1, le=1_000_000)]
    # Fits inside the prepared ten-second socket/twelve-second process envelope.
    # This validates an approval ceiling; no request preparation is selected here.
    provider_seconds: Annotated[int, Field(strict=True, ge=1, le=8)]
    max_tokens: Annotated[int, Field(strict=True, ge=256, le=16_000)]

    @model_validator(mode="after")
    def coherent(self):
        _require(timedelta(0) < self.ends_at - self.starts_at <= timedelta(hours=4))
        SinglePostHTTPS(hostname=self.hostname, token="probe", request_sha256=self.request_sha256)
        return self

    def canonical(self):
        value = self.model_dump(mode="json")
        value.update(starts_at=_instant(self.starts_at), ends_at=_instant(self.ends_at))
        return canonical_json(value)


class ReportedTokenUsage(ImmutableContract):
    origin: Literal["unverified-provider-report-v1"] = "unverified-provider-report-v1"
    input_tokens: _COUNT | None
    output_tokens: _COUNT | None


class SingleCallStatus(ImmutableContract):
    phase: Literal["ready", "issued", "observed"]
    reserved_units: _COUNT
    uncertain_units: _COUNT
    issued_at: AwareDatetime | None
    response_sha256: Digest | None
    provider_run_id: str | None = Field(repr=False)
    reported_usage: ReportedTokenUsage | None


_SCHEMA = """
CREATE TABLE single_call (
 id INTEGER PRIMARY KEY CHECK(id=1), pin TEXT NOT NULL,
 phase TEXT NOT NULL CHECK(phase IN ('ready','issued','observed')),
 issued_at TEXT, response_sha256 TEXT, provider_run_id TEXT, usage TEXT,
 CHECK((phase='ready' AND issued_at IS NULL AND response_sha256 IS NULL
        AND provider_run_id IS NULL AND usage IS NULL)
    OR (phase='issued' AND issued_at IS NOT NULL AND response_sha256 IS NULL
        AND provider_run_id IS NULL AND usage IS NULL)
    OR (phase='observed' AND issued_at IS NOT NULL AND response_sha256 IS NOT NULL
        AND provider_run_id IS NOT NULL AND usage IS NOT NULL))
);
CREATE TRIGGER no_delete BEFORE DELETE ON single_call
BEGIN SELECT RAISE(ABORT,'immutable_call'); END;
CREATE TRIGGER forward_only BEFORE UPDATE ON single_call
WHEN NEW.id != OLD.id OR NEW.pin != OLD.pin
 OR NOT ((OLD.phase='ready' AND NEW.phase='issued')
      OR (OLD.phase='issued' AND NEW.phase='observed' AND NEW.issued_at=OLD.issued_at))
BEGIN SELECT RAISE(ABORT,'immutable_call'); END;
"""


class SingleCallJournal:
    """One retained file, one call, one issue, one immutable observation.

    No reset, refund, regrant, automatic provisioning, transport or publication.
    An issued row is permanently uncertain for admission accounting, even after
    observing a response. Observation is not provider authentication, financial
    reconciliation, clinical validation or permission to release the allowance.
    """

    def __init__(self, directory: Path, pin: ReviewedCallPin):
        try:
            _require(type(pin) is ReviewedCallPin)
            self._pin = ReviewedCallPin.model_validate(
                pin.model_dump(mode="python", warnings=False),
            )
            self._canonical = self._pin.canonical()
            self.directory = Path(directory)
            self.path = self.directory / "single-call.sqlite3"
        except Exception:
            raise ValueError(ERROR) from None

    @classmethod
    def provision(cls, directory: Path, pin: ReviewedCallPin):
        journal = cls(directory, pin)
        try:
            # Never adopt/delete a previous file, directory or dangling symlink.
            journal.directory.mkdir(mode=0o700)
            fd = os.open(journal.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            os.close(fd)
            with journal._connection(fresh=True) as db:
                # executescript would implicitly commit BEGIN IMMEDIATE. Execute
                # each complete statement separately so DDL+pin are one commit.
                pending = ""
                for line in _SCHEMA.splitlines(keepends=True):
                    pending += line
                    if sqlite3.complete_statement(pending):
                        db.execute(pending)
                        pending = ""
                _require(not pending.strip())
                db.execute("INSERT INTO single_call VALUES(1,?,'ready',NULL,NULL,NULL,NULL)",
                           (journal._canonical,))
            for path in (journal.directory, journal.directory.parent):
                fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
            return journal
        except Exception:
            # A failed/partially acknowledged provision is preserved for review,
            # never repaired or retried as an empty authority automatically.
            raise ValueError(ERROR) from None

    @contextmanager
    def _connection(self, *, fresh=False):
        db = None
        try:
            for path, kind, mode in ((self.directory, stat.S_ISDIR, 0o700),
                                     (self.path, stat.S_ISREG, 0o600)):
                item = path.lstat()
                _require(kind(item.st_mode) and item.st_uid == os.getuid()
                         and stat.S_IMODE(item.st_mode) == mode)
                if path == self.path:
                    _require(item.st_nlink == 1
                             and (0 if fresh else 1) <= item.st_size <= 256 * 1024)
            db = sqlite3.connect(f"file:{quote(str(self.path.absolute()), safe='/')}?mode=rw",
                                 uri=True, timeout=1)
            db.execute("PRAGMA trusted_schema=OFF")
            db.execute("PRAGMA journal_mode=DELETE")
            db.execute("PRAGMA synchronous=FULL")
            db.execute("PRAGMA max_page_count=64")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except Exception:
            raise ValueError(ERROR) from None
        finally:
            if db is not None:
                db.close()

    def _row(self, db):
        rows = db.execute("SELECT * FROM single_call LIMIT 2").fetchall()
        _require(len(rows) == 1 and rows[0][:2] == (1, self._canonical))
        return rows[0]

    def issue(self, *, now: datetime):
        """Commit before any remote I/O; returns no reconstructible I/O ticket.

        Caller supplies a trusted current UTC wall clock. The future supervisor
        must also fence clock rollback/deadlines and clinical authority. Any
        exception/commit ambiguity denies dispatch and holds existing history.
        """
        try:
            issued = _instant(now)
            with self._connection() as db:
                row = self._row(db)
                _require(self._pin.starts_at <= now and row[2] == "ready"
                         and now + timedelta(seconds=MAX_PROCESS_SECONDS + 1) <= self._pin.ends_at)
                _require(db.execute(
                    "UPDATE single_call SET phase='issued',issued_at=? "
                    "WHERE id=1 AND phase='ready'",
                    (issued,),
                ).rowcount == 1)
        except Exception:
            raise ValueError(ERROR) from None

    def observe(self, raw: bytes, *, provider_run_id: str, usage: ReportedTokenUsage):
        """Record one trusted caller's raw-response association, not authentication.

        A future authenticated wire/controller must supply this association.
        Never derive an expected provider ID from itself and call that validation.
        This method neither decodes nor publishes a clinical candidate.
        """
        try:
            _require(type(raw) is bytes and 0 < len(raw) <= MAX_RESPONSE_BYTES)
            _require(type(provider_run_id) is str and 0 < len(provider_run_id) <= 200
                     and all(32 <= ord(char) <= 126 for char in provider_run_id))
            _require(type(usage) is ReportedTokenUsage)
            usage = ReportedTokenUsage.model_validate(
                usage.model_dump(mode="python", warnings=False),
            )
            with self._connection() as db:
                _require(self._row(db)[2] == "issued")
                _require(db.execute(
                    "UPDATE single_call SET phase='observed',response_sha256=?,"
                    "provider_run_id=?,usage=? "
                    "WHERE id=1 AND phase='issued'",
                    (hashlib.sha256(raw).hexdigest(), provider_run_id,
                     canonical_json(usage.model_dump(mode="json"))),
                ).rowcount == 1)
        except Exception:
            raise ValueError(ERROR) from None

    def status(self) -> SingleCallStatus:
        with self._connection() as db:
            _, _, phase, issued, digest, provider_id, usage = self._row(db)
            units = self._pin.reserved_units
            reported = ReportedTokenUsage.model_validate(json.loads(usage)) if usage else None
            return SingleCallStatus(
                phase=phase, reserved_units=units if phase == "ready" else 0,
                uncertain_units=0 if phase == "ready" else units, issued_at=issued,
                response_sha256=digest, provider_run_id=provider_id,
                reported_usage=reported,
            )
