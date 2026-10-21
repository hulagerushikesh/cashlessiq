"""Offline synthetic Chrony CSV and independent temporary RSA keys only."""

import json
from dataclasses import replace
from fractions import Fraction
from unittest.mock import Mock

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import ValidationError

from ciq_api.worker_health import (
    SECOND,
    CollectionWindow,
    HealthBinding,
    HealthDenied,
    HealthNow,
    HealthPolicy,
    check_envelope,
    make_evidence,
    parse_tracking,
    sign_for_offline_test,
)

CSV = (
    b"C633640F,198.51.100.15,3,995.000000000,0.000000001,-0.000000002,"
    b"0.000000003,-1.000,0.001,0.001,0.000000001,0.000000001,1.0,Normal\n"
)


@pytest.fixture
def policy():
    return HealthPolicy(
        sources=frozenset({("C633640F", "198.51.100.15")}),
        max_reference_age_ns=30 * SECOND,
        max_error_ns=100_000,
        max_collection_ns=SECOND,
        max_evidence_age_ns=2 * SECOND,
        max_read_skew_ns=1_000_000,
        holdover_floor_ppb=10,
    )


@pytest.fixture
def setup(policy):
    binding = HealthBinding(
        host_id="test-host",
        boot_id="00000000-0000-0000-0000-000000000001",
        health_generation="00000000-0000-0000-0000-000000000002",
        collector_epoch="00000000-0000-0000-0000-000000000003",
    )
    window = CollectionWindow(
        start_wall_ns=1000 * SECOND,
        end_wall_ns=1000 * SECOND + 100,
        start_monotonic_ns=10 * SECOND,
        end_monotonic_ns=10 * SECOND + 100,
        start_boottime_ns=20 * SECOND,
        end_boottime_ns=20 * SECOND + 100,
    )
    evidence = make_evidence(
        parse_tracking(CSV, policy=policy),
        binding=binding,
        sequence=1,
        window=window,
        policy=policy,
    )
    now = HealthNow(
        boot_id=binding.boot_id,
        wall_ns=window.end_wall_ns,
        monotonic_ns=window.end_monotonic_ns,
        boottime_ns=window.end_boottime_ns,
    )
    return binding, evidence, now


@pytest.fixture(scope="module")
def key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def change_field(index, value):
    fields = CSV.decode().strip().split(",")
    fields[index] = value
    return ",".join(fields).encode()


def test_exact_uncertainty_and_holdover_round_up(policy, setup, key):
    observation = parse_tracking(CSV, policy=policy)
    assert observation.base_error_ns == 5  # ceil(1 + 1 + 0.5) + 2 print-rounding ns.
    assert observation.skew_ppb == 2
    binding, evidence, now = setup
    checked = check_envelope(
        sign_for_offline_test(evidence, key),
        public_key=key.public_key(),
        binding=binding,
        now=now,
        policy=policy,
    )
    assert checked.reference_age_ns == 5 * SECOND + 105
    growth = Fraction(checked.reference_age_ns * 10, SECOND)
    assert checked.error_ns == 5 + -(-growth.numerator // growth.denominator)
    assert len(checked.content_sha256) == 64
    # This deliberately exposes no ready-to-install ClockHealth adapter.
    assert not hasattr(checked, "synchronized")


@pytest.mark.parametrize(
    "index,value",
    [
        (0, "7F7F0101"),
        (0, "00000000"),
        (0, "c633640f"),
        (1, "127.0.0.1"),
        (1, "time.example.com"),
        (1, "198.51.100.16"),
        (2, "0"),
        (2, "16"),
        (2, "3.0"),
        (3, "0"),
        (3, "1e999"),
        (4, "NaN"),
        (4, "Infinity"),
        (4, "0.0000000001"),
        (4, " 0.1"),
        (6, "-0.01"),
        (9, "-1"),
        (10, "-1"),
        (11, "-1"),
        (12, "0"),
        (13, "Not synchronised"),
        (13, "Insert second"),
        (13, "Delete second"),
    ],
)
def test_invalid_daemon_fields_deny(policy, index, value):
    with pytest.raises(HealthDenied, match=r"^Health evidence denied$"):
        parse_tracking(change_field(index, value), policy=policy)


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"x" * 2049,
        b"\xff",
        CSV + CSV,
        CSV + b"\n",
        CSV.replace(b",3,", b",3,extra,"),
        CSV.replace(b",3,", b","),
        CSV.replace(b"Normal", b'"Normal"'),
        CSV.replace(b"Normal", b"Normal\r"),
        "not bytes",
    ],
)
def test_response_bounds_and_single_record_shape(policy, payload):
    with pytest.raises(HealthDenied):
        parse_tracking(payload, policy=policy)


