"""Narrow membership query with disposable PostgreSQL schemas, no service grants."""

from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text, update
from sqlalchemy.orm import Session

from ciq_api.models import AppUser, Membership, Tenant
from ciq_api.seed import PROFILES, TENANT_ID
from ciq_api.worker_authority import WorkerDenied
from ciq_api.worker_membership_store import RestrictedMembershipStore


@pytest.fixture
def lookup(engine):
    with engine.connect() as connection:
        schema = connection.scalar(text("SELECT current_schema()"))
    return RestrictedMembershipStore(engine.connect, schema=schema)


@pytest.mark.parametrize("role", ["processor", "auditor", "medical_officer"])
def test_current_roles(lookup, role):
    member = lookup.lookup(PROFILES[role][0], TENANT_ID)
    assert member.tenant_id == TENANT_ID
    assert member.role == role


@pytest.mark.parametrize("model", [AppUser, Tenant, Membership])
def test_deactivation_is_fresh(engine, lookup, model):
    subject = PROFILES["processor"][0]
    assert lookup.lookup(subject, TENANT_ID) is not None
    with Session(engine) as session, session.begin():
        session.execute(update(model).values(active=False))
    assert lookup.lookup(subject, TENANT_ID) is None


def test_role_change_is_fresh(engine, lookup):
    subject = PROFILES["medical_officer"][0]
    assert lookup.lookup(subject, TENANT_ID).role == "medical_officer"
    with Session(engine) as session, session.begin():
        session.execute(update(Membership).values(role="auditor"))
    assert lookup.lookup(subject, TENANT_ID).role == "auditor"


def test_absence_and_foreign_tenant(lookup):
    assert lookup.lookup(str(uuid4()), TENANT_ID) is None
    assert lookup.lookup(PROFILES["processor"][0], uuid4()) is None


@pytest.mark.parametrize("subject", ["bad", "'; SELECT 1; --", uuid4().hex, None])
def test_bad_identity_never_connects(subject):
    connect = Mock()
    store = RestrictedMembershipStore(connect, schema="public")
    with pytest.raises(WorkerDenied, match=r"^Worker access denied$"):
        store.lookup(subject, TENANT_ID)
    connect.assert_not_called()


def test_database_error_is_denial():
    connect = Mock(side_effect=RuntimeError("private connection information"))
    store = RestrictedMembershipStore(connect, schema="public")
    with pytest.raises(WorkerDenied, match=r"^Worker access denied$"):
        store.lookup(str(uuid4()), TENANT_ID)
    connect.assert_called_once()


@pytest.mark.parametrize("schema", ["x.y", "PUBLIC", "public; DROP TABLE x", "", None])
def test_schema_is_trusted_configuration(schema):
    with pytest.raises(ValueError):
        RestrictedMembershipStore(Mock(), schema=schema)


def test_transaction_is_read_only_and_bounded(engine):
    with engine.connect() as connection:
        schema = connection.scalar(text("SELECT current_schema()"))
    observations = []

    def connect():
        connection = engine.connect()
        from sqlalchemy import event

        @event.listens_for(connection, "before_cursor_execute")
        def capture(_connection, _cursor, statement, _parameters, _context, _many):
            observations.append(statement)

        return connection

    member = RestrictedMembershipStore(connect, schema=schema).lookup(
        PROFILES["processor"][0], TENANT_ID
    )
    assert member is not None
    assert observations[:3] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '1000ms'",
        "SET LOCAL lock_timeout = '250ms'",
    ]
    assert len(observations) == 4
    assert schema + ".app_user" in observations[-1]
    assert "display_name" not in observations[-1]
    assert "issuer" not in observations[-1]
    assert "subject" not in observations[-1]


def test_bad_tenant_never_connects():
    connect = Mock()
    store = RestrictedMembershipStore(connect, schema="public")
    with pytest.raises(WorkerDenied):
        store.lookup(str(UUID(PROFILES["processor"][0])), str(TENANT_ID))
    connect.assert_not_called()
