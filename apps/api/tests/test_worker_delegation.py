"""Fake peer context and raw synthetic inputs; no HTTP/TLS/Snowflake or saved keys."""

from copy import deepcopy
from unittest.mock import Mock

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from test_source_cases import build_test_sources

from ciq_api.source_alpha import SOURCE_TENANTS
from ciq_api.source_scopes import source_alpha_scopes
from ciq_api.validation_worker import OfflineValidationWorker, ValidationInputs
from ciq_api.worker_authority import Membership, WorkerDenied
from ciq_api.worker_delegation import (
    DelegatedSummaryAuthority,
    DetailAuthority,
    OfflineDelegatedValidator,
    OfflinePeer,
    OfflineReadRelay,
    issue_detail_assertion,
)


@pytest.fixture
def delegation():
    def build(role="processor", index=0, request_id="GOL001"):
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        tenant = SOURCE_TENANTS[index]
        scopes = source_alpha_scopes()
        scope = scopes.get(tenant.tenant_id)
        state = {"now": 1000, "member": Membership(tenant.tenant_id, role)}
        disclosure = "medical" if role == "medical_officer" else "nonclinical"
        reader_audience = f"reader:{index}:{disclosure}"
        validator_audience = f"validator:{index}"
        _, _, _, records, details = build_test_sources()
        case = next(row for row in records[tenant.tenant_id] if row.request_id == request_id)
        rows = deepcopy(details[request_id])
        read = Mock(return_value=ValidationInputs(case, rows["decision"], rows["evidence"]))
        common = dict(
            public_key=private.public_key(),
            tenant_id=tenant.tenant_id,
            scopes=scopes,
            membership=lambda _: state["member"],
            clock=lambda: state["now"],
        )
        reader = DetailAuthority(**common, audience=reader_audience, disclosure=disclosure)
        validator = DelegatedSummaryAuthority(
            **common, audience=validator_audience, readers={reader_audience: disclosure}
        )
        worker = OfflineValidationWorker(authority=validator, scope=scope, read_inputs=read)
        endpoint = OfflineDelegatedValidator(validator, worker)
        peer = OfflinePeer(reader_audience)
        invoke = Mock(side_effect=lambda signed: endpoint.validate(signed, peer=peer))
        relay = OfflineReadRelay(
            authority=reader,
            public_key=private.public_key(),
            validator_audience=validator_audience,
            invoke_validator=invoke,
        )

        def issue():
            return issue_detail_assertion(
                private,
                subject="internal-user-uuid",
                membership=state["member"],
                reader_audience=reader_audience,
                validator_audience=validator_audience,
                request_id=request_id,
                scopes=scopes,
                now=state["now"],
            )

        return private, state, read, endpoint, relay, invoke, issue

    return build


def unpack(token):
    return jwt.decode(token, options={"verify_signature": False})


@pytest.mark.parametrize("role", ["processor", "auditor", "medical_officer"])
@pytest.mark.parametrize("index,request_id", [(0, "GOL001"), (1, "GOL024"), (1, "GOL027")])
def test_fixed_delegate_path_and_summary_only(delegation, role, index, request_id):
    _, _, read, _, relay, invoke, issue = delegation(role, index, request_id)
    token = issue()
    result = relay.summary(token)
    assert result.request_id == request_id
    assert result.recommendation.state == ("SAVED" if index == 0 else "MISSING")
    if index == 0:
        assert result.recommendation.payable_inr == 95_000
    payload = result.model_dump_json()
    for field in ('"lines"', '"decision_json"', '"clinical_note"', '"summary"', '"calc"'):
        assert field not in payload
    read.assert_called_once_with(request_id)
    invoke.assert_called_once_with(unpack(token)["summary_token"])
    with pytest.raises(WorkerDenied):
        relay.summary(token)
    assert read.call_count == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("parent_jti", "unrelated-parent"),
        ("reader_audience", "foreign-reader"),
        ("aud", "foreign-validator"),
        ("sub", "other-user"),
        ("tenant", str(SOURCE_TENANTS[1].tenant_id)),
        ("request_id", "GOL024"),
        ("disclosure", "medical"),
        ("operation", "export_raw"),
        ("exp", 1060),
    ],
)
def test_signed_child_cannot_widen_or_swap_parent_scope(delegation, field, value):
    key, _, read, _, relay, invoke, issue = delegation()
    parent = unpack(issue())
    child = unpack(parent["summary_token"])
    child[field] = value
    parent["summary_token"] = jwt.encode(child, key, algorithm="RS256")
    token = jwt.encode(parent, key, algorithm="RS256")
    with pytest.raises(WorkerDenied):
        relay.summary(token)
    read.assert_not_called()
    invoke.assert_not_called()


