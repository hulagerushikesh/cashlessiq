"""Inactive v2 health continuity prototype; no v1 guard/runtime adapter.

Explicit offline provisioning only. Signatures and local samples are checked
under the write lock. Trusted whole-file rollback and mount/key custody are
outside this prototype's guarantees. No automatic migration, reset or recovery.
"""

import re
import sqlite3
from collections.abc import Callable
from contextlib import closing
from pathlib import Path

from ciq_api.worker_health import (
    MAX_INTEGER,
    CheckedHealthEnvelope,
    HealthBinding,
    HealthDenied,
    HealthNow,
    HealthPolicy,
    check_envelope,
)

COLUMNS = [
    "singleton",
    "version",
    "host",
    "boot",
    "generation",
    "epoch",
    "sequence",
    "digest",
    "wall",
    "mono",
    "boottime",
    "end_wall",
    "end_mono",
    "end_boot",
    "reference",
    "unsafe",
]


class RetainedHealthConsumer:
    """Separate retained evidence state, NOT token/replay or clock authorization."""

    def __init__(
        self,
        path: Path,
        *,
        binding: HealthBinding,
        policy: HealthPolicy,
        public_key: object,
        sample: Callable[[], HealthNow],
        max_gap_ns: int,
    ):
        if (
            not isinstance(binding, HealthBinding)
            or not isinstance(policy, HealthPolicy)
            or not callable(sample)
            or type(max_gap_ns) is not int
            or not 0 < max_gap_ns <= MAX_INTEGER
        ):
            raise ValueError("Invalid health configuration")
        self._uri = path.resolve().as_uri() + "?mode=rw"
        self._binding, self._policy = binding, policy
        self._key, self._sample, self._gap = public_key, sample, max_gap_ns

    @staticmethod
    def initialize_for_offline_test(
        path: Path,
        *,
        binding: HealthBinding,
        initial: HealthNow,
    ) -> None:
        """New private test file only; never called by startup or acceptance."""
        if (
            not isinstance(binding, HealthBinding)
            or not isinstance(initial, HealthNow)
            or initial.boot_id != binding.boot_id
            or initial.boottime_ns < initial.monotonic_ns
        ):
            raise ValueError("Invalid initial health state")
        path.touch(mode=0o600, exist_ok=False)
        with closing(sqlite3.connect(path)) as db, db:
            db.execute(
                "CREATE TABLE health_state (singleton INTEGER PRIMARY KEY CHECK(singleton=1), "
                "version INTEGER NOT NULL, host TEXT NOT NULL, boot TEXT NOT NULL, "
                "generation TEXT NOT NULL, epoch TEXT NOT NULL, sequence INTEGER NOT NULL, "
                "digest TEXT NOT NULL, wall INTEGER NOT NULL, mono INTEGER NOT NULL, "
                "boottime INTEGER NOT NULL, end_wall INTEGER NOT NULL, end_mono INTEGER NOT NULL, "
                "end_boot INTEGER NOT NULL, reference INTEGER NOT NULL, "
                "unsafe INTEGER NOT NULL CHECK(unsafe IN (0,1)))"
            )
            db.execute(
                "INSERT INTO health_state VALUES (1,2,?,?,?,?,0,'',?,?,?,0,0,0,0,0)",
                (
                    *binding.model_dump().values(),
                    initial.wall_ns,
                    initial.monotonic_ns,
                    initial.boottime_ns,
                ),
            )

    def _state(self, db):
        if db.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
            raise HealthDenied("Health evidence denied")
        if [row[1] for row in db.execute("PRAGMA table_info(health_state)")] != COLUMNS:
            raise HealthDenied("Health evidence denied")
        rows = db.execute("SELECT * FROM health_state").fetchall()
        if len(rows) != 1:
            raise HealthDenied("Health evidence denied")
        row = dict(zip(COLUMNS, rows[0], strict=True))
        identities = tuple(row[key] for key in ("host", "boot", "generation", "epoch"))
        numbers = (
            "sequence",
            "wall",
            "mono",
            "boottime",
            "end_wall",
            "end_mono",
            "end_boot",
            "reference",
        )
        if (
            row["singleton"] != 1
            or row["version"] != 2
            or row["unsafe"] != 0
            or identities != tuple(self._binding.model_dump().values())
            or any(type(row[key]) is not int or not 0 <= row[key] <= MAX_INTEGER for key in numbers)
            or row["boottime"] < row["mono"]
            or (
                row["sequence"] == 0
                and (
                    row["digest"] != ""
                    or any(
                        row[key] != 0 for key in ("end_wall", "end_mono", "end_boot", "reference")
                    )
                )
            )
            or (
                row["sequence"] > 0
                and (
                    not isinstance(row["digest"], str)
                    or not re.fullmatch(r"[0-9a-f]{64}", row["digest"])
                )
            )
        ):
            raise HealthDenied("Health evidence denied")
        return row

    def accept(self, token: Callable[[], str]) -> CheckedHealthEnvelope:
        """Revalidate original freshness even on identical repeated delivery.

        Any invalid/unavailable measurement latches a structurally valid state.
        Missing/corrupt/legacy/binding-mismatched state denies without rewriting it.
        Failed durable writes deny; they cannot promise a persisted latch.
        """
        try:
            with closing(sqlite3.connect(self._uri, uri=True, timeout=0.25)) as db:
                db.execute("PRAGMA synchronous=FULL")
                db.execute("BEGIN IMMEDIATE")
                row = self._state(db)
                try:
                    # Measure freshness after delivery, never reuse a sample
                    # taken before a potentially delayed evidence callback.
                    delivered = token()
                    now = self._sample()
                    if not isinstance(now, HealthNow):
                        raise ValueError("Invalid sample")
                    delta = [
                        now.wall_ns - row["wall"],
                        now.monotonic_ns - row["mono"],
                        now.boottime_ns - row["boottime"],
                    ]
                    if (
                        min(delta) < 0
                        or max(delta) > self._gap
                        or max(delta) - min(delta) > self._policy.max_read_skew_ns
                    ):
                        raise ValueError("Uncertain continuity")
                    checked = check_envelope(
                        delivered,
                        public_key=self._key,
                        binding=self._binding,
                        now=now,
                        policy=self._policy,
                    )
                    evidence = checked.evidence
                    ends = (
                        evidence.window.end_wall_ns,
                        evidence.window.end_monotonic_ns,
                        evidence.window.end_boottime_ns,
                        evidence.reference_wall_ns,
                    )
                    previous = tuple(
                        row[key] for key in ("end_wall", "end_mono", "end_boot", "reference")
                    )
                    if (
                        evidence.sequence < row["sequence"]
                        or (
                            evidence.sequence == row["sequence"]
                            and checked.content_sha256 != row["digest"]
                        )
                        or any(new < old for new, old in zip(ends, previous, strict=True))
                    ):
                        raise ValueError("Invalid continuity")
                except Exception:
                    db.execute("UPDATE health_state SET unsafe=1 WHERE singleton=1")
                    db.commit()
                    raise HealthDenied("Health evidence denied") from None
                db.execute(
                    "UPDATE health_state SET sequence=?,digest=?,wall=?,mono=?,boottime=?,"
                    "end_wall=?,end_mono=?,end_boot=?,reference=? WHERE singleton=1",
                    (
                        evidence.sequence,
                        checked.content_sha256,
                        now.wall_ns,
                        now.monotonic_ns,
                        now.boottime_ns,
                        *ends,
                    ),
                )
                db.commit()
                return checked
        except Exception:
            raise HealthDenied("Health evidence denied") from None
