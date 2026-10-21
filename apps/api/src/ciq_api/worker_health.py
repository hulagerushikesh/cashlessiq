"""Inactive offline host-health parsing/signature candidate, NOT clock authorization.

No subprocess, host clock, file/key discovery, daemon or network access. Evidence
epoch/sequence continuity is NOT persisted here; callers must not convert this
stateless result into ClockHealth or use it to activate existing v1 guards.
"""

import base64
import hashlib
import ipaddress
import json
import re
from dataclasses import dataclass
from fractions import Fraction
from typing import Annotated, Literal

import jwt
from pydantic import BaseModel, ConfigDict, Field, model_validator

SECOND = 1_000_000_000
MAX_INTEGER = 2**63 - 1
ISSUER = "urn:cashlessiq:clock-health:offline"
AUDIENCE = "urn:cashlessiq:clock-consumer:offline"
Integer = Annotated[int, Field(ge=0, le=MAX_INTEGER)]
Positive = Annotated[int, Field(gt=0, le=MAX_INTEGER)]
Identifier = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")]
Uuid = Annotated[str, Field(pattern=r"^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$")]
Refid = Annotated[str, Field(pattern=r"^[0-9A-F]{8}$")]


class HealthDenied(Exception):
    """Generic denial; no raw daemon response, key or underlying exception."""


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


def _source(refid: str, address: str) -> None:
    if not re.fullmatch(r"[0-9A-F]{8}", refid) or refid in {"00000000", "7F7F0101"}:
        raise ValueError("Invalid health source")
    parsed = ipaddress.ip_address(address)
    checked = getattr(parsed, "ipv4_mapped", None) or parsed
    if (
        str(parsed) != address
        or checked.is_loopback
        or checked.is_unspecified
        or checked.is_multicast
        or checked.is_link_local
    ):
        raise ValueError("Invalid health source")


class HealthPolicy(StrictModel):
    """Explicit fictional policy in tests; no approved operational defaults."""

    sources: frozenset[tuple[Refid, str]]
    max_reference_age_ns: Positive
    max_error_ns: Positive
    max_collection_ns: Positive
    max_evidence_age_ns: Positive
    max_read_skew_ns: Positive
    holdover_floor_ppb: Positive

    @model_validator(mode="after")
    def check_sources(self):
        if not self.sources or len(self.sources) > 16:
            raise ValueError("Invalid health policy")
        for refid, address in self.sources:
            _source(refid, address)
        return self


class HealthBinding(StrictModel):
    host_id: Identifier
    boot_id: Uuid
    health_generation: Uuid
    collector_epoch: Uuid


class HealthNow(StrictModel):
    boot_id: Uuid
    wall_ns: Integer
    monotonic_ns: Integer
    boottime_ns: Integer


class CollectionWindow(StrictModel):
    start_wall_ns: Integer
    end_wall_ns: Integer
    start_monotonic_ns: Integer
    end_monotonic_ns: Integer
    start_boottime_ns: Integer
    end_boottime_ns: Integer


class HealthEvidence(HealthBinding):
    version: Annotated[int, Field(ge=1, le=1)]
    iss: Literal["urn:cashlessiq:clock-health:offline"]
    aud: Literal["urn:cashlessiq:clock-consumer:offline"]
    source_format: Literal["chrony-4.7-tracking-csv"]
    sequence: Positive
    window: CollectionWindow
    source_refid: Refid
    source_address: Annotated[str, Field(min_length=1, max_length=45)]
    reference_wall_ns: Positive
    base_error_ns: Annotated[int, Field(ge=2, le=MAX_INTEGER)]
    holdover_rate_ppb: Positive
    synchronized: Literal[True]
    leap_status: Literal["Normal"]


@dataclass(frozen=True)
class TrackingObservation:
    source_refid: str
    source_address: str
    reference_wall_ns: int
    base_error_ns: int
    skew_ppb: int


@dataclass(frozen=True)
class CheckedHealthEnvelope:
    """Signature/freshness checked only; NOT replay/continuity authorization."""

    evidence: HealthEvidence
    reference_age_ns: int
    error_ns: int
    content_sha256: str


