"""PostgreSQL integration fixtures isolated in a disposable per-test schema."""

import os
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from ciq_api.auth import LOCAL_ISSUER
from ciq_api.config import Settings
from ciq_api.main import create_app
from ciq_api.models import AppUser, Membership, Tenant
from ciq_api.seed import PROFILES, TENANT_ID


@pytest.fixture
def settings():
    return Settings(
        environment="test",
        auth_mode="local",
        local_auth_secret="test-only-signing-key-with-at-least-32-characters",
    )


@pytest.fixture
def engine():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.fail("TEST_DATABASE_URL is required; run make product-up then make product-test")
    schema = "test_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    isolated = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        with isolated.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        with Session(isolated) as session, session.begin():
            session.add(Tenant(id=TENANT_ID, name="Synthetic test TPA"))
            session.flush()
            for profile, (user_id, name) in PROFILES.items():
                session.add(
                    AppUser(
                        id=UUID(user_id),
                        issuer=LOCAL_ISSUER,
                        subject=profile,
                        display_name=name,
                    )
                )
                session.flush()
                session.add(Membership(tenant_id=TENANT_ID, user_id=UUID(user_id), role=profile))
        yield isolated
    finally:
        isolated.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture
def client(settings, engine):
    with TestClient(create_app(settings, engine)) as http:
        yield http
