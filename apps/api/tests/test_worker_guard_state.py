"""Offline v3 schema/custody candidates; no authorization or live host work."""

import os
import sqlite3
from pathlib import Path

import pytest
from pydantic import ValidationError
from test_worker_health import policy as policy
from test_worker_health import setup as setup

from ciq_api.worker_guard_state import (
    GuardStateConfig,
    GuardStateDenied,
    OfflineGuardState,
)


@pytest.fixture
def state_setup(tmp_path, setup, policy):
    binding, _evidence, now = setup
    config = GuardStateConfig(
        authority="validator:tenant-one",
        assertion_generation="test-generation",
        health_key_sha256="a" * 64,
        binding=binding,
        health_policy=policy,
        max_gap_ns=10_000_000_000,
        max_step_ns=1_000_000_000,
        max_nonces=4,
        max_file_bytes=65_536,
    )
    path = tmp_path / "v3.sqlite"
    OfflineGuardState.initialize_for_offline_test(path, config=config, initial=now)
    return path, config, now


def test_explicit_new_state_reopens_without_conveying_readiness(state_setup):
    path, config, now = state_setup
    before = path.read_bytes()
    for _ in range(2):
        store = OfflineGuardState(path, config=config)
        snapshot, nonces = store.inspect()
        assert snapshot.version == 3 and snapshot.sequence == 0 and not snapshot.digest
        assert (snapshot.wall, snapshot.mono, snapshot.boottime) == (
            now.wall_ns,
            now.monotonic_ns,
            now.boottime_ns,
        )
        assert nonces == ()
        assert not hasattr(store, "check") and not hasattr(store, "consume")
    assert path.read_bytes() == before
    assert path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize(
    "field,value",
    [
        ("authority", "other"),
        ("assertion_generation", "other"),
        ("health_key_sha256", "b" * 64),
        ("max_gap_ns", 1),
        ("max_step_ns", 1),
        ("max_nonces", 5),
        ("max_file_bytes", 131_072),
        ("binding", None),
        ("health_policy", None),
    ],
)
def test_configuration_mismatch_preserves_state(state_setup, field, value):
    path, config, _now = state_setup
    if field == "binding":
        value = config.binding.model_copy(update={"host_id": "other-host"})
    elif field == "health_policy":
        value = config.health_policy.model_copy(update={"max_error_ns": 1})
    changed = GuardStateConfig.model_validate(config.model_dump() | {field: value})
    before = path.read_bytes()
    with pytest.raises(GuardStateDenied, match=r"^Guard state denied$"):
        OfflineGuardState(path, config=changed).inspect()
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "failure",
    [
        "missing",
        "corrupt",
        "legacy-v1",
        "legacy-v2",
        "schema",
        "trigger",
        "index",
        "constraints",
        "version",
        "empty",
        "unsafe",
        "bad-digest",
        "bad-sequence",
        "nonce-hash",
        "nonce-expiry",
        "nonce-capacity",
        "permissions",
        "oversize",
        "hardlink",
        "symlink",
        "wal",
    ],
)
def test_invalid_state_never_repaired(state_setup, failure):
    path, config, _now = state_setup
    if failure == "missing":
        path.unlink()
    elif failure == "corrupt":
        path.write_bytes(b"private corrupt state")
    elif failure == "permissions":
        path.chmod(0o644)
    elif failure == "oversize":
        with path.open("ab") as stream:
            stream.write(b"x" * config.max_file_bytes)
    elif failure in {"hardlink", "symlink"}:
        target = path.with_name("original.sqlite")
        path.rename(target)
        if failure == "hardlink":
            os.link(target, path)
        else:
            path.symlink_to(target)
    else:
        with sqlite3.connect(path) as db:
            if failure.startswith("legacy"):
                db.execute("DROP TABLE guard_state")
                prefix = "clock" if failure == "legacy-v1" else "health"
                db.execute(f"CREATE TABLE {prefix}_state (version INTEGER)")
            elif failure == "schema":
                db.execute("CREATE TABLE unrelated (value TEXT)")
            elif failure == "trigger":
                db.execute("CREATE TRIGGER extra AFTER INSERT ON guard_nonce BEGIN SELECT 1; END")
            elif failure == "index":
                db.execute("CREATE INDEX extra ON guard_nonce(expiry)")
            elif failure == "constraints":
                db.execute("ALTER TABLE guard_nonce RENAME TO old_nonce")
                db.execute("CREATE TABLE guard_nonce (nonce TEXT, expiry INTEGER)")
                db.execute("DROP TABLE old_nonce")
            elif failure == "wal":
                db.execute("PRAGMA journal_mode=WAL")
            elif failure == "version":
                db.execute("PRAGMA ignore_check_constraints=ON")
                db.execute("UPDATE guard_state SET version=99")
            elif failure == "empty":
                db.execute("DELETE FROM guard_state")
            elif failure == "unsafe":
                db.execute("UPDATE guard_state SET unsafe=1")
            elif failure == "bad-digest":
                db.execute("UPDATE guard_state SET digest='not-an-initial-digest'")
            elif failure == "bad-sequence":
                db.execute("UPDATE guard_state SET sequence=1")
            elif failure == "nonce-hash":
                db.execute("INSERT INTO guard_nonce VALUES ('not-a-hash',1030)")
            elif failure == "nonce-expiry":
                db.execute("INSERT INTO guard_nonce VALUES (?,?)", ("a" * 64, 2**63 - 1))
            else:
                db.executemany(
                    "INSERT INTO guard_nonce VALUES (?,1030)",
                    [(f"{number:064x}",) for number in range(5)],
                )
    before = path.read_bytes() if path.exists() else None
    with pytest.raises(GuardStateDenied, match=r"^Guard state denied$"):
        OfflineGuardState(path, config=config).inspect()
    assert (path.read_bytes() if path.exists() else None) == before


