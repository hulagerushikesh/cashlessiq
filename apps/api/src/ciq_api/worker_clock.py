"""Inactive single-host clock guard. Explicit fake providers in offline tests only.

No default clock, health discovery, provisioning or runtime wiring. This cannot
detect a trusted administrator restoring an older complete database snapshot.
"""

import sqlite3
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

SECOND = 1_000_000_000
MAX_INTEGER = 2**63 - 1


class ClockDenied(Exception):
    """Generic safety denial without provider, file or source details."""


def _integer(value: object) -> bool:
    return type(value) is int and 0 <= value <= MAX_INTEGER


def _identity(value: object) -> bool:
    return isinstance(value, str) and 0 < len(value) <= 200 and value.isascii()


@dataclass(frozen=True)
class ClockSample:
    wall_ns: int
    monotonic_ns: int
    boot_id: str


@dataclass(frozen=True)
class ClockHealth:
    synchronized: bool
    error_ns: int
    observed_monotonic_ns: int


@dataclass(frozen=True)
class ClockLimits:
    """Explicit inputs, not approved production policy or recommended thresholds."""

    max_error_ns: int
    max_health_age_ns: int
    max_drift_ns: int
    max_gap_ns: int

    def __post_init__(self):
        if any(not _integer(value) or value == 0 for value in vars(self).values()):
            raise ValueError("Invalid clock limits")


