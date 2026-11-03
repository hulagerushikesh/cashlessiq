"""Reservation client rejects malformed requests and hides private DB failures."""

from uuid import uuid4

import pytest
from test_agent_controller_capture_offline import FailingEngine

from ciq_api.agent_contracts import AgentContractError
from ciq_api.agent_controller_reservation import ControllerReservation, FakeReservationApproval
from ciq_api.agent_ledger import ClaimReceipt, OperationReceipt


@pytest.mark.parametrize("request_id", [None, "", "x" * 121, 1, True, uuid4(), {}, []])
def test_invalid_request_never_connects(request_id):
    engine = FailingEngine()
    with pytest.raises(AgentContractError, match=r"^reservation_unavailable$"):
        ControllerReservation(engine).reserve(request_id)
    assert engine.calls == 0


@pytest.mark.parametrize("timeout", [None, 0, -1, 121, True, 1.5, "30"])
def test_invalid_timeout_never_connects(timeout):
    engine = FailingEngine()
    with pytest.raises(AgentContractError, match=r"^reservation_unavailable$"):
        ControllerReservation(engine).reserve("REQ-SYNTHETIC", timeout_seconds=timeout)
    assert engine.calls == 0


@pytest.mark.parametrize("schema", [None, "", "public", 'ciq_agent_capture"; DROP SCHEMA public'])
def test_fixed_trusted_schema_only(schema):
    with pytest.raises(AgentContractError, match=r"^reservation_unavailable$"):
        ControllerReservation(FailingEngine(), schema=schema)


@pytest.mark.parametrize("method", ["reserve", "claim", "heartbeat"])
def test_private_driver_failures_are_suppressed_and_transaction_closes(method):
    engine = FailingEngine()
    client = ControllerReservation(engine)
    receipt = OperationReceipt(operation_id=uuid4(), state="reserved", version=0)
    claim = ClaimReceipt(**receipt.model_dump(), fence_id=uuid4())
    args = {"reserve": (), "claim": (receipt,), "heartbeat": (claim,)}[method]
    with pytest.raises(AgentContractError, match=r"^reservation_unavailable$") as failure:
        getattr(client, method)("REQ-SYNTHETIC", *args)
    assert engine.calls == 1 and engine.closed and failure.value.__suppress_context__
    assert "private" not in str(failure.value)


@pytest.mark.parametrize("receipt", [None, {}, "operation", uuid4()])
def test_no_untyped_transition_parameters(receipt):
    engine = FailingEngine()
    client = ControllerReservation(engine)
    for method in (client.claim, client.heartbeat):
        with pytest.raises(AgentContractError, match=r"^reservation_unavailable$"):
            method("REQ-SYNTHETIC", receipt)
    assert engine.calls == 0


def test_operator_staging_validates_shared_snapshot_and_defaults_disabled():
    from test_agent_contracts import capture

    from ciq_api.agent_admission import FakeEpochPin
    from ciq_api.agent_ledger import operation_key

    captured = capture()
    approval = FakeReservationApproval(
        epoch=FakeEpochPin(database_id=uuid4(), epoch_id=uuid4()),
        grant_id=uuid4(),
        snapshot=captured,
        config_digest="a" * 64,
        source_digest="b" * 64,
    )
    values = approval.staging_values()
    assert values["enabled"] is False
    assert values["operation_key"] == operation_key(captured, "a" * 64, "b" * 64)
    assert values["snapshot"] == captured.model_dump(mode="json")
    assert "facts_json" not in repr(approval)
    corrupt = captured.model_copy(update={"facts_json": "{}"})
    with pytest.raises(ValueError):
        FakeReservationApproval(
            epoch=approval.epoch,
            grant_id=approval.grant_id,
            snapshot=corrupt,
            config_digest="a" * 64,
            source_digest="b" * 64,
        ).staging_values()
