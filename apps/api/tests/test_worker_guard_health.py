"""Disposable v3 state, independently signed fake health and injected clocks only."""

import sqlite3
from hashlib import sha256
from unittest.mock import Mock

import pytest
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from test_worker_guard_state import state_setup as state_setup
from test_worker_health import key as key
from test_worker_health import policy as policy
from test_worker_health import setup as setup

from ciq_api import worker_guard_health
from ciq_api.worker_guard_health import ObservedInterval, OfflineHealthGuard
from ciq_api.worker_guard_state import GuardStateConfig, GuardStateDenied, OfflineGuardState
from ciq_api.worker_health import MAX_INTEGER, SECOND, check_envelope, sign_for_offline_test


@pytest.fixture
def health(state_setup, setup, key, request):
    old_path, original, now = state_setup
    _binding, evidence, _now = setup
    config = GuardStateConfig.model_validate(
        original.model_dump()
        | {
            "health_key_sha256": sha256(
                key.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
            ).hexdigest()
        }
    )
    if "stale" in getattr(request.node, "callspec", Mock(params={})).params.get("failure", ""):
        config = config.model_copy(update={"max_step_ns": 4 * SECOND})
    path = old_path.with_name("health-v3.sqlite")
    OfflineGuardState.initialize_for_offline_test(path, config=config, initial=now)
    clock = [now]
    token = [sign_for_offline_test(evidence, key)]
    sample, delivery = Mock(side_effect=lambda: clock[0]), Mock(side_effect=lambda: token[0])

    def reopen(**overrides):
        return OfflineHealthGuard(
            path,
            config=config,
            public_key=key.public_key(),
            sample=overrides.get("sample", sample),
        )

    return path, config, evidence, clock, token, sample, delivery, reopen


def stored(path):
    with sqlite3.connect(path) as db:
        return (
            db.execute("SELECT * FROM guard_state").fetchone(),
            db.execute("SELECT * FROM guard_nonce ORDER BY nonce").fetchall(),
        )


def advance(now, amount):
    return now.model_copy(
        update={
            "wall_ns": now.wall_ns + amount,
            "monotonic_ns": now.monotonic_ns + amount,
            "boottime_ns": now.boottime_ns + amount,
        }
    )


def test_healthy_observation_reopens_and_uses_final_uncertainty(health, key):
    path, config, _evidence, clock, token, sample, delivery, reopen = health
    initial = clock[0]
    samples = [initial, advance(initial, 100), advance(initial, 200)]
    result = reopen(sample=Mock(side_effect=samples)).observe(delivery)
    checked = check_envelope(
        token[0],
        public_key=key.public_key(),
        binding=config.binding,
        now=samples[-1],
        policy=config.health_policy,
    )
    assert result.lower_ns == samples[-1].wall_ns - checked.error_ns
    assert result.upper_ns == samples[-1].wall_ns + checked.error_ns
    snapshot, nonces = reopen().inspect()
    assert snapshot.sequence == 1 and snapshot.digest == checked.content_sha256
    assert snapshot.wall == samples[-1].wall_ns and nonces == ()
    clock[0] = samples[-1]
    assert reopen().observe(delivery) == result
    assert sample.call_count == 3 and delivery.call_count == 2
    assert not hasattr(reopen(), "consume")
    assert stored(path)[0][-1] == 0


@pytest.mark.parametrize(
    "failure",
    [
        "signature",
        "missing",
        "oversize",
        "wrong-epoch",
        "wrong-boot",
        "sample-type",
        "sample-bool",
        "wall-rollback",
        "mono-rollback",
        "boot-rollback",
        "suspend",
        "gap",
        "delivery-stale",
        "verification-stale",
        "delivery-step",
        "verification-step",
        "total-step",
        "sequence-regression",
        "sequence-conflict",
        "end-regression",
        "reference-regression",
        "uncertainty",
    ],
)
def test_health_failures_latch_only_and_survive_reopen(health, key, monkeypatch, failure):
    path, config, evidence, clock, token, sample, delivery, reopen = health
    reopen().observe(delivery)
    with sqlite3.connect(path) as db:
        # Even a definitely expired nonce must not be pruned on unsafe time.
        db.execute("INSERT INTO guard_nonce VALUES (?,1)", ("a" * 64,))
    before, before_nonces = stored(path)
    original = clock[0]
    if failure == "signature":
        token[0] = token[0][:-8] + "AAAAAAAA"
    elif failure == "missing":
        delivery.side_effect = RuntimeError("private collector path")
    elif failure == "oversize":
        token[0] = "x" * 8193
    elif failure == "wrong-epoch":
        token[0] = sign_for_offline_test(
            evidence.model_copy(update={"collector_epoch": "00000000-0000-0000-0000-000000000099"}),
            key,
        )
    elif failure == "wrong-boot":
        clock[0] = original.model_copy(update={"boot_id": "00000000-0000-0000-0000-000000000099"})
    elif failure == "sample-type":
        clock[0] = object()
    elif failure == "sample-bool":
        clock[0] = original.model_copy(update={"wall_ns": True})
    elif failure.endswith("rollback"):
        field = {
            "wall-rollback": "wall_ns",
            "mono-rollback": "monotonic_ns",
            "boot-rollback": "boottime_ns",
        }[failure]
        clock[0] = original.model_copy(update={field: getattr(original, field) - 1})
    elif failure == "suspend":
        clock[0] = original.model_copy(update={"boottime_ns": original.boottime_ns + SECOND})
    elif failure == "gap":
        clock[0] = advance(original, config.max_gap_ns + 1)
    elif failure in {"delivery-stale", "delivery-step"}:
        amount = 3 * SECOND if failure == "delivery-stale" else config.max_step_ns + 1

        def deliver_late():
            clock[0] = advance(original, amount)
            return token[0]

        delivery.side_effect = deliver_late
    elif failure in {"verification-stale", "verification-step"}:
        real_check = worker_guard_health.check_envelope

        def delayed(*args, **kwargs):
            checked = real_check(*args, **kwargs)
            amount = 3 * SECOND if failure == "verification-stale" else config.max_step_ns + 1
            clock[0] = advance(original, amount)
            return checked

        monkeypatch.setattr(worker_guard_health, "check_envelope", delayed)
    elif failure == "total-step":
        sample.side_effect = [
            original,
            advance(original, 600_000_000),
            advance(original, 1_200_000_000),
        ]
    else:
        changes = {"sequence": 2}
        if failure == "sequence-regression":
            with sqlite3.connect(path) as db:
                db.execute("UPDATE guard_state SET sequence=2")
            before, before_nonces = stored(path)
            changes = {"sequence": 1}
        elif failure == "sequence-conflict":
            changes = {"sequence": 1, "base_error_ns": evidence.base_error_ns + 1}
        elif failure == "end-regression":
            changes["window"] = evidence.window.model_copy(
                update={
                    "end_wall_ns": evidence.window.end_wall_ns - 1,
                    "end_monotonic_ns": evidence.window.end_monotonic_ns - 1,
                    "end_boottime_ns": evidence.window.end_boottime_ns - 1,
                }
            )
        elif failure == "reference-regression":
            changes["reference_wall_ns"] = evidence.reference_wall_ns - 1
        elif failure == "uncertainty":
            changes["base_error_ns"] = config.health_policy.max_error_ns + 1
        token[0] = sign_for_offline_test(evidence.model_copy(update=changes), key)
    with pytest.raises(GuardStateDenied, match=r"^Guard state denied$"):
        reopen().observe(delivery)
    after, nonces = stored(path)
    assert after[:-1] == before[:-1] and after[-1] == 1
    assert nonces == before_nonces
    clock[0] = original
    sample.side_effect = lambda: clock[0]
    delivery.side_effect = lambda: sign_for_offline_test(evidence, key)
    sample.reset_mock()
    delivery.reset_mock()
    with pytest.raises(GuardStateDenied):
        reopen().observe(delivery)
    sample.assert_not_called()
    delivery.assert_not_called()


