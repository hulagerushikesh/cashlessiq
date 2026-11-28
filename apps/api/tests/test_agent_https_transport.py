"""Scripted HTTP and loopback TLS only; no provider or real credential."""

import hashlib
import http.client
import io
import socket
import ssl
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from test_agent_contracts import candidate, capture, context
from test_agent_one_shot import CONFIG
from test_agent_provider_response import REMOTE, body, text

from ciq_api import agent_https_transport as transport
from ciq_api.agent_contracts import canonical_json
from ciq_api.agent_one_shot import (
    ENDPOINT_PATH,
    MAX_ONE_SHOT_REQUEST_BYTES,
    decode_captured_one_shot,
    prepare_captured_one_shot,
)
from ciq_api.agent_provider_response import MAX_PROVIDER_RESPONSE_BYTES

HOST = "reviewed-account.snowflakecomputing.com"
TOKEN = "DUMMY-only-private-token"
REQUEST = b'{"synthetic":"PRIVATE clinical bytes"}'
REPLY = b'{"synthetic":"PRIVATE response"}'
REAL_CONNECTION = http.client.HTTPSConnection


def response_wire(payload=REPLY, *, status=200, headers=None):
    if headers is None:
        headers = [("Content-Type", "application/json"), ("Content-Length", str(len(payload)))]
    return (
        f"HTTP/1.1 {status} PRIVATE SERVER MESSAGE\r\n".encode()
        + b"".join(f"{k}: {v}\r\n".encode() for k, v in headers)
        + b"\r\n" + payload
    )


class TrackedStream(io.BytesIO):
    def close(self):
        if not self.closed:
            self.position_at_close = self.tell()
        super().close()


class ScriptedSocket:
    def __init__(self, wire):
        self.stream = TrackedStream(wire)
        self.sent = []
        self.timeouts = []
        self.closed = False

    def makefile(self, mode):
        assert mode == "rb"
        return self.stream

    def sendall(self, raw):
        self.sent.append(raw)

    def settimeout(self, value):
        assert 0 < value <= transport.MAX_SOCKET_SECONDS
        self.timeouts.append(value)

    def close(self):
        self.closed = True


@pytest.fixture
def wire_harness(monkeypatch):
    state = {
        "wire": response_wire(), "connections": [], "connects": 0,
        "fault": None, "fault_after_send": False,
    }

    class ScriptedHTTPS(REAL_CONNECTION):
        def __init__(self, host, *, port, timeout, context):
            # Use the real stdlib request writer and HTTPResponse parser, with
            # a byte-stream socket replacing every DNS/TCP/TLS operation.
            assert host == HOST and port == 443 and timeout <= 10
            assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
            assert context.minimum_version >= ssl.TLSVersion.TLSv1_2
            super().__init__(host, port=port, timeout=timeout, context=context)
            self.scripted = ScriptedSocket(state["wire"])
            state["connections"].append(self)

        def connect(self):
            state["connects"] += 1
            if state["fault"] is not None:
                raise state["fault"]
            self.sock = self.scripted

        def request(self, *args, **kwargs):
            super().request(*args, **kwargs)
            if state["fault_after_send"]:
                raise OSError("PRIVATE ambiguous failure after request send")

    monkeypatch.setattr(transport, "HTTPSConnection", ScriptedHTTPS)
    monkeypatch.setattr(socket, "create_connection", lambda *a, **kw: pytest.fail("real network"))
    return state


def single(request=REQUEST, **changes):
    return transport.SinglePostHTTPS(**{
        "hostname": HOST, "token": TOKEN, "request_sha256": hashlib.sha256(request).hexdigest(),
        **changes,
    })


def denied(instance, request=REQUEST, timeout=5):
    with pytest.raises(ValueError, match=r"^agent_https_unavailable$") as error:
        instance.exchange(request, timeout=timeout)
    assert error.value.__suppress_context__
    assert "PRIVATE" not in str(error.value) and TOKEN not in repr(error.value)


