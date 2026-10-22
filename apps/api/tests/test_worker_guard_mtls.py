"""Real loopback TLS and v3 state; fake health, membership and source only."""

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
from http.server import ThreadingHTTPServer
from threading import Thread
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from test_source_cases import build_test_sources
from test_worker_guard_health import advance
from test_worker_health import policy as policy
from test_worker_health import setup as setup
from test_worker_transport import context
from test_worker_transport import pki as pki

from ciq_api.auth import Principal
from ciq_api.source_alpha import SOURCE_TENANTS
from ciq_api.source_scopes import source_alpha_scopes
from ciq_api.validation_worker import OfflineValidationWorker, ValidationInputs
from ciq_api.worker_authority import ISSUER, Membership, WorkerDenied
from ciq_api.worker_broker import OfflineSummaryRoute, ResolvedWorkerIdentity
from ciq_api.worker_delegation import OfflineDelegatedValidator, TransportPeer
from ciq_api.worker_guard_authority import (
    GuardedAuthority,
    GuardedReadRelay,
    GuardedSummaryBroker,
)
from ciq_api.worker_guard_health import OfflineHealthGuard
from ciq_api.worker_guard_state import GuardStateConfig, GuardStateDenied, OfflineGuardState
from ciq_api.worker_guard_transport import GuardedPrivateSummaryServer, GuardedSummaryServer
from ciq_api.worker_health import SECOND, sign_for_offline_test
from ciq_api.worker_transport import LoopbackSummaryClient, PrivateEndpoint


@pytest.fixture(scope="module")
def assertion_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="module")
def health_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def build_world(tmp_path, setup, policy, health_key, assertion_key, index, role, generation="g1"):
    binding, evidence, initial = setup
    tenant = SOURCE_TENANTS[index].tenant_id
    disclosure = "medical" if role == "medical_officer" else "nonclinical"
    reader_aud, validator_aud = f"reader:{index}:{disclosure}", f"validator:{index}"
    reader_name = ("reader" if index == 0 else "reader1") + (
        "_medical" if disclosure == "medical" else ""
    )
    request_id = "GOL001" if index == 0 else "GOL024"
    scopes = source_alpha_scopes()
    member = [Membership(tenant, role)]
    names = ("broker", "reader", "validator")
    samples = dict.fromkeys(names, initial)
    tokens = dict.fromkeys(names, sign_for_offline_test(evidence, health_key))
    config, paths = {}, {}
    for name in names:
        audience = reader_aud if name == "reader" else validator_aud
        namespace = (
            "broker"
            if name == "broker"
            else sha256(f"{ISSUER}\0{audience}\0{tenant}".encode()).hexdigest()
        )
        config[name] = GuardStateConfig(
            authority=namespace,
            assertion_generation=generation,
            health_key_sha256=sha256(
                health_key.public_key().public_bytes(
                    serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
                )
            ).hexdigest(),
            binding=binding,
            health_policy=policy,
            max_gap_ns=60 * SECOND,
            max_step_ns=SECOND,
            max_nonces=50,
            max_file_bytes=65536,
        )
        paths[name] = tmp_path / f"{generation}-{name}.sqlite"
        OfflineGuardState.initialize_for_offline_test(
            paths[name], config=config[name], initial=initial
        )

    def guard(name):
        return OfflineHealthGuard(
            paths[name],
            config=config[name],
            public_key=health_key.public_key(),
            sample=lambda: samples[name],
        )

    common = dict(
        public_key=assertion_key.public_key(),
        generation=generation,
        tenant_id=tenant,
        scopes=scopes,
        membership=lambda _: member[0],
    )
    reader = GuardedAuthority(
        **common,
        audience=reader_aud,
        guard=guard("reader"),
        evidence=lambda: tokens["reader"],
        disclosure=disclosure,
    )
    validator = GuardedAuthority(
        **common,
        audience=validator_aud,
        guard=guard("validator"),
        evidence=lambda: tokens["validator"],
        readers={reader_aud: disclosure},
    )
    _, _, _, records, details = build_test_sources()
    case = next(row for row in records[tenant] if row.request_id == request_id)
    rows = deepcopy(details[request_id])
    inputs = ValidationInputs(case, rows["decision"], rows["evidence"])
    read = Mock(return_value=inputs)
    endpoint = OfflineDelegatedValidator(
        validator,
        OfflineValidationWorker(authority=validator, scope=scopes.get(tenant), read_inputs=read),
    )
    verifier, memberships = Mock(), Mock()
    verifier.verify.return_value = Principal("test-issuer", "test-subject", tenant)
    identity = ResolvedWorkerIdentity(uuid4(), member[0])
    memberships.resolve.side_effect = lambda _: (
        replace(identity, membership=member[0]) if member[0] else None
    )
    w = SimpleNamespace(
        paths=paths,
        configs=config,
        guard=guard,
        samples=samples,
        health_tokens=tokens,
        initial=initial,
        reader=reader,
        validator=validator,
        endpoint=endpoint,
        read=read,
        inputs=inputs,
        member=member,
        tenant=tenant,
        disclosure=disclosure,
        reader_aud=reader_aud,
        validator_aud=validator_aud,
        reader_name=reader_name,
        validator_name="validator" if index == 0 else "validator1",
        request_id=request_id,
        captured=[],
        verifier=verifier,
        memberships=memberships,
    )

    def invoke(token):
        w.captured.append(token)
        return w.parent_client.summary(token)

    w.broker = GuardedSummaryBroker(
        verifier=verifier,
        memberships=memberships,
        scopes=scopes,
        routes={(tenant, disclosure): OfflineSummaryRoute(reader_aud, invoke, validator_aud)},
        private_key=assertion_key,
        generation=generation,
        guard=guard("broker"),
        evidence=lambda: tokens["broker"],
    )
    return w