@pytest.mark.parametrize(
    "field,value",
    [
        ("version", True),
        ("sequence", True),
        ("sequence", 0),
        ("sequence", 2**63),
        ("host_id", "foreign"),
        ("boot_id", "00000000-0000-0000-0000-000000000099"),
        ("health_generation", "00000000-0000-0000-0000-000000000099"),
        ("collector_epoch", "00000000-0000-0000-0000-000000000099"),
        ("iss", "foreign"),
        ("aud", ["urn:cashlessiq:clock-consumer:offline"]),
        ("source_format", "chrony-unknown"),
        ("source_address", "127.0.0.1"),
        ("source_refid", "00000000"),
        ("synchronized", False),
        ("synchronized", 1),
        ("leap_status", "Insert second"),
        ("base_error_ns", 0),
        ("base_error_ns", 1.5),
        ("holdover_rate_ppb", 0),
        ("extra", "untrusted"),
    ],
)
def test_even_correctly_signed_bad_claims_deny(setup, policy, key, field, value):
    binding, evidence, now = setup
    raw = evidence.model_dump()
    raw[field] = value
    token = jwt.encode(raw, key, algorithm="RS256")
    with pytest.raises(HealthDenied, match=r"^Health evidence denied$"):
        check_envelope(token, public_key=key.public_key(), binding=binding, now=now, policy=policy)


@pytest.mark.parametrize(
    "failure",
    [
        "stale",
        "future",
        "suspend",
        "clock_jump",
        "wrong_boot",
        "reference_old",
        "reference_future",
        "collection_long",
        "collection_reversed",
        "collection_suspend",
        "holdover",
        "excess_error",
        "invalid_domain",
    ],
)
def test_freshness_error_and_domain_negatives(setup, policy, key, failure):
    binding, evidence, now = setup
    raw = evidence.model_dump()
    now_raw = now.model_dump()
    if failure == "stale":
        for field in ("wall_ns", "monotonic_ns", "boottime_ns"):
            now_raw[field] += 3 * SECOND
    elif failure == "future":
        for field in ("wall_ns", "monotonic_ns", "boottime_ns"):
            now_raw[field] -= 1
    elif failure == "suspend":
        now_raw["boottime_ns"] += SECOND
        now_raw["wall_ns"] += SECOND
    elif failure == "clock_jump":
        now_raw["wall_ns"] += SECOND
    elif failure == "wrong_boot":
        now_raw["boot_id"] = "00000000-0000-0000-0000-000000000099"
    elif failure == "reference_old":
        raw["reference_wall_ns"] = SECOND  # Fresh signature does not refresh this reference.
    elif failure == "reference_future":
        raw["reference_wall_ns"] = now.wall_ns + SECOND
    elif failure == "collection_long":
        for field in ("start_wall_ns", "start_monotonic_ns", "start_boottime_ns"):
            raw["window"][field] -= 2 * SECOND
    elif failure == "collection_reversed":
        raw["window"]["start_wall_ns"] += SECOND
    elif failure == "collection_suspend":
        raw["window"]["start_boottime_ns"] -= SECOND
    elif failure == "holdover":
        raw["holdover_rate_ppb"] = 1_000_000
    elif failure == "excess_error":
        raw["base_error_ns"] = policy.max_error_ns + 1
    else:
        now_raw["boottime_ns"] = 0
    with pytest.raises(HealthDenied):
        check_envelope(
            jwt.encode(raw, key, algorithm="RS256"),
            public_key=key.public_key(),
            binding=binding,
            now=HealthNow(**now_raw),
            policy=policy,
        )


