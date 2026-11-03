"""Offline protocol/constructor denials. No socket listener or local service."""

import copy
import json
from pathlib import Path
from uuid import uuid4

import pytest

from ciq_api import agent_receipt_peer as peer
from ciq_api.agent_admission import ERROR, FakeCheckpoint, FakeEpochPin
from ciq_api.agent_contracts import AgentContractError, canonical_json


@pytest.fixture
def packet():
    pin = FakeEpochPin(database_id=uuid4(), epoch_id=uuid4())
    receipt = FakeCheckpoint(
        tenant_id=uuid4(), request_id="SYN-IPC", operation_id=uuid4(),
        submission_id=uuid4(), digest="a" * 64,
    )
    return {
        "version": "fake-receipt-peer-v1", "epoch": pin.model_dump(mode="json"),
        "command": "check_issued", "expected": [receipt.model_dump(mode="json")],
        "selected": receipt.model_dump(mode="json"),
    }


@pytest.mark.parametrize("command", ["check", "check_issued", "prepare", "issue"])
def test_exact_protocol_has_no_credential_body_path_or_permission(packet, command):
    packet["command"] = command
    if command == "check":
        packet["selected"] = None
    elif command in ("prepare", "issue"):
        packet["expected"] = []
    parsed = peer._parse(canonical_json(packet).encode())
    assert parsed.command == command
    assert set(parsed.model_dump()) == {"version", "epoch", "command", "expected", "selected"}


@pytest.mark.parametrize("fault", [
    "reset", "close", "provision", "quarantine", "reconcile", "path", "credential",
    "tenant_selector", "permission", "clinical_body", "live", "version", "no_selected",
    "duplicate_operation", "duplicate_case", "duplicate_submission", "31_receipts",
    "bad_digest", "empty_request", "missing_field", "coerced_request", "wrong_shape",
])
def test_protocol_mutations_are_rejected_before_journal(packet, fault):
    if fault in ("reset", "close", "provision", "quarantine", "reconcile"):
        packet["command"] = fault
    elif fault in ("path", "credential", "tenant_selector", "permission", "clinical_body"):
        packet[fault] = "PRIVATE-DUMMY-ONLY"
    elif fault == "live":
        packet["epoch"]["mode"] = "live"
    elif fault == "version":
        packet["version"] = True
    elif fault == "no_selected":
        packet["selected"] = None
    elif fault.startswith("duplicate"):
        duplicate = copy.deepcopy(packet["expected"][0])
        if fault == "duplicate_operation":
            duplicate.update(submission_id=str(uuid4()), request_id="SYN-OTHER")
        elif fault == "duplicate_submission":
            duplicate.update(operation_id=str(uuid4()), request_id="SYN-OTHER")
        else:
            duplicate.update(operation_id=str(uuid4()), submission_id=str(uuid4()))
        packet["expected"].append(duplicate)
    elif fault == "31_receipts":
        packet["expected"] *= 31
    elif fault == "bad_digest":
        packet["selected"]["digest"] = "x"
    elif fault == "empty_request":
        packet["selected"]["request_id"] = ""
    elif fault == "missing_field":
        del packet["epoch"]["mode"]
    elif fault == "coerced_request":
        packet["selected"]["request_id"] = 3
    else:
        packet["command"] = "issue"  # expected inventory forbidden for a mutation
    with pytest.raises(ValueError):
        peer._parse(canonical_json(packet).encode())


@pytest.mark.parametrize("fault", ["empty", "over_bound", "whitespace", "duplicate_key", "utf8"])
def test_single_canonical_bounded_encoding(packet, fault):
    raw = canonical_json(packet).encode()
    raw = {
        "empty": b"", "over_bound": b"x" * (peer.MAX_PACKET + 1),
        "whitespace": json.dumps(packet).encode(),
        "duplicate_key": raw[:-1] + b',"version":"fake-receipt-peer-v1"}',
        "utf8": b"\xff",
    }[fault]
    with pytest.raises(ValueError):
        peer._parse(raw)


@pytest.mark.parametrize("uid", [None, True, 0, -1, 2**31, "11003"])
def test_invalid_os_identity_never_creates_socket(packet, monkeypatch, uid):
    def forbidden(*_args, **_kwargs):
        pytest.fail("socket created before identity validation")

    monkeypatch.setattr(peer.socket, "socket", forbidden)
    pin = FakeEpochPin.model_validate(packet["epoch"])
    with pytest.raises(AgentContractError, match=f"^{ERROR}$") as caught:
        peer.FakeReceiptPeerClient(Path("/nonexistent/peer.sock"), pin,
                                   server_uid=uid, custody_uid=11003)
    assert caught.value.__suppress_context__


def test_non_linux_fails_before_files_or_socket(packet, monkeypatch):
    monkeypatch.setattr(peer.sys, "platform", "darwin")
    with pytest.raises(AgentContractError, match=f"^{ERROR}$"):
        peer.FakeReceiptPeerClient(Path("/nonexistent/peer.sock"),
                                   FakeEpochPin.model_validate(packet["epoch"]),
                                   server_uid=11002, custody_uid=11003)
