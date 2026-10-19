"""Exercise RS256 verification with an in-memory issuer; no network or paid IdP."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

from ciq_api.auth import JWTVerifier
from ciq_api.config import Settings
from ciq_api.seed import TENANT_ID


def test_oidc_signature_and_claims(monkeypatch):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    verifier = JWTVerifier(
        Settings(
            environment="staging",
            auth_mode="oidc",
            oidc_issuer="https://identity.example",
            oidc_jwks_url="https://identity.example/jwks.json",
        )
    )
    monkeypatch.setattr(
        verifier.jwks,
        "get_signing_key_from_jwt",
        lambda token: SimpleNamespace(key=private.public_key()),
    )
    now = datetime.now(UTC)
    claims = {
        "iss": "https://identity.example",
        "aud": "cashlessiq-api",
        "sub": "external-reviewer",
        "ciq_tenant_id": str(TENANT_ID),
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    token = jwt.encode(claims, private, algorithm="RS256")
    assert verifier.verify(token).subject == "external-reviewer"
    assert verifier.verify(token).tenant_id == TENANT_ID
    del claims["ciq_tenant_id"]
    with pytest.raises(HTTPException) as rejected:
        verifier.verify(jwt.encode(claims, private, algorithm="RS256"))
    assert rejected.value.status_code == 401


def test_oidc_configuration_requires_https():
    with pytest.raises(ValueError, match="HTTPS"):
        Settings(auth_mode="oidc", oidc_issuer="http://issuer", oidc_jwks_url="http://issuer/jwks")
