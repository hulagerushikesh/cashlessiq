"""OPT-IN TEST IMAGE ONLY: private broker ingress with disposable local identity.

No normal API route, public authentication, DB credential or state initializer.
The external controller owns readiness, operation deadlines and process exit.
"""

import json
import signal
from contextlib import ExitStack
from pathlib import Path
from threading import Event, Thread
from types import SimpleNamespace
from uuid import UUID, uuid4

from broker_composition_fixture import SyntheticBrokerMemberships
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from pydantic import BaseModel, ConfigDict, SecretStr

from ciq_api.auth import JWTVerifier
from ciq_api.source_alpha import SOURCE_TENANTS
from ciq_api.source_scopes import source_alpha_scopes
from ciq_api.validation_worker import SummaryObservation
from ciq_api.worker_authority import WorkerDenied
from ciq_api.worker_broker import OfflineSummaryRoute
from ciq_api.worker_guard_broker import GuardedSummaryBroker
from ciq_api.worker_guard_transport import GuardedSummaryServer
from ciq_api.worker_membership import PrivateMembershipClient
from ciq_api.worker_transport import (
    LoopbackSummaryClient,
    PrivateEndpoint,
    PrivateSummaryClient,
    tls_context,
)

BROKER_PATH = "/v1/broker-summary"
READERS = {
    f"reader:{index}:{disclosure}": (tenant.tenant_id, disclosure, f"validator:{index}")
    for index, tenant in enumerate(SOURCE_TENANTS)
    for disclosure in ("nonclinical", "medical")
}


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    token: str
    request_id: str
    nonce: str