def test_real_http_writer_sends_exact_body_once_and_ignores_proxy_cli_and_db_environment(
    wire_harness, monkeypatch, capsys,
):
    for key in (
        "HTTPS_PROXY", "ALL_PROXY", "SNOWFLAKE_TOKEN", "SNOWFLAKE_CONNECTION_NAME",
        "DATABASE_URL", "GOOGLE_APPLICATION_CREDENTIALS",
    ):
        monkeypatch.setenv(key, "PRIVATE ignored parent configuration")
    instance = single()
    assert instance.exchange(REQUEST, timeout=5) == REPLY
    connection = wire_harness["connections"][0]
    sent = b"".join(connection.scripted.sent)
    head, payload = sent.split(b"\r\n\r\n", 1)
    assert head.startswith(b"POST /api/v2/cortex/agent:run HTTP/1.1\r\n")
    assert b"Host: " + HOST.encode() in head
    assert b"Authorization: Bearer " + TOKEN.encode() in head
    assert b"X-Snowflake-Authorization-Token-Type: PROGRAMMATIC_ACCESS_TOKEN" in head
    assert b"Accept-Encoding: identity" in head and b"Connection: close" in head
    assert b"PRIVATE ignored" not in sent and payload == REQUEST
    assert connection.debuglevel == 0 and connection.scripted.closed
    assert instance._token is None
    assert TOKEN not in repr(instance) and "PRIVATE" not in repr(instance)
    denied(instance)
    assert wire_harness["connects"] == 1 and len(wire_harness["connections"]) == 1
    assert capsys.readouterr() == ("", "")


def test_prepared_capture_roundtrip_with_separately_supplied_expected_run_id(
    wire_harness,
):
    snapshot, operation = capture(), uuid4()
    prepared = prepare_captured_one_shot(snapshot, context(snapshot), operation, CONFIG)
    request = prepared.body_json.encode()
    response = canonical_json(body([text(canonical_json(candidate(snapshot, operation)))])).encode()
    wire_harness["wire"] = response_wire(response)
    raw = single(request).exchange(request, timeout=5)
    # Expected ID is still independently supplied test metadata. Reading a run
    # ID from its own reply would not authenticate it or settle durable usage.
    final = decode_captured_one_shot(snapshot, context(snapshot), operation, REMOTE, raw)
    assert final.candidate.run_id == operation
    assert transport.ENDPOINT == ENDPOINT_PATH
    assert transport.MAX_REQUEST_BYTES == MAX_ONE_SHOT_REQUEST_BYTES
    assert transport.MAX_RESPONSE_BYTES == MAX_PROVIDER_RESPONSE_BYTES


@pytest.mark.parametrize("hostname", (
    "https://" + HOST, HOST + ":443", HOST + "/path", HOST + "?query", HOST + "#fragment",
    "user@" + HOST, "127.0.0.1", "localhost", "app.snowflake.com", "snowflakecomputing.com",
    HOST + ".attacker.com", "x.attacker.com", "a..snowflakecomputing.com",
    "-a.snowflakecomputing.com", "a-.snowflakecomputing.com", "a_1.snowflakecomputing.com",
    "a" * 64 + ".snowflakecomputing.com", "A.snowflakecomputing.com", HOST + ".",
    "a\r\nPRIVATE.snowflakecomputing.com", "\u0430.snowflakecomputing.com", None,
))
def test_unreviewable_hostname_rejected_before_any_connection(hostname, wire_harness):
    with pytest.raises(ValueError, match=r"^agent_https_unavailable$"):
        single(hostname=hostname)
    assert not wire_harness["connections"]


@pytest.mark.parametrize("field,value", (
    ("token", ""), ("token", "a" * 8193), ("token", "PRIVATE\r\nX: injected"),
    ("token", "PRIVATE space"), ("token", "秘密"), ("token", b"PRIVATE"),
    ("request_sha256", "0" * 63), ("request_sha256", "A" * 64),
    ("request_sha256", "PRIVATE"), ("request_sha256", None),
))
def test_invalid_trusted_config_is_private_and_never_connects(field, value, wire_harness):
    with pytest.raises(ValueError, match=r"^agent_https_unavailable$"):
        single(**{field: value})
    assert not wire_harness["connections"]


