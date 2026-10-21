"""Explicitly constructed offline mTLS candidate, never normal API startup.

No credential generation/discovery, proxy, redirects or retries. Loopback remains
the default; separate private adapters require a fixed RFC1918 IPv4 endpoint.
Certificate files must be explicitly supplied; live custody/activation stays gated.
"""

import json
import ssl
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from hashlib import sha256
from http.client import HTTPSConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path
from threading import BoundedSemaphore
from types import MappingProxyType
from typing import Literal

from ciq_api.validation_worker import SummaryObservation
from ciq_api.worker_authority import WorkerDenied
from ciq_api.worker_delegation import TransportPeer

SUMMARY_PATH = "/v1/validate-summary"
READ_PATH = "/v1/read-summary"
Operation = Literal["validate_summary", "read_detail"]
MAX_BODY = 8192
TIMEOUT = 3


@dataclass(frozen=True)
class PrivateEndpoint:
    """Trusted configuration only: exact RFC1918 IP/port, never a caller URL/DNS.

    Private addressing is not authentication or egress policy. Operators must
    isolate the network separately; TLS still checks IP SAN, URI identity and pin.
    """

    address: str
    port: int

    def __post_init__(self):
        if type(self.address) is not str or type(self.port) is not int:
            raise ValueError("Invalid private worker endpoint")
        try:
            address = IPv4Address(self.address)
        except ValueError:
            raise ValueError("Invalid private worker endpoint") from None
        if (
            str(address) != self.address
            or not any(
                address in IPv4Network(network)
                for network in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
            )
            or not 0 < self.port < 65536
        ):
            raise ValueError("Invalid private worker endpoint")


def _path(operation: Operation) -> str:
    if operation not in {"validate_summary", "read_detail"}:
        raise ValueError("Invalid worker operation")
    return SUMMARY_PATH if operation == "validate_summary" else READ_PATH


