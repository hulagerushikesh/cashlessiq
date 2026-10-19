"""Offline-only internal assertion primitive; no routes, transport or live source setup.

The broker is trusted. Callers must resolve application identity before minting.
Workers receive verification keys only and independently resolve fresh membership.
Default replay is process-local. An explicitly injected same-host ledger is an
offline candidate only, not permission to deploy workers.
"""

from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from threading import Lock
from typing import Literal
from uuid import UUID, uuid4

import jwt
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ciq_api.source_scopes import SyntheticSourceScopes
from ciq_api.worker_replay import ReplayLedger

ISSUER = "urn:cashlessiq:internal:offline"
MAX_LIFETIME = 30
Disclosure = Literal["nonclinical", "medical"]


class WorkerDenied(Exception):
    """Generic denial; never embed a token, source payload or underlying error."""


class Assertion(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    iss: Literal["urn:cashlessiq:internal:offline"]
    aud: str = Field(min_length=1, max_length=120)
    sub: str = Field(min_length=1, max_length=200)
    tenant: str
    disclosure: Disclosure
    operation: Literal["validate_summary"]
    request_id: str = Field(min_length=1, max_length=20)
    iat: int
    exp: int
    jti: str = Field(min_length=1, max_length=80)


@dataclass(frozen=True)
class Membership:
    tenant_id: UUID
    role: Literal["processor", "auditor", "medical_officer"]


def _membership_matches(claims: Assertion, member: Membership | None) -> bool:
    return (
        member is not None
        and str(member.tenant_id) == claims.tenant
        and member.role in {"processor", "auditor", "medical_officer"}
        and claims.disclosure == ("medical" if member.role == "medical_officer" else "nonclinical")
    )


def issue_summary_assertion(
    private_key: object,
    *,
    subject: str,
    membership: Membership,
    audience: str,
    request_id: str,
    scopes: SyntheticSourceScopes,
    now: int,
) -> str:
    """Mint only after a trusted broker has authenticated and resolved membership."""
    scope = scopes.get(membership.tenant_id)
    if scope is None or request_id not in scope.request_ids:
        raise WorkerDenied("Worker access denied")
    claims = Assertion(
        iss=ISSUER,
        aud=audience,
        sub=subject,
        tenant=str(membership.tenant_id),
        disclosure="medical" if membership.role == "medical_officer" else "nonclinical",
        operation="validate_summary",
        request_id=request_id,
        iat=now,
        exp=now + MAX_LIFETIME,
        jti=str(uuid4()),
    )
    if not _membership_matches(claims, membership):
        raise WorkerDenied("Worker access denied")
    return jwt.encode(claims.model_dump(), private_key, algorithm="RS256")


class SummaryAuthority:
    """One fixed tenant/audience validator; no key discovery or caller role switching."""

    def __init__(
        self,
        *,
        public_key: object,
        audience: str,
        tenant_id: UUID,
        scopes: SyntheticSourceScopes,
        membership: Callable[[str], Membership | None],
        clock: Callable[[], int],
        capacity: int = 1000,
        replay: ReplayLedger | None = None,
    ):
        scope = scopes.get(tenant_id)
        if scope is None or type(capacity) is not int or capacity < 1:
            raise ValueError("Invalid offline worker configuration")
        self._key = public_key
        self._audience = audience
        self._scope = scope
        self._membership = membership
        self._clock = clock
        self._capacity = capacity
        self._used: dict[str, int] = {}
        self._lock = Lock()
        self._replay = replay
        self._replay_namespace = sha256(f"{ISSUER}\0{audience}\0{tenant_id}".encode()).hexdigest()

    def _check_current(self, claims: Assertion) -> None:
        now = self._clock()
        if (
            claims.tenant != str(self._scope.tenant_id)
            or claims.request_id not in self._scope.request_ids
            or not claims.iat <= now < claims.exp
            or not 0 < claims.exp - claims.iat <= MAX_LIFETIME
            or not _membership_matches(claims, self._membership(claims.sub))
        ):
            raise WorkerDenied("Worker access denied")

    def _parse_claims(self, raw: dict) -> Assertion:
        return Assertion.model_validate(raw)

    def consume(self, token: str) -> Assertion:
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
            self._check_current(claims)
            now = self._clock()
            if not claims.iat <= now < claims.exp:
                raise WorkerDenied("Worker access denied")
            if self._replay is not None:
                self._replay.consume(
                    self._replay_namespace,
                    sha256(claims.jti.encode()).hexdigest(),
                    claims.exp,
                    now,
                )
            else:
                with self._lock:
                    self._used = {key: expiry for key, expiry in self._used.items() if expiry > now}
                    if claims.jti in self._used or len(self._used) >= self._capacity:
                        raise WorkerDenied("Worker access denied")
                    self._used[claims.jti] = claims.exp
            if not claims.iat <= self._clock() < claims.exp:
                raise WorkerDenied("Worker access denied")
            return claims
        except (jwt.PyJWTError, ValidationError, ValueError, TypeError, WorkerDenied):
            raise WorkerDenied("Worker access denied") from None
        except Exception:
            # Membership outage is denial, never a stale positive authorisation.
            raise WorkerDenied("Worker access denied") from None

    def before_delivery(self, claims: Assertion) -> None:
        """Recheck after source work, including expiry and medical downgrade."""
        try:
            self._check_current(claims)
        except Exception:
            raise WorkerDenied("Worker access denied") from None