def test_child_from_another_valid_request_nonce_cannot_be_spliced(delegation):
    key, _, read, _, relay, _, issue = delegation()
    parent = unpack(issue())
    parent["summary_token"] = unpack(issue())["summary_token"]
    with pytest.raises(WorkerDenied):
        relay.summary(jwt.encode(parent, key, algorithm="RS256"))
    read.assert_not_called()


@pytest.mark.parametrize("peer", [None, OfflinePeer("broker"), OfflinePeer("other-reader")])
def test_direct_or_foreign_peer_denied_before_input(delegation, peer):
    _, _, read, endpoint, _, _, issue = delegation()
    child = unpack(issue())["summary_token"]
    with pytest.raises(WorkerDenied):
        endpoint.validate(child, peer=peer)
    read.assert_not_called()
    # A rejected peer does not consume the legitimate reader's capability.
    endpoint.validate(child, peer=OfflinePeer("reader:0:nonclinical"))
    read.assert_called_once()


@pytest.mark.parametrize("change", ["revoke", "downgrade", "expire"])
def test_read_relay_rechecks_delivery_after_validator_return(delegation, change):
    _, state, read, _, relay, invoke, issue = delegation("medical_officer")
    original = invoke.side_effect

    def return_then_change(token):
        result = original(token)
        if change == "revoke":
            state["member"] = None
        elif change == "downgrade":
            state["member"] = Membership(SOURCE_TENANTS[0].tenant_id, "processor")
        else:
            state["now"] += 30
        return result

    invoke.side_effect = return_then_change
    with pytest.raises(WorkerDenied):
        relay.summary(issue())
    read.assert_called_once()


def test_foreign_parent_rejected_before_delegation(delegation):
    key, _, read, _, relay, invoke, issue = delegation()
    parent = unpack(issue())
    parent["tenant"] = str(SOURCE_TENANTS[1].tenant_id)
    with pytest.raises(WorkerDenied):
        relay.summary(jwt.encode(parent, key, algorithm="RS256"))
    read.assert_not_called()
    invoke.assert_not_called()


def test_validator_failure_never_becomes_missing(delegation):
    _, _, read, _, relay, _, issue = delegation()
    read.side_effect = RuntimeError("private source payload")
    with pytest.raises(WorkerDenied, match=r"^Worker access denied$"):
        relay.summary(issue())


@pytest.mark.parametrize("damage", ["request_id", "tpa_id", "product_id", "raw_export"])
def test_validator_response_scope_or_extra_payload_is_rejected(delegation, damage):
    _, _, _, _, relay, invoke, issue = delegation()
    original = invoke.side_effect

    def damaged(token):
        payload = original(token).model_dump()
        payload[damage] = "FORBIDDEN"
        return Mock(model_dump=Mock(return_value=payload))

    invoke.side_effect = damaged
    with pytest.raises(WorkerDenied):
        relay.summary(issue())


def test_validator_independently_consumes_child_once(delegation):
    _, _, read, endpoint, _, _, issue = delegation()
    child = unpack(issue())["summary_token"]
    peer = OfflinePeer("reader:0:nonclinical")
    endpoint.validate(child, peer=peer)
    with pytest.raises(WorkerDenied):
        endpoint.validate(child, peer=peer)
    read.assert_called_once()