def tls_context(*, server: bool, ca: Path, certificate: Path, private_key: Path) -> ssl.SSLContext:
    """Explicit CA only, mandatory peer certs, TLS 1.3; never environment key logging."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER if server else ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.verify_mode = ssl.CERT_REQUIRED
    context.keylog_filename = None
    context.load_verify_locations(cafile=str(ca))
    context.load_cert_chain(str(certificate), str(private_key))
    if not server:
        context.check_hostname = True
        context.hostname_checks_common_name = False
    return context


def _check_context(context: ssl.SSLContext, *, server: bool) -> None:
    if (
        context.protocol != (ssl.PROTOCOL_TLS_SERVER if server else ssl.PROTOCOL_TLS_CLIENT)
        or context.verify_mode != ssl.CERT_REQUIRED
        or context.minimum_version < ssl.TLSVersion.TLSv1_3
        or context.keylog_filename is not None
        or (not server and (not context.check_hostname or context.hostname_checks_common_name))
    ):
        raise ValueError("Invalid worker TLS configuration")


def _pins(pins: Mapping[str, str]) -> Mapping[str, str]:
    copied = dict(pins)
    if not copied or any(
        len(pin) != 64
        or any(c not in "0123456789abcdef" for c in pin)
        or not audience
        or len(audience) > 120
        for pin, audience in copied.items()
    ):
        raise ValueError("Invalid worker peer configuration")
    return MappingProxyType(copied)


def _peer(connection: ssl.SSLSocket, pins: Mapping[str, str]) -> TransportPeer:
    # TLS already verified chain, validity and appropriate client/server EKU.
    audience = pins.get(sha256(connection.getpeercert(binary_form=True)).hexdigest())
    identities = [
        value for kind, value in connection.getpeercert().get("subjectAltName", ()) if kind == "URI"
    ]
    if audience is None or identities != [f"urn:cashlessiq:worker:{audience}"]:
        raise WorkerDenied("Worker access denied")
    return TransportPeer(audience)


def _json(payload: bytes) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Invalid worker message")
            result[key] = value
        return result

    value = json.loads(payload, object_pairs_hook=unique)
    if type(value) is not dict:
        raise ValueError("Invalid worker message")
    return value


def _length(headers) -> int:
    values = headers.get_all("Content-Length", [])
    if (
        len(values) != 1
        or headers.get_all("Transfer-Encoding")
        or len(values[0]) > 5
        or not values[0].isascii()
        or not values[0].isdigit()
        or not 0 < int(values[0]) <= MAX_BODY
        or headers.get_all("Content-Type", []) != ["application/json"]
    ):
        raise ValueError("Invalid worker message")
    return int(values[0])


class LoopbackSummaryServer(ThreadingHTTPServer):
    """Bounded local test listener; no CLI/startup or public/container binding.

    The fixed callback must be the delegated-validator boundary, not raw input
    access. This adapter never accepts peer identity from headers or JSON.
    """

    daemon_threads = True
    allow_reuse_address = False
    request_queue_size = 8

    def __init__(
        self,
        *,
        context: ssl.SSLContext,
        peers: Mapping[str, str],
        validate: Callable[..., SummaryObservation],
        operation: Operation = "validate_summary",
    ):
        _check_context(context, server=True)
        self._context = context
        self._peers = _pins(peers)
        self._validate = validate
        self._path = _path(operation)
        self._slots = BoundedSemaphore(8)
        super().__init__(self._listen_address(), _SummaryHandler)

    def _listen_address(self) -> tuple[str, int]:
        return ("127.0.0.1", 0)

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(TIMEOUT)
        try:
            return self._context.wrap_socket(connection, server_side=True), address
        except Exception:
            connection.close()
            raise

    def process_request(self, request, client_address):
        if not self._slots.acquire(blocking=False):
            self.close_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self._slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()

    def handle_error(self, request, client_address):
        # No request, assertion, source exception or TLS credential logging.
        pass

    def _dispatch(self, message: dict, peer: TransportPeer) -> bytes:
        if (
            set(message) != {"token"}
            or type(message["token"]) is not str
            or not 0 < len(message["token"]) <= 4096
        ):
            raise ValueError("Invalid worker message")
        result = SummaryObservation.model_validate(
            self._validate(message["token"], peer=peer).model_dump()
        )
        return result.model_dump_json().encode()


class _SummaryHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _reply(self, status: int, body: bytes) -> None:
        self.close_connection = True
        self.send_response_only(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def send_error(self, code, message=None, explain=None):
        self._reply(403, b'{"error":"Worker access denied"}')

    def do_POST(self):
        try:
            peer = _peer(self.connection, self.server._peers)
            if self.path != self.server._path:
                raise WorkerDenied("Worker access denied")
            length = _length(self.headers)
            body = self.rfile.read(length)
            if len(body) != length:
                raise ValueError("Invalid worker message")
            message = _json(body)
            response = self.server._dispatch(message, peer)
            if len(response) > MAX_BODY:
                raise ValueError("Invalid worker message")
        except Exception:
            self._reply(403, b'{"error":"Worker access denied"}')
            return
        self._reply(200, response)


class LoopbackSummaryClient:
    """One pinned loopback peer and fixed operation; no browser-selected target."""

    def __init__(
        self,
        *,
        context: ssl.SSLContext,
        port: int,
        server_pin: str,
        server_audience: str,
        operation: Operation = "validate_summary",
    ):
        _check_context(context, server=False)
        if type(port) is not int or not 0 < port < 65536:
            raise ValueError("Invalid worker endpoint")
        self._context = context
        self._host = "127.0.0.1"
        self._port = port
        self._peers = _pins({server_pin: server_audience})
        self._path = _path(operation)

    def summary(self, token: str) -> SummaryObservation:
        if type(token) is not str or not 0 < len(token) <= 4096:
            raise WorkerDenied("Worker access denied")
        try:
            return SummaryObservation.model_validate(self._exchange({"token": token}))
        except Exception:
            raise WorkerDenied("Worker access denied") from None

    def _exchange(self, message: dict) -> dict:
        """Shared framing/TLS only; subclasses must enforce their strict contract."""
        connection = HTTPSConnection(self._host, self._port, timeout=TIMEOUT, context=self._context)
        try:
            body = json.dumps(message).encode()
            if len(body) > MAX_BODY:
                raise WorkerDenied("Worker access denied")
            connection.connect()
            _peer(connection.sock, self._peers)  # Before sending any capability.
            connection.request(
                "POST", self._path, body=body, headers={"Content-Type": "application/json"}
            )
            response = connection.getresponse()
            if response.status != 200 or response.getheader("Cache-Control") != "no-store":
                raise WorkerDenied("Worker access denied")
            length = _length(response.headers)
            payload = response.read(length + 1)
            if len(payload) != length:
                raise ValueError("Invalid worker message")
            return _json(payload)
        except Exception:
            raise WorkerDenied("Worker access denied") from None
        finally:
            connection.close()


class PrivateSummaryServer(LoopbackSummaryServer):
    """Explicit private test adapter, not a production HTTP server/startup hook."""

    def __init__(self, *, endpoint: PrivateEndpoint, **configuration):
        if type(endpoint) is not PrivateEndpoint:
            raise ValueError("Invalid private worker endpoint")
        self._endpoint = endpoint
        super().__init__(**configuration)

    def _listen_address(self) -> tuple[str, int]:
        return (self._endpoint.address, self._endpoint.port)


class PrivateSummaryClient(LoopbackSummaryClient):
    """One trusted exact IP/port; no DNS resolution, URLs or destination override."""

    def __init__(self, *, endpoint: PrivateEndpoint, **configuration):
        if type(endpoint) is not PrivateEndpoint:
            raise ValueError("Invalid private worker endpoint")
        super().__init__(port=endpoint.port, **configuration)
        self._host = endpoint.address
