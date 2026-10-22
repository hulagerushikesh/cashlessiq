"""Explicit offline v3 authorities; never mounted by normal startup.

Not a legacy ClockHealth/replay adapter. Only fake health/identity/source inputs
and disposable keys/state are approved. TLS, membership, filesystem custody and
hard operational deadlines remain separate concerns.
"""

import re
from collections.abc import Callable, Mapping
from hashlib import sha256
from types import MappingProxyType
from uuid import UUID

import jwt
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey

from ciq_api.source_identity import ALPHA_REFERENCES
from ciq_api.source_scopes import SyntheticSourceScopes
from ciq_api.validation_worker import SummaryObservation
from ciq_api.worker_authority import ISSUER, Disclosure, Membership, WorkerDenied
from ciq_api.worker_delegation import DelegatedSummary, DetailAssertion, TransportPeer
from ciq_api.worker_guard_health import OfflineHealthGuard, VerifiedGuardClaims
from ciq_api.worker_guard_state import Identity
from ciq_api.worker_health import _object


class GuardedDetail(DetailAssertion):
    assertion_generation: Identity


class GuardedSummary(DelegatedSummary):
    assertion_generation: Identity


def _decode(token: str, key: RSAPublicKey, audience: str, model):
    """Strict bounded JWS/schema verification, with no ambient datetime checks."""
    if type(token) is not str or not 0 < len(token) <= 4096:
        raise WorkerDenied("Worker access denied")
    header, payload, signature = token.split(".")
    if _object(header) != {"alg": "RS256", "typ": "JWT"} or not re.fullmatch(
        r"[A-Za-z0-9_-]+", signature
    ):
        raise WorkerDenied("Worker access denied")
    raw = _object(payload)
    jwt.PyJWS().decode_complete(token, key, algorithms=["RS256"])
    claims = model.model_validate(raw)
    if claims.iss != ISSUER or claims.aud != audience:
        raise WorkerDenied("Worker access denied")
    return claims


def _verified(claims, authority: str) -> VerifiedGuardClaims:
    return VerifiedGuardClaims(
        authority=authority,
        assertion_generation=claims.assertion_generation,
        nonce=sha256(claims.jti.encode()).hexdigest(),
        iat=claims.iat,
        exp=claims.exp,
    )


class GuardedAuthority:
    """One pinned tenant and reader OR delegated-validator authority.

    The assertion verification key and expected generation are explicit trusted
    configuration. A supplied health guard must pin this exact authority namespace
    and generation. No key discovery, v1/v2 fallback, source or membership I/O
    occurs inside its SQLite transaction.
    """

    def __init__(
        self,
        *,
        public_key: RSAPublicKey,
        audience: str,
        generation: str,
        tenant_id: UUID,
        scopes: SyntheticSourceScopes,
        membership: Callable[[str], Membership | None],
        guard: OfflineHealthGuard,
        evidence: Callable[[], str],
        disclosure: Disclosure | None = None,
        readers: Mapping[str, Disclosure] | None = None,
    ):
        scope = scopes.get(tenant_id)
        namespace = sha256(f"{ISSUER}\0{audience}\0{tenant_id}".encode()).hexdigest()
        copied = dict(readers or {})
        if (
            not isinstance(public_key, RSAPublicKey)
            or scope is None
            or not audience
            or len(audience) > 120
            or type(guard) is not OfflineHealthGuard
            or guard._config.authority != namespace
            or guard._config.assertion_generation != generation
            or not callable(evidence)
            or not callable(membership)
            or (disclosure is None) == (not copied)
            or (disclosure is not None and disclosure not in {"medical", "nonclinical"})
            or any(
                not name
                or len(name) > 120
                or name == audience
                or value not in {"medical", "nonclinical"}
                for name, value in copied.items()
            )
        ):
            raise ValueError("Invalid offline v3 authority")
        self._key, self._audience, self._scope = public_key, audience, scope
        self._generation, self._namespace = generation, namespace
        self._membership, self._guard, self._evidence = membership, guard, evidence
        self._disclosure, self._readers = disclosure, MappingProxyType(copied)

    def _parse(self, token: str):
        model = GuardedDetail if self._disclosure is not None else GuardedSummary
        claims = _decode(token, self._key, self._audience, model)
        self._check_scope(claims)
        return claims

    def _check_scope(self, claims):
        if (
            claims.aud != self._audience
            or claims.assertion_generation != self._generation
            or claims.tenant != str(self._scope.tenant_id)
            or claims.request_id not in self._scope.request_ids
            or (self._disclosure is not None and claims.disclosure != self._disclosure)
            or (
                self._disclosure is None
                and self._readers.get(claims.reader_audience) != claims.disclosure
            )
        ):
            raise WorkerDenied("Worker access denied")

    def _current(self, claims):
        member = self._membership(claims.sub)
        if (
            member is None
            or str(member.tenant_id) != claims.tenant
            or member.role not in {"processor", "auditor", "medical_officer"}
            or claims.disclosure
            != ("medical" if member.role == "medical_officer" else "nonclinical")
        ):
            raise WorkerDenied("Worker access denied")

    def consume(self, token: str):
        try:
            claims = self._parse(token)
            self._current(claims)
            self._guard.consume_verified(self._evidence, _verified(claims, self._namespace))
            return claims
        except Exception:
            raise WorkerDenied("Worker access denied") from None

    def before_delivery(self, claims):
        try:
            # Claims only originate from this authority's verified consume. Still
            # reject a mismatched model/configuration rather than widening it.
            expected = GuardedDetail if self._disclosure is not None else GuardedSummary
            if type(claims) is not expected:
                raise WorkerDenied("Worker access denied")
            claims = expected.model_validate(claims.model_dump())
            self._check_scope(claims)
            self._current(claims)
            interval = self._guard.observe(self._evidence)
            if not interval.permits(_verified(claims, self._namespace)):
                raise WorkerDenied("Worker access denied")
        except Exception:
            raise WorkerDenied("Worker access denied") from None

    def check_peer(self, token: str, peer: TransportPeer):
        try:
            claims = self._parse(token)
            if (
                self._disclosure is not None
                or type(peer) is not TransportPeer
                or peer.audience != claims.reader_audience
            ):
                raise WorkerDenied("Worker access denied")
        except Exception:
            raise WorkerDenied("Worker access denied") from None


class GuardedReadRelay:
    """Unchanged child capability forwarding with explicit v3 generation binding."""

    def __init__(self, *, authority: GuardedAuthority, validator_audience: str, invoke: Callable):
        if authority._disclosure is None or not validator_audience:
            raise ValueError("Invalid offline v3 relay")
        self._authority, self._validator, self._invoke = authority, validator_audience, invoke

    def summary(self, token: str) -> SummaryObservation:
        try:
            parent = self._authority.consume(token)
            child = _decode(
                parent.summary_token, self._authority._key, self._validator, GuardedSummary
            )
            if (
                child.parent_jti != parent.jti
                or child.reader_audience != parent.aud
                or any(
                    getattr(child, field) != getattr(parent, field)
                    for field in (
                        "sub",
                        "tenant",
                        "disclosure",
                        "request_id",
                        "iat",
                        "exp",
                        "assertion_generation",
                    )
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
