"""Disposable PostgreSQL membership with in-memory keys and fake source only."""

from copy import deepcopy
from unittest.mock import Mock
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy.orm import Session
from test_source_cases import build_test_sources

from ciq_api.auth import JWTVerifier, Principal, issue_local_token
from ciq_api.models import AppUser, Tenant
from ciq_api.models import Membership as StoredMembership
from ciq_api.source_alpha import SOURCE_TENANTS
from ciq_api.source_scopes import source_alpha_scopes
from ciq_api.validation_worker import OfflineValidationWorker, ValidationInputs
from ciq_api.worker_authority import SummaryAuthority, WorkerDenied
from ciq_api.worker_broker import OfflineSummaryBroker, OfflineSummaryRoute, WorkerMembershipStore
from ciq_api.worker_delegation import (
    DelegatedSummaryAuthority,
    DetailAuthority,
    OfflineDelegatedValidator,
    OfflinePeer,
    OfflineReadRelay,
)


@pytest.fixture(params=["direct", "delegated"])
def broker_setup(engine, settings, request):
    tenant = SOURCE_TENANTS[0].tenant_id
    user_id = uuid4()
    other_id = uuid4()
    with Session(engine) as session, session.begin():
        session.add(Tenant(id=tenant, name="Synthetic worker test"))
        session.add_all(
            [
                AppUser(
                    id=user_id, issuer="urn:cashlessiq:local", subject="same", display_name="A"
                ),
                AppUser(id=other_id, issuer="urn:other", subject="same", display_name="B"),
            ]
        )
        session.flush()
        session.add(StoredMembership(tenant_id=tenant, user_id=user_id, role="processor"))
    store = WorkerMembershipStore(lambda: Session(engine))
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    scopes = source_alpha_scopes()
    _, _, _, cases, details = build_test_sources()
    case = cases[tenant][0]
    rows = deepcopy(details[case.request_id])
    read = Mock(return_value=ValidationInputs(case, rows["decision"], rows["evidence"]))
    state = {"now": 1000}

    def clock():
        return state["now"]

    routes = {}
    calls = {}
    tokens = []
    validator_audience = f"offline:{tenant}:validator"
    delegated_authority = DelegatedSummaryAuthority(
        public_key=key.public_key(),
        audience=validator_audience,
        tenant_id=tenant,
        scopes=scopes,
        membership=lambda subject: store.lookup(subject, tenant),
        clock=clock,
        readers={f"offline:{tenant}:{d}:summary": d for d in ("nonclinical", "medical")},
    )
    delegated_endpoint = OfflineDelegatedValidator(
        delegated_authority,
        OfflineValidationWorker(
            authority=delegated_authority, scope=scopes.get(tenant), read_inputs=read
        ),
    )
    for disclosure in ("nonclinical", "medical"):
        audience = f"offline:{tenant}:{disclosure}:summary"
        authority = SummaryAuthority(
            public_key=key.public_key(),
            audience=audience,
            tenant_id=tenant,
            scopes=scopes,
            membership=lambda subject: store.lookup(subject, tenant),
            clock=clock,
        )
        worker = OfflineValidationWorker(
            authority=authority, scope=scopes.get(tenant), read_inputs=read
        )
        validate = worker.validate
        if request.param == "delegated":
            relay = OfflineReadRelay(
                authority=DetailAuthority(
                    public_key=key.public_key(),
                    audience=audience,
                    tenant_id=tenant,
                    scopes=scopes,
                    membership=lambda subject: store.lookup(subject, tenant),
                    clock=clock,
                    disclosure=disclosure,
                ),
                public_key=key.public_key(),
                validator_audience=validator_audience,
                invoke_validator=lambda token, audience=audience: delegated_endpoint.validate(
                    token, peer=OfflinePeer(audience)
                ),
            )
            validate = relay.summary

        def invoke(token, validate=validate):
            tokens.append(
                jwt.decode(
                    token,
                    key.public_key(),
                    algorithms=["RS256"],
                    options={"verify_aud": False, "verify_exp": False},
                )
            )
            return validate(token)

        calls[disclosure] = Mock(side_effect=invoke)
        routes[(tenant, disclosure)] = OfflineSummaryRoute(
            audience,
            calls[disclosure],
            validator_audience if request.param == "delegated" else None,
        )
    broker = OfflineSummaryBroker(
        verifier=JWTVerifier(settings),
        memberships=store,
        scopes=scopes,
        routes=routes,
        private_key=key,
        clock=clock,
    )
    return (
        broker,
        issue_local_token(settings, "same", tenant),
        store,
        user_id,
        tenant,
        read,
        calls,
        tokens,
        state,
    )


