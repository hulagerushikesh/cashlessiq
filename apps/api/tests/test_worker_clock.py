"""Fake time/health and disposable SQLite only; no real host clock changes."""

import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from unittest.mock import Mock

import pytest

from ciq_api.worker_clock import (
    SECOND,
    ClockDenied,
    ClockHealth,
    ClockLimits,
    ClockSample,
    SqliteClockGuard,
)


@pytest.fixture
def setup(tmp_path):
    path = tmp_path / "clock.sqlite"
    initial = ClockSample(1000 * SECOND, 10 * SECOND, "test-boot")
    state = {"sample": initial, "health": ClockHealth(True, 1, initial.monotonic_ns)}
    SqliteClockGuard.initialize_for_offline_test(
        path, authority="validator", generation="test-generation", initial=initial
    )

    def build(**changes):
        arguments = dict(
            authority="validator",
            generation="test-generation",
            sample=lambda: state["sample"],
            health=lambda: state["health"],
            limits=ClockLimits(100, SECOND, SECOND, 60 * SECOND),
        )
        arguments.update(changes)
        return SqliteClockGuard(path, **arguments)

    def advance(seconds):
        state["sample"] = replace(
            initial,
            wall_ns=initial.wall_ns + seconds * SECOND,
            monotonic_ns=initial.monotonic_ns + seconds * SECOND,
        )
        state["health"] = ClockHealth(True, 1, state["sample"].monotonic_ns)

    return path, state, initial, build, advance


def persisted(path):
    with sqlite3.connect(path) as db:
        return db.execute("SELECT wall, mono, unsafe FROM clock_state").fetchone()


def test_forward_prune_then_rollback_cannot_reuse_nonce(setup):
    path, _, initial, build, advance = setup
    build().consume("validator", "A", 1030, 1000)
    advance(30)
    build().consume("validator", "B", 1060, 1030)
    advance(1)
    with pytest.raises(ClockDenied, match=r"^Clock access denied$"):
        build().consume("validator", "A", 1030, 1001)
    assert persisted(path) == (1030 * SECOND, initial.monotonic_ns + 30 * SECOND, 1)
    advance(31)
    with pytest.raises(ClockDenied):
        build().check()


@pytest.mark.parametrize(
    "failure",
    [
        "backward",
        "mono_backward",
        "forward_jump",
        "boot",
        "gap",
        "unsynchronized",
        "stale",
        "future_health",
        "uncertain",
        "bool_wall",
        "negative_mono",
        "provider",
    ],
)
def test_unsafe_observation_latches_without_pruning_or_consuming(setup, failure):
    path, state, initial, build, advance = setup
    guard = build()
    guard.consume("validator", "retained", 1030, 1000)
    if failure == "backward":
        state["sample"] = replace(initial, wall_ns=initial.wall_ns - 1)
    elif failure == "mono_backward":
        state["sample"] = replace(initial, monotonic_ns=initial.monotonic_ns - 1)
    elif failure == "forward_jump":
        state["sample"] = replace(initial, wall_ns=2000 * SECOND)
    elif failure == "boot":
        state["sample"] = replace(initial, boot_id="another-boot")
    elif failure == "gap":
        advance(61)
    elif failure == "unsynchronized":
        state["health"] = replace(state["health"], synchronized=False)
    elif failure == "stale":
        state["health"] = replace(state["health"], observed_monotonic_ns=0)
    elif failure == "future_health":
        state["health"] = replace(state["health"], observed_monotonic_ns=initial.monotonic_ns + 1)
    elif failure == "uncertain":
        state["health"] = replace(state["health"], error_ns=101)
    elif failure == "bool_wall":
        state["sample"] = replace(initial, wall_ns=True)
    elif failure == "negative_mono":
        state["sample"] = replace(initial, monotonic_ns=-1)
    else:
        guard = build(health=Mock(side_effect=RuntimeError("private provider detail")))
    with pytest.raises(ClockDenied, match=r"^Clock access denied$"):
        guard.consume("validator", "new", 3000, 2000)
    assert persisted(path) == (initial.wall_ns, initial.monotonic_ns, 1)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT nonce FROM clock_nonce").fetchall() == [("retained",)]
    advance(1)
    with pytest.raises(ClockDenied):
        build().check()


