"""Verify identity, revocation, tenant boundaries, and database readiness."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from ciq_api.auth import LOCAL_ISSUER, issue_local_token
from ciq_api.config import Settings
from ciq_api.main import create_app
from ciq_api.models import AppUser, Membership, Tenant
from ciq_api.seed import PROFILES, TENANT_ID


def bearer(settings, profile="processor", tenant_id=TENANT_ID):
    return {"Authorization": f"Bearer {issue_local_token(settings, profile, tenant_id)}"}


def test_health_and_readiness(client):
    assert client.get("/health/live").json() == {"status": "ok"}
    assert client.get("/health/ready").json() == {"status": "ready"}


def test_readiness_detects_missing_migration(client, engine):
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE alembic_version"))
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 503


@pytest.mark.parametrize("profile", PROFILES)
def test_identity_and_role_capabilities(client, settings, profile):
    response = client.get("/v1/me", headers=bearer(settings, profile))
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == profile
    assert data["user"]["display_name"] == PROFILES[profile][1]
    assert data["tenant"]["id"] == str(TENANT_ID)
    assert ("case:approve" in data["capabilities"]) == (profile == "medical_officer")
    assert response.headers["cache-control"] == "no-store"


def test_unauthenticated_and_malformed_tokens_rejected(client):
    assert client.get("/v1/me").status_code == 401
    assert client.get("/v1/me", headers={"Authorization": "Bearer bogus"}).status_code == 401


@pytest.mark.parametrize(
    "mutation", ["expired", "wrong_audience", "wrong_issuer", "wrong_signature"]
)
def test_invalid_signed_claims_rejected(client, settings, mutation):
    now = datetime.now(UTC)
    claims = {
        "iss": LOCAL_ISSUER,
        "aud": settings.oidc_audience,
        "sub": "processor",
        "iat": now,
        "exp": now + timedelta(minutes=5),
        "ciq_tenant_id": str(TENANT_ID),
    }
    key = settings.local_auth_secret.get_secret_value()
    if mutation == "expired":
        claims["exp"] = now - timedelta(seconds=5)
    elif mutation == "wrong_audience":
        claims["aud"] = "another-api"
    elif mutation == "wrong_issuer":
        claims["iss"] = "urn:another-issuer"
    else:
        key = "a-different-test-only-secret-key-of-sufficient-length"
    token = jwt.encode(claims, key, algorithm="HS256")
    assert client.get("/v1/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_cross_tenant_membership_cannot_be_forged(client, settings, engine):
    other = uuid4()
    with Session(engine) as session, session.begin():
        session.add(Tenant(id=other, name="Different tenant"))
    assert client.get("/v1/me", headers=bearer(settings, tenant_id=other)).status_code == 403
    # Client-supplied tenant/role headers cannot override the signed/database context.
    response = client.get(
        "/v1/me",
        headers=bearer(settings)
        | {
            "X-Tenant-ID": str(other),
            "X-Role": "medical_officer",
        },
    )
    assert response.json()["tenant"]["id"] == str(TENANT_ID)
    assert response.json()["role"] == "processor"


@pytest.mark.parametrize("entity", ["user", "membership", "tenant"])
def test_revocation_applies_to_existing_session(client, settings, engine, entity):
    headers = bearer(settings)
    assert client.get("/v1/me", headers=headers).status_code == 200
    with Session(engine) as session, session.begin():
        user_id = UUID(PROFILES["processor"][0])
        obj = (
            session.get(AppUser, user_id)
            if entity == "user"
            else session.get(Tenant, TENANT_ID)
            if entity == "tenant"
            else session.get(Membership, (TENANT_ID, user_id))
        )
        obj.active = False
    assert client.get("/v1/me", headers=headers).status_code == 403


def test_local_bootstrap_requires_server_key(client, settings):
    assert client.post("/v1/auth/local/session", json={"profile": "processor"}).status_code == 401
    response = client.post(
        "/v1/auth/local/session",
        json={"profile": "processor"},
        headers={"X-Local-Auth-Key": settings.local_auth_secret.get_secret_value()},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    assert client.get("/v1/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_local_auth_impossible_in_production():
    with pytest.raises(ValidationError, match="local/test"):
        Settings(environment="production", auth_mode="local", local_auth_secret="x" * 40)


def test_oidc_mode_does_not_expose_local_bootstrap(engine):
    settings = Settings(
        environment="staging",
        auth_mode="oidc",
        oidc_issuer="https://identity.example",
        oidc_jwks_url="https://identity.example/jwks.json",
    )
    with TestClient(create_app(settings, engine)) as client:
        assert (
            client.post("/v1/auth/local/session", json={"profile": "processor"}).status_code == 404
        )


def test_migration_is_repeatable_and_preserves_append_only_history(engine):
    from pathlib import Path

    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        command.upgrade(config, "head")
        command.check(config)
        with pytest.raises(RuntimeError, match="forward-only"):
            command.downgrade(config, "base")
        assert "review_audit" in inspect(connection).get_table_names()
        assert "tenant_membership" in inspect(connection).get_table_names()
