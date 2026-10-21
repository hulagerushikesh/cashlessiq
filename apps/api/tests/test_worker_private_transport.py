"""Private configuration rejects public/wildcard/DNS input before network I/O."""

from unittest.mock import patch

import pytest
from test_worker_transport import context
from test_worker_transport import pki as pki

from ciq_api.source_alpha import SOURCE_TENANTS
from ciq_api.worker_membership import PrivateMembershipClient, PrivateMembershipServer
from ciq_api.worker_transport import (
    PrivateEndpoint,
    PrivateSummaryClient,
    PrivateSummaryServer,
)


@pytest.mark.parametrize("address", ["10.1.2.3", "172.16.0.2", "172.31.255.254", "192.168.1.2"])
def test_exact_rfc1918_configuration(address):
    assert PrivateEndpoint(address, 8443).address == address


@pytest.mark.parametrize(
    "address",
    [
        "0.0.0.0",
        "127.0.0.1",
        "169.254.169.254",
        "100.64.0.1",
        "172.32.0.1",
        "8.8.8.8",
        "198.51.100.1",
        "224.0.0.1",
        "::1",
        "::ffff:10.1.2.3",
        "reader",
        "https://10.1.2.3",
        "10.1.2.3:8443",
        "010.1.2.3",
        "10.1.2.3 ",
        None,
    ],
)
def test_nonprivate_or_ambiguous_address_rejected(address):
    with pytest.raises(ValueError):
        PrivateEndpoint(address, 8443)


@pytest.mark.parametrize("port", [0, -1, 65536, True, "8443", None])
def test_invalid_private_port_rejected(port):
    with pytest.raises(ValueError):
        PrivateEndpoint("10.1.2.3", port)


@pytest.mark.parametrize("membership", [False, True])
def test_private_client_destination_is_exact_not_loopback(pki, membership):
    cls = PrivateMembershipClient if membership else PrivateSummaryClient
    configuration = {"tenant_id": SOURCE_TENANTS[0].tenant_id} if membership else {}
    client = cls(
        endpoint=PrivateEndpoint("10.1.2.3", 8443),
        context=context(pki, "reader"),
        server_pin=pki[1]["validator"][2],
        server_audience="validator:0",
        **configuration,
    )
    assert client._host == "10.1.2.3" and client._port == 8443


@pytest.mark.parametrize("membership", [False, True])
def test_private_server_binds_only_supplied_interface(pki, membership):
    cls = PrivateMembershipServer if membership else PrivateSummaryServer
    configuration = (
        {
            "tenants": {"reader:0:nonclinical": SOURCE_TENANTS[0].tenant_id},
            "lookup": lambda *_: None,
        }
        if membership
        else {"validate": lambda *_: None}
    )
    with patch("ciq_api.worker_transport.ThreadingHTTPServer.__init__") as bind:
        cls(
            endpoint=PrivateEndpoint("10.1.2.3", 8443),
            context=context(pki, "validator", server=True),
            peers={pki[1]["reader"][2]: "reader:0:nonclinical"},
            **configuration,
        )
    assert bind.call_args.args[0] == ("10.1.2.3", 8443)
