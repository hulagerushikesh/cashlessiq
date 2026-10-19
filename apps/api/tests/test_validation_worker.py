"""Raw synthetic fixture inputs stay in validator; no SQL, HTTP or credentials."""

from copy import deepcopy
from unittest.mock import Mock

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from test_source_cases import build_test_sources

from ciq_api.snowflake_reads import SourceReadUnavailable
from ciq_api.source_alpha import SOURCE_TENANTS
from ciq_api.source_scopes import source_alpha_scopes
from ciq_api.validation_worker import OfflineValidationWorker, ValidationInputs
from ciq_api.worker_authority import (
    Membership,
    SummaryAuthority,
    WorkerDenied,
    issue_summary_assertion,
)


@pytest.fixture
def setup_worker():
    def build(index=0, request_id="GOL001"):
        tenant = SOURCE_TENANTS[index]
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        scopes = source_alpha_scopes()
        _, _, _, records, details = build_test_sources()
        case = next(r for r in records[tenant.tenant_id] if r.request_id == request_id)
        rows = deepcopy(details[request_id])
        inputs = ValidationInputs(case, rows["decision"], rows["evidence"])
        state = {"member": Membership(tenant.tenant_id, "processor")}
        authority = SummaryAuthority(
            public_key=key.public_key(),
            audience="validator-test",
            tenant_id=tenant.tenant_id,
            scopes=scopes,
            membership=lambda _: state["member"],
            clock=lambda: 1000,
        )
        read = Mock(return_value=inputs)
        worker = OfflineValidationWorker(
            authority=authority, scope=scopes.get(tenant.tenant_id), read_inputs=read
        )
        signed = issue_summary_assertion(
            key,
            subject="reviewer",
            membership=state["member"],
            audience="validator-test",
            request_id=request_id,
            scopes=scopes,
            now=1000,
        )
        return worker, signed, inputs, read, state

    return build


def test_saved_summary_uses_canonical_validator_without_raw_export(setup_worker):
    worker, token, _, _, _ = setup_worker()
    result = worker.validate(token)
    assert result.recommendation.state == "SAVED"
    assert result.recommendation.payable_inr == 95_000
    payload = result.model_dump_json()
    for forbidden in ("Sensitive", "Restricted", "decision_json", "lines", "summary", "calc"):
        # amount_basis legitimately contains saved_calculation, not raw calc fields.
        if forbidden == "calc":
            assert '"calc"' not in payload
        else:
            assert forbidden not in payload


@pytest.mark.parametrize("outcome", ["QUERY", "REFER"])
def test_uncomputed_saved_summary_preserves_null_payable(setup_worker, outcome):
    worker, token, inputs, _, _ = setup_worker()
    row = inputs.decisions[0]
    row["outcome"] = outcome
    row["payable_inr"] = 0
    row["decision_json"].update(
        outcome=outcome,
        total_claimed_inr=0,
        total_payable_inr=0,
        lines=[],
        queries=["Restricted query"] if outcome == "QUERY" else [],
        refer_reasons=["Restricted referral"] if outcome == "REFER" else [],
    )
    recommendation = worker.validate(token).recommendation
    assert recommendation.state == "SAVED"
    assert recommendation.outcome == outcome
    assert recommendation.claimed_inr == 100_000
    assert recommendation.payable_inr is None
    assert recommendation.amount_basis == "supplied_estimate"


@pytest.mark.parametrize("request_id", ["GOL024", "GOL027"])
def test_true_absence_stays_missing(setup_worker, request_id):
    worker, token, _, _, _ = setup_worker(1, request_id)
    result = worker.validate(token)
    assert result.recommendation.model_dump() == {"state": "MISSING"}


@pytest.mark.parametrize("damage", ["amount", "citation", "foreign", "duplicate", "overflow"])
def test_invalid_inputs_never_become_missing(setup_worker, damage):
    worker, token, inputs, _, _ = setup_worker()
    if damage == "amount":
        inputs.decisions[0]["decision_json"]["total_payable_inr"] = 1
    elif damage == "citation":
        inputs.decisions[0]["decision_json"]["lines"][0]["citations"][0]["id"] = "UNKNOWN"
    elif damage == "foreign":
        inputs.evidence[0]["tpa_id"] = "TPA003"
    elif damage == "duplicate":
        inputs.evidence.append(deepcopy(inputs.evidence[0]))
    else:
        inputs.evidence.extend([inputs.evidence[0]] * 101)
    with pytest.raises(SourceReadUnavailable, match=r"^Source validation unavailable$"):
        worker.validate(token)


def test_revocation_before_source_prevents_io(setup_worker):
    worker, token, _, read, state = setup_worker()
    state["member"] = None
    with pytest.raises(WorkerDenied):
        worker.validate(token)
    read.assert_not_called()


def test_revocation_during_source_prevents_delivery(setup_worker):
    worker, token, inputs, read, state = setup_worker()

    def read_then_revoke(_):
        state["member"] = None
        return inputs

    read.side_effect = read_then_revoke
    with pytest.raises(WorkerDenied):
        worker.validate(token)


def test_read_failure_is_generic_unavailable_not_absence(setup_worker):
    worker, token, _, read, _ = setup_worker()
    read.side_effect = RuntimeError("private source failure")
    with pytest.raises(SourceReadUnavailable, match=r"^Source validation unavailable$"):
        worker.validate(token)