@contextmanager
def listening(pki, name, guard, evidence, callback, peers, operation):
    listener = GuardedSummaryServer(
        guard=guard,
        evidence=evidence,
        context=context(pki, name, server=True),
        peers=peers,
        validate=callback,
        operation=operation,
    )
    thread = Thread(target=listener.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        yield listener.server_port
    finally:
        listener.shutdown()
        listener.server_close()
        thread.join(timeout=4)
        assert not thread.is_alive()


@contextmanager
def transport(w, pki):
    def client(port, caller, target, audience, operation):
        return LoopbackSummaryClient(
            context=context(pki, caller),
            port=port,
            server_pin=pki[1][target][2],
            server_audience=audience,
            operation=operation,
        )

    with listening(
        pki,
        w.validator_name,
        w.guard("validator"),
        lambda: w.health_tokens["validator"],
        w.endpoint.validate,
        {pki[1][w.reader_name][2]: w.reader_aud},
        "validate_summary",
    ) as port:
        w.child_client = client(
            port, w.reader_name, w.validator_name, w.validator_aud, "validate_summary"
        )
        relay = GuardedReadRelay(
            authority=w.reader, validator_audience=w.validator_aud, invoke=w.child_client.summary
        )

        def reader_callback(token, *, peer):
            if type(peer) is not TransportPeer or peer.audience != "broker":
                raise WorkerDenied("Worker access denied")
            return relay.summary(token)

        with listening(
            pki,
            w.reader_name,
            w.guard("reader"),
            lambda: w.health_tokens["reader"],
            reader_callback,
            {pki[1]["broker"][2]: "broker"},
            "read_detail",
        ) as parent_port:
            w.parent_client = client(
                parent_port, "broker", w.reader_name, w.reader_aud, "read_detail"
            )
            yield w


@pytest.mark.parametrize("index", [0, 1])
@pytest.mark.parametrize("role", ["processor", "auditor", "medical_officer"])
@pytest.mark.parametrize(
    "failure",
    [
        "healthy",
        "broker-health",
        "reader-health",
        "validator-health",
        "broker-late",
        "reader-late",
        "validator-late",
        "revoked",
        "source",
        "downgraded",
        "foreign-case",
    ],
)
def test_guarded_two_hop_matrix(
    tmp_path, setup, policy, health_key, assertion_key, pki, index, role, failure
):
    w = build_world(tmp_path, setup, policy, health_key, assertion_key, index, role)
    with transport(w, pki):
        result = w.broker.summary("fake-session", w.request_id)
        assert result.recommendation.state == ("SAVED" if index == 0 else "MISSING")
        if index == 0:
            assert result.recommendation.payable_inr == 95000
        assert all(
            field not in result.model_dump_json()
            for field in ('"decision_json"', '"clinical_note"', '"lines"', '"calc"')
        )
        w.read.assert_called_once_with(w.request_id)
        w.read.reset_mock()
        parent = w.captured[-1]
        child = jwt.decode(parent, options={"verify_signature": False})["summary_token"]
        for client, token in ((w.parent_client, parent), (w.child_client, child)):
            with pytest.raises(WorkerDenied):
                client.summary(token)
        w.read.assert_not_called()
        if failure == "healthy":
            assert w.broker.summary("fake-session", w.request_id) == result
            return
        if failure.endswith("-health"):
            w.health_tokens[failure.removesuffix("-health")] = "invalid"
        elif failure.endswith("-late"):

            def fail_late(_):
                target = failure.removesuffix("-late")
                w.samples[target] = advance(w.initial, 3 * SECOND)
                return w.inputs

            w.read.side_effect = fail_late
        elif failure in {"revoked", "downgraded"}:

            def revoke(_):
                # Different tenant must deny for nonclinical roles as well.
                w.member[0] = (
                    Membership(w.tenant, "processor")
                    if role == "medical_officer" and failure == "downgraded"
                    else None
                )
                return w.inputs

            w.read.side_effect = revoke
        elif failure == "source":
            w.read.side_effect = RuntimeError("private raw source details")
        else:
            w.read.return_value = ValidationInputs(
                w.inputs.case.model_copy(update={"tpa_id": "FOREIGN"}), [], []
            )
        with pytest.raises(WorkerDenied, match=r"^Worker access denied$"):
            w.broker.summary("fake-session", w.request_id)
        assert w.read.call_count == (0 if failure.endswith("-health") else 1)
        if failure.endswith(("-health", "-late")):
            target = failure.split("-")[0]
            w.samples[target] = w.initial
            w.health_tokens[target] = sign_for_offline_test(setup[1], health_key)
            with pytest.raises(GuardStateDenied):
                w.guard(target).observe(lambda: w.health_tokens[target])


@pytest.mark.parametrize("private", [False, True])
@pytest.mark.parametrize("failure", ["missing", "signature", "stale", "latched"])
def test_v3_denies_before_bind(
    tmp_path, setup, policy, health_key, assertion_key, pki, monkeypatch, private, failure
):
    w = build_world(tmp_path, setup, policy, health_key, assertion_key, 0, "processor")
    if failure == "missing":
        w.paths["validator"].unlink()
    elif failure == "stale":
        w.samples["validator"] = advance(w.initial, 3 * SECOND)
    else:
        w.health_tokens["validator"] = "invalid"
        if failure == "latched":
            with pytest.raises(GuardStateDenied):
                w.guard("validator").observe(lambda: "invalid")
            w.health_tokens["validator"] = sign_for_offline_test(setup[1], health_key)
    bind, callback = Mock(), Mock()
    monkeypatch.setattr(ThreadingHTTPServer, "server_bind", bind)
    config = dict(
        guard=w.guard("validator"),
        evidence=lambda: w.health_tokens["validator"],
        context=context(pki, "validator", server=True),
        peers={pki[1]["reader"][2]: w.reader_aud},
        validate=callback,
    )
    server = GuardedSummaryServer
    if private:
        server = GuardedPrivateSummaryServer
        config["endpoint"] = PrivateEndpoint("10.20.30.40", 8443)
    with pytest.raises(WorkerDenied):
        server(**config)
    bind.assert_not_called()
    callback.assert_not_called()


def reissue(token, key, *, parent_changes=None, child_changes=None):
    """Trusted test signer creates UNUSED parent/child capabilities."""
    parent = jwt.decode(token, options={"verify_signature": False})
    child = jwt.decode(parent["summary_token"], options={"verify_signature": False})
    parent["jti"], child["jti"] = str(uuid4()), str(uuid4())
    child["parent_jti"] = parent["jti"]
    parent.update(parent_changes or {})
    child.update(child_changes or {})
    parent["summary_token"] = jwt.encode(child, key, algorithm="RS256")
    return jwt.encode(parent, key, algorithm="RS256"), parent["summary_token"]


@pytest.mark.parametrize(
    "failure",
    [
        "generation",
        "audience",
        "tenant",
        "iat-bool",
        "expired",
        "lifetime",
        "child-generation",
        "child-parent",
        "child-subject",
        "signature",
        "peer",
    ],
)
def test_invalid_unused_capabilities_never_read_source(
    tmp_path, setup, policy, health_key, assertion_key, pki, failure
):
    w = build_world(tmp_path, setup, policy, health_key, assertion_key, 0, "processor")
    with transport(w, pki):
        w.broker.summary("fake-session", w.request_id)
        w.read.reset_mock()
        changes = {
            "generation": {"assertion_generation": "old"},
            "audience": {"aud": w.validator_aud},
            "tenant": {"tenant": str(SOURCE_TENANTS[1].tenant_id)},
            "iat-bool": {"iat": True},
            "expired": {"exp": 1000},
            "lifetime": {"exp": 1031},
        }.get(failure, {})
        child_changes = {
            "child-generation": {"assertion_generation": "old"},
            "child-parent": {"parent_jti": str(uuid4())},
            "child-subject": {"sub": "other-user"},
        }.get(failure, {})
        parent, child = reissue(
            w.captured[-1], assertion_key, parent_changes=changes, child_changes=child_changes
        )
        if failure == "signature":
            foreign_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            parent, child = reissue(parent, foreign_key)
        if failure == "peer":
            with pytest.raises(WorkerDenied):
                w.endpoint.validate(child, peer=TransportPeer("reader:1:nonclinical"))
        else:
            with pytest.raises(WorkerDenied):
                w.parent_client.summary(parent)
        w.read.assert_not_called()
        # A rejected child cannot refund an already consumed valid parent.
        if failure.startswith("child-"):
            assert len(w.guard("reader").inspect()[1]) == 2
            assert len(w.guard("validator").inspect()[1]) == 1


@pytest.mark.parametrize("index", [0, 1])
def test_stopped_full_generation_recovery_rejects_old_unused_tokens(
    tmp_path, setup, policy, health_key, assertion_key, pki, index
):
    old = build_world(tmp_path, setup, policy, health_key, assertion_key, index, "medical_officer")
    with transport(old, pki):
        old.broker.summary("fake-session", old.request_id)
        unused_parent, unused_child = reissue(old.captured[-1], assertion_key)
    # All old listeners are closed and no issuer tasks exist. Old paths remain
    # untouched; rotate BOTH assertion and health keys plus generations/epoch.
    preserved = {path: path.read_bytes() for path in old.paths.values()}
    new_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    new_health_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    binding, evidence, now = setup
    binding = binding.model_copy(
        update={
            "health_generation": "00000000-0000-0000-0000-000000000098",
            "collector_epoch": "00000000-0000-0000-0000-000000000099",
        }
    )
    rotated_setup = binding, evidence.model_copy(update=binding.model_dump()), now
    fresh = build_world(
        tmp_path,
        rotated_setup,
        policy,
        new_health_key,
        new_key,
        index,
        "medical_officer",
        generation="g2",
    )
    with transport(fresh, pki):
        # Old unused parent AND child fail signature/generation, not replay.
        for client, token in (
            (fresh.parent_client, unused_parent),
            (fresh.child_client, unused_child),
        ):
            with pytest.raises(WorkerDenied):
                client.summary(token)
        # A new key cannot make old-generation claims valid; an old key cannot
        # mint new-generation claims even if all other fields fit.
        old_generation, old_generation_child = reissue(unused_parent, new_key)
        old_key, old_key_child = reissue(
            unused_parent,
            assertion_key,
            parent_changes={"assertion_generation": "g2"},
            child_changes={"assertion_generation": "g2"},
        )
        for client, token in (
            (fresh.parent_client, old_generation),
            (fresh.parent_client, old_key),
            (fresh.child_client, old_generation_child),
            (fresh.child_client, old_key_child),
        ):
            with pytest.raises(WorkerDenied):
                client.summary(token)
        fresh.read.assert_not_called()
        assert fresh.guard("reader").inspect()[1] == ()
        assert fresh.guard("validator").inspect()[1] == ()
        result = fresh.broker.summary("fake-session", fresh.request_id)
        assert result.recommendation.state == ("SAVED" if index == 0 else "MISSING")
        fresh.read.reset_mock()
        # Cryptographically valid NEW-key evidence with OLD domain must fail.
        fresh.health_tokens["reader"] = sign_for_offline_test(evidence, new_health_key)
        with pytest.raises(WorkerDenied):
            fresh.broker.summary("fake-session", fresh.request_id)
        fresh.read.assert_not_called()
    assert all(path.read_bytes() == original for path, original in preserved.items())
    with pytest.raises(GuardStateDenied):
        fresh.guard("reader").observe(lambda: fresh.health_tokens["reader"])


def test_broker_rechecks_health_after_signing_without_invocation(
    tmp_path, setup, policy, health_key, assertion_key, monkeypatch
):
    w = build_world(tmp_path, setup, policy, health_key, assertion_key, 0, "processor")
    encode = jwt.encode

    def delayed_sign(*args, **kwargs):
        signed = encode(*args, **kwargs)
        w.samples["broker"] = advance(w.initial, 3 * SECOND)
        return signed

    monkeypatch.setattr(jwt, "encode", delayed_sign)
    with pytest.raises(WorkerDenied):
        w.broker.summary("fake-session", w.request_id)
    assert not w.captured
    w.read.assert_not_called()
    with pytest.raises(GuardStateDenied):
        w.guard("broker").inspect()


def test_broker_rejects_foreign_request_and_membership_outage_before_issuance(
    tmp_path, setup, policy, health_key, assertion_key
):
    w = build_world(tmp_path, setup, policy, health_key, assertion_key, 0, "processor")
    with pytest.raises(WorkerDenied):
        w.broker.summary("fake-session", "GOL024")
    w.memberships.resolve.side_effect = RuntimeError("private membership outage")
    with pytest.raises(WorkerDenied):
        w.broker.summary("fake-session", w.request_id)
    assert not w.captured and w.guard("broker").inspect()[0].sequence == 0
    w.read.assert_not_called()


def test_unknown_certificate_denies_before_validator_source(
    tmp_path, setup, policy, health_key, assertion_key, pki
):
    w = build_world(tmp_path, setup, policy, health_key, assertion_key, 0, "processor")
    with transport(w, pki):
        w.broker.summary("fake-session", w.request_id)
        _parent, child = reissue(w.captured[-1], assertion_key)
        w.read.reset_mock()
        foreign = LoopbackSummaryClient(
            context=context(pki, "foreign"),
            port=w.child_client._port,
            server_pin=pki[1][w.validator_name][2],
            server_audience=w.validator_aud,
        )
        with pytest.raises(WorkerDenied):
            foreign.summary(child)
        w.read.assert_not_called()
        assert len(w.guard("validator").inspect()[1]) == 1


@pytest.mark.parametrize("failure", ["namespace", "generation", "both-modes", "no-mode"])
def test_inconsistent_authority_configuration_never_modifies_state(
    tmp_path, setup, policy, health_key, assertion_key, failure
):
    w = build_world(tmp_path, setup, policy, health_key, assertion_key, 0, "processor")
    before = {path: path.read_bytes() for path in w.paths.values()}
    config = dict(
        public_key=assertion_key.public_key(),
        audience=w.reader_aud,
        generation="g1",
        tenant_id=w.tenant,
        scopes=source_alpha_scopes(),
        membership=lambda _: w.member[0],
        guard=w.guard("reader"),
        evidence=lambda: w.health_tokens["reader"],
        disclosure="nonclinical",
    )
    if failure == "namespace":
        config["guard"] = w.guard("validator")
    elif failure == "generation":
        config["generation"] = "g2"
    elif failure == "both-modes":
        config["readers"] = {"other": "medical"}
    else:
        config["disclosure"] = None
    with pytest.raises(ValueError, match="Invalid offline v3 authority"):
        GuardedAuthority(**config)
    assert all(path.read_bytes() == contents for path, contents in before.items())