def _ceil(value: Fraction) -> int:
    return -(-value.numerator // value.denominator)


def _number(value: str) -> Fraction:
    if not re.fullmatch(r"-?[0-9]{1,12}(?:\.[0-9]{1,9})?", value):
        raise ValueError("Invalid numeric field")
    return Fraction(value)


def parse_tracking(payload: bytes, *, policy: HealthPolicy) -> TrackingObservation:
    """Strict 4.7 CSV contract: fourteen fields, including BOTH refid and address.

    Independently implemented from the documented/source output layout; no
    executable invocation. Only an explicitly allowlisted source is accepted.
    """
    try:
        if type(payload) is not bytes or not 0 < len(payload) <= 2048:
            raise ValueError("Invalid response")
        text = payload.decode("ascii")
        if text.endswith("\n"):
            text = text[:-1]
        fields = text.split(",")
        if len(fields) != 14 or any("\n" in field or "\r" in field for field in fields):
            raise ValueError("Invalid response")
        refid, address, stratum, reference, *metrics, leap = fields
        _source(refid, address)
        if (refid, address) not in policy.sources or not re.fullmatch(r"[1-9]|1[0-5]", stratum):
            raise ValueError("Invalid source")
        if leap != "Normal":
            raise ValueError("Unhealthy source")
        reference_ns = _number(reference) * SECOND
        if reference_ns.denominator != 1 or not 0 < reference_ns <= MAX_INTEGER:
            raise ValueError("Invalid reference")
        offset, _last, rms, _frequency, _residual, skew, delay, dispersion, interval = map(
            _number, metrics
        )
        if min(rms, skew, delay, dispersion) < 0 or interval <= 0:
            raise ValueError("Invalid uncertainty")
        # Each seconds metric is printed to 9 decimals in this pinned format.
        # Two added ns conservatively cover rounding of offset, dispersion,
        # and half delay. Source/reference accuracy remains a trust assumption.
        error = _ceil((abs(offset) + dispersion + delay / 2) * SECOND) + 2
        rate = _ceil(skew * 1000) + 1  # 0.001 ppm print precision, rounded upward.
        if error > MAX_INTEGER or rate > MAX_INTEGER:
            raise ValueError("Invalid uncertainty")
        return TrackingObservation(refid, address, int(reference_ns), error, rate)
    except Exception:
        raise HealthDenied("Health evidence denied") from None


def _check_measurement(
    evidence: HealthEvidence, *, binding: HealthBinding, now: HealthNow, policy: HealthPolicy
) -> tuple[int, int]:
    if any(
        getattr(evidence, field) != getattr(binding, field) for field in HealthBinding.model_fields
    ):
        raise ValueError("Invalid binding")
    if now.boot_id != binding.boot_id:
        raise ValueError("Invalid domain")
    _source(evidence.source_refid, evidence.source_address)
    if (evidence.source_refid, evidence.source_address) not in policy.sources:
        raise ValueError("Invalid source")
    window = evidence.window
    spans = [
        window.end_wall_ns - window.start_wall_ns,
        window.end_monotonic_ns - window.start_monotonic_ns,
        window.end_boottime_ns - window.start_boottime_ns,
    ]
    ages = [
        now.wall_ns - window.end_wall_ns,
        now.monotonic_ns - window.end_monotonic_ns,
        now.boottime_ns - window.end_boottime_ns,
    ]
    if (
        min(spans) < 0
        or max(spans) > policy.max_collection_ns
        or max(spans) - min(spans) > policy.max_read_skew_ns
        or min(ages) < 0
        or max(ages) > policy.max_evidence_age_ns
        or max(ages) - min(ages) > policy.max_read_skew_ns
        or now.boottime_ns < now.monotonic_ns
        or window.start_boottime_ns < window.start_monotonic_ns
        or window.end_boottime_ns < window.end_monotonic_ns
        or evidence.reference_wall_ns > window.start_wall_ns
        or evidence.holdover_rate_ppb < policy.holdover_floor_ppb
    ):
        raise ValueError("Invalid freshness")
    # Preserve original source age; a newly signed old reference is not fresh.
    age = (
        max(
            now.wall_ns - evidence.reference_wall_ns,
            window.end_wall_ns - evidence.reference_wall_ns + ages[2],
        )
        + evidence.base_error_ns
    )
    error = evidence.base_error_ns + _ceil(Fraction(age * evidence.holdover_rate_ppb, SECOND))
    if age > policy.max_reference_age_ns or error > policy.max_error_ns or error > MAX_INTEGER:
        raise ValueError("Uncertain measurement")
    return age, error


def make_evidence(
    observation: TrackingObservation,
    *,
    binding: HealthBinding,
    sequence: int,
    window: CollectionWindow,
    policy: HealthPolicy,
) -> HealthEvidence:
    """Build an offline claim from explicit input, never read a host clock."""
    try:
        evidence = HealthEvidence(
            **binding.model_dump(),
            version=1,
            iss=ISSUER,
            aud=AUDIENCE,
            source_format="chrony-4.7-tracking-csv",
            sequence=sequence,
            window=window,
            source_refid=observation.source_refid,
            source_address=observation.source_address,
            reference_wall_ns=observation.reference_wall_ns,
            base_error_ns=observation.base_error_ns,
            holdover_rate_ppb=max(observation.skew_ppb, policy.holdover_floor_ppb),
            synchronized=True,
            leap_status="Normal",
        )
        _check_measurement(
            evidence,
            binding=binding,
            policy=policy,
            now=HealthNow(
                boot_id=binding.boot_id,
                wall_ns=window.end_wall_ns,
                monotonic_ns=window.end_monotonic_ns,
                boottime_ns=window.end_boottime_ns,
            ),
        )
        return evidence
    except Exception:
        raise HealthDenied("Health evidence denied") from None


def sign_for_offline_test(evidence: HealthEvidence, private_key: object) -> str:
    """Explicit temporary test key only; no key generation/discovery/provisioning."""
    try:
        return jwt.encode(evidence.model_dump(), private_key, algorithm="RS256")
    except Exception:
        raise HealthDenied("Health evidence denied") from None


def _object(segment: str) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", segment):
        raise ValueError("Invalid envelope")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate field")
            result[key] = value
        return result

    def reject_constant(_):
        raise ValueError("Invalid number")

    result = json.loads(
        base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4)),
        object_pairs_hook=unique,
        parse_constant=reject_constant,
    )
    if type(result) is not dict:
        raise ValueError("Invalid envelope")
    return result


