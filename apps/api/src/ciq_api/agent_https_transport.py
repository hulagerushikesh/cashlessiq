"""Inactive HTTPS primitive; not an execution permit or a sandbox launcher.

No entrypoint, environment/config discovery, credential loading, SDK or database.
Trusted custody must pin the exact body/host and issue durably before calling.
This code must run in a separately credentialed, externally deadline-supervised
process before live use. Socket timeouts do not bound DNS or slow HTTP headers.
"""

import hashlib
import math
import re
import ssl
import threading
import time
from contextlib import closing
from http.client import HTTPSConnection

ENDPOINT = "/api/v2/cortex/agent:run"
MAX_REQUEST_BYTES = 256_000
MAX_RESPONSE_BYTES = 384_000
MAX_SOCKET_SECONDS = 10
ERROR = "agent_https_unavailable"
_HOST = re.compile(
    r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.){1,4}snowflakecomputing\.com",
)
_TOKEN = re.compile(r"[A-Za-z0-9._~+/-]+=*")
_DIGEST = re.compile(r"[0-9a-f]{64}")


def _require(condition):
    if not condition:
        raise ValueError(ERROR)


def _tls_context():
    # Unlike create_default_context(), do not activate SSLKEYLOGFILE from the
    # environment. Trust-store environment isolation remains the future
    # launcher's responsibility; no caller-supplied unverified context exists.
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_default_certs(ssl.Purpose.SERVER_AUTH)
    return context


def _response_length(response):
    """Reject ambiguous framing/compression before reading any response body."""
    headers = response.getheaders()
    _require(len(headers) <= 64 and sum(len(k) + len(v) for k, v in headers) <= 32_768)
    values = {}
    for key, value in headers:
        values.setdefault(key.lower(), []).append(value.strip())
    for name in ("content-type", "content-encoding", "content-length", "transfer-encoding"):
        _require(len(values.get(name, [])) <= 1)
    _require(bool(re.fullmatch(
        r'application/json(?:;\s*charset=(?:utf-8|"utf-8"))?',
        values.get("content-type", [""])[0].lower(),
    )))
    _require(values.get("content-encoding", ["identity"])[0].lower() == "identity")
    length = values.get("content-length")
    transfer = values.get("transfer-encoding")
    _require(bool(length) != bool(transfer))
    if transfer:
        _require(transfer[0].lower() == "chunked" and response.chunked)
        return None
    _require(bool(re.fullmatch(r"[0-9]{1,6}", length[0])))
    size = int(length[0])
    _require(0 < size <= MAX_RESPONSE_BYTES and response.length == size)
    return size


class SinglePostHTTPS:
    """At most one POST per instance, including uncertain or invalid attempts.

    Constructor arguments are trusted reviewed configuration, never request
    selectors. Token syntax does not establish service identity or role scope.
    The in-memory latch is not durable replay protection. No runtime uses this
    primitive yet; fake approval/receipt protocols cannot authorize it.
    """

    __slots__ = ("_host", "_lock", "_request_sha256", "_token", "_used")

    def __init__(self, *, hostname: str, token: str, request_sha256: str):
        _require(type(hostname) is str and len(hostname) <= 253 and _HOST.fullmatch(hostname))
        _require(type(token) is str and 1 <= len(token) <= 8192 and _TOKEN.fullmatch(token))
        _require(type(request_sha256) is str and _DIGEST.fullmatch(request_sha256))
        self._host = hostname
        self._token = token
        self._request_sha256 = request_sha256
        self._used = False
        self._lock = threading.Lock()

    def exchange(self, body: bytes, *, timeout: float) -> bytes:
        """Return bounded raw JSON bytes; clinical/provider validation is separate.

        Never follows redirects, retries, refreshes credentials, polls, cancels
        or returns HTTP error bodies. Timeout/failure does not mean remote work
        stopped, so custody must retain uncertain allowance. Hard wall-clock
        supervision and durable request/response association remain external.
        """
        try:
            with self._lock:
                _require(not self._used)
                self._used = True
                token, self._token = self._token, None
            _require(type(body) is bytes and 0 < len(body) <= MAX_REQUEST_BYTES)
            _require(hashlib.sha256(body).hexdigest() == self._request_sha256)
            _require(
                type(timeout) in (int, float) and math.isfinite(timeout)
                and 0 < timeout <= MAX_SOCKET_SECONDS,
            )
            end = time.monotonic() + timeout

            def remaining():
                value = end - time.monotonic()
                _require(value > 0)
                return value

            # Direct HTTPSConnection does not consult HTTP(S)_PROXY, .netrc,
            # Snowflake CLI profiles or SDK retry/session settings. The future
            # worker must also supply a clean environment and reviewed CA store.
            context = _tls_context()
            _require(context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED)
            with closing(HTTPSConnection(
                self._host, port=443, timeout=remaining(), context=context,
            )) as connection:
                connection.set_debuglevel(0)
                connection.connect()
                connection.sock.settimeout(remaining())
                connection.request("POST", ENDPOINT, body=body, headers={
                    "Authorization": "Bearer " + token,
                    "X-Snowflake-Authorization-Token-Type": "PROGRAMMATIC_ACCESS_TOKEN",
                    "Content-Type": "application/json", "Accept": "application/json",
                    "Accept-Encoding": "identity", "Connection": "close",
                })
                connection.sock.settimeout(remaining())
                sock = connection.sock
                response = connection.getresponse()
                with closing(response):
                    _require(response.status == 200)
                    length = _response_length(response)
                    chunks, size = [], 0
                    while length is None or size < length:
                        sock.settimeout(remaining())
                        chunk = response.read1(min(8192, MAX_RESPONSE_BYTES + 1 - size))
                        if not chunk:
                            break
                        size += len(chunk)
                        _require(size <= MAX_RESPONSE_BYTES)
                        chunks.append(chunk)
                    remaining()
                    _require(size > 0 and (length is None or size == length))
                    return b"".join(chunks)
        except Exception:
            # Never propagate HTTP messages, token, clinical bytes, URLs, server
            # error bodies or library diagnostics. No network attempt is retried.
            raise ValueError(ERROR) from None