@pytest.mark.parametrize(
    "header",
    [
        {"kid": "choose-a-key"},
        {"jku": "https://example.com/key"},
        {"crit": ["exp"]},
        {"typ": "OTHER"},
        {"jwk": {}},
    ],
)
def test_no_key_or_algorithm_discovery(setup, policy, key, header):
    binding, evidence, now = setup
    token = jwt.encode(evidence.model_dump(), key, algorithm="RS256", headers=header)
    with pytest.raises(HealthDenied):
        check_envelope(token, public_key=key.public_key(), binding=binding, now=now, policy=policy)


def test_wrong_key_hmac_tamper_size_and_duplicate_json_deny(setup, policy, key):
    binding, evidence, now = setup
    raw = evidence.model_dump()
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    # PyJWS creates an actually signed duplicate-field payload, not a signature
    # failure masquerading as a duplicate-parser test.
    duplicated = json.dumps(raw)[:-1] + ',"sequence":2}'
    nested_duplicate = json.dumps(raw).replace(
        '"start_wall_ns":', '"end_wall_ns":0,"start_wall_ns":'
    )
    tokens = [
        jwt.encode(raw, other, algorithm="RS256"),
        jwt.encode(raw, b"test-only-health-hmac-secret-at-least-32-bytes", algorithm="HS256"),
        "x" * 8193,
        "opaque",
        sign_for_offline_test(evidence, key) + "x",
        jwt.PyJWS().encode(duplicated.encode(), key, algorithm="RS256"),
        jwt.PyJWS().encode(nested_duplicate.encode(), key, algorithm="RS256"),
    ]
    for token in tokens:
        with pytest.raises(HealthDenied):
            check_envelope(
                token, public_key=key.public_key(), binding=binding, now=now, policy=policy
            )


def test_signature_layer_does_not_consult_ambient_jwt_wall_clock(setup, policy, key, monkeypatch):
    binding, evidence, now = setup
    token = sign_for_offline_test(evidence, key)
    forbidden = Mock()
    forbidden.now.side_effect = AssertionError("No host clock")
    monkeypatch.setattr(jwt.api_jwt, "datetime", forbidden)
    check_envelope(
        token,
        public_key=key.public_key(),
        binding=binding,
        now=now,
        policy=policy,
    )
    forbidden.now.assert_not_called()


def test_canonical_digest_and_explicit_stateless_limit(setup, policy, key):
    binding, evidence, now = setup

    def check(raw):
        return check_envelope(
            jwt.encode(raw, key, algorithm="RS256"),
            public_key=key.public_key(),
            binding=binding,
            now=now,
            policy=policy,
        )

    first = check(evidence.model_dump())
    assert (
        check(dict(reversed(list(evidence.model_dump().items())))).content_sha256
        == first.content_sha256
    )
    # Same or older sequence can still pass this STATELESS layer. A retained
    # continuity consumer is required; do not claim replay authorization here.
    assert check(evidence.model_dump()).content_sha256 == first.content_sha256
    assert check(evidence.model_dump() | {"sequence": 2}).content_sha256 != first.content_sha256


@pytest.mark.parametrize("value", [0, -1, True, 1.5, 2**63])
def test_policy_no_implicit_or_coerced_numeric_limits(policy, value):
    with pytest.raises(ValidationError):
        HealthPolicy(**(policy.model_dump() | {"max_error_ns": value}))


def test_builder_does_not_sign_stale_or_unapproved_observations(setup, policy):
    binding, evidence, _ = setup
    original = parse_tracking(CSV, policy=policy)
    for observation in (
        replace(original, reference_wall_ns=SECOND),
        replace(original, source_address="198.51.100.16"),
    ):
        with pytest.raises(HealthDenied):
            make_evidence(
                observation, binding=binding, sequence=1, window=evidence.window, policy=policy
            )
