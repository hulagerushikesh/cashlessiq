"""Real loopback TLS handshakes with disposable PKI and fake source inputs only."""

import ipaddress
import json
import ssl
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from http.client import HTTPSConnection
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from unittest.mock import Mock

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
from test_worker_delegation import delegation as delegation
from test_worker_delegation import unpack

from ciq_api.worker_authority import WorkerDenied
from ciq_api.worker_delegation import TransportPeer
from ciq_api.worker_transport import (
    SUMMARY_PATH,
    LoopbackSummaryClient,
    LoopbackSummaryServer,
    tls_context,
)


@pytest.fixture(scope="module")
def pki():
    now = datetime.now(UTC)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Disposable test CA")])
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.KeyUsage(False, False, False, False, False, True, True, False, False),
            critical=True,
        )
        .sign(ca_key, hashes.SHA256())
    )
    with TemporaryDirectory(prefix="ciq-test-mtls-") as directory:
        root = Path(directory)
        ca = root / "ca.pem"
        ca.write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))
        credentials = {}
        for name, audience, usage in [
            ("reader", "reader:0:nonclinical", ExtendedKeyUsageOID.CLIENT_AUTH),
            ("broker", "broker", ExtendedKeyUsageOID.CLIENT_AUTH),
            ("foreign", "reader:1:nonclinical", ExtendedKeyUsageOID.CLIENT_AUTH),
            ("medical", "reader:0:medical", ExtendedKeyUsageOID.CLIENT_AUTH),
            ("validator", "validator:0", ExtendedKeyUsageOID.SERVER_AUTH),
            ("membership", "membership:0", ExtendedKeyUsageOID.SERVER_AUTH),
            ("wrong_uri", "other-validator", ExtendedKeyUsageOID.SERVER_AUTH),
            ("expired", "validator:0", ExtendedKeyUsageOID.SERVER_AUTH),
            ("wrong_eku", "reader:0:nonclinical", ExtendedKeyUsageOID.SERVER_AUTH),
            ("wrong_host", "validator:0", ExtendedKeyUsageOID.SERVER_AUTH),
            ("untrusted", "reader:0:nonclinical", ExtendedKeyUsageOID.CLIENT_AUTH),
        ]:
            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            leaf = (
                x509.CertificateBuilder()
                .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)]))
                .issuer_name(ca_name)
                .public_key(key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(now - timedelta(days=2))
                .not_valid_after(
                    now - timedelta(days=1) if name == "expired" else now + timedelta(days=1)
                )
                .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
                .add_extension(
                    x509.ExtendedKeyUsage(
                        [ExtendedKeyUsageOID.CLIENT_AUTH, ExtendedKeyUsageOID.SERVER_AUTH]
                        if name == "reader"
                        else [usage]
                    ),
                    critical=True,
                )
                .add_extension(
                    x509.SubjectAlternativeName(
                        [
                            x509.UniformResourceIdentifier(f"urn:cashlessiq:worker:{audience}"),
                            x509.IPAddress(
                                ipaddress.ip_address(
                                    "127.0.0.2" if name == "wrong_host" else "127.0.0.1"
                                )
                            ),
                        ]
                    ),
                    critical=False,
                )
                .sign(key if name == "untrusted" else ca_key, hashes.SHA256())
            )
            certificate = root / f"{name}.pem"
            private_key = root / f"{name}.key"
            certificate.write_bytes(leaf.public_bytes(serialization.Encoding.PEM))
            private_key.touch(mode=0o600)
            private_key.write_bytes(
                key.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.PKCS8,
                    serialization.NoEncryption(),
                )
            )
            credentials[name] = (certificate, private_key, leaf.fingerprint(hashes.SHA256()).hex())
        yield ca, credentials


def context(pki, name, *, server=False):
    ca, credentials = pki
    certificate, private_key, _ = credentials[name]
    return tls_context(server=server, ca=ca, certificate=certificate, private_key=private_key)