@pytest.mark.parametrize("failure", ["missing", "schema", "config", "locked"])
def test_state_denial_precedes_all_callbacks(health, failure):
    path, _config, _evidence, _clock, _token, sample, delivery, reopen = health
    connection = sqlite3.connect(path)
    try:
        if failure == "missing":
            path.unlink()
        elif failure == "schema":
            connection.execute("CREATE TABLE unexpected (x INTEGER)")
            connection.commit()
        elif failure == "config":
            connection.execute("UPDATE guard_state SET config='{}'")
            connection.commit()
        else:
            connection.execute("BEGIN IMMEDIATE")
        before = path.read_bytes() if path.exists() else None
        with pytest.raises(GuardStateDenied):
            reopen().observe(delivery)
        assert (path.read_bytes() if path.exists() else None) == before
        sample.assert_not_called()
        delivery.assert_not_called()
    finally:
        connection.close()


def test_key_pin_mismatch_fails_without_state_mutation(health, key):
    path, config, _evidence, _clock, _token, sample, _delivery, _reopen = health
    before = path.read_bytes()
    changed = config.model_copy(update={"health_key_sha256": "f" * 64})
    with pytest.raises(ValueError, match="Invalid guard health configuration"):
        OfflineHealthGuard(path, config=changed, public_key=key.public_key(), sample=sample)
    assert path.read_bytes() == before
    sample.assert_not_called()


@pytest.mark.parametrize(
    "wall,error",
    [(0, 1), (MAX_INTEGER, 1), (-1, 0), (1, -1), (True, 0), (1, True), (1.0, 0)],
)
def test_interval_arithmetic_never_clamps_or_accepts_nonintegers(wall, error):
    with pytest.raises(ValueError, match="Invalid interval arithmetic"):
        ObservedInterval.from_wall_error(wall, error)


@pytest.mark.parametrize("wall,error", [(0, 0), (10, 10), (MAX_INTEGER - 5, 5)])
def test_interval_inclusive_extreme_boundaries(wall, error):
    result = ObservedInterval.from_wall_error(wall, error)
    assert (result.lower_ns, result.upper_ns) == (wall - error, wall + error)


def test_advancing_measurement_updates_all_highwaters_without_nonce_changes(health, key):
    path, _config, evidence, clock, token, _sample, delivery, reopen = health
    reopen().observe(delivery)
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO guard_nonce VALUES (?,1)", ("b" * 64,))
    window = evidence.window.model_copy(
        update={name: value + 1000 for name, value in evidence.window.model_dump().items()}
    )
    next_evidence = evidence.model_copy(
        update={
            "sequence": 2,
            "window": window,
            "reference_wall_ns": evidence.reference_wall_ns + 1000,
        }
    )
    token[0] = sign_for_offline_test(next_evidence, key)
    clock[0] = advance(clock[0], 1000)
    reopen().observe(delivery)
    snapshot, nonces = reopen().inspect()
    assert snapshot.sequence == 2 and snapshot.wall == clock[0].wall_ns
    assert snapshot.reference == next_evidence.reference_wall_ns
    assert snapshot.end_wall == window.end_wall_ns
    assert snapshot.end_mono == window.end_monotonic_ns
    assert snapshot.end_boot == window.end_boottime_ns
    assert len(nonces) == 1 and nonces[0].expiry == 1
