"""Offline atomic consumption, real-process replay and stopped recovery only."""

import multiprocessing
import sqlite3
from hashlib import sha256

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from test_worker_guard_health import advance, stored
from test_worker_guard_health import health as health
from test_worker_guard_state import state_setup as state_setup
from test_worker_health import key as key
from test_worker_health import policy as policy
from test_worker_health import setup as setup

from ciq_api.worker_guard_health import ObservedInterval, OfflineHealthGuard, VerifiedGuardClaims
from ciq_api.worker_guard_state import GuardStateDenied, OfflineGuardState
from ciq_api.worker_health import SECOND, sign_for_offline_test


def claims_for(config, **changes):
    return VerifiedGuardClaims.model_validate(
        dict(
            authority=config.authority,
            assertion_generation=config.assertion_generation,
            nonce="c" * 64,
            iat=999,
            exp=1029,
        )
        | changes
    )


@pytest.mark.parametrize(
    "lower,upper,iat,exp,allowed",
    [
        (1000 * SECOND, 1000 * SECOND, 1000, 1030, True),
        (1000 * SECOND - 1, 1000 * SECOND, 1000, 1030, False),
        (1000 * SECOND, 1001 * SECOND - 1, 999, 1001, True),
        (1000 * SECOND, 1001 * SECOND, 999, 1001, False),
        (1000 * SECOND, 1000 * SECOND, 1000, 1031, False),
        (1000 * SECOND, 1000 * SECOND, 1000, 1000, False),
        (1000 * SECOND, 1000 * SECOND, 1001, 1000, False),
    ],
)
def test_exact_claim_interval_boundaries(health, lower, upper, iat, exp, allowed):
    config = health[1]
    interval = ObservedInterval(lower_ns=lower, upper_ns=upper)
    assert interval.permits(claims_for(config, iat=iat, exp=exp)) is allowed


@pytest.mark.parametrize(
    "changes",
    [
        {"authority": "other"},
        {"assertion_generation": "old"},
        {"iat": 1001},
        {"exp": 1000},
        {"exp": 1031},
        {"exp": 999},
    ],
)
def test_ordinary_rejection_commits_observation_without_latching(health, changes):
    path, config, _e, _c, _t, _s, delivery, reopen = health
    with pytest.raises(GuardStateDenied):
        reopen().consume_verified(delivery, claims_for(config, **changes))
    state, nonces = reopen().inspect()
    assert state.sequence == 1 and state.unsafe == 0 and nonces == ()
    assert stored(path)[0][-1] == 0


def test_atomic_success_reopen_replay_capacity_and_conservative_pruning(health):
    path, config, _e, clock, _t, _s, delivery, reopen = health
    claim = claims_for(config)
    reopen().consume_verified(delivery, claim)
    clock[0] = advance(clock[0], 100)
    with pytest.raises(GuardStateDenied):
        reopen().consume_verified(delivery, claim)
    state, nonces = reopen().inspect()
    assert state.wall == clock[0].wall_ns and len(nonces) == 1
    with sqlite3.connect(path) as db:
        # Expiry 1000 is definitely past at this sample. 1001 is not.
        for name, expiry in [("a", 1000), ("b", 1001), ("d", 1029)]:
            db.execute("INSERT INTO guard_nonce VALUES (?,?)", (name * 64, expiry))
    reopen().consume_verified(delivery, claims_for(config, nonce="e" * 64))
    _state, nonces = reopen().inspect()
    assert {n.nonce for n in nonces} == {c * 64 for c in "bcde"}
    clock[0] = advance(clock[0], 100)
    with pytest.raises(GuardStateDenied):
        reopen().consume_verified(delivery, claims_for(config, nonce="f" * 64))
    assert reopen().inspect()[0].wall == clock[0].wall_ns
    assert len(reopen().inspect()[1]) == config.max_nonces


