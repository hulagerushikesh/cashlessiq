"""Clock-checked signed two-hop loopback TLS; host/identity/source are fake.

Actual TLS peer identities, guard/replay files and RS256 assertions are used.
No deployment host clock policy, HTTP login, process/container isolation or
Snowflake source acceptance is implied.
"""

import sqlite3
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
from http.server import ThreadingHTTPServer
from threading import Thread
from unittest.mock import Mock
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from test_source_cases import build_test_sources
from test_worker_health import policy as policy
from test_worker_health import setup as setup
from test_worker_transport import context
from test_worker_transport import pki as pki

from ciq_api.auth import Principal
from ciq_api.source_alpha import SOURCE_TENANTS
from ciq_api.source_scopes import source_alpha_scopes
from ciq_api.validation_worker import OfflineValidationWorker, ValidationInputs
from ciq_api.worker_authority import ISSUER, Membership, WorkerDenied
from ciq_api.worker_broker import OfflineSummaryBroker, OfflineSummaryRoute, ResolvedWorkerIdentity
from ciq_api.worker_clock import (
    SECOND,
    ClockDenied,
    ClockHealth,
    ClockLimits,
    ClockSample,
    SqliteClockGuard,
)
from ciq_api.worker_delegation import (
    DelegatedSummaryAuthority,
    DetailAuthority,
    OfflineDelegatedValidator,
    OfflineReadRelay,
    TransportPeer,
)
from ciq_api.worker_health import HealthNow, sign_for_offline_test
from ciq_api.worker_health_state import RetainedHealthConsumer
from ciq_api.worker_transport import (
    ClockCheckedPrivateSummaryServer,
    ClockCheckedSummaryServer,
    LoopbackSummaryClient,
    PrivateEndpoint,
)


