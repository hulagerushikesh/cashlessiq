"""Ownership configuration fails closed before any connector can be opened."""

from dataclasses import FrozenInstanceError
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from ciq_api.seed import TENANT_ID
from ciq_api.snowflake_reads import SnowflakeCaseSource
from ciq_api.source_scopes import SyntheticSourceScopes


def test_no_default_or_unknown_tenant_scope():
    assert SyntheticSourceScopes({}).get(uuid4()) is None


@pytest.mark.parametrize(
    "bindings",
    [
        {TENANT_ID: "TPA001"},
        {TENANT_ID: "TPA003"},
        {"not-a-uuid": "TPA001"},
        {uuid4(): "TPA002"},
        {uuid4(): ""},
        {uuid4(): "' OR 1=1 --"},
        {uuid4(): ["TPA001", "TPA003"]},
        {uuid4(): "TPA001", uuid4(): "TPA001"},
    ],
)
def test_invalid_bindings_rejected_without_io(bindings):
    connect = MagicMock()
    with pytest.raises(ValueError):
        SnowflakeCaseSource(connect, bindings)
    connect.assert_not_called()


def test_bindings_are_copied_and_scopes_are_immutable():
    tenant = uuid4()
    bindings = {tenant: "TPA001"}
    registry = SyntheticSourceScopes(bindings)
    bindings[tenant] = "TPA003"
    scope = registry.get(tenant)
    assert scope.tpa_id == "TPA001"
    assert scope.request_ids == ("GOL001",)
    with pytest.raises(FrozenInstanceError):
        scope.tpa_id = "TPA003"