@pytest.mark.parametrize("payload,timeout", (
    (b"", 5), ("PRIVATE", 5), (b"PRIVATE changed body", 5),
    (b"a" * (transport.MAX_REQUEST_BYTES + 1), 5),
    (REQUEST, 0), (REQUEST, -1), (REQUEST, 10.1), (REQUEST, True),
    (REQUEST, "5"), (REQUEST, float("inf")), (REQUEST, float("nan")),
), ids=lambda value: f"bytes-{len(value)}" if type(value) is bytes else None)
def test_invalid_exchange_consumes_instance_before_network(payload, timeout, wire_harness):
    instance = single()
    denied(instance, request=payload, timeout=timeout)
    denied(instance)
    assert instance._token is None and not wire_harness["connections"]


@pytest.mark.parametrize("status", (
    201, 202, 204, 301, 302, 303, 307, 308, 400, 401, 403, 429, 500, 503,
))
def test_error_async_and_redirect_responses_never_read_body_or_retry(status, wire_harness):
    wire_harness["wire"] = response_wire(b"PRIVATE server error", status=status, headers=[
        ("Location", "https://attacker.com/"), ("Retry-After", "0"),
        ("Content-Length", "20"),
    ])
    instance = single()
    denied(instance)
    connection = wire_harness["connections"][0]
    assert connection.scripted.stream.position_at_close == len(wire_harness["wire"]) - 20
    assert connection.scripted.closed
    denied(instance)
    assert wire_harness["connects"] == 1


@pytest.mark.parametrize("headers", (
    [], [("Content-Type", "text/event-stream"), ("Content-Length", "2")],
    [("Content-Type", "application/json"), ("Content-Length", "2"), ("Content-Length", "2")],
    [("Content-Type", "application/json"), ("Content-Length", "2, 2")],
    [("Content-Type", "application/json"), ("Content-Length", "-1")],
    [("Content-Type", "application/json"), ("Content-Length", "0")],
    [("Content-Type", "application/json"), ("Content-Length", "384001")],
    [("Content-Type", "application/json"), ("Transfer-Encoding", "gzip")],
    [("Content-Type", "application/json"),
     ("Transfer-Encoding", "chunked"), ("Content-Length", "2")],
    [("Content-Type", "application/json"), ("Content-Length", "2"), ("Content-Encoding", "gzip")],
    [("Content-Type", "application/json"), ("Content-Type", "text/plain"), ("Content-Length", "2")],
    [("Content-Type", "application/json; charset=latin-1"), ("Content-Length", "2")],
    [("Content-Type", "application/json; other=value"), ("Content-Length", "2")],
    [("Content-Type", "application/json"), ("Content-Length", "2")]
    + [("X-Padding", "a")] * 63,
    [("Content-Type", "application/json"), ("Content-Length", "2"), ("X-Padding", "a" * 32768)],
))
def test_ambiguous_oversize_or_unexpected_headers_fail_closed(headers, wire_harness):
    wire_harness["wire"] = response_wire(b"{}", headers=headers)
    instance = single()
    denied(instance)
    denied(instance)
    assert wire_harness["connects"] == 1 and wire_harness["connections"][0].scripted.closed


@pytest.mark.parametrize("chunked", (False, True))
def test_exact_response_limit_and_complete_chunked_or_length_framing(chunked, wire_harness):
    payload = b"x" * transport.MAX_RESPONSE_BYTES
    headers = [("Content-Type", 'application/json; charset="UTF-8"')]
    if chunked:
        headers.append(("Transfer-Encoding", "chunked"))
        framed = f"{len(payload):x}\r\n".encode() + payload + b"\r\n0\r\n\r\n"
    else:
        headers.append(("Content-Length", str(len(payload))))
        framed = payload
    wire_harness["wire"] = response_wire(framed, headers=headers)
    assert single().exchange(REQUEST, timeout=5) == payload


