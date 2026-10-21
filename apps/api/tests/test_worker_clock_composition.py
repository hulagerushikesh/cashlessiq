"""Real signed delegation, fake peers/identity/source/host health; no startup wiring."""

from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
from unittest.mock import Mock
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from test_source_cases import build_test_sources

from ciq_api.auth import Principal
from ciq_api.source_alpha import SOURCE_TENANTS
from ciq_api.source_scopes import source_alpha_scopes
from ciq_api.validation_worker import OfflineValidationWorker, ValidationInputs
from ciq_api.worker_authority import ISSUER, Membership, WorkerDenied
from ciq_api.worker_broker import OfflineSummaryBroker, OfflineSummaryRoute, ResolvedWorkerIdentity
from ciq_api.worker_clock import SECOND, ClockHealth, ClockLimits, ClockSample, SqliteClockGuard
from ciq_api.worker_delegation import (
    DelegatedSummaryAuthority,
    DetailAuthority,
    OfflineDelegatedValidator,
    OfflinePeer,
    OfflineReadRelay,
)


@pytest.mark.parametrize("index,request_id", [(0, "GOL001"), (1, "GOL024")])
@pytest.mark.parametrize("role", ["processor", "auditor", "medical_officer"])
@pytest.mark.parametrize(
    "failure",
    ["broker", "reader", "validator", "validator_delivery", "reader_delivery", "broker_delivery"],
)
def test_guarded_signed_path_denies_unsafe_time_and_preserves_truthful_results(
    tmp_path, index, request_id, role, failure
):
    tenant = SOURCE_TENANTS[index].tenant_id
    member = Membership(tenant, role)
    disclosure = "medical" if role == "medical_officer" else "nonclinical"
    scopes = source_alpha_scopes()
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    reader_aud, validator_aud = f"reader:{index}:{disclosure}", f"validator:{index}"
    initial = ClockSample(1000 * SECOND, 10 * SECOND, "fake-boot")
    samples = {name: initial for name in ("broker", "reader", "validator")}
    identities = {
        name: sha256(f"{ISSUER}\0{audience}\0{tenant}".encode()).hexdigest()
        for name, audience in (("reader", reader_aud), ("validator", validator_aud))
    }
    identities["broker"] = "fixed-test-broker"

    def guard(name, provision=False):
        path = tmp_path / f"{name}.sqlite"
        if provision:
            SqliteClockGuard.initialize_for_offline_test(
                path, authority=identities[name], generation="test-key-generation", initial=initial
            )
        return SqliteClockGuard(
            path,
            authority=identities[name],
            generation="test-key-generation",
            sample=lambda: samples[name],
            health=lambda: ClockHealth(True, 1, samples[name].monotonic_ns),
            limits=ClockLimits(100, SECOND, SECOND, 60 * SECOND),
        )

    guards = {name: guard(name, True) for name in samples}
    _, _, _, records, details = build_test_sources()
    case = next(row for row in records[tenant] if row.request_id == request_id)
    rows = deepcopy(details[request_id])
    read = Mock(return_value=ValidationInputs(case, rows["decision"], rows["evidence"]))
    verifier = Mock()
    verifier.verify.return_value = Principal("test-issuer", "test-subject", tenant)
    memberships = Mock()
    memberships.resolve.return_value = ResolvedWorkerIdentity(uuid4(), member)

    def build():
        common = dict(
            public_key=key.public_key(),
            tenant_id=tenant,
            scopes=scopes,
            membership=lambda _: member,
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
            OfflineValidationWorker(
                authority=validator, scope=scopes.get(tenant), read_inputs=read
            ),
        )
        relay = OfflineReadRelay(
            authority=reader,
            public_key=key.public_key(),
            validator_audience=validator_aud,
            invoke_validator=lambda token: endpoint.validate(token, peer=OfflinePeer(reader_aud)),
        )
        return OfflineSummaryBroker(
            verifier=verifier,
            memberships=memberships,
            scopes=scopes,
            routes={
                (tenant, disclosure): OfflineSummaryRoute(reader_aud, relay.summary, validator_aud)
            },
            private_key=key,
            clock=guards["broker"].check,
        )

    broker = build()
    result = broker.summary("fake-session", request_id)
    assert result.recommendation.state == ("SAVED" if index == 0 else "MISSING")
    if index == 0:
        assert result.recommendation.payable_inr == 95_000
    read.reset_mock()
    at_delivery = failure.endswith("_delivery")
    if at_delivery:

        def fail_after_read(*_):
            samples[failure.removesuffix("_delivery")] = replace(
                initial, wall_ns=initial.wall_ns - 1
            )
            return ValidationInputs(case, rows["decision"], rows["evidence"])

        read.side_effect = fail_after_read
    else:
        samples[failure] = replace(initial, wall_ns=initial.wall_ns - 1)
    with pytest.raises(WorkerDenied, match=r"^Worker access denied$"):
        broker.summary("fake-session", request_id)
    assert read.call_count == (1 if at_delivery else 0)
    read.reset_mock(side_effect=True)
    # Reconstruct every guard/authority/broker: a healthy sample cannot clear the latch.
    samples.update(dict.fromkeys(samples, initial))
    guards.update({name: guard(name) for name in samples})
    with pytest.raises(WorkerDenied):
        build().summary("fake-session", request_id)
    read.assert_not_called()
