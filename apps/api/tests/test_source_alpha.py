"""Real PostgreSQL membership checks for optional, disjoint synthetic tenants."""

from unittest.mock import MagicMock

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import ciq_api.seed as identity_seed
from ciq_api.auth import LOCAL_ISSUER, issue_local_token
from ciq_api.models import AppUser, Membership, Tenant
from ciq_api.source_alpha import SOURCE_TENANTS
from ciq_api.source_scopes import source_alpha_scopes


@pytest.fixture
def seed_source(monkeypatch, engine, settings):
    monkeypatch.setattr(identity_seed, "make_engine", lambda _: engine)

    def run():
        identity_seed.seed(settings, include_source_tenants=True)

    return run


def bearer(settings, source, profile):
    token = issue_local_token(settings, profile.subject, source.tenant_id)
    return {"Authorization": f"Bearer {token}"}


def test_default_seed_does_not_provision_source_tenants(monkeypatch, engine, settings):
    monkeypatch.setattr(identity_seed, "make_engine", lambda _: engine)
    identity_seed.seed(settings)
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Tenant)) == 1
        assert session.scalar(select(func.count()).select_from(AppUser)) == 3
        assert session.scalar(select(func.count()).select_from(Membership)) == 3


def test_optional_seed_idempotent_with_one_membership_per_user(seed_source, engine):
    seed_source()
    seed_source()
    scopes = source_alpha_scopes()
    assert scopes.get(identity_seed.TENANT_ID) is None
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Tenant)) == 3
        assert session.scalar(select(func.count()).select_from(AppUser)) == 9
        assert session.scalar(select(func.count()).select_from(Membership)) == 9
        for source in SOURCE_TENANTS:
            assert scopes.get(source.tenant_id).tpa_id == source.tpa_id
            for profile in source.profiles:
                user = session.get(AppUser, profile.user_id)
                assert (user.issuer, user.subject) == (LOCAL_ISSUER, profile.subject)
                memberships = session.scalars(
                    select(Membership).where(Membership.user_id == profile.user_id)
                ).all()
                assert len(memberships) == 1
                assert memberships[0].tenant_id == source.tenant_id
                assert memberships[0].role == profile.role


@pytest.mark.parametrize("source", SOURCE_TENANTS, ids=lambda source: source.tpa_id)
def test_all_source_profiles_resolve_only_their_own_membership(
    seed_source, client, settings, source
):
    seed_source()
    for profile in source.profiles:
        response = client.get("/v1/me", headers=bearer(settings, source, profile))
        assert response.status_code == 200
        assert response.json()["tenant"]["id"] == str(source.tenant_id)
        assert response.json()["role"] == profile.role
        assert ("case:approve" in response.json()["capabilities"]) == (
            profile.role == "medical_officer"
        )
        for other_id in (
            identity_seed.TENANT_ID,
            *(t.tenant_id for t in SOURCE_TENANTS if t != source),
        ):
            token = issue_local_token(settings, profile.subject, other_id)
            assert (
                client.get("/v1/me", headers={"Authorization": f"Bearer {token}"}).status_code
                == 403
            )
    demo_token = issue_local_token(settings, "processor", source.tenant_id)
    assert (
        client.get("/v1/me", headers={"Authorization": f"Bearer {demo_token}"}).status_code == 403
    )


def test_source_identity_does_not_fall_back_to_offline_cases(seed_source, client, settings):
    seed_source()
    for source in SOURCE_TENANTS:
        headers = bearer(settings, source, source.profiles[0]) | {
            "X-Tenant-ID": str(identity_seed.TENANT_ID),
            "X-TPA-ID": "TPA001",
        }
        assert client.get("/v1/cases", headers=headers).json()["total"] == 0
        for request_id in ("GOL001", "GOL024", "GOL027"):
            assert client.get(f"/v1/cases/{request_id}", headers=headers).status_code == 404
    # Existing mixed demo journey is intentionally unchanged.
    token = issue_local_token(settings, "processor", identity_seed.TENANT_ID)
    assert (
        client.get("/v1/cases", headers={"Authorization": f"Bearer {token}"}).json()["total"] == 3
    )


@pytest.mark.parametrize("entity", ["user", "membership", "tenant"])
def test_reseed_does_not_restore_revoked_access(seed_source, client, settings, engine, entity):
    seed_source()
    source = SOURCE_TENANTS[0]
    profile = source.profiles[0]
    headers = bearer(settings, source, profile)
    assert client.get("/v1/me", headers=headers).status_code == 200
    with Session(engine) as session, session.begin():
        record = (
            session.get(AppUser, profile.user_id)
            if entity == "user"
            else session.get(Tenant, source.tenant_id)
            if entity == "tenant"
            else session.get(Membership, (source.tenant_id, profile.user_id))
        )
        record.active = False
    seed_source()
    assert client.get("/v1/me", headers=headers).status_code == 403
    assert client.get("/v1/cases", headers=headers).status_code == 403


def test_seed_refuses_identity_collision_and_rolls_back(seed_source, engine):
    profile = SOURCE_TENANTS[0].profiles[0]
    with Session(engine) as session, session.begin():
        session.add(
            AppUser(
                id=profile.user_id,
                issuer=LOCAL_ISSUER,
                subject="unrelated",
                display_name="Existing identity",
            )
        )
    with pytest.raises(RuntimeError, match="identity conflict"):
        seed_source()
    with Session(engine) as session:
        assert session.get(Tenant, SOURCE_TENANTS[0].tenant_id) is None
        assert session.get(AppUser, profile.user_id).subject == "unrelated"


def test_source_seed_rejected_outside_local_identity(settings, monkeypatch):
    connect = MagicMock()
    monkeypatch.setattr(identity_seed, "make_engine", connect)
    for environment, mode in (("production", "oidc"), ("staging", "oidc"), ("local", "oidc")):
        config = settings.model_copy(update={"environment": environment, "auth_mode": mode})
        with pytest.raises(RuntimeError, match="local/test"):
            identity_seed.seed(config, include_source_tenants=True)
    connect.assert_not_called()


def test_manifest_alone_does_not_grant_access(client, settings):
    source = SOURCE_TENANTS[0]
    assert source_alpha_scopes().get(source.tenant_id) is not None
    assert (
        client.get("/v1/me", headers=bearer(settings, source, source.profiles[0])).status_code
        == 403
    )


def test_local_bootstrap_cannot_select_source_identity(seed_source, client, settings):
    seed_source()
    response = client.post(
        "/v1/auth/local/session",
        json={"profile": SOURCE_TENANTS[0].profiles[0].subject},
        headers={"X-Local-Auth-Key": settings.local_auth_secret.get_secret_value()},
    )
    assert response.status_code == 422


def test_reseed_preserves_database_owned_role(seed_source, client, settings, engine):
    seed_source()
    source = SOURCE_TENANTS[0]
    profile = source.profiles[1]
    with Session(engine) as session, session.begin():
        session.get(Membership, (source.tenant_id, profile.user_id)).role = "auditor"
    seed_source()
    response = client.get("/v1/me", headers=bearer(settings, source, profile))
    assert response.json()["role"] == "auditor"
    assert "case:approve" not in response.json()["capabilities"]
