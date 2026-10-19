"""Token verification and database-backed membership resolution."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID, uuid4

import jwt
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ciq_api.config import Settings
from ciq_api.contracts import MeResponse, TenantView, UserView
from ciq_api.models import AppUser, Membership, Tenant

LOCAL_ISSUER = "urn:cashlessiq:local"
CAPABILITIES = {
    "processor": ["case:read", "case:draft", "case:query"],
    "medical_officer": ["case:read", "case:draft", "case:query", "case:refer", "case:approve"],
    "auditor": ["case:read", "audit:read"],
}


@dataclass(frozen=True)
class Principal:
    issuer: str
    subject: str
    tenant_id: UUID


class IdentityVerifier(Protocol):
    def verify(self, token: str) -> Principal: ...


class JWTVerifier:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.jwks = (
            jwt.PyJWKClient(settings.oidc_jwks_url, timeout=5)
            if settings.auth_mode == "oidc"
            else None
        )

    def verify(self, token: str) -> Principal:
        try:
            local = self.settings.auth_mode == "local"
            key = (
                self.settings.local_auth_secret.get_secret_value()
                if local
                else self.jwks.get_signing_key_from_jwt(token).key
            )
            claims = jwt.decode(
                token,
                key,
                algorithms=["HS256"] if local else ["RS256"],
                issuer=LOCAL_ISSUER if local else self.settings.oidc_issuer,
                audience=self.settings.oidc_audience,
                options={"require": ["exp", "iat", "iss", "aud", "sub", "ciq_tenant_id"]},
            )
            return Principal(claims["iss"], claims["sub"], UUID(claims["ciq_tenant_id"]))
        except (jwt.PyJWTError, ValueError, TypeError, KeyError):
            raise HTTPException(401, "Invalid or expired session") from None


def issue_local_token(settings: Settings, subject: str, tenant_id: UUID) -> str:
    if settings.auth_mode != "local" or settings.environment not in {"local", "test"}:
        raise HTTPException(404, "Not found")
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "iss": LOCAL_ISSUER,
            "aud": settings.oidc_audience,
            "sub": subject,
            "ciq_tenant_id": str(tenant_id),
            "iat": now,
            "exp": now + timedelta(minutes=30),
            "jti": str(uuid4()),
        },
        settings.local_auth_secret.get_secret_value(),
        algorithm="HS256",
    )


def resolve_identity(session: Session, principal: Principal, mode: str) -> MeResponse:
    row = session.execute(
        select(AppUser, Membership, Tenant)
        .join(Membership, Membership.user_id == AppUser.id)
        .join(Tenant, Tenant.id == Membership.tenant_id)
        .where(
            AppUser.issuer == principal.issuer,
            AppUser.subject == principal.subject,
            AppUser.active.is_(True),
            Membership.tenant_id == principal.tenant_id,
            Membership.active.is_(True),
            Tenant.active.is_(True),
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(403, "No active tenant membership")
    user, membership, tenant = row
    return MeResponse(
        user=UserView(id=user.id, display_name=user.display_name),
        tenant=TenantView(id=tenant.id, name=tenant.name),
        role=membership.role,
        capabilities=CAPABILITIES[membership.role],
        identity_mode=mode,
    )
