"""Offline trust-generation acceptance, not an operator recovery controller.

Fresh in-memory signing keys and temporary ledgers only. Fake peer/membership,
fixed trusted time and synthetic source fixtures do not prove TLS, clock safety,
service shutdown, secret custody or production generation inventory.
"""

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
from ciq_api.worker_replay import SqliteReplayLedger


@pytest.mark.parametrize("failure", ["healthy", "missing", "corrupt"])
@pytest.mark.parametrize("role", ["processor", "auditor", "medical_officer"])
@pytest.mark.parametrize("index,request_id", [(0, "GOL001"), (1, "GOL024")])
def test_new_generation_rejects_old_unconsumed_tokens_and_retains_replay(
    tmp_path, failure, role, index, request_id
):
    scopes = source_alpha_scopes()
    tenant = SOURCE_TENANTS[index].tenant_id
    member = Membership(tenant, role)
    disclosure = "medical" if role == "medical_officer" else "nonclinical"
    reader_audience = f"reader:{index}:{disclosure}"
    validator_audience = f"validator:{index}"
    _, _, _, records, details = build_test_sources()
    case = next(row for row in records[tenant] if row.request_id == request_id)
    rows = deepcopy(details[request_id])
    read = Mock(return_value=ValidationInputs(case, rows["decision"], rows["evidence"]))
    old_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    new_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    paths = tuple(tmp_path / f"{name}.sqlite" for name in ("reader", "validator"))
    for path in paths:
        SqliteReplayLedger.initialize_for_offline_test(path)

    def issue(key):
        return issue_detail_assertion(
            key,
            subject="synthetic-reviewer",
            membership=member,
            reader_audience=reader_audience,
            validator_audience=validator_audience,
            request_id=request_id,
            scopes=scopes,
            now=1000,
        )

    def build(key, ledgers):
        common = dict(
            public_key=key.public_key(),
            tenant_id=tenant,
            scopes=scopes,
            membership=lambda _: member,
            clock=lambda: 1000,  # All old/new capabilities stay unexpired.
        )
        reader = DetailAuthority(
            **common,
            audience=reader_audience,
            disclosure=disclosure,
            replay=SqliteReplayLedger(ledgers[0]),
        )
        validator = DelegatedSummaryAuthority(
            **common,
            audience=validator_audience,
            readers={reader_audience: disclosure},
            replay=SqliteReplayLedger(ledgers[1]),
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
            validator_audience=validator_audience,
            invoke_validator=lambda token: endpoint.validate(
                token, peer=OfflinePeer(reader_audience)
            ),
        )
        return relay, endpoint

    def child(token):
        return jwt.decode(token, options={"verify_signature": False})["summary_token"]

    def reject_pair(relay, endpoint, token):
        for signed in (token, child(token)):
            assert jwt.decode(signed, options={"verify_signature": False})["exp"] > 1000
        with pytest.raises(WorkerDenied, match=r"^Worker access denied$"):
            relay.summary(token)
        with pytest.raises(WorkerDenied, match=r"^Worker access denied$"):
            endpoint.validate(child(token), peer=OfflinePeer(reader_audience))
        read.assert_not_called()

    relay, endpoint = build(old_key, paths)
    relay.summary(issue(old_key))
    old_unused = issue(old_key)  # Signature rejection cannot be confused with replay.
    read.reset_mock()
    del relay, endpoint  # Test models stopped authorities; no live routing exists.

    if failure != "healthy":
        for path in paths:
            if failure == "missing":
                path.unlink()  # Only explicitly named disposable test files.
            else:
                path.write_bytes(b"synthetic corrupt replay state")
        damaged = tuple(path.read_bytes() if path.exists() else None for path in paths)
        broken_relay, broken_endpoint = build(old_key, paths)
        reject_pair(broken_relay, broken_endpoint, old_unused)
        assert tuple(path.read_bytes() if path.exists() else None for path in paths) == damaged
        del broken_relay, broken_endpoint
        # Explicit test-only provisioning uses NEW filenames after discarding
        # old authority instances; damaged evidence is never overwritten.
        recovered_paths = tuple(tmp_path / f"new-{path.name}" for path in paths)
    else:
        damaged = None
        recovered_paths = paths  # Healthy rotation preserves both ledgers byte-for-byte.
        retained = tuple(path.read_bytes() for path in paths)

    relay, endpoint = build(new_key, recovered_paths)
    if failure != "healthy":
        reject_pair(relay, endpoint, issue(new_key))
        for path in recovered_paths:
            assert not path.exists()  # Neither construction nor requests provision state.
            SqliteReplayLedger.initialize_for_offline_test(path)
    else:
        assert tuple(path.read_bytes() for path in paths) == retained
    reject_pair(relay, endpoint, old_unused)
    fresh = issue(new_key)
    result = relay.summary(fresh)
    assert result.recommendation.state == ("SAVED" if index == 0 else "MISSING")
    read.assert_called_once_with(request_id)
    read.reset_mock()
    del relay, endpoint
    relay, endpoint = build(new_key, recovered_paths)
    reject_pair(relay, endpoint, fresh)  # Same generation/files after restart.
    reject_pair(relay, endpoint, old_unused)
    assert relay.summary(issue(new_key)).recommendation.state == result.recommendation.state
    read.assert_called_once_with(request_id)
    if damaged is not None:
        assert tuple(path.read_bytes() if path.exists() else None for path in paths) == damaged