@contextmanager
def running(pki, callback, *, server="validator", peers=None, operation="validate_summary"):
    _, credentials = pki
    listener = LoopbackSummaryServer(
        context=context(pki, server, server=True),
        peers=peers or {credentials["reader"][2]: "reader:0:nonclinical"},
        validate=callback,
        operation=operation,
    )
    thread = Thread(target=listener.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
    thread.start()
    try:
        yield listener.server_port
    finally:
        listener.shutdown()
        listener.server_close()
        thread.join(timeout=4)
        assert not thread.is_alive()


def client(
    pki,
    port,
    *,
    name="reader",
    server="validator",
    audience="validator:0",
    operation="validate_summary",
):
    return LoopbackSummaryClient(
        context=context(pki, name),
        port=port,
        server_pin=pki[1][server][2],
        server_audience=audience,
        operation=operation,
    )


def test_real_mtls_relay_validator_path_and_no_raw_export(pki, delegation):
    _, _, read, endpoint, relay, _, issue = delegation()
    callback = Mock(side_effect=endpoint.validate)
    with running(pki, callback) as port:
        relay._invoke = client(pki, port).summary
        result = relay.summary(issue())
    assert result.recommendation.payable_inr == 95_000
    assert type(callback.call_args.kwargs["peer"]) is TransportPeer
    assert callback.call_args.kwargs["peer"].audience == "reader:0:nonclinical"
    read.assert_called_once_with("GOL001")
    assert '"decision_json"' not in result.model_dump_json()


def test_both_broker_reader_and_reader_validator_hops_use_mtls(pki, delegation):
    _, _, read, endpoint, relay, _, issue = delegation()

    def reader_endpoint(token, *, peer):
        assert type(peer) is TransportPeer
        assert peer.audience == "broker"
        return relay.summary(token)

    with running(pki, endpoint.validate) as validator_port:
        relay._invoke = client(pki, validator_port).summary
        with running(
            pki,
            reader_endpoint,
            server="reader",
            peers={pki[1]["broker"][2]: "broker"},
            operation="read_detail",
        ) as reader_port:
            broker = client(
                pki,
                reader_port,
                name="broker",
                server="reader",
                audience="reader:0:nonclinical",
                operation="read_detail",
            )
            result = broker.summary(issue())
    assert result.recommendation.payable_inr == 95_000
    read.assert_called_once_with("GOL001")


def test_reader_listener_rejects_nonbroker_peer(pki):
    callback = Mock()
    with (
        running(
            pki,
            callback,
            server="reader",
            peers={pki[1]["broker"][2]: "broker"},
            operation="read_detail",
        ) as port,
        pytest.raises(WorkerDenied),
    ):
        client(
            pki,
            port,
            server="reader",
            audience="reader:0:nonclinical",
            operation="read_detail",
        ).summary("opaque")
    callback.assert_not_called()


@pytest.mark.parametrize("name", ["foreign", "untrusted", "wrong_eku"])
def test_wrong_client_cert_denied_before_callback(pki, name):
    callback = Mock()
    with (
        running(pki, callback) as port,
        pytest.raises(WorkerDenied, match=r"^Worker access denied$"),
    ):
        client(pki, port, name=name).summary("opaque-capability")
    callback.assert_not_called()


def test_client_certificate_is_mandatory(pki):
    callback = Mock()
    no_certificate = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    no_certificate.minimum_version = ssl.TLSVersion.TLSv1_3
    no_certificate.hostname_checks_common_name = False
    no_certificate.load_verify_locations(cafile=str(pki[0]))
    with running(pki, callback) as port:
        transport = LoopbackSummaryClient(
            context=no_certificate,
            port=port,
            server_pin=pki[1]["validator"][2],
            server_audience="validator:0",
        )
        with pytest.raises(WorkerDenied):
            transport.summary("opaque-capability")
    callback.assert_not_called()


@pytest.mark.parametrize("server", ["wrong_uri", "expired", "wrong_host"])
def test_wrong_server_identity_or_validity_denied_before_capability(pki, server):
    callback = Mock()
    with running(pki, callback, server=server) as port, pytest.raises(WorkerDenied):
        client(pki, port, server=server).summary("opaque-capability")
    callback.assert_not_called()


def test_wrong_server_pin_denied_before_capability(pki):
    callback = Mock()
    with running(pki, callback) as port, pytest.raises(WorkerDenied):
        client(pki, port, server="wrong_uri").summary("opaque-capability")
    callback.assert_not_called()


def test_trusted_foreign_reader_cannot_use_nonclinical_capability(pki, delegation):
    _, _, read, endpoint, _, _, issue = delegation()
    with (
        running(pki, endpoint.validate, peers={pki[1]["medical"][2]: "reader:0:medical"}) as port,
        pytest.raises(WorkerDenied),
    ):
        client(pki, port, name="medical").summary(unpack(issue())["summary_token"])
    read.assert_not_called()


@pytest.mark.parametrize("damage", ["extra", "duplicate", "large", "path", "method", "framing"])
def test_bounded_fixed_protocol_rejects_malformed_messages(pki, damage):
    callback = Mock()
    with running(pki, callback) as port:
        connection = HTTPSConnection("127.0.0.1", port, context=context(pki, "reader"), timeout=3)
        body = b'{"token":"opaque"}'
        path, method = SUMMARY_PATH, "POST"
        headers = {"Content-Type": "application/json"}
        if damage == "extra":
            body = b'{"token":"opaque","peer":"reader:0:medical"}'
        elif damage == "duplicate":
            body = b'{"token":"opaque","token":"other"}'
        elif damage == "large":
            body = b"x" * 8193
        elif damage == "path":
            path = "/raw-export"
        elif damage == "method":
            method = "GET"
        else:
            headers["Transfer-Encoding"] = "chunked"
        try:
            connection.request(method, path, body, headers)
            response = connection.getresponse()
            assert response.status == 403
            assert response.getheader("Cache-Control") == "no-store"
            assert response.read() == b'{"error":"Worker access denied"}'
        finally:
            connection.close()
    callback.assert_not_called()


def test_spoofed_identity_header_does_not_override_tls_peer(pki, delegation):
    _, _, read, endpoint, _, _, issue = delegation()
    callback = Mock(side_effect=endpoint.validate)
    with running(pki, callback) as port:
        connection = HTTPSConnection("127.0.0.1", port, context=context(pki, "reader"), timeout=3)
        try:
            connection.request(
                "POST",
                SUMMARY_PATH,
                json.dumps({"token": unpack(issue())["summary_token"]}),
                {"Content-Type": "application/json", "X-Worker-Identity": "reader:0:medical"},
            )
            response = connection.getresponse()
            assert response.status == 200
            response.read()
        finally:
            connection.close()
    assert callback.call_args.kwargs["peer"].audience == "reader:0:nonclinical"
    read.assert_called_once()


def test_callback_errors_are_generic_and_not_logged(pki, capsys):
    callback = Mock(side_effect=RuntimeError("SECRET SOURCE FAILURE"))
    with running(pki, callback) as port, pytest.raises(WorkerDenied) as error:
        client(pki, port).summary("opaque-capability")
    assert str(error.value) == "Worker access denied"
    assert capsys.readouterr() == ("", "")


def test_insecure_context_rejected(pki):
    insecure = context(pki, "reader")
    insecure.check_hostname = False
    with pytest.raises(ValueError):
        LoopbackSummaryClient(
            context=insecure,
            port=1234,
            server_pin=pki[1]["validator"][2],
            server_audience="validator:0",
        )


def test_tls_key_logging_environment_is_not_used(pki, tmp_path, monkeypatch):
    log_path = tmp_path / "must-not-exist.log"
    monkeypatch.setenv("SSLKEYLOGFILE", str(log_path))
    assert context(pki, "reader").keylog_filename is None
    assert context(pki, "validator", server=True).keylog_filename is None
    assert not log_path.exists()


def test_transport_does_not_bypass_assertion_replay_protection(pki, delegation):
    _, _, read, endpoint, _, _, issue = delegation()
    token = unpack(issue())["summary_token"]
    with running(pki, endpoint.validate) as port:
        transport = client(pki, port)
        transport.summary(token)
        with pytest.raises(WorkerDenied):
            transport.summary(token)
    read.assert_called_once()