def check_envelope(
    token: str, *, public_key: object, binding: HealthBinding, now: HealthNow, policy: HealthPolicy
) -> CheckedHealthEnvelope:
    """Stateless signature/domain/freshness check; no sequence replay acceptance.

    A later versioned retained-state consumer must latch/authorize continuity.
    This intentionally cannot be installed as the current guard's health callback.
    """
    try:
        if type(token) is not str or not 0 < len(token) <= 8192:
            raise ValueError("Invalid envelope")
        header, payload, signature = token.split(".")
        if _object(header) != {"alg": "RS256", "typ": "JWT"}:
            raise ValueError("Invalid header")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", signature):
            raise ValueError("Invalid signature")
        raw = _object(payload)
        # JWS verifies the signature only; strict model literals below verify
        # issuer/audience. Do not read PyJWT's ambient wall clock for this protocol.
        jwt.PyJWS().decode_complete(token, public_key, algorithms=["RS256"])
        evidence = HealthEvidence.model_validate(raw)
        # Literal[True] alone follows Python equality; reject numeric true as well.
        if raw.get("synchronized") is not True:
            raise ValueError("Invalid synchronization")
        age, error = _check_measurement(evidence, binding=binding, now=now, policy=policy)
        canonical = json.dumps(evidence.model_dump(), sort_keys=True, separators=(",", ":"))
        return CheckedHealthEnvelope(
            evidence, age, error, hashlib.sha256(canonical.encode()).hexdigest()
        )
    except Exception:
        raise HealthDenied("Health evidence denied") from None
