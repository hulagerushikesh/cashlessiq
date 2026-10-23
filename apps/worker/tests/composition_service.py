"""OPT-IN TEST IMAGE ONLY: six separately runnable canonical worker handlers.

Fictional frozen health and synthetic source only. No broker signer, application
DB, Snowflake, automatic state provisioning or production entry point. This is
not a supervisor, readiness receipt, hard deadline or operational health source.
"""

import json
import signal
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from threading import Event, Thread

from ciq_api.source_alpha import SOURCE_TENANTS
from ciq_api.source_models import SourceCase
from ciq_api.source_scopes import source_alpha_scopes
from ciq_api.validation_worker import OfflineValidationWorker, ValidationInputs
from ciq_api.worker_authority import WorkerDenied
from ciq_api.worker_delegation import OfflineDelegatedValidator, TransportPeer
from ciq_api.worker_guard_authority import GuardedAuthority, GuardedReadRelay
from ciq_api.worker_guard_transport import GuardedPrivateSummaryServer
from ciq_api.worker_membership import PrivateMembershipClient
from ciq_api.worker_transport import PrivateEndpoint, PrivateSummaryClient, tls_context
from cryptography.hazmat.primitives.serialization import load_pem_public_key

# Closed configuration map: never choose a tenant/audience from a request.
BINDINGS = {
    "reader-0-nonclinical": (0, "reader:0:nonclinical", "nonclinical"),
    "reader-0-clinical": (0, "reader:0:medical", "medical"),
    "reader-1-nonclinical": (1, "reader:1:nonclinical", "nonclinical"),
    "reader-1-clinical": (1, "reader:1:medical", "medical"),
    "validator-0": (0, "validator:0", None),
    "validator-1": (1, "validator:1", None),
}


@dataclass(frozen=True)
class Handler:
    callback: object
    operation: str
    peer_audiences: frozenset[str]


def binding(role):
    if type(role) is not str or role not in BINDINGS:
        raise ValueError("Unknown disposable worker role")
    return BINDINGS[role]


def build_handler(
    role, *, public_key, generation, guard, evidence, membership, invoke=None, read_inputs=None
):
    """Same assembly in shared TLS tests and the separate-service test image.

    Readers receive only an invocation callback; validators receive only their
    tenant's synthetic input callback. Construction performs no state repair.
    """
    index, audience, disclosure = binding(role)
    if (disclosure is not None and (not callable(invoke) or read_inputs is not None)) or (
        disclosure is None and (not callable(read_inputs) or invoke is not None)
    ):
        raise ValueError("Invalid disposable worker dependencies")
    readers = {
        f"reader:{index}:nonclinical": "nonclinical",
        f"reader:{index}:medical": "medical",
    }
    authority = GuardedAuthority(
        public_key=public_key,
        generation=generation,
        tenant_id=SOURCE_TENANTS[index].tenant_id,
        scopes=source_alpha_scopes(),
        audience=audience,
        membership=membership,
        guard=guard,
        evidence=evidence,
        **({"disclosure": disclosure} if disclosure else {"readers": readers}),
    )
    if disclosure:
        relay = GuardedReadRelay(
            authority=authority, validator_audience=f"validator:{index}", invoke=invoke
        )

        def callback(token, *, peer):
            if type(peer) is not TransportPeer or peer.audience != "broker":
                raise WorkerDenied("Worker access denied")
            return relay.summary(token)

        return Handler(callback, "read_detail", frozenset({"broker"}))
    worker = OfflineValidationWorker(
        authority=authority,
        scope=source_alpha_scopes().get(SOURCE_TENANTS[index].tenant_id),
        read_inputs=read_inputs,
    )
    return Handler(
        OfflineDelegatedValidator(authority, worker).validate,
        "validate_summary",
        frozenset(readers),
    )


def configuration(raw):
    """Reject extra authority/secret/source settings before opening any listener."""
    if type(raw) is not dict or "role" not in raw:
        raise ValueError("Invalid disposable service configuration")
    index, _, disclosure = binding(raw["role"])
    fields = {"role", "listen", "peers", "membership"}
    if disclosure:
        fields.add("validator")
    if set(raw) != fields:
        raise ValueError("Invalid disposable service configuration")
    listen = raw["listen"]
    if type(listen) is not list or not 1 <= len(listen) <= 3 or len(set(listen)) != len(listen):
        raise ValueError("Invalid disposable listeners")
    for address in listen:
        PrivateEndpoint(address, 8443)
    peers = raw["peers"]
    expected = (
        {"broker"} if disclosure else {f"reader:{index}:nonclinical", f"reader:{index}:medical"}
    )
    if type(peers) is not dict or len(peers) != len(expected) or set(peers.values()) != expected:
        raise ValueError("Invalid disposable service peers")
    for pin in peers:
        _pin(pin)
    for name in ("membership", "validator") if disclosure else ("membership",):
        target = raw[name]
        if type(target) is not dict or set(target) != {"address", "pin"}:
            raise ValueError("Invalid disposable target")
        PrivateEndpoint(target["address"], 8443)
        _pin(target["pin"])
    return index, disclosure