@pytest.mark.parametrize("failure", ["duplicate", "full", "expired", "wrong_namespace"])
def test_ordinary_denial_still_commits_forward_observation(setup, failure):
    path, _, _, build, advance = setup
    guard = build(capacity=1 if failure == "full" else 1000)
    guard.consume("validator", "A", 1030, 1000)
    advance(1)
    with pytest.raises(ClockDenied):
        guard.consume(
            "foreign" if failure == "wrong_namespace" else "validator",
            "A" if failure == "duplicate" else "B",
            1001 if failure == "expired" else 1030,
            1001,
        )
    assert persisted(path)[0] == 1001 * SECOND
    advance(0)
    with pytest.raises(ClockDenied):
        build().check()
    assert persisted(path)[2] == 1


def test_same_sample_concurrent_consumers_and_restart(setup):
    _, _, _, build, _ = setup

    def consume(_):
        try:
            build().consume("validator", "once", 1030, 1000)
            return True
        except ClockDenied:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(consume, range(8))) == 1
    assert build().check() == 1000


def test_sampling_occurs_only_after_database_lock(setup):
    path, _, _, build, _ = setup
    sample = Mock(side_effect=AssertionError("must not sample before lock"))
    with sqlite3.connect(path) as blocker:
        blocker.execute("BEGIN IMMEDIATE")
        with pytest.raises(ClockDenied):
            build(sample=sample).check()
    sample.assert_not_called()


@pytest.mark.parametrize("failure", ["missing", "corrupt", "legacy", "version", "generation"])
def test_invalid_existing_state_denies_without_reset(setup, failure):
    path, _, _, build, _ = setup
    if failure == "missing":
        path.unlink()
    elif failure == "corrupt":
        path.write_bytes(b"not a sqlite database")
    else:
        with sqlite3.connect(path) as db:
            if failure == "legacy":
                db.execute("DROP TABLE clock_state")
            elif failure == "version":
                db.execute("UPDATE clock_state SET version=99")
            else:
                db.execute("UPDATE clock_state SET generation='old-generation'")
    before = path.read_bytes() if path.exists() else None
    with pytest.raises(ClockDenied):
        build().check()
    assert (path.read_bytes() if path.exists() else None) == before


def test_failed_latch_write_denies_without_nonce_use(setup):
    path, state, initial, build, _ = setup
    with sqlite3.connect(path) as db:
        db.execute(
            "CREATE TRIGGER refuse_latch BEFORE UPDATE ON clock_state "
            "WHEN NEW.unsafe=1 BEGIN SELECT RAISE(ABORT, 'private failure'); END"
        )
    state["sample"] = replace(initial, wall_ns=initial.wall_ns - 1)
    with pytest.raises(ClockDenied, match=r"^Clock access denied$"):
        build().check()
    # Persistence failed; denial is guaranteed, not durable latching through a
    # failed disk. Repeated unsafe samples must still deny, with no nonce use.
    with pytest.raises(ClockDenied):
        build().consume("validator", "A", 1030, 1000)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM clock_nonce").fetchone()[0] == 0


@pytest.mark.parametrize("latched", [False, True])
def test_new_process_preserves_replay_or_unsafe_latch(setup, latched):
    path, state, initial, build, _ = setup
    build().consume("validator", "prior-process", 1030, 1000)
    if latched:
        state["sample"] = replace(initial, boot_id="new-boot")
        with pytest.raises(ClockDenied):
            build().check()
    code = """
import sys
from pathlib import Path
from ciq_api.worker_clock import *
guard = SqliteClockGuard(Path(sys.argv[1]), authority='validator',
 generation='test-generation', sample=lambda: ClockSample(1000*SECOND,10*SECOND,'test-boot'),
 health=lambda: ClockHealth(True,1,10*SECOND), limits=ClockLimits(100,SECOND,SECOND,60*SECOND))
try:
 guard.check()
except ClockDenied:
 sys.exit(0 if sys.argv[2] == 'True' else 1)
if sys.argv[2] == 'True':
 sys.exit(1)
try:
 guard.consume('validator','prior-process',1030,1000)
except ClockDenied:
 guard.consume('validator','fresh-process',1030,1000)
 sys.exit(0)
sys.exit(1)
"""
    assert (
        subprocess.run([sys.executable, "-c", code, str(path), str(latched)], timeout=5).returncode
        == 0
    )


@pytest.mark.parametrize("value", [0, -1, True, 1.5, 2**63])
def test_limits_require_explicit_positive_bounded_integers(value):
    with pytest.raises(ValueError):
        ClockLimits(value, SECOND, SECOND, 60 * SECOND)


def test_provisioning_never_overwrites_existing_state(setup):
    path, _, initial, _, _ = setup
    before = path.read_bytes()
    with pytest.raises(FileExistsError):
        SqliteClockGuard.initialize_for_offline_test(
            path, authority="validator", generation="new", initial=initial
        )
    assert path.read_bytes() == before
