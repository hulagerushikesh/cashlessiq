"""Disposable Linux v3 probe, NOT a synchronization provider or service startup.

Only public fake signed health/configuration persists alongside the private test
ledger. The ephemeral health signing key is discarded during explicit setup.
"""

import json
import os
import sqlite3
import sys
import time
from hashlib import sha256
from pathlib import Path

from ciq_api.worker_guard_health import OfflineHealthGuard, VerifiedGuardClaims
from ciq_api.worker_guard_state import GuardStateConfig, GuardStateDenied, OfflineGuardState
from ciq_api.worker_health import (
    SECOND,
    CollectionWindow,
    HealthBinding,
    HealthEvidence,
    HealthNow,
    HealthPolicy,
    sign_for_offline_test,
)
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

STATE = Path("/state/guard.sqlite")
FIXTURE = Path("/state/public-test-fixture.json")


def sample():
    return HealthNow(
        boot_id=Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
        wall_ns=time.time_ns(),
        monotonic_ns=time.monotonic_ns(),
        boottime_ns=time.clock_gettime_ns(time.CLOCK_BOOTTIME),
    )


def initialize():
    STATE.parent.chmod(0o700)
    now = sample()
    binding = HealthBinding(
        host_id="disposable-linux-vm",
        boot_id=now.boot_id,
        health_generation="00000000-0000-0000-0000-000000000002",
        collector_epoch="00000000-0000-0000-0000-000000000003",
    )
    policy = HealthPolicy(
        sources=frozenset({("C633640F", "198.51.100.15")}),
        max_reference_age_ns=60 * SECOND,
        max_error_ns=1_000_000,
        max_collection_ns=SECOND,
        max_evidence_age_ns=30 * SECOND,
        max_read_skew_ns=100_000_000,
        holdover_floor_ppb=10,
    )
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    config = GuardStateConfig(
        authority="disposable-authority",
        assertion_generation="disposable-generation",
        health_key_sha256=sha256(
            key.public_key().public_bytes(
                serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
            )
        ).hexdigest(),
        binding=binding,
        health_policy=policy,
        max_gap_ns=60 * SECOND,
        max_step_ns=SECOND,
        max_nonces=4,
        max_file_bytes=65536,
    )
    evidence = HealthEvidence(
        **binding.model_dump(),
        version=1,
        iss="urn:cashlessiq:clock-health:offline",
        aud="urn:cashlessiq:clock-consumer:offline",
        source_format="chrony-4.7-tracking-csv",
        sequence=1,
        window=CollectionWindow(
            start_wall_ns=now.wall_ns,
            end_wall_ns=now.wall_ns,
            start_monotonic_ns=now.monotonic_ns,
            end_monotonic_ns=now.monotonic_ns,
            start_boottime_ns=now.boottime_ns,
            end_boottime_ns=now.boottime_ns,
        ),
        source_refid="C633640F",
        source_address="198.51.100.15",
        reference_wall_ns=now.wall_ns - SECOND,
        base_error_ns=2,
        holdover_rate_ppb=10,
        synchronized=True,
        leap_status="Normal",
    )
    claim = VerifiedGuardClaims(
        authority=config.authority,
        assertion_generation=config.assertion_generation,
        nonce="a" * 64,
        iat=now.wall_ns // SECOND - 1,
        exp=now.wall_ns // SECOND + 29,
    )
    OfflineGuardState.initialize_for_offline_test(STATE, config=config, initial=now)
    # Explicit test fixture only, never an app assertion/private key/source row.
    with FIXTURE.open("x") as output:
        json.dump(
            dict(
                config=config.model_dump(mode="json"),
                public=public.decode(),
                evidence=sign_for_offline_test(evidence, key),
                claims=claim.model_dump(),
            ),
            output,
        )
    FIXTURE.chmod(0o400)
    for path in (STATE, FIXTURE, STATE.parent):
        os.chown(path, 10001, 10001)
    print("Explicit disposable v3 state initialized; fake health only")


def main():
    operation = sys.argv[1]
    if operation == "initialize":
        initialize()
        return
    assert os.getuid() == 10001
    fixture = json.loads(FIXTURE.read_text())
    config = GuardStateConfig.model_validate_json(json.dumps(fixture["config"]))
    claims = VerifiedGuardClaims.model_validate(fixture["claims"])
    latest = {}

    def read_sample():
        now = sample()
        if operation == "latch":
            now = now.model_copy(update={"wall_ns": now.wall_ns - 3600 * SECOND})
        latest["value"] = now
        return now

    guard = OfflineHealthGuard(
        STATE,
        config=config,
        public_key=serialization.load_pem_public_key(fixture["public"].encode()),
        sample=read_sample,
    )

    def evidence():
        return fixture["evidence"]

    if operation in {"latch", "deny"}:
        try:
            guard.observe(evidence)
        except GuardStateDenied:
            with sqlite3.connect(STATE) as db:
                assert db.execute("SELECT unsafe FROM guard_state").fetchone() == (1,)
                assert db.execute("SELECT nonce,expiry FROM guard_nonce").fetchall() == [
                    (claims.nonce, claims.exp)
                ]
            print("Guard denied as required")
            return
        raise AssertionError("Unsafe state accepted")
    assert operation in {"consume", "replay"}
    # Prove replay rejection is NOT merely expiry or stale fake health.
    assert guard.observe(evidence).permits(claims)
    try:
        guard.consume_verified(evidence, claims)
    except GuardStateDenied:
        assert operation == "replay"
    else:
        assert operation == "consume"
    snapshot, nonces = guard.inspect()
    assert [(n.nonce, n.expiry) for n in nonces] == [(claims.nonce, claims.exp)]
    assert snapshot.sequence == 1 and snapshot.unsafe == 0
    now = latest["value"]
    print(
        json.dumps(
            dict(
                wall_ns=now.wall_ns,
                mono_ns=now.monotonic_ns,
                boot=now.boot_id,
                boottime_ns=now.boottime_ns,
            )
        )
    )


if __name__ == "__main__":
    main()
