"""No-network checks for the pending operator parity inspection boundary."""

from unittest.mock import MagicMock, call
from uuid import uuid4

import pytest

from ciq_api.snowflake_reads import SourceReadUnavailable
from ciq_api.source_inspection import QUERIES, SnowflakeSourceInspection


def inspection():
    connect = MagicMock()
    cursor = connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    tenant = uuid4()
    rows = [
        [("GOL001", "TPA001", "POL0001")],
        [],
        [],
        [("GOL001", "TPA001", "NIA-9.5")],
    ]
    index = -1

    def execute(sql, params=None, **kwargs):
        nonlocal index
        if params is not None:
            index += 1
            cursor.description = [(key,) for key in ("REQUEST_ID", "TPA_ID", QUERIES[index].key)]

    cursor.execute.side_effect = execute
    cursor.fetchmany.side_effect = lambda size: rows[index]
    return SnowflakeSourceInspection(connect, {tenant: "TPA001"}), tenant, connect, cursor, rows


@pytest.mark.parametrize("request_id", ["GOL024", "GOL027", "UNKNOWN", "' OR 1=1 --"])
def test_unowned_request_never_connects(request_id):
    source, tenant, connect, _, _ = inspection()
    assert source.inspect(tenant, request_id) == {}
    connect.assert_not_called()


def test_unknown_tenant_never_connects():
    source, _, connect, _, _ = inspection()
    assert source.inspect(uuid4(), "GOL001") == {}
    connect.assert_not_called()


def test_fixed_bound_queries_and_missing_decision_not_fabricated():
    source, tenant, connect, cursor, _ = inspection()
    result = source.inspect(tenant, "GOL001")
    assert result["decision"] == [] and result["conditions"] == []
    assert result["member"][0]["policy_id"] == "POL0001"
    assert cursor.execute.call_args_list == [
        call("USE SECONDARY ROLES NONE", timeout=30),
        *(call(q.sql, ("GOL001", "TPA001"), timeout=30) for q in QUERIES),
    ]
    assert cursor.fetchmany.call_args_list == [call(q.maximum + 1) for q in QUERIES]
    connect.return_value.__exit__.assert_called_once()


@pytest.mark.parametrize("query_index", range(4))
@pytest.mark.parametrize("fault", ["wrong_owner", "wrong_request", "overflow", "duplicate"])
def test_bad_rows_fail_closed(query_index, fault):
    source, tenant, connect, _, rows = inspection()
    row = ("GOL001", "TPA001", "KEY")
    if fault == "wrong_owner":
        rows[query_index] = [("GOL001", "TPA003", "KEY")]
    elif fault == "wrong_request":
        rows[query_index] = [("GOL024", "TPA001", "KEY")]
    elif fault == "overflow":
        rows[query_index] = [row] * (QUERIES[query_index].maximum + 1)
    else:
        rows[query_index] = [row, row]
    with pytest.raises(SourceReadUnavailable):
        source.inspect(tenant, "GOL001")
    connect.return_value.__exit__.assert_called_once()


def test_no_member_context_is_not_success():
    source, tenant, _, _, rows = inspection()
    rows[0] = []
    with pytest.raises(SourceReadUnavailable):
        source.inspect(tenant, "GOL001")


def test_session_failure_prevents_all_selects_and_hides_diagnostic():
    source, tenant, connect, cursor, _ = inspection()
    cursor.execute.side_effect = RuntimeError("secret connector error")
    with pytest.raises(SourceReadUnavailable) as error:
        source.inspect(tenant, "GOL001")
    assert "secret" not in str(error.value)
    cursor.execute.assert_called_once_with("USE SECONDARY ROLES NONE", timeout=30)
    cursor.fetchmany.assert_not_called()
    connect.return_value.__exit__.assert_called_once()


@pytest.mark.parametrize("fault", ["ambiguous", "missing_scope", "row_shape"])
def test_malformed_columns_or_rows_fail_closed(fault):
    source, tenant, _, cursor, rows = inspection()
    original = cursor.execute.side_effect

    def execute(sql, params=None, **kwargs):
        original(sql, params, **kwargs)
        if params is not None and fault == "ambiguous":
            cursor.description = [("REQUEST_ID",), ("TPA_ID",), ("TPA_ID",)]
        elif params is not None and fault == "missing_scope":
            cursor.description = [("OTHER",), ("TPA_ID",), ("POLICY_ID",)]

    cursor.execute.side_effect = execute
    if fault == "row_shape":
        rows[0] = [("GOL001", "TPA001")]
    with pytest.raises(SourceReadUnavailable):
        source.inspect(tenant, "GOL001")
