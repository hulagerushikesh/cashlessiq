"""Unit tests for extracting the final JSON from agent responses."""

from cashlessiq.agent_client import _json_object


def test_extracts_decision_from_nested_text() -> None:
    decision = {"request_id": "GOL001", "outcome": "APPROVE", "lines": []}
    response = {
        "message": {
            "content": [
                {
                    "type": "text",
                    "text": '{"request_id":"GOL001","outcome":"APPROVE","lines":[]}',
                }
            ]
        }
    }
    assert _json_object(response) == decision