def test_provisioning_never_overwrites_or_accepts_wrong_boot(state_setup):
    path, config, now = state_setup
    before = path.read_bytes()
    with pytest.raises(FileExistsError):
        OfflineGuardState.initialize_for_offline_test(path, config=config, initial=now)
    assert path.read_bytes() == before
    absent = path.with_name("absent.sqlite")
    bad = now.model_copy(update={"boot_id": "00000000-0000-0000-0000-000000000099"})
    with pytest.raises(ValueError):
        OfflineGuardState.initialize_for_offline_test(absent, config=config, initial=bad)
    assert not absent.exists()


def test_nonce_shape_is_immutable_data_not_consumption(state_setup):
    path, config, _now = state_setup
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO guard_nonce VALUES (?,1030)", ("a" * 64,))
    before = path.read_bytes()
    _, nonces = OfflineGuardState(path, config=config).inspect()
    assert len(nonces) == 1 and nonces[0].expiry == 1030
    with pytest.raises(ValidationError):
        nonces[0].expiry = 2000
    assert path.read_bytes() == before


def test_lock_contention_denies_without_mutation(state_setup):
    path, config, _now = state_setup
    before = path.read_bytes()
    with sqlite3.connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        with pytest.raises(GuardStateDenied):
            OfflineGuardState(path, config=config).inspect()
    assert path.read_bytes() == before


def test_policy_fingerprint_is_canonical_and_all_settings_are_bound(state_setup):
    _path, config, _now = state_setup
    sources = config.health_policy.sources | {("C6336410", "198.51.100.16")}
    first = config.model_copy(
        update={
            "health_policy": config.health_policy.model_copy(
                update={"sources": frozenset(sorted(sources))}
            )
        }
    )
    second = config.model_copy(
        update={
            "health_policy": config.health_policy.model_copy(
                update={"sources": frozenset(reversed(sorted(sources)))}
            )
        }
    )
    assert first.canonical() == second.canonical()
    assert first.fingerprint == second.fingerprint != config.fingerprint


@pytest.mark.parametrize(
    "field,value",
    [
        ("max_nonces", True),
        ("max_nonces", 0),
        ("max_file_bytes", 1),
        ("health_key_sha256", "secret"),
        ("authority", "invalid space"),
        ("max_gap_ns", 0),
    ],
)
def test_config_rejects_invalid_inputs(state_setup, field, value):
    _path, config, _now = state_setup
    with pytest.raises(ValidationError):
        GuardStateConfig.model_validate(config.model_dump() | {field: value})


def test_constructor_rejects_non_path(state_setup):
    _path, config, _now = state_setup
    with pytest.raises(ValueError):
        OfflineGuardState("not-a-path", config=config)
    assert isinstance(_path, Path)


def test_model_copy_cannot_bypass_strict_provisioning(state_setup):
    path, config, now = state_setup
    absent = path.with_name("unprovisioned.sqlite")
    bad_config = config.model_copy(update={"max_nonces": True})
    with pytest.raises(ValidationError):
        OfflineGuardState(absent, config=bad_config)
    for arguments in (
        dict(config=bad_config, initial=now),
        dict(config=config, initial=now.model_copy(update={"wall_ns": True})),
    ):
        with pytest.raises(ValidationError):
            OfflineGuardState.initialize_for_offline_test(absent, **arguments)
        assert not absent.exists()


def test_prior_accepted_measurement_shape_is_data_only(state_setup):
    path, config, now = state_setup
    with sqlite3.connect(path) as db:
        db.execute(
            "UPDATE guard_state SET sequence=2,digest=?,end_wall=?,end_mono=?,"
            "end_boot=?,reference=?",
            ("b" * 64, now.wall_ns, now.monotonic_ns, now.boottime_ns, now.wall_ns - 1),
        )
    before = path.read_bytes()
    snapshot, _ = OfflineGuardState(path, config=config).inspect()
    assert snapshot.sequence == 2 and snapshot.digest == "b" * 64
    assert path.read_bytes() == before
