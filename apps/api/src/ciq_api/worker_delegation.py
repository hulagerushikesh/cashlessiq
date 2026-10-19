"""Offline detail -> summary delegation; fake peer context is NOT mTLS.

Only the trusted broker signs both capabilities. A reader forwards the enclosed
summary capability unchanged, holds verification keys only and cannot widen scope.
Nothing here is mounted in startup, creates credentials or opens a connection.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal
from uuid import uuid4

import jwt
from pydantic import Field

from ciq_api.source_cases import ALPHA_REFERENCES
from ciq_api.source_scopes import SyntheticSourceScopes
from ciq_api.validation_worker import OfflineValidationWorker, SummaryObservation
from ciq_api.worker_authority import (
    ISSUER,
    MAX_LIFETIME,
    Assertion,
    Disclosure,
    Membership,
    SummaryAuthority,
    WorkerDenied,
)


class DelegatedSummary(Assertion):
    reader_audience: str = Field(min_length=1, max_length=120)
    parent_jti: str = Field(min_length=1, max_length=80)


class DetailAssertion(Assertion):
    operation: Literal["read_detail"]
    summary_token: str = Field(min_length=1, max_length=3000, repr=False)


@dataclass(frozen=True)
class OfflinePeer:
    """Test-double for a verified transport identity, NEVER a request/header value.

    A future transport must derive identity from verified peer credentials. Merely
    constructing this object establishes no authentication or network isolation.
    """

    audience: str


@dataclass(frozen=True)
class TransportPeer:
    """Transport-derived identity inside the trusted process, never a wire field.

    The TLS adapter constructs this only after chain, certificate pin and URI SAN
    checks. Like any Python object it is not isolation from compromised local code.
    """

    audience: str


def issue_detail_assertion(
    private_key: object,
    *,
    subject: str,
    membership: Membership,
    reader_audience: str,
    validator_audience: str,
    request_id: str,
    scopes: SyntheticSourceScopes,
    now: int,
) -> str:
    """Trusted-broker primitive only, after fresh identity/membership resolution."""
    scope = scopes.get(membership.tenant_id)
    if (
        scope is None
        or request_id not in scope.request_ids
        or membership.role not in {"processor", "auditor", "medical_officer"}
        or not reader_audience
        or not validator_audience
        or reader_audience == validator_audience
    ):
        raise WorkerDenied("Worker access denied")
    parent_jti = str(uuid4())
    common = dict(
        iss=ISSUER,
        sub=subject,
        tenant=str(membership.tenant_id),
        disclosure="medical" if membership.role == "medical_officer" else "nonclinical",
        request_id=request_id,
        iat=now,
        exp=now + MAX_LIFETIME,
    )
    child = DelegatedSummary(
        **common,
        aud=validator_audience,
        operation="validate_summary",
        jti=str(uuid4()),
        reader_audience=reader_audience,
        parent_jti=parent_jti,
    )
    parent = DetailAssertion(
        **common,
        aud=reader_audience,
        operation="read_detail",
        jti=parent_jti,
        summary_token=jwt.encode(child.model_dump(), private_key, algorithm="RS256"),
    )
    return jwt.encode(parent.model_dump(), private_key, algorithm="RS256")


class DetailAuthority(SummaryAuthority):
    """Pinned reader disclosure; uses inherited membership/time/replay checks."""

    def __init__(self, *, disclosure: Disclosure, **kwargs):
        if disclosure not in {"nonclinical", "medical"}:
            raise ValueError("Invalid offline reader configuration")
        super().__init__(**kwargs)
        self._disclosure = disclosure

    def _parse_claims(self, raw: dict) -> DetailAssertion:
        claims = DetailAssertion.model_validate(raw)
        if claims.disclosure != self._disclosure:
            raise WorkerDenied("Worker access denied")
        return claims


class DelegatedSummaryAuthority(SummaryAuthority):
    """Tenant validator accepts only fixed reader/disclosure pairings."""

    def __init__(self, *, readers: Mapping[str, Disclosure], **kwargs):
        super().__init__(**kwargs)
        if not readers or any(
            not audience
            or len(audience) > 120
            or audience == self._audience
            or disclosure not in {"nonclinical", "medical"}
            for audience, disclosure in readers.items()
        ):
            raise ValueError("Invalid offline validator configuration")
        self._readers = MappingProxyType(dict(readers))

    def _parse_claims(self, raw: dict) -> DelegatedSummary:
        claims = DelegatedSummary.model_validate(raw)
        if self._readers.get(claims.reader_audience) != claims.disclosure:
            raise WorkerDenied("Worker access denied")
        return claims

    def check_peer(self, token: str, peer: OfflinePeer | TransportPeer) -> None:
        try:
            if not isinstance(token, str) or len(token) > 4096:
                raise WorkerDenied("Worker access denied")
            raw = jwt.decode(
                token,
                self._key,
                algorithms=["RS256"],
                issuer=ISSUER,
                audience=self._audience,
                options={"strict_aud": True, "verify_exp": False, "verify_iat": False},
            )
            claims = self._parse_claims(raw)
            if (
                type(peer) not in {OfflinePeer, TransportPeer}
                or peer.audience != claims.reader_audience
            ):
                raise WorkerDenied("Worker access denied")
        except Exception:
            raise WorkerDenied("Worker access denied") from None


class OfflineDelegatedValidator:
    def __init__(self, authority: DelegatedSummaryAuthority, worker: OfflineValidationWorker):
        if worker._authority is not authority:
            raise ValueError("Invalid offline validator composition")
        self._authority = authority
        self._worker = worker

    def validate(self, token: str, *, peer: OfflinePeer | TransportPeer) -> SummaryObservation:
        self._authority.check_peer(token, peer)
        return self._worker.validate(token)


class OfflineReadRelay:
    """Summary-only detail-path slice, not a complete queue/case read worker."""

    def __init__(
        self,
        *,
        authority: DetailAuthority,
        public_key: object,
        validator_audience: str,
        invoke_validator: Callable[[str], SummaryObservation],
    ):
        if not validator_audience or validator_audience == authority._audience:
            raise ValueError("Invalid offline relay configuration")
        self._authority = authority
        self._key = public_key
        self._validator_audience = validator_audience
        self._invoke = invoke_validator

    def summary(self, token: str) -> SummaryObservation:
        try:
            parent = self._authority.consume(token)
            raw = jwt.decode(
                parent.summary_token,
                self._key,
                algorithms=["RS256"],
                issuer=ISSUER,
                audience=self._validator_audience,
                options={"strict_aud": True, "verify_exp": False, "verify_iat": False},
            )
            child = DelegatedSummary.model_validate(raw)
            if (
                child.parent_jti != parent.jti
                or child.reader_audience != parent.aud
                or any(
                    getattr(child, field) != getattr(parent, field)
                    for field in ("sub", "tenant", "disclosure", "request_id", "iat", "exp")
                )
            ):
                raise WorkerDenied("Worker access denied")
            result = SummaryObservation.model_validate(
                self._invoke(parent.summary_token).model_dump()
            )
            if (
                result.request_id != parent.request_id
                or result.tpa_id != self._authority._scope.tpa_id
                or result.product_id != ALPHA_REFERENCES[parent.request_id].product_id
            ):
                raise WorkerDenied("Worker access denied")
            self._authority.before_delivery(parent)
            return result
        except Exception:
            raise WorkerDenied("Worker access denied") from None
