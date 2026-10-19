"""Offline same-host replay candidate; not wired to startup or a deployed worker.

All processes for one authority must use the same retained local database file.
Deleting/restoring that file, using separate files or a network filesystem is not
supported. Host/file administrators remain trusted. No token or payload is stored.
"""

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Protocol


class ReplayLedger(Protocol):
    def consume(self, namespace: str, nonce: str, expiry: int, now: int) -> None:
        """Atomically consume once or raise; storage failure must deny access."""


class SqliteReplayLedger:
    """Explicit test-only provisioning, then existing-file connections per request.

    SQLite serializes consumers across processes. A short lock timeout denies on
    contention; it does not retry or fall back to process-local state. Capacity
    is per namespace, not per process. This is not a distributed-host solution.
    """

    def __init__(self, path: Path, *, capacity: int = 1000):
        if type(capacity) is not int or capacity < 1:
            raise ValueError("Invalid replay configuration")
        self._uri = path.resolve().as_uri() + "?mode=rw"
        self._capacity = capacity

    @staticmethod
    def initialize_for_offline_test(path: Path) -> None:
        """Create a new local test ledger; refuse to replace any existing file."""
        path.touch(mode=0o600, exist_ok=False)
        with closing(sqlite3.connect(path)) as connection:
            connection.execute(
                "CREATE TABLE used_assertion ("
                "namespace TEXT NOT NULL, nonce TEXT NOT NULL, expiry INTEGER NOT NULL, "
                "PRIMARY KEY (namespace, nonce))"
            )
            connection.commit()

    def consume(self, namespace: str, nonce: str, expiry: int, now: int) -> None:
        if (
            not namespace
            or not nonce
            or type(now) is not int
            or type(expiry) is not int
            or expiry <= now
        ):
            raise ValueError("Replay denied")
        with closing(sqlite3.connect(self._uri, uri=True, timeout=0.25)) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "DELETE FROM used_assertion WHERE namespace = ? AND expiry <= ?",
                (namespace, now),
            )
            count = connection.execute(
                "SELECT COUNT(*) FROM used_assertion WHERE namespace = ?", (namespace,)
            ).fetchone()[0]
            if count >= self._capacity:
                raise ValueError("Replay denied")
            connection.execute(
                "INSERT INTO used_assertion (namespace, nonce, expiry) VALUES (?, ?, ?)",
                (namespace, nonce, expiry),
            )