def test_unsafe_consumption_neither_prunes_nor_inserts(health):
    path, config, _e, _clock, token, _s, delivery, reopen = health
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO guard_nonce VALUES (?,1)", ("a" * 64,))
    before = stored(path)
    token[0] = "invalid"
    with pytest.raises(GuardStateDenied):
        reopen().consume_verified(delivery, claims_for(config))
    after = stored(path)
    assert after[0][:-1] == before[0][:-1] and after[0][-1] == 1
    assert after[1] == before[1]


def test_expiry_uses_final_sample_not_preverification_time(health):
    _p, config, _e, clock, _t, _s, delivery, reopen = health
    initial = clock[0]
    samples = iter([initial, initial, advance(initial, SECOND)])
    with pytest.raises(GuardStateDenied):
        reopen(sample=lambda: next(samples)).consume_verified(
            delivery, claims_for(config, exp=1001)
        )
    state, nonces = reopen().inspect()
    assert state.wall == initial.wall_ns + SECOND
    assert state.unsafe == 0 and nonces == ()


def test_consumption_lock_denies_before_callbacks_and_preserves_rows(health):
    path, config, _e, _c, _t, sample, delivery, reopen = health
    before = stored(path)
    with sqlite3.connect(path) as locked:
        locked.execute("BEGIN IMMEDIATE")
        with pytest.raises(GuardStateDenied):
            reopen().consume_verified(delivery, claims_for(config))
    sample.assert_not_called()
    delivery.assert_not_called()
    assert stored(path) == before


@pytest.mark.parametrize("changes", [{"iat": True}, {"exp": 1.2}, {"nonce": "raw-jti"}])
def test_unvalidated_copied_claims_deny_before_callbacks(health, changes):
    path, config, _e, _clock, _t, sample, delivery, reopen = health
    before = path.read_bytes()
    with pytest.raises(GuardStateDenied):
        reopen().consume_verified(delivery, claims_for(config).model_copy(update=changes))
    sample.assert_not_called()
    delivery.assert_not_called()
    assert path.read_bytes() == before


def process_consume(path, config, pem, now, token, claims, ready, start, results):
    """Fresh interpreter, independent connection and independently loaded key."""
    guard = OfflineHealthGuard(
        path,
        config=config,
        public_key=serialization.load_pem_public_key(pem),
        sample=lambda: now,
    )
    ready.put(True)
    if not start.wait(10):
        results.put("timeout")
        return
    try:
        guard.consume_verified(lambda: token, claims)
        results.put("accepted")
    except GuardStateDenied:
        results.put("denied")


def run_processes(health, key, claims, count=1):
    path, config, _e, clock, token, _s, _d, _r = health
    ctx = multiprocessing.get_context("spawn")
    ready, results, start = ctx.Queue(), ctx.Queue(), ctx.Event()
    pem = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    workers = [
        ctx.Process(
            target=process_consume,
            args=(path, config, pem, clock[0], token[0], claims, ready, start, results),
        )
        for _ in range(count)
    ]
    try:
        for worker in workers:
            worker.start()
        for _ in workers:
            assert ready.get(timeout=15) is True
        start.set()
        outcomes = [results.get(timeout=15) for _ in workers]
        for worker in workers:
            worker.join(timeout=10)
            assert worker.exitcode == 0
        return outcomes
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
                worker.join(timeout=5)
        ready.close()
        results.close()


def test_concurrent_processes_accept_once_and_restart_cannot_replay(health, key):
    claim = claims_for(health[1])
    assert sorted(run_processes(health, key, claim, count=3)) == ["accepted", "denied", "denied"]
    assert run_processes(health, key, claim) == ["denied"]
    assert len(health[-1]().inspect()[1]) == 1


def test_latch_survives_fresh_process_with_restored_health(health, key):
    token = health[4]
    original = token[0]
    token[0] = "invalid"
    with pytest.raises(GuardStateDenied):
        health[-1]().observe(health[-2])
    token[0] = original
    assert run_processes(health, key, claims_for(health[1])) == ["denied"]


