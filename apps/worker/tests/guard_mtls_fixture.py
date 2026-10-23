"""Explicit container TEST fixture with frozen fictional time, never a provider.

The independent Linux probe tests real clock-domain continuity. This helper only
composes canonical v3 authorization with private TLS and disposable membership.
No private health key survives initialization. No default image contains it.
"""

import json
import os
from hashlib import sha256
from pathlib import Path

from ciq_api.source_alpha import SOURCE_TENANTS
from ciq_api.worker_authority import ISSUER
from ciq_api.worker_guard_health import OfflineHealthGuard
from ciq_api.worker_guard_state import GuardStateConfig, OfflineGuardState
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

STATE = Path("/var/lib/ciq-replay/used.sqlite")
PUBLIC = Path("/var/lib/ciq-replay/public-guard.json")
GENERATION = "disposable-v3-generation"
NOW = HealthNow(
    boot_id="00000000-0000-0000-0000-000000000001",
    wall_ns=1000 * SECOND + SECOND // 2,
    monotonic_ns=100 * SECOND,
    boottime_ns=100 * SECOND,
)

# Supervisor names are not wire audiences: in particular clinical -> medical.
# Membership deliberately has no v3 state. This mapping is test material only.
SERVICE_BINDINGS = {
    "broker": None,
    "reader-0-nonclinical": (0, "reader:0:nonclinical"),
    "reader-0-clinical": (0, "reader:0:medical"),
    "reader-1-nonclinical": (1, "reader:1:nonclinical"),
    "reader-1-clinical": (1, "reader:1:medical"),
    "validator-0": (0, "validator:0"),
    "validator-1": (1, "validator:1"),
}


def authority_for(role):
    """Exact seven-state inventory; never infer a tenant/audience from input."""
    if type(role) is not str or role not in SERVICE_BINDINGS:
        raise ValueError("Unknown disposable authority role")
    binding = SERVICE_BINDINGS[role]
    if binding is None:
        return "broker"
    index, audience = binding
    tenant = SOURCE_TENANTS[index].tenant_id
    return sha256(f"{ISSUER}\0{audience}\0{tenant}".encode()).hexdigest()


def _paths(directory):
    if directory is None:
        return STATE, PUBLIC
    return Path(directory) / "used.sqlite", Path(directory) / "public-guard.json"


def initialize(role, *, directory=None, generation=GENERATION):
    # Preserve the existing single-tenant test harness, not runtime aliases.
    if type(role) is not str:
        raise ValueError("Unknown disposable authority role")
    role = {"reader": "reader-0-nonclinical", "validator": "validator-0"}.get(role, role)
    authority = authority_for(role)
    state, public_path = _paths(directory)
    if os.path.lexists(state) or os.path.lexists(public_path):
        raise FileExistsError("Disposable state already exists")
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    binding = HealthBinding(
        host_id="fictional-container-test",
        boot_id=NOW.boot_id,
        health_generation="00000000-0000-0000-0000-000000000002",
        collector_epoch="00000000-0000-0000-0000-000000000003",
    )
    config = GuardStateConfig(
        authority=authority,
        assertion_generation=generation,
        health_key_sha256=sha256(
            key.public_key().public_bytes(
                serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
            )
        ).hexdigest(),
        binding=binding,
        health_policy=HealthPolicy(
            sources=frozenset({("C633640F", "198.51.100.15")}),
            max_reference_age_ns=60 * SECOND,
            max_error_ns=1_000_000,
            max_collection_ns=SECOND,
            max_evidence_age_ns=30 * SECOND,
            max_read_skew_ns=100_000_000,
            holdover_floor_ppb=10,
        ),
        max_gap_ns=60 * SECOND,
        max_step_ns=SECOND,
        max_nonces=1000,
        max_file_bytes=262144,
    )
    evidence = HealthEvidence(
        **binding.model_dump(),
        version=1,
        iss="urn:cashlessiq:clock-health:offline",
        aud="urn:cashlessiq:clock-consumer:offline",
        source_format="chrony-4.7-tracking-csv",
        sequence=1,
        window=CollectionWindow(
            start_wall_ns=NOW.wall_ns,
            end_wall_ns=NOW.wall_ns,
            start_monotonic_ns=NOW.monotonic_ns,
            end_monotonic_ns=NOW.monotonic_ns,
            start_boottime_ns=NOW.boottime_ns,
            end_boottime_ns=NOW.boottime_ns,
        ),
        source_refid="C633640F",
        source_address="198.51.100.15",
        reference_wall_ns=NOW.wall_ns - SECOND,
        base_error_ns=2,
        holdover_rate_ppb=10,
        synchronized=True,
        leap_status="Normal",
    )
    state.parent.chmod(0o700)
    OfflineGuardState.initialize_for_offline_test(state, config=config, initial=NOW)
    with public_path.open("x") as output:
        json.dump(
            dict(
                config=config.model_dump(mode="json"),
                public=public.decode(),
                evidence=sign_for_offline_test(evidence, key),
            ),
            output,
        )
    public_path.chmod(0o400)
    for path in (state, public_path, state.parent):
        os.chown(path, 10001, 10001)


def load(*, unsafe=False, directory=None):
    """Open existing fixture only; never initialize or repair on reload."""
    state, public_path = _paths(directory)
    fixture = json.loads(public_path.read_text())
    guard = OfflineHealthGuard(
        state,
        config=GuardStateConfig.model_validate_json(json.dumps(fixture["config"])),
        public_key=serialization.load_pem_public_key(fixture["public"].encode()),
        sample=lambda: NOW.model_copy(update={"wall_ns": NOW.wall_ns - SECOND}) if unsafe else NOW,
    )
    return guard, lambda: fixture["evidence"]