@pytest.fixture(scope="module")
def health_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@contextmanager
def listening(pki, name, guard, callback, peers, operation):
    listener = ClockCheckedSummaryServer(
        clock_guard=guard,
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


@pytest.mark.parametrize("index,request_id", [(0, "GOL001"), (1, "GOL024")])
@pytest.mark.parametrize("role", ["processor", "auditor", "medical_officer"])
@pytest.mark.parametrize(
    "failure",
    [
        "healthy",
        "broker",
        "reader",
        "validator",
        "broker_delivery",
        "reader_delivery",
        "validator_delivery",
        "broker_signature",
        "reader_signature",
        "validator_signature",
        "broker_stale_delivery",
        "reader_stale_delivery",
        "validator_stale_delivery",
    ],
)
def test_clock_guard_composes_with_signed_two_hop_tls(
    tmp_path, pki, setup, policy, health_key, index, request_id, role, failure
):
    tenant = SOURCE_TENANTS[index].tenant_id
    member = Membership(tenant, role)
    scopes = source_alpha_scopes()
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    disclosure = "medical" if role == "medical_officer" else "nonclinical"
    reader_aud, validator_aud = f"reader:{index}:{disclosure}", f"validator:{index}"
    reader_name = ("reader" if index == 0 else "reader1") + (
        "_medical" if disclosure == "medical" else ""
    )
    validator_name = "validator" if index == 0 else "validator1"
    binding, evidence, health_now = setup
    initial = ClockSample(health_now.wall_ns, health_now.monotonic_ns, binding.boot_id)
    samples = {name: initial for name in ("broker", "reader", "validator")}
    # Independent temporary key, not the assertion or TLS private key. This bridge
    # exists ONLY in tests: two files/transactions are not unified authorization.
    assert key.public_key().public_numbers() != health_key.public_key().public_numbers()
    signed = sign_for_offline_test(evidence, health_key)
    health_tokens = dict.fromkeys(samples, signed)
    consumers = {}

    def health_sample(name):
        sample = samples[name]
        return HealthNow(
            boot_id=sample.boot_id,
            wall_ns=sample.wall_ns,
            monotonic_ns=sample.monotonic_ns,
            boottime_ns=health_now.boottime_ns + sample.monotonic_ns - initial.monotonic_ns,
        )

    def consumer(name):
        return RetainedHealthConsumer(
            tmp_path / f"{name}-health.sqlite",
            binding=binding,
            policy=policy,
            public_key=health_key.public_key(),
            sample=lambda: health_sample(name),
            max_gap_ns=60 * SECOND,
        )

    for name in samples:
        RetainedHealthConsumer.initialize_for_offline_test(
            tmp_path / f"{name}-health.sqlite", binding=binding, initial=health_now
        )
        consumers[name] = consumer(name)

    def checked_health(name):
        checked = consumers[name].accept(lambda: health_tokens[name])
        return ClockHealth(True, checked.error_ns, checked.evidence.window.end_monotonic_ns)

    names = {
        name: sha256(f"{ISSUER}\0{audience}\0{tenant}".encode()).hexdigest()
        for name, audience in (("reader", reader_aud), ("validator", validator_aud))
    }
    names["broker"] = "test-broker"

    def guard(name, *, initialize=False):
        path = tmp_path / f"{name}.sqlite"
        if initialize:
            SqliteClockGuard.initialize_for_offline_test(
                path, authority=names[name], generation="test-generation", initial=initial
            )
        return SqliteClockGuard(
            path,
            authority=names[name],
            generation="test-generation",
            sample=lambda: samples[name],
            health=lambda: checked_health(name),
            limits=ClockLimits(100, SECOND, SECOND, 60 * SECOND),
        )

    guards = {name: guard(name, initialize=True) for name in samples}
    _, _, _, records, details = build_test_sources()
    case = next(row for row in records[tenant] if row.request_id == request_id)
    rows = deepcopy(details[request_id])
    inputs = ValidationInputs(case, rows["decision"], rows["evidence"])
    read = Mock(return_value=inputs)
    common = dict(
        public_key=key.public_key(), tenant_id=tenant, scopes=scopes, membership=lambda _: member
    )
    reader = DetailAuthority(
        **common,
        audience=reader_aud,
        disclosure=disclosure,
        clock=guards["reader"].check,
        replay=guards["reader"],
    )
    validator = DelegatedSummaryAuthority(
        **common,
        audience=validator_aud,
        readers={reader_aud: disclosure},
        clock=guards["validator"].check,
        replay=guards["validator"],
    )
    endpoint = OfflineDelegatedValidator(
        validator,
        OfflineValidationWorker(authority=validator, scope=scopes.get(tenant), read_inputs=read),
    )
    verifier, memberships = Mock(), Mock()
    verifier.verify.return_value = Principal("test-issuer", "test-subject", tenant)
    memberships.resolve.return_value = ResolvedWorkerIdentity(uuid4(), member)
    tokens = []

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
        validator_name,
        guards["validator"],
        endpoint.validate,
        {pki[1][reader_name][2]: reader_aud},
        "validate_summary",
    ) as validator_port:
        child_client = client(
            validator_port, reader_name, validator_name, validator_aud, "validate_summary"
        )
        relay = OfflineReadRelay(
            authority=reader,
            public_key=key.public_key(),
            validator_audience=validator_aud,
            invoke_validator=child_client.summary,
        )

        def reader_callback(token, *, peer):
            assert type(peer) is TransportPeer and peer.audience == "broker"
            return relay.summary(token)

        with listening(
            pki,
            reader_name,
            guards["reader"],
            reader_callback,
            {pki[1]["broker"][2]: "broker"},
            "read_detail",
        ) as reader_port:
            parent_client = client(reader_port, "broker", reader_name, reader_aud, "read_detail")

            def invoke(token):
                tokens.append(token)
                return parent_client.summary(token)

            broker = OfflineSummaryBroker(
                verifier=verifier,
                memberships=memberships,
                scopes=scopes,
                routes={
                    (tenant, disclosure): OfflineSummaryRoute(reader_aud, invoke, validator_aud)
                },
                private_key=key,
                clock=guards["broker"].check,
            )
            result = broker.summary("fake-session", request_id)
            assert result.recommendation.state == ("SAVED" if index == 0 else "MISSING")
            if index == 0:
                assert result.recommendation.payable_inr == 95_000
            for field in ('"decision_json"', '"clinical_note"', '"lines"', '"calc"'):
                assert field not in result.model_dump_json()
            read.assert_called_once_with(request_id)
            read.reset_mock()
            # The same guarded authorities reject consumed unexpired parent AND child.
            for target, token in (
                (parent_client, tokens[-1]),
                (
                    child_client,
                    jwt.decode(tokens[-1], options={"verify_signature": False})["summary_token"],
                ),
            ):
                with pytest.raises(WorkerDenied):
                    target.summary(token)
            read.assert_not_called()
            if failure == "healthy":
                assert broker.summary("fake-session", request_id) == result
                return
            if failure.endswith("_delivery"):

                def fail_during_source(_):
                    if failure.endswith("_stale_delivery"):
                        target = failure.removesuffix("_stale_delivery")
                        samples[target] = replace(
                            initial,
                            wall_ns=initial.wall_ns + 3 * SECOND,
                            monotonic_ns=initial.monotonic_ns + 3 * SECOND,
                        )
                    else:
                        samples[failure.removesuffix("_delivery")] = replace(
                            initial, wall_ns=initial.wall_ns - 1
                        )
                    return inputs

                read.side_effect = fail_during_source
            elif failure.endswith("_signature"):
                health_tokens[failure.removesuffix("_signature")] = "invalid"
            else:
                samples[failure] = replace(initial, wall_ns=initial.wall_ns - 1)
            with pytest.raises(WorkerDenied, match=r"^Worker access denied$"):
                broker.summary("fake-session", request_id)
            assert read.call_count == (1 if failure.endswith("_delivery") else 0)
            read.reset_mock(side_effect=True)
            samples.update(dict.fromkeys(samples, initial))
            health_tokens.update(dict.fromkeys(health_tokens, signed))
            consumers.update({name: consumer(name) for name in consumers})
            with pytest.raises(WorkerDenied):
                broker.summary("fake-session", request_id)
            read.assert_not_called()
    # After TLS shutdown, a reconstructed guard cannot clear the offending latch.
    failed = failure.split("_")[0]
    with pytest.raises(ClockDenied):
        guard(failed).check()
    if "signature" in failure or "stale" in failure:
        with sqlite3.connect(tmp_path / f"{failed}-health.sqlite") as db:
            assert db.execute("SELECT sequence,unsafe FROM health_state").fetchone() == (1, 1)


