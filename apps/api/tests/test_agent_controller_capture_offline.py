"""Capture client denies invalid projections without leaking private failures."""

from contextlib import contextmanager
from uuid import uuid4

import pytest
from sqlalchemy.exc import DBAPIError

from ciq_api.agent_contracts import AgentContractError
from ciq_api.agent_controller_capture import ControllerCapture


class FailingEngine:
    def __init__(self):
        self.calls = 0
        self.closed = False

    @contextmanager
    def begin(self):
        self.calls += 1
        try:
            yield self
        finally:
            self.closed = True

    def scalar(self, statement, params):
        raise DBAPIError(
            "private SQL", {"secret": "private parameter"}, ValueError("private driver")
        )


@pytest.mark.parametrize("request_id", [None, "", "x" * 121, 1, True, uuid4(), {}, []])
def test_invalid_request_never_connects(request_id):
    engine = FailingEngine()
    with pytest.raises(AgentContractError, match=r"^scope_unavailable$"):
        ControllerCapture(engine).capture(request_id)
    assert engine.calls == 0


@pytest.mark.parametrize("schema", ["public", "ciq_agent_capture; DROP SCHEMA public", "", None])
def test_no_arbitrary_schema_or_sql_selector(schema):
    with pytest.raises(AgentContractError, match=r"^scope_unavailable$"):
        ControllerCapture(FailingEngine(), schema=schema)


def test_driver_failure_is_fixed_and_transaction_closes():
    engine = FailingEngine()
    with pytest.raises(AgentContractError, match=r"^scope_unavailable$") as failure:
        ControllerCapture(engine).capture("REQ-SYNTHETIC")
    assert engine.calls == 1 and engine.closed
    assert failure.value.__suppress_context__
    assert "private" not in str(failure.value)