@pytest.mark.parametrize(
    "fault", ["write", "observation-write", "commit-before", "commit-after", "latch-commit"]
)
def test_storage_faults_never_report_success_or_retry(health, monkeypatch, fault):
    path, config, _e, _c, token, _s, delivery, reopen = health
    before = stored(path)
    original = sqlite3.connect
    commits = []

    class FaultConnection(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            if fault == "write" and sql.startswith("INSERT INTO guard_nonce"):
                raise sqlite3.OperationalError("private storage details")
            if fault == "observation-write" and sql.startswith("UPDATE guard_state SET sequence"):
                raise sqlite3.OperationalError("private storage details")
            return super().execute(sql, parameters)

        def commit(self):
            commits.append(True)
            if fault == "commit-after":
                super().commit()
            raise sqlite3.OperationalError("ambiguous private commit")

    def connect(*args, **kwargs):
        return original(*args, **kwargs, factory=FaultConnection)

    if fault == "latch-commit":
        token[0] = "invalid"
    with monkeypatch.context() as patch:
        patch.setattr(sqlite3, "connect", connect)
        with pytest.raises(GuardStateDenied, match=r"^Guard state denied$"):
            reopen().consume_verified(delivery, claims_for(config))
    assert len(commits) == (0 if fault in {"write", "observation-write"} else 1)
    after = stored(path)
    if fault == "commit-after":
        assert after[0][3] == 1 and after[1] == [("c" * 64, 1029)]
        # Acknowledgement failed, but committed consumption must not be refunded.
        with pytest.raises(GuardStateDenied):
            reopen().consume_verified(delivery, claims_for(config))
    else:
        assert after == before


def test_stopped_recovery_rotates_trust_and_preserves_old_authorities(health, key):
    path, config, evidence, clock, token, _s, delivery, reopen = health
    # No listeners or issuers are running. Preserve both authorities' old files.
    old_claim = claims_for(config)
    reopen().observe(delivery)
    old_paths = [path]
    for role in ("reader", "validator"):
        old = path.with_name(f"old-{role}.sqlite")
        OfflineGuardState.initialize_for_offline_test(old, config=config, initial=clock[0])
        old_paths.append(old)
    preserved = {old: old.read_bytes() for old in old_paths}
    fresh_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    binding = config.binding.model_copy(
        update={
            "health_generation": "00000000-0000-0000-0000-000000000098",
            "collector_epoch": "00000000-0000-0000-0000-000000000099",
        }
    )
    fresh_config = config.model_copy(
        update={
            "assertion_generation": "rotated-generation",
            "binding": binding,
            "health_key_sha256": sha256(
                fresh_key.public_key().public_bytes(
                    serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
                )
            ).hexdigest(),
        }
    )
    fresh_evidence = evidence.model_copy(update=binding.model_dump())
    fresh_token = sign_for_offline_test(fresh_evidence, fresh_key)
    for role in ("reader", "validator"):
        fresh_path = path.with_name(f"new-{role}.sqlite")
        OfflineGuardState.initialize_for_offline_test(
            fresh_path, config=fresh_config, initial=clock[0]
        )
        guard = OfflineHealthGuard(
            fresh_path,
            config=fresh_config,
            public_key=fresh_key.public_key(),
            sample=lambda: clock[0],
        )
        with pytest.raises(GuardStateDenied):
            guard.consume_verified(lambda: fresh_token, old_claim)
        guard.consume_verified(lambda: fresh_token, claims_for(fresh_config))
        # Old signed health fails even with otherwise new application claims.
        with pytest.raises(GuardStateDenied):
            guard.consume_verified(lambda: token[0], claims_for(fresh_config, nonce="d" * 64))
        assert stored(fresh_path)[0][-1] == 1
    assert all(old.read_bytes() == contents for old, contents in preserved.items())
    # No assertion signature/key recovery is claimed here: full authority tests
    # must verify rotated assertion keys before constructing VerifiedGuardClaims.
