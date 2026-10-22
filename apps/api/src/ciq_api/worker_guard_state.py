"""Inactive v3 offline state foundation, NOT a health/authorization/replay guard.

No startup, migration, evidence provider, token consumption or recovery. File
checks are not a substitute for real mount custody or protection from TOCTOU.
"""

import json
import os
import sqlite3
import stat
from contextlib import closing
from hashlib import sha256
from pathlib import Path
from typing import Annotated

from pydantic import Field, model_validator

from ciq_api.worker_health import (
    MAX_INTEGER,
    SECOND,
    HealthBinding,
    HealthNow,
    HealthPolicy,
    Integer,
    Positive,
    StrictModel,
)

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Identity = Annotated[str, Field(pattern=r"^[a-zA-Z0-9:._-]{1,200}$")]


class GuardStateDenied(Exception):
    """Generic state denial, with no path, configuration or storage details."""


class GuardStateConfig(StrictModel):
    """Explicit fictional limits/configuration; no operational defaults."""

    authority: Identity
    assertion_generation: Identity
    health_key_sha256: Digest
    binding: HealthBinding
    health_policy: HealthPolicy
    max_gap_ns: Positive
    max_step_ns: Positive
    max_nonces: Annotated[int, Field(ge=1, le=10_000)]
    max_file_bytes: Annotated[int, Field(ge=16_384, le=16_777_216)]

    def canonical(self) -> str:
        raw = self.model_dump(mode="json")
        raw["health_policy"]["sources"] = sorted(raw["health_policy"]["sources"])
        return json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    @property
    def fingerprint(self) -> str:
        return sha256(self.canonical().encode("ascii")).hexdigest()


class GuardStateSnapshot(StrictModel):
    """Stored data only: even an unlatched snapshot does NOT confer readiness."""

    singleton: Annotated[int, Field(ge=1, le=1)]
    version: Annotated[int, Field(ge=3, le=3)]
    config: str
    sequence: Integer
    digest: str
    wall: Integer
    mono: Integer
    boottime: Integer
    end_wall: Integer
    end_mono: Integer
    end_boot: Integer
    reference: Integer
    unsafe: Annotated[int, Field(ge=0, le=1)]

    @model_validator(mode="after")
    def continuity_shape(self):
        if self.boottime < self.mono:
            raise ValueError("Invalid state")
        if self.sequence == 0:
            if self.digest or any((self.end_wall, self.end_mono, self.end_boot, self.reference)):
                raise ValueError("Invalid state")
        elif (
            len(self.digest) != 64
            or any(char not in "0123456789abcdef" for char in self.digest)
            or self.end_boot < self.end_mono
            or self.end_wall > self.wall
            or self.end_mono > self.mono
            or self.end_boot > self.boottime
            or not 0 < self.reference <= self.end_wall
        ):
            raise ValueError("Invalid state")
        return self


