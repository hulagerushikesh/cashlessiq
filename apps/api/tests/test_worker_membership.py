"""Real local TLS + disposable PostgreSQL; no live identity or Snowflake use."""

import json
from contextlib import contextmanager
from http.client import HTTPSConnection
from threading import Thread
from unittest.mock import Mock
from uuid import uuid4

import jwt
import pytest
from sqlalchemy.orm import Session
from test_worker_delegation import delegation as delegation
from test_worker_delegation import unpack
from test_worker_transport import context
from test_worker_transport import pki as pki

from ciq_api.models import AppUser, Tenant
from ciq_api.models import Membership as StoredMembership
from ciq_api.source_alpha import SOURCE_TENANTS
from ciq_api.worker_authority import Membership, WorkerDenied
from ciq_api.worker_broker import WorkerMembershipStore
from ciq_api.worker_membership import (
    MEMBERSHIP_PATH,
    LoopbackMembershipClient,
    LoopbackMembershipServer,
)


@contextmanager
def service(pki, lookup, *, tenants=None, peers=None):
    listener = LoopbackMembershipServer(
        context=context(pki, "membership", server=True),
        peers=peers or {pki[1]["reader"][2]: "reader:0:nonclinical"},
        tenants=tenants or {"reader:0:nonclinical": SOURCE_TENANTS[0].tenant_id},
        lookup=lookup,
    )
    thread = Thread(target=listener.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
    thread.start()
    try:
        yield listener.server_port
    finally:
        listener.shutdown()
        listener.server_close()
        thread.join(timeout=4)
        assert not thread.is_alive()


def client(pki, port, *, tenant=None, name="reader"):
    return LoopbackMembershipClient(
        context=context(pki, name),
        port=port,
        server_pin=pki[1]["membership"][2],
        server_audience="membership:0",
        tenant_id=tenant or SOURCE_TENANTS[0].tenant_id,
    )


@pytest.fixture
def stored(engine):
    tenant = SOURCE_TENANTS[0].tenant_id
    user = uuid4()
    with Session(engine) as session, session.begin():
        session.add(Tenant(id=tenant, name="Synthetic membership transport"))
        session.add(
            AppUser(id=user, issuer="urn:test:membership", subject="oidc", display_name="A")
        )
        session.flush()
        session.add(StoredMembership(tenant_id=tenant, user_id=user, role="medical_officer"))
    return tenant, user, WorkerMembershipStore(lambda: Session(engine))


@pytest.mark.parametrize("role", ["processor", "auditor", "medical_officer"])
def test_fresh_database_role_no_cache_or_worker_db_credential(pki, engine, stored, role):
    tenant, user, store = stored
    lookup = Mock(side_effect=store.lookup)
    with service(pki, lookup) as port:
        remote = client(pki, port)
        assert remote.lookup(str(user)) == Membership(tenant, "medical_officer")
        with Session(engine) as session, session.begin():
            session.get(StoredMembership, (tenant, user)).role = role
        assert remote.lookup(str(user)) == Membership(tenant, role)
        assert remote.lookup(str(uuid4())) is None
    assert lookup.call_count == 3
    assert not hasattr(remote, "_sessions")


@pytest.mark.parametrize("inactive", ["user", "tenant", "membership"])
def test_database_revocation_visible_on_next_network_check(pki, engine, stored, inactive):
    tenant, user, store = stored
    with service(pki, store.lookup) as port:
        remote = client(pki, port)
        assert remote.lookup(str(user)) is not None
        with Session(engine) as session, session.begin():
            model, key = {
                "user": (AppUser, user),
                "tenant": (Tenant, tenant),
                "membership": (StoredMembership, (tenant, user)),
            }[inactive]
            session.get(model, key).active = False
        assert remote.lookup(str(user)) is None


def test_foreign_client_denied_before_database_lookup(pki):
    lookup = Mock()
    with service(pki, lookup) as port, pytest.raises(WorkerDenied):
        client(pki, port, name="foreign").lookup(str(uuid4()))
    lookup.assert_not_called()


def test_worker_cannot_choose_tenant_and_client_checks_returned_tenant(pki):
    lookup = Mock(return_value=None)
    with service(pki, lookup) as port, pytest.raises(WorkerDenied):
        client(pki, port, tenant=SOURCE_TENANTS[1].tenant_id).lookup(str(uuid4()))
    assert lookup.call_args.args[1] == SOURCE_TENANTS[0].tenant_id


@pytest.mark.parametrize("failure", ["exception", "foreign", "invalid_role"])
def test_lookup_failure_never_becomes_missing_or_leaks_error(pki, capsys, failure):
    lookup = Mock(return_value=Membership(SOURCE_TENANTS[1].tenant_id, "processor"))
    if failure == "exception":
        lookup.side_effect = RuntimeError("private DB credential and detail")
    if failure == "invalid_role":
        lookup.return_value = Membership(SOURCE_TENANTS[0].tenant_id, "admin")
    with service(pki, lookup) as port, pytest.raises(WorkerDenied, match=r"^Worker access denied$"):
        client(pki, port).lookup(str(uuid4()))
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize(
    "change",
    ["tenant", "role", "peer", "nonce", "subject", "duplicate", "summary"],
)
def test_wire_rejects_scope_identity_role_injection_and_malformed_uuid(pki, change):
    lookup = Mock()
    message = {"subject": str(uuid4()), "nonce": str(uuid4())}
    if change in {"tenant", "role", "peer"}:
        message[change] = "spoofed"
    elif change in {"nonce", "subject"}:
        message[change] = "not-an-internal-uuid"
    elif change == "summary":
        message = {"token": "not-a-membership-query"}
    body = json.dumps(message)
    if change == "duplicate":
        body = body[:-1] + ',"subject":"duplicate"}'
    with service(pki, lookup) as port:
        connection = HTTPSConnection("127.0.0.1", port, context=context(pki, "reader"), timeout=3)
        try:
            connection.request(
                "POST", MEMBERSHIP_PATH, body, headers={"Content-Type": "application/json"}
            )
            response = connection.getresponse()
            assert response.status == 403
            assert response.getheader("Cache-Control") == "no-store"
            assert response.read() == b'{"error":"Worker access denied"}'
        finally:
            connection.close()
    lookup.assert_not_called()


@pytest.mark.parametrize("field", ["subject", "nonce", "tenant", "role", "extra"])
def test_client_rejects_mismatched_or_widened_response(pki, field):
    remote = client(pki, 1)

    def tamper(message):
        result = {**message, "tenant": str(SOURCE_TENANTS[0].tenant_id), "role": "processor"}
        result[field] = "invalid"
        return result

    remote._exchange = tamper
    with pytest.raises(WorkerDenied):
        remote.lookup(str(uuid4()))


@pytest.mark.parametrize("change", ["revoke", "downgrade", "outage"])
def test_validator_rechecks_remote_membership_after_source_work(pki, delegation, change):
    key, state, read, endpoint, relay, _, issue = delegation("medical_officer")
    subject = str(uuid4())
    lookup = Mock(side_effect=lambda *_: state["member"])
    with service(pki, lookup) as port:
        remote = client(pki, port)
        relay._authority._membership = remote.lookup
        endpoint._authority._membership = remote.lookup
        parent = unpack(issue())
        child = unpack(parent["summary_token"])
        parent["sub"] = child["sub"] = subject
        parent["summary_token"] = jwt.encode(child, key, algorithm="RS256")
        token = jwt.encode(parent, key, algorithm="RS256")
        inputs = read.return_value

        def during_read(_):
            if change == "outage":
                lookup.side_effect = RuntimeError("DB unavailable")
            else:
                state["member"] = (
                    None
                    if change == "revoke"
                    else Membership(state["member"].tenant_id, "processor")
                )
            return inputs

        read.side_effect = during_read
        with pytest.raises(WorkerDenied):
            relay.summary(token)
    read.assert_called_once()
    assert lookup.call_count >= 3


def test_configuration_requires_exact_peer_tenant_mapping(pki):
    with pytest.raises(ValueError, match="Invalid membership peer"):
        LoopbackMembershipServer(
            context=context(pki, "membership", server=True),
            peers={pki[1]["reader"][2]: "reader:0:nonclinical"},
            tenants={"other-peer": SOURCE_TENANTS[0].tenant_id},
            lookup=Mock(),
        )


@pytest.mark.parametrize("role", ["processor", "auditor", "medical_officer"])
@pytest.mark.parametrize("index,request_id", [(0, "GOL001"), (1, "GOL024")])
def test_remote_membership_composes_with_both_authorities(pki, delegation, role, index, request_id):
    key, state, read, endpoint, relay, _, issue = delegation(role, index, request_id)
    tenant = state["member"].tenant_id
    lookup = Mock(side_effect=lambda *_: state["member"])
    with service(pki, lookup, tenants={"reader:0:nonclinical": tenant}) as port:
        # Test cert labels are fixed; production peer maps must match deployment identities.
        remote = client(pki, port, tenant=tenant)
        relay._authority._membership = remote.lookup
        endpoint._authority._membership = remote.lookup
        parent = unpack(issue())
        child = unpack(parent["summary_token"])
        parent["sub"] = child["sub"] = str(uuid4())
        parent["summary_token"] = jwt.encode(child, key, algorithm="RS256")
        token = jwt.encode(parent, key, algorithm="RS256")
        result = relay.summary(token)
    assert result.recommendation.state == ("SAVED" if index == 0 else "MISSING")
    assert lookup.call_count == 4  # reader/validator before input and before delivery
    read.assert_called_once_with(request_id)


def test_reader_rechecks_network_membership_after_validator_returns(pki, delegation):
    key, state, read, endpoint, relay, invoke, issue = delegation("medical_officer")
    lookup = Mock(side_effect=lambda *_: state["member"])
    with service(pki, lookup) as port:
        remote = client(pki, port)
        relay._authority._membership = remote.lookup
        endpoint._authority._membership = remote.lookup
        parent = unpack(issue())
        child = unpack(parent["summary_token"])
        parent["sub"] = child["sub"] = str(uuid4())
        parent["summary_token"] = jwt.encode(child, key, algorithm="RS256")
        original = invoke.side_effect

        def downgrade(token):
            result = original(token)
            state["member"] = Membership(state["member"].tenant_id, "processor")
            return result

        invoke.side_effect = downgrade
        with pytest.raises(WorkerDenied):
            relay.summary(jwt.encode(parent, key, algorithm="RS256"))
    read.assert_called_once()
    assert lookup.call_count == 4