def _pin(value):
    if (
        type(value) is not str
        or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
    ):
        raise ValueError("Invalid disposable pin")


def prepare(root, raw, *, guard, evidence, generation):
    """Load only public assertion verification and this service's test material."""
    index, disclosure = configuration(raw)

    def context(server=False):
        return tls_context(
            server=server,
            ca=root / "ca.pem",
            certificate=root / "identity.pem",
            private_key=root / "identity.key",
        )

    def target(name, cls, **options):
        endpoint = raw[name]
        return cls(
            endpoint=PrivateEndpoint(endpoint["address"], 8443),
            context=context(),
            server_pin=endpoint["pin"],
            **options,
        )

    member = target(
        "membership",
        PrivateMembershipClient,
        tenant_id=SOURCE_TENANTS[index].tenant_id,
        server_audience="membership:0",
    )
    dependencies = {}
    if disclosure:
        validator = target(
            "validator",
            PrivateSummaryClient,
            server_audience=f"validator:{index}",
            operation="validate_summary",
        )
        dependencies["invoke"] = validator.summary
    else:
        # Read on each request so the test launcher can inject source outage.
        # A reader never opens or needs this file. No cross-tenant input fallback.
        def read(request_id):
            rows = json.loads((root / "source.json").read_text())
            row = rows[request_id]
            case = SourceCase.model_validate_json(json.dumps(row["case"]))
            if case.tpa_id != SOURCE_TENANTS[index].tpa_id or case.request_id != request_id:
                raise WorkerDenied("Worker access denied")
            return ValidationInputs(case, row["decisions"], row["evidence"])

        dependencies["read_inputs"] = read
    handler = build_handler(
        raw["role"],
        public_key=load_pem_public_key((root / "verify.pem").read_bytes()),
        generation=generation,
        guard=guard,
        evidence=evidence,
        membership=member.lookup,
        **dependencies,
    )
    return handler, context


def serve(root, raw, *, guard, evidence, generation, stopped):
    """All binds succeed before READY; partial bind failures close earlier sockets.

    READY is only a test diagnostic, not the supervisor's bound readiness receipt.
    The external launcher still must impose process deadlines and confirm exit.
    """
    handler, context = prepare(root, raw, guard=guard, evidence=evidence, generation=generation)
    with ExitStack() as stack:
        listeners = []
        for address in raw["listen"]:
            if stopped.is_set():
                raise WorkerDenied("Worker access denied")
            listener = GuardedPrivateSummaryServer(
                endpoint=PrivateEndpoint(address, 8443),
                context=context(True),
                peers=raw["peers"],
                validate=handler.callback,
                operation=handler.operation,
                guard=guard,
                evidence=evidence,
            )
            stack.callback(listener.server_close)
            listeners.append(listener)
        for listener in listeners:
            if stopped.is_set():
                raise WorkerDenied("Worker access denied")
            thread = Thread(target=listener.serve_forever, daemon=True)
            thread.start()
            stack.callback(thread.join, 4)
            stack.callback(listener.shutdown)
        if stopped.is_set():
            raise WorkerDenied("Worker access denied")
        print("READY", flush=True)
        stopped.wait()


def main():
    # Only the explicit composition-test image supplies this package helper.
    from ciq_worker_runtime.guard_mtls_fixture import GENERATION, load

    root = Path("/run/ciq")
    raw = json.loads((root / "config.json").read_text())
    configuration(raw)  # No state/key reads on invalid configuration.
    guard, evidence = load()  # Existing own store only; no initialization.
    stopped = Event()
    for name in (signal.SIGTERM, signal.SIGINT):
        signal.signal(name, lambda *_: stopped.set())
    serve(root, raw, guard=guard, evidence=evidence, generation=GENERATION, stopped=stopped)


if __name__ == "__main__":
    main()
