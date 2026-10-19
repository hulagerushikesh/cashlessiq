"""Ephemeral in-memory signing keys and fake membership; no network/source calls."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from ciq_api.source_alpha import SOURCE_TENANTS
from ciq_api.source_scopes import source_alpha_scopes
from ciq_api.worker_authority import (
    Membership,
    SummaryAuthority,
    WorkerDenied,
    issue_summary_assertion,
)


@pytest.fixture
def boundary():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    tenant = SOURCE_TENANTS[0].tenant_id
    state = {"now": 1000, "member": Membership(tenant, "processor"), "calls": 0}

    def member(subject):
        state["calls"] += 1
        assert subject == "reviewer"
        return state["member"]

    def worker(**overrides):
        return SummaryAuthority(
            **{
                "public_key": private.public_key(),
                "audience": "validator:tpa001",
                "tenant_id": tenant,
                "scopes": source_alpha_scopes(),
                "membership": member,
                "clock": lambda: state["now"],
                **overrides,
            }
        )

    def token(**overrides):
        return issue_summary_assertion(
            private,
            **{
                "subject": "reviewer",
                "membership": state["member"],
                "audience": "validator:tpa001",
                "request_id": "GOL001",
                "scopes": source_alpha_scopes(),
                "now": state["now"],
                **overrides,
            },
        )

    return private, state, worker, token


@pytest.mark.parametrize("role", ["processor", "auditor", "medical_officer"])
def test_fresh_membership_each_read_and_delivery(boundary, role):
    _, state, worker, token = boundary
    state["member"] = replace(state["member"], role=role)
    authority = worker()
    claims = authority.consume(token())
    authority.before_delivery(claims)
    assert state["calls"] == 2


@pytest.mark.parametrize("change", ["revoked", "foreign", "downgraded", "expired"])
def test_delivery_rechecks_membership_and_time(boundary, change):
    _, state, worker, token = boundary
    state["member"] = replace(state["member"], role="medical_officer")
    authority = worker()
    claims = authority.consume(token())
    if change == "revoked":
        state["member"] = None
    elif change == "foreign":
        state["member"] = Membership(SOURCE_TENANTS[1].tenant_id, "medical_officer")
    elif change == "downgraded":
        state["member"] = replace(state["member"], role="processor")
    else:
        state["now"] += 30
    with pytest.raises(WorkerDenied):
        authority.before_delivery(claims)


@pytest.mark.parametrize(
    "field,value",
    [
        ("aud", "other-worker"),
        ("tenant", str(SOURCE_TENANTS[1].tenant_id)),
        ("request_id", "GOL024"),
        ("operation", "export_raw"),
        ("disclosure", "medical"),
        ("exp", 1031),
        ("iat", 1001),
        ("iat", True),
        ("sql", "SELECT secret"),
    ],
)
def test_signed_but_invalid_assertions_denied(boundary, field, value):
    private, _, worker, token = boundary
    raw = jwt.decode(token(), options={"verify_signature": False})
    raw[field] = value
    with pytest.raises(WorkerDenied):
        worker().consume(jwt.encode(raw, private, algorithm="RS256"))


def test_wrong_signer_denied_before_membership(boundary):
    _, state, worker, token = boundary
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(WorkerDenied):
        worker(public_key=other.public_key()).consume(token())
    assert state["calls"] == 0


def test_replay_and_capacity_fail_closed(boundary):
    _, state, worker, token = boundary
    authority = worker(capacity=1)
    signed = token()
    authority.consume(signed)
    with pytest.raises(WorkerDenied):
        authority.consume(signed)
    with pytest.raises(WorkerDenied):
        authority.consume(token())
    state["now"] += 30
    authority.consume(token())


def test_concurrent_replay_has_one_winner(boundary):
    _, _, worker, token = boundary
    authority, signed = worker(), token()

    def attempt(_):
        try:
            authority.consume(signed)
            return True
        except WorkerDenied:
            return False

    with ThreadPoolExecutor(max_workers=8) as executor:
        assert sum(executor.map(attempt, range(8))) == 1


def test_membership_outage_denied(boundary):
    _, _, worker, token = boundary

    def outage(_):
        raise RuntimeError("private database details")

    with pytest.raises(WorkerDenied, match=r"^Worker access denied$"):
        worker(membership=outage).consume(token())


def test_broker_rejects_foreign_case_before_signing(boundary):
    _, _, _, token = boundary
    with pytest.raises(WorkerDenied):
        token(request_id="GOL027")