@pytest.mark.parametrize("private", [False, True])
@pytest.mark.parametrize("failure", ["signature", "missing", "stale"])
def test_signed_health_denies_before_any_listener_bind(
    tmp_path, pki, setup, policy, health_key, monkeypatch, private, failure
):
    binding, evidence, now = setup
    health_path, clock_path = tmp_path / "health.sqlite", tmp_path / "clock.sqlite"
    RetainedHealthConsumer.initialize_for_offline_test(health_path, binding=binding, initial=now)
    sample = ClockSample(now.wall_ns, now.monotonic_ns, now.boot_id)
    SqliteClockGuard.initialize_for_offline_test(
        clock_path, authority="validator", generation="test-generation", initial=sample
    )
    signed = sign_for_offline_test(evidence, health_key)
    if failure == "signature":
        signed = "invalid"
    elif failure == "missing":
        health_path.unlink()
    else:
        now = now.model_copy(
            update={
                field: getattr(now, field) + 3 * SECOND
                for field in ("wall_ns", "monotonic_ns", "boottime_ns")
            }
        )
        sample = ClockSample(now.wall_ns, now.monotonic_ns, now.boot_id)
    consumer = RetainedHealthConsumer(
        health_path,
        binding=binding,
        policy=policy,
        public_key=health_key.public_key(),
        sample=lambda: now,
        max_gap_ns=60 * SECOND,
    )

    def health():
        checked = consumer.accept(lambda: signed)
        return ClockHealth(True, checked.error_ns, checked.evidence.window.end_monotonic_ns)

    guard = SqliteClockGuard(
        clock_path,
        authority="validator",
        generation="test-generation",
        sample=lambda: sample,
        health=health,
        limits=ClockLimits(100, SECOND, SECOND, 60 * SECOND),
    )
    bind, callback = Mock(), Mock()
    monkeypatch.setattr(ThreadingHTTPServer, "server_bind", bind)
    config = dict(
        clock_guard=guard,
        context=context(pki, "validator", server=True),
        peers={pki[1]["reader"][2]: "reader:0:nonclinical"},
        validate=callback,
    )
    server = ClockCheckedSummaryServer
    if private:
        config["endpoint"] = PrivateEndpoint("10.20.30.40", 8443)
        server = ClockCheckedPrivateSummaryServer
    with pytest.raises(WorkerDenied, match=r"^Worker access denied$"):
        server(**config)
    bind.assert_not_called()
    callback.assert_not_called()
    if failure == "missing":
        assert not health_path.exists()
    with sqlite3.connect(clock_path) as db:
        assert db.execute("SELECT unsafe FROM clock_state").fetchone() == (1,)