class Response(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    nonce: str
    summary: SummaryObservation


def check_request(message):
    request = Request.model_validate(message)
    if (
        not 0 < len(request.token) <= 4096
        or not 0 < len(request.request_id) <= 120
        or str(UUID(request.nonce)) != request.nonce
    ):
        raise WorkerDenied("Worker access denied")
    return request


class BrokerServer(GuardedSummaryServer):
    """Reuse bounded framing/TLS; only the controller can invoke the broker."""

    def __init__(self, *, summary, peers, **configuration):
        if type(peers) is not dict or len(peers) != 1 or set(peers.values()) != {"controller"}:
            raise ValueError("Invalid disposable broker peer")
        self._summary = summary
        super().__init__(peers=peers, validate=None, **configuration)
        self._path = BROKER_PATH

    def _dispatch(self, message, peer):
        if peer.audience != "controller":
            raise WorkerDenied("Worker access denied")
        request = check_request(message)
        result = SummaryObservation.model_validate(
            self._summary(request.token, request.request_id).model_dump()
        )
        if result.request_id != request.request_id:
            raise WorkerDenied("Worker access denied")
        return Response(nonce=request.nonce, summary=result).model_dump_json().encode()


class PrivateBrokerServer(BrokerServer):
    def __init__(self, *, endpoint, **configuration):
        if type(endpoint) is not PrivateEndpoint:
            raise ValueError("Invalid disposable broker endpoint")
        self._endpoint = endpoint
        super().__init__(**configuration)

    def _listen_address(self):
        return self._endpoint.address, self._endpoint.port


class BrokerClient(LoopbackSummaryClient):
    """Exact trusted broker peer; response nonce and case must match this call."""

    def __init__(self, **configuration):
        super().__init__(**configuration)
        self._path = BROKER_PATH

    def summary(self, token, request_id):
        try:
            request = check_request(dict(token=token, request_id=request_id, nonce=str(uuid4())))
            response = Response.model_validate(self._exchange(request.model_dump()))
            if response.nonce != request.nonce or response.summary.request_id != request_id:
                raise WorkerDenied("Worker access denied")
            return response.summary
        except Exception:
            raise WorkerDenied("Worker access denied") from None


class PrivateBrokerClient(BrokerClient):
    def __init__(self, *, endpoint, **configuration):
        if type(endpoint) is not PrivateEndpoint:
            raise ValueError("Invalid disposable broker endpoint")
        super().__init__(port=endpoint.port, **configuration)
        self._host = endpoint.address


def _pin(value):
    if (
        type(value) is not str
        or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
    ):
        raise ValueError("Invalid disposable broker pin")


def configuration(raw):
    if type(raw) is not dict or set(raw) != {"listen", "controller_pin", "readers", "membership"}:
        raise ValueError("Invalid disposable broker configuration")
    PrivateEndpoint(raw["listen"], 8443)
    _pin(raw["controller_pin"])
    if (
        type(raw["readers"]) is not dict
        or set(raw["readers"]) != set(READERS)
        or type(raw["membership"]) is not list
        or len(raw["membership"]) != 2
    ):
        raise ValueError("Invalid disposable broker routes")
    addresses = [raw["listen"]]
    reader_pins = []
    for name, target in [*raw["readers"].items(), *enumerate(raw["membership"])]:
        if type(target) is not dict or set(target) != {"address", "pin"}:
            raise ValueError("Invalid disposable broker target")
        PrivateEndpoint(target["address"], 8443)
        _pin(target["pin"])
        addresses.append(target["address"])
        if type(name) is str:
            reader_pins.append(target["pin"])
    if (
        len(set(addresses)) != len(addresses)
        or len(set(reader_pins)) != 4
        or raw["controller_pin"] in reader_pins
        or raw["controller_pin"] in {item["pin"] for item in raw["membership"]}
        or set(reader_pins) & {item["pin"] for item in raw["membership"]}
    ):
        raise ValueError("Invalid disposable broker destinations")


def build_handler(*, settings, lookups, routes, private_key, guard, evidence, generation):
    expected = {
        (tenant.tenant_id, disclosure)
        for tenant in SOURCE_TENANTS
        for disclosure in ("nonclinical", "medical")
    }
    if set(routes) != expected or any(
        (route.audience, route.validator_audience)
        != (f"reader:{index}:{disclosure}", f"validator:{index}")
        for index, tenant in enumerate(SOURCE_TENANTS)
        for disclosure in ("nonclinical", "medical")
        for route in [routes[tenant.tenant_id, disclosure]]
    ):
        raise ValueError("Invalid disposable broker handler routes")
    return GuardedSummaryBroker(
        verifier=JWTVerifier(settings),
        memberships=SyntheticBrokerMemberships(lookups),
        scopes=source_alpha_scopes(),
        routes=routes,
        private_key=private_key,
        generation=generation,
        guard=guard,
        evidence=evidence,
    )


def prepare(root, raw, *, guard, evidence, generation):
    configuration(raw)  # Invalid trusted config cannot read keys/state or bind.

    def context(server=False):
        return tls_context(
            server=server,
            ca=root / "ca.pem",
            certificate=root / "identity.pem",
            private_key=root / "identity.key",
        )

    secret = json.loads((root / "local-auth.json").read_text())
    if (
        type(secret) is not dict
        or set(secret) != {"secret"}
        or type(secret["secret"]) is not str
        or len(secret["secret"]) < 32
    ):
        raise ValueError("Invalid disposable local identity")
    # Explicit verifier-only settings, not BaseSettings/environment/normal API DB.
    settings = SimpleNamespace(
        auth_mode="local",
        oidc_audience="cashlessiq-api",
        local_auth_secret=SecretStr(secret["secret"]),
    )
    key = load_pem_private_key((root / "signer.pem").read_bytes(), password=None)
    if not isinstance(key, RSAPrivateKey) or key.key_size < 2048:
        raise ValueError("Invalid disposable assertion key")
    routes, lookups = {}, {}
    for audience, (tenant, disclosure, validator) in READERS.items():
        target = raw["readers"][audience]
        client = PrivateSummaryClient(
            endpoint=PrivateEndpoint(target["address"], 8443),
            context=context(),
            server_pin=target["pin"],
            server_audience=audience,
            operation="read_detail",
        )
        routes[tenant, disclosure] = OfflineSummaryRoute(audience, client.summary, validator)
    for tenant, target in zip(SOURCE_TENANTS, raw["membership"], strict=True):
        client = PrivateMembershipClient(
            endpoint=PrivateEndpoint(target["address"], 8443),
            context=context(),
            server_pin=target["pin"],
            server_audience="membership:0",
            tenant_id=tenant.tenant_id,
        )
        lookups[tenant.tenant_id] = client.lookup
    return build_handler(
        settings=settings,
        lookups=lookups,
        routes=routes,
        private_key=key,
        guard=guard,
        evidence=evidence,
        generation=generation,
    ), context


def serve(root, raw, *, guard, evidence, generation, stopped):
    if stopped.is_set():
        raise WorkerDenied("Worker access denied")
    broker, context = prepare(root, raw, guard=guard, evidence=evidence, generation=generation)
    with ExitStack() as stack:
        if stopped.is_set():
            raise WorkerDenied("Worker access denied")
        server = PrivateBrokerServer(
            endpoint=PrivateEndpoint(raw["listen"], 8443),
            context=context(True),
            peers={raw["controller_pin"]: "controller"},
            summary=broker.summary,
            guard=guard,
            evidence=evidence,
        )
        stack.callback(server.server_close)
        if stopped.is_set():
            raise WorkerDenied("Worker access denied")
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        stack.callback(thread.join, 4)
        stack.callback(server.shutdown)
        if stopped.is_set():
            raise WorkerDenied("Worker access denied")
        print("READY", flush=True)
        stopped.wait()


def main():
    from guard_mtls_fixture import GENERATION, load

    root = Path("/run/ciq")
    raw = json.loads((root / "config.json").read_text())
    configuration(raw)
    guard, evidence = load()  # Existing own disposable state, never repair/init.
    stopped = Event()
    for name in (signal.SIGTERM, signal.SIGINT):
        signal.signal(name, lambda *_: stopped.set())
    serve(root, raw, guard=guard, evidence=evidence, generation=GENERATION, stopped=stopped)


if __name__ == "__main__":
    main()