@pytest.mark.parametrize("payload,headers", (
    (b"{}", [("Content-Length", "3")]),
    (b"", [("Transfer-Encoding", "chunked")]),
    (b"2\r\n{}\r\n", [("Transfer-Encoding", "chunked")]),
    (b"invalid\r\nPRIVATE", [("Transfer-Encoding", "chunked")]),
    (b"0\r\n\r\n", [("Transfer-Encoding", "chunked")]),
    (b"5dc01\r\n" + b"x" * 384001 + b"\r\n0\r\n\r\n", [("Transfer-Encoding", "chunked")]),
), ids=lambda value: f"bytes-{len(value)}" if type(value) is bytes else None)
def test_invalid_body_retains_one_attempt(payload, headers, wire_harness):
    wire_harness["wire"] = response_wire(
        payload, headers=[("Content-Type", "application/json"), *headers],
    )
    instance = single()
    denied(instance)
    denied(instance)
    assert wire_harness["connects"] == 1


@pytest.mark.parametrize("fault", (
    OSError("PRIVATE DNS failure"), TimeoutError("PRIVATE timeout"),
    ssl.SSLCertVerificationError("PRIVATE certificate failure"),
))
def test_connect_or_tls_failure_cannot_retry_or_leak_diagnostics(fault, wire_harness):
    wire_harness["fault"] = fault
    instance = single()
    denied(instance)
    denied(instance)
    assert wire_harness["connects"] == 1 and instance._token is None


def test_failure_after_complete_send_never_becomes_a_second_submission(wire_harness):
    wire_harness["fault_after_send"] = True
    instance = single()
    denied(instance)
    sent = b"".join(wire_harness["connections"][0].scripted.sent)
    assert sent.endswith(REQUEST) and b"Authorization: Bearer " + TOKEN.encode() in sent
    denied(instance)
    assert wire_harness["connects"] == 1 and wire_harness["connections"][0].scripted.closed


def test_phase_expiry_prevents_later_send_without_resetting_budget(wire_harness, monkeypatch):
    ticks = iter((10.0, 10.1, 15.1))
    monkeypatch.setattr(transport.time, "monotonic", lambda: next(ticks))
    instance = single()
    denied(instance)
    assert wire_harness["connects"] == 1
    assert not wire_harness["connections"][0].scripted.sent
    denied(instance)


def test_concurrent_calls_share_one_local_latch_but_not_durable_authority(wire_harness):
    instance = single()

    def call(_):
        try:
            return instance.exchange(REQUEST, timeout=5)
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(call, range(2)))
    assert sorted(result is None for result in results) == [False, True]
    assert wire_harness["connects"] == 1