class StoredNonce(StrictModel):
    nonce: Digest
    expiry: Annotated[int, Field(gt=0, le=MAX_INTEGER // SECOND)]


STATE_SQL = (
    "CREATE TABLE guard_state ("
    "singleton INTEGER PRIMARY KEY CHECK(singleton=1), "
    "version INTEGER NOT NULL CHECK(version=3), config TEXT NOT NULL, "
    "sequence INTEGER NOT NULL CHECK(sequence>=0), digest TEXT NOT NULL, "
    "wall INTEGER NOT NULL CHECK(wall>=0), mono INTEGER NOT NULL CHECK(mono>=0), "
    "boottime INTEGER NOT NULL CHECK(boottime>=mono), "
    "end_wall INTEGER NOT NULL CHECK(end_wall>=0), "
    "end_mono INTEGER NOT NULL CHECK(end_mono>=0), "
    "end_boot INTEGER NOT NULL CHECK(end_boot>=0), "
    "reference INTEGER NOT NULL CHECK(reference>=0), "
    "unsafe INTEGER NOT NULL CHECK(unsafe IN (0,1)))"
)
NONCE_SQL = (
    "CREATE TABLE guard_nonce (nonce TEXT PRIMARY KEY NOT NULL, "
    "expiry INTEGER NOT NULL CHECK(expiry>0)) WITHOUT ROWID"
)
SCHEMA = {
    ("table", "guard_state", "guard_state"): STATE_SQL,
    ("table", "guard_nonce", "guard_nonce"): NONCE_SQL,
}


def _file(path: Path, config: GuardStateConfig) -> None:
    info = path.lstat()
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o600
        or info.st_nlink != 1
        or info.st_size > config.max_file_bytes
    ):
        raise GuardStateDenied("Guard state denied")


class OfflineGuardState:
    """Existing-file inspection only; no clock or nonce authorization methods."""

    def __init__(self, path: Path, *, config: GuardStateConfig):
        if not isinstance(path, Path) or not isinstance(config, GuardStateConfig):
            raise ValueError("Invalid guard state configuration")
        # Do not resolve away a final symlink before inspecting it.
        self._path = path.absolute()
        self._config = GuardStateConfig.model_validate(config.model_dump())

    @staticmethod
    def initialize_for_offline_test(
        path: Path, *, config: GuardStateConfig, initial: HealthNow
    ) -> None:
        """Explicit new-file provisioning only; never repair/overwrite old state."""
        if (
            not isinstance(path, Path)
            or not isinstance(config, GuardStateConfig)
            or not isinstance(initial, HealthNow)
            or initial.boot_id != config.binding.boot_id
            or initial.boottime_ns < initial.monotonic_ns
        ):
            raise ValueError("Invalid initial guard state")
        config = GuardStateConfig.model_validate(config.model_dump())
        initial = HealthNow.model_validate(initial.model_dump())
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(descriptor)
        # Failures intentionally leave the suspect new path; never auto-delete/retry.
        with closing(sqlite3.connect(path)) as db, db:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("PRAGMA journal_mode=DELETE")
            db.execute(STATE_SQL)
            db.execute(NONCE_SQL)
            db.execute(
                "INSERT INTO guard_state VALUES (1,3,?,0,'',?,?,?,0,0,0,0,0)",
                (config.canonical(), initial.wall_ns, initial.monotonic_ns, initial.boottime_ns),
            )

    def inspect(self) -> tuple[GuardStateSnapshot, tuple[StoredNonce, ...]]:
        """Validate bounded existing state; never read evidence or modify rows.

        BEGIN IMMEDIATE provides the future write boundary, not authorization.
        Latched state denies; missing/legacy/invalid state is not rebuilt.
        """
        try:
            _file(self._path, self._config)
            uri = self._path.as_uri() + "?mode=rw"
            with closing(sqlite3.connect(uri, uri=True, timeout=0.25)) as db:
                if db.execute("PRAGMA journal_mode").fetchone() != ("delete",):
                    raise ValueError("Invalid state mode")
                db.execute("PRAGMA synchronous=FULL")
                db.execute("BEGIN IMMEDIATE")
                if db.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                    raise ValueError("Invalid integrity")
                actual = {
                    (kind, name, table): sql
                    for kind, name, table, sql in db.execute(
                        "SELECT type,name,tbl_name,sql FROM sqlite_master"
                    )
                }
                if actual != SCHEMA:
                    raise ValueError("Invalid schema")
                columns = [row[1] for row in db.execute("PRAGMA table_info(guard_state)")]
                rows = db.execute("SELECT * FROM guard_state LIMIT 2").fetchall()
                if len(rows) != 1:
                    raise ValueError("Invalid singleton")
                state = GuardStateSnapshot.model_validate(dict(zip(columns, rows[0], strict=True)))
                if state.unsafe or state.config != self._config.canonical():
                    raise ValueError("Invalid binding")
                rows = db.execute(
                    "SELECT nonce,expiry FROM guard_nonce ORDER BY nonce LIMIT ?",
                    (self._config.max_nonces + 1,),
                ).fetchall()
                if len(rows) > self._config.max_nonces:
                    raise ValueError("Invalid capacity")
                nonces = tuple(StoredNonce(nonce=nonce, expiry=expiry) for nonce, expiry in rows)
                _file(self._path, self._config)
                db.rollback()  # Read-only rows; never normalize or repair suspect data.
                return state, nonces
        except Exception:
            raise GuardStateDenied("Guard state denied") from None