class SqliteClockGuard:
    """Own durable state, optionally co-located with this authority's nonce ledger.

    BEGIN IMMEDIATE precedes sampling. Clock observations/latches commit even on
    ordinary token denial; unsafe observations never prune or consume a nonce.
    Existing-file connections only. No retries, reset, migration or memory fallback.
    File ownership/TOCTOU, real host health and power-loss acceptance remain gates.
    """

    def __init__(
        self,
        path: Path,
        *,
        authority: str,
        generation: str,
        sample: Callable[[], ClockSample],
        health: Callable[[], ClockHealth],
        limits: ClockLimits,
        capacity: int = 1000,
    ):
        if (
            not _identity(authority)
            or not _identity(generation)
            or not isinstance(limits, ClockLimits)
            or not callable(sample)
            or not callable(health)
            or type(capacity) is not int
            or capacity < 1
        ):
            raise ValueError("Invalid clock configuration")
        self._uri = path.resolve().as_uri() + "?mode=rw"
        self._authority = authority
        self._generation = generation
        self._sample = sample
        self._health = health
        self._limits = limits
        self._capacity = capacity

    @staticmethod
    def initialize_for_offline_test(
        path: Path, *, authority: str, generation: str, initial: ClockSample
    ) -> None:
        """Explicit new-file test provisioning, never startup or recovery."""
        if (
            not _identity(authority)
            or not _identity(generation)
            or not isinstance(initial, ClockSample)
            or not _integer(initial.wall_ns)
            or not _integer(initial.monotonic_ns)
            or not _identity(initial.boot_id)
        ):
            raise ValueError("Invalid initial clock state")
        path.touch(mode=0o600, exist_ok=False)
        with closing(sqlite3.connect(path)) as db, db:
            db.execute(
                "CREATE TABLE clock_state (singleton INTEGER PRIMARY KEY CHECK(singleton=1), "
                "version INTEGER NOT NULL, authority TEXT NOT NULL, generation TEXT NOT NULL, "
                "boot TEXT NOT NULL, wall INTEGER NOT NULL, mono INTEGER NOT NULL, "
                "unsafe INTEGER NOT NULL CHECK(unsafe IN (0,1)))"
            )
            db.execute(
                "INSERT INTO clock_state VALUES (1,1,?,?,?,?,?,0)",
                (authority, generation, initial.boot_id, initial.wall_ns, initial.monotonic_ns),
            )
            db.execute("CREATE TABLE clock_nonce (nonce TEXT PRIMARY KEY, expiry INTEGER NOT NULL)")

    def _state(self, db):
        if db.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
            raise ClockDenied("Clock access denied")
        rows = db.execute("SELECT * FROM clock_state").fetchall()
        columns = [row[1] for row in db.execute("PRAGMA table_info(clock_state)")]
        nonce_columns = [row[1] for row in db.execute("PRAGMA table_info(clock_nonce)")]
        if (
            columns
            != ["singleton", "version", "authority", "generation", "boot", "wall", "mono", "unsafe"]
            or nonce_columns != ["nonce", "expiry"]
            or len(rows) != 1
        ):
            raise ClockDenied("Clock access denied")
        singleton, version, authority, generation, boot, wall, mono, unsafe = rows[0]
        if (
            singleton != 1
            or version != 1
            or authority != self._authority
            or generation != self._generation
            or not _identity(boot)
            or not _integer(wall)
            or not _integer(mono)
            or unsafe != 0
        ):
            raise ClockDenied("Clock access denied")
        return boot, wall, mono

    def _observe(self, db) -> ClockSample | None:
        boot, wall, mono = self._state(db)
        try:
            sample = self._sample()
            health = self._health()
            safe = (
                isinstance(sample, ClockSample)
                and isinstance(health, ClockHealth)
                and _integer(sample.wall_ns)
                and _integer(sample.monotonic_ns)
                and sample.boot_id == boot
                and sample.wall_ns >= wall
                and sample.monotonic_ns >= mono
                and sample.monotonic_ns - mono <= self._limits.max_gap_ns
                and abs((sample.wall_ns - wall) - (sample.monotonic_ns - mono))
                <= self._limits.max_drift_ns
                and health.synchronized is True
                and _integer(health.error_ns)
                and health.error_ns <= self._limits.max_error_ns
                and _integer(health.observed_monotonic_ns)
                and 0
                <= sample.monotonic_ns - health.observed_monotonic_ns
                <= self._limits.max_health_age_ns
            )
        except Exception:
            safe = False
        if not safe:
            db.execute("UPDATE clock_state SET unsafe=1 WHERE singleton=1")
            return None
        db.execute(
            "UPDATE clock_state SET wall=?, mono=? WHERE singleton=1",
            (sample.wall_ns, sample.monotonic_ns),
        )
        return sample

    def _run(self, token: tuple[str, str, int, int] | None = None) -> int:
        denied = False
        try:
            with closing(sqlite3.connect(self._uri, uri=True, timeout=0.25)) as db:
                db.execute("PRAGMA synchronous=FULL")
                db.execute("BEGIN IMMEDIATE")
                sample = self._observe(db)
                denied = sample is None
                now = sample.wall_ns // SECOND if sample is not None else 0
                if token is not None and not denied:
                    namespace, nonce, expiry, supplied_now = token
                    denied = (
                        namespace != self._authority
                        or not _identity(nonce)
                        or not _integer(expiry)
                        or not _integer(supplied_now)
                        or supplied_now != now
                        or expiry <= now
                    )
                    if not denied:
                        db.execute("DELETE FROM clock_nonce WHERE expiry<=?", (now,))
                        denied = (
                            db.execute("SELECT COUNT(*) FROM clock_nonce").fetchone()[0]
                            >= self._capacity
                            or db.execute(
                                "SELECT 1 FROM clock_nonce WHERE nonce=?", (nonce,)
                            ).fetchone()
                            is not None
                        )
                        if not denied:
                            db.execute("INSERT INTO clock_nonce VALUES (?,?)", (nonce, expiry))
                db.commit()  # Persist observation/latch BEFORE raising ordinary denial.
            if denied:
                raise ClockDenied("Clock access denied")
            return now
        except Exception:
            raise ClockDenied("Clock access denied") from None

    def check(self) -> int:
        """Persist health/continuity observation and return safe integer seconds."""
        return self._run()

    def consume(self, namespace: str, nonce: str, expiry: int, now: int) -> None:
        """Explicit ReplayLedger adapter; namespace must match provisioned authority."""
        self._run((namespace, nonce, expiry, now))