@pytest.mark.parametrize("fault", (None, "hostname", "untrusted"))
@pytest.mark.parametrize("pinned", (False, True))
def test_real_loopback_tls_checks_certificate_before_sending_token(
    fault, pinned, tmp_path, monkeypatch,
):
    # All keys/certificates are ephemeral test fixtures. TCP is forced to one
    # loopback listener while real HTTPSConnection retains the configured SNI
    # hostname and Python/OpenSSL performs actual certificate verification.
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Synthetic loopback only")])
    now = datetime.now(UTC)
    certificate = (
        x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1)).not_valid_after(now + timedelta(minutes=5))
        .add_extension(x509.SubjectAlternativeName([
            x509.DNSName("wrong.example" if fault == "hostname" else HOST),
        ]), critical=False).sign(key, hashes.SHA256())
    )
    cert_path, key_path = tmp_path / "dummy-cert.pem", tmp_path / "dummy-key.pem"
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))
    key_path.chmod(0o600)
    server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_context.load_cert_chain(cert_path, key_path)
    client_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    if fault != "untrusted":
        client_context.load_verify_locations(cafile=cert_path)
    monkeypatch.setattr(transport, "_tls_context", lambda: client_context)
    seen, failures = [], []
    real_connect = socket.create_connection
    with socket.socket() as listener:
        listener.settimeout(2)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)

        def serve():
            try:
                peer, _ = listener.accept()
                with peer:
                    peer.settimeout(2)
                    try:
                        with server_context.wrap_socket(peer, server_side=True) as secured:
                            incoming = b""
                            while b"\r\n\r\n" not in incoming:
                                chunk = secured.recv(4096)
                                if not chunk or len(incoming) + len(chunk) > 8192:
                                    raise ValueError("dummy server input unavailable")
                                incoming += chunk
                            headers, payload = incoming.split(b"\r\n\r\n", 1)
                            while len(payload) < len(REQUEST):
                                chunk = secured.recv(4096)
                                if not chunk:
                                    raise ValueError("dummy server input unavailable")
                                payload += chunk
                            seen.append((headers, payload))
                            secured.sendall(response_wire(headers=[
                                ("Content-Type", "application/json"),
                                ("Content-Length", str(len(REPLY))), ("Connection", "close"),
                            ]))
                    except ssl.SSLError:
                        if fault is None:
                            failures.append("unexpected dummy TLS failure")
            except Exception:
                failures.append("dummy listener failed")

        class LoopbackHTTPS(REAL_CONNECTION):
            def __init__(self, host, *, port, timeout, context):
                assert host == HOST and port == 443
                super().__init__(host, port=port, timeout=timeout, context=context)

                def connect_loopback(address, timeout, source_address):
                    assert address == (HOST, 443) and source_address is None
                    return real_connect(listener.getsockname(), timeout=timeout)

                self._create_connection = connect_loopback

        monkeypatch.setattr(transport, "HTTPSConnection", LoopbackHTTPS)
        if pinned:
            original_socket = socket.socket
            destination = listener.getsockname()

            class DirectedSocket(original_socket):
                def connect(self, address):
                    assert address == ("1.1.1.1", 443)
                    return super().connect(destination)  # Test-only loopback redirection.

            monkeypatch.setattr(socket, "socket", DirectedSocket)
            monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: pytest.fail("DNS forbidden"))
        worker = threading.Thread(target=serve)
        worker.start()
        try:
            instance = (transport.PinnedSinglePostHTTPS(
                address_ipv4="1.1.1.1", hostname=HOST, token=TOKEN,
                request_sha256=hashlib.sha256(REQUEST).hexdigest(),
            ) if pinned else single())
            if fault is None:
                assert instance.exchange(REQUEST, timeout=1.5) == REPLY
            else:
                denied(instance, timeout=1.5)
            denied(instance)
        finally:
            worker.join(timeout=3)
        assert not worker.is_alive() and not failures
    if fault is None:
        assert len(seen) == 1 and seen[0][1] == REQUEST
        assert b"Authorization: Bearer " + TOKEN.encode() in seen[0][0]
    else:
        assert not seen


def test_default_tls_context_does_not_enable_environment_key_logging(tmp_path, monkeypatch):
    keylog = tmp_path / "must-not-create-tls-secrets.log"
    monkeypatch.setenv("SSLKEYLOGFILE", str(keylog))
    context = transport._tls_context()
    assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
    assert context.minimum_version >= ssl.TLSVersion.TLSv1_2
    assert context.keylog_filename is None and not keylog.exists()


@pytest.mark.parametrize("address", (
    None, b"1.1.1.1", ["1.1.1.1"], "1.1.1.1:443", "https://1.1.1.1", "1.1.1.1 ",
    "01.1.1.1", "::1", "::ffff:1.1.1.1", "127.0.0.1", "10.0.0.1", "169.254.169.254",
    "192.0.2.1", "0.0.0.0", "224.0.0.1", "255.255.255.255", "PRIVATE hostname",
))
def test_pinned_transport_rejects_nonpublic_noncanonical_or_multiple_addresses(address):
    with pytest.raises(ValueError, match="^" + transport.ERROR + "$"):
        transport.PinnedSinglePostHTTPS(address_ipv4=address, hostname=HOST, token=TOKEN,
                                      request_sha256=hashlib.sha256(REQUEST).hexdigest())


def test_pinned_connect_failure_closes_one_socket_without_dns_fallback_or_retry(monkeypatch):
    from unittest.mock import Mock
    raw = Mock()
    raw.connect.side_effect = OSError("PRIVATE dummy connection failure")
    factory = Mock(return_value=raw)
    monkeypatch.setattr(socket, "socket", factory)
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: pytest.fail("DNS forbidden"))
    instance = transport.PinnedSinglePostHTTPS(
        address_ipv4="1.1.1.1", hostname=HOST, token=TOKEN,
        request_sha256=hashlib.sha256(REQUEST).hexdigest(),
    )
    denied(instance)
    denied(instance)
    factory.assert_called_once_with(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
    raw.connect.assert_called_once_with(("1.1.1.1", 443))
    raw.close.assert_called_once()
