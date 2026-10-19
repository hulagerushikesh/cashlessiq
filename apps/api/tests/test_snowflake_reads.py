"""No-network tests for the source gateway's scope and resource lifecycle."""

from datetime import date
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from ciq_api.snowflake_reads import READ_SQL, SnowflakeCaseSource, SourceReadUnavailable

COLUMNS = [
    "REQUEST_ID",
    "POLICY_ID",
    "TPA_ID",
    "PRODUCT_ID",
    "PRODUCT_NAME",
    "POLICY_VERSION",
    "CONTINUOUS_COVER_SINCE",
    "ADMISSION_DATE",
    "ESTIMATED_TOTAL_INR",
]
ROW = (
    "GOL001",
    "POL001",
    "TPA001",
    "PRODUCT001",
    "Synthetic policy",
    "v1",
    date(2020, 1, 1),
    date(2026, 1, 1),
    100000,
)


def source(rows=None):
    connect = MagicMock()
    connection = connect.return_value.__enter__.return_value
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.description = [(name,) for name in COLUMNS]
    cursor.fetchmany.return_value = [ROW] if rows is None else rows
    tenant = uuid4()
    return SnowflakeCaseSource(connect, {tenant: "TPA001"}), tenant, connect, cursor


def test_unknown_tenant_does_not_connect():
    gateway, _, connect, _ = source()
    assert gateway.read_cases(uuid4()) == []
    connect.assert_not_called()


def test_bounded_parameterized_read_and_cleanup():
    gateway, tenant, connect, cursor = source()
    records = gateway.read_cases(tenant)
    assert records[0].estimated_total_inr == 100000
    cursor.execute.assert_called_once_with(
        READ_SQL, ("TPA001", "GOL001", "GOL024", "GOL027"), timeout=30
    )
    cursor.fetchmany.assert_called_once_with(4)
    connect.return_value.__exit__.assert_called_once()
    assert "CLINICAL_NOTE" not in READ_SQL and "FULL_NAME" not in READ_SQL


@pytest.mark.parametrize("replacement", ["TPA002", "' OR 1=1 --"])
def test_wrong_tpa_fails_closed(replacement):
    row = (*ROW[:2], replacement, *ROW[3:])
    gateway, tenant, _, _ = source([row])
    with pytest.raises(SourceReadUnavailable, match="source read unavailable"):
        gateway.read_cases(tenant)


@pytest.mark.parametrize("rows", [[ROW, ROW], [ROW] * 4, [("OTHER", *ROW[1:])]])
def test_duplicate_excess_or_unapproved_requests_fail_closed(rows):
    gateway, tenant, _, _ = source(rows)
    with pytest.raises(SourceReadUnavailable):
        gateway.read_cases(tenant)


def test_error_is_generic_and_connections_close():
    gateway, tenant, connect, cursor = source()
    cursor.execute.side_effect = RuntimeError("sensitive connector diagnostic")
    with pytest.raises(SourceReadUnavailable) as error:
        gateway.read_cases(tenant)
    assert "sensitive" not in str(error.value)
    connect.return_value.__exit__.assert_called_once()


def test_absent_source_rows_are_not_fabricated():
    gateway, tenant, _, _ = source([])
    assert gateway.read_cases(tenant) == []