@pytest.mark.parametrize(
    "role,disclosure",
    [("processor", "nonclinical"), ("auditor", "nonclinical"), ("medical_officer", "medical")],
)
def test_fixed_routing_and_internal_uuid_subject(broker_setup, engine, role, disclosure):
    broker, token, _, user_id, tenant, _, calls, tokens, _ = broker_setup
    with Session(engine) as session, session.begin():
        session.get(StoredMembership, (tenant, user_id)).role = role
    result = broker.summary(token, "GOL001")
    assert result.recommendation.payable_inr == 95_000
    calls[disclosure].assert_called_once()
    calls["medical" if disclosure == "nonclinical" else "nonclinical"].assert_not_called()
    assert tokens[0]["sub"] == str(user_id)
    assert tokens[0]["disclosure"] == disclosure


def test_same_oidc_subject_different_issuer_is_not_same_user(broker_setup):
    _, _, store, user_id, tenant, *_ = broker_setup
    assert store.resolve(Principal("urn:other", "same", tenant)) is None
    assert store.lookup("same", tenant) is None
    assert store.lookup(str(user_id), SOURCE_TENANTS[1].tenant_id) is None


@pytest.mark.parametrize("target", ["user", "tenant", "membership"])
def test_inactive_authority_denied_before_worker(broker_setup, engine, target):
    broker, token, _, user_id, tenant, read, calls, _, _ = broker_setup
    with Session(engine) as session, session.begin():
        entity = {
            "user": session.get(AppUser, user_id),
            "tenant": session.get(Tenant, tenant),
            "membership": session.get(StoredMembership, (tenant, user_id)),
        }[target]
        entity.active = False
    with pytest.raises(WorkerDenied):
        broker.summary(token, "GOL001")
    read.assert_not_called()
    assert all(call.call_count == 0 for call in calls.values())


@pytest.mark.parametrize("request_id", ["GOL024", "UNKNOWN"])
def test_foreign_or_unknown_case_does_no_io(broker_setup, request_id):
    broker, token, _, _, _, read, *_ = broker_setup
    with pytest.raises(WorkerDenied):
        broker.summary(token, request_id)
    read.assert_not_called()


@pytest.mark.parametrize(
    "change", ["revoke", "downgrade", "expiry", "wrong_scope", "inactive_user", "inactive_tenant"]
)
def test_broker_checks_delivery_after_worker_returns(broker_setup, engine, change):
    broker, token, _, user_id, tenant, _, calls, _, state = broker_setup
    with Session(engine) as session, session.begin():
        session.get(StoredMembership, (tenant, user_id)).role = "medical_officer"
    original = calls["medical"].side_effect

    def altered(assertion):
        result = original(assertion)
        if change == "expiry":
            state["now"] += 30
        elif change == "wrong_scope":
            return result.model_copy(update={"product_id": "FOREIGN"})
        else:
            with Session(engine) as session, session.begin():
                member = session.get(StoredMembership, (tenant, user_id))
                if change == "inactive_user":
                    session.get(AppUser, user_id).active = False
                elif change == "inactive_tenant":
                    session.get(Tenant, tenant).active = False
                elif change == "revoke":
                    member.active = False
                else:
                    member.role = "processor"
        return result

    calls["medical"].side_effect = altered
    with pytest.raises(WorkerDenied, match=r"^Worker access denied$"):
        broker.summary(token, "GOL001")


def test_bad_session_token_never_routes(broker_setup):
    broker, _, _, _, _, read, *_ = broker_setup
    with pytest.raises(WorkerDenied):
        broker.summary("not-a-token", "GOL001")
    read.assert_not_called()


def test_membership_outage_denies_without_exception_detail():
    store = WorkerMembershipStore(Mock(side_effect=RuntimeError("private connection details")))
    with pytest.raises(WorkerDenied, match=r"^Worker access denied$") as error:
        store.lookup(str(uuid4()), SOURCE_TENANTS[0].tenant_id)
    assert error.value.__cause__ is None
