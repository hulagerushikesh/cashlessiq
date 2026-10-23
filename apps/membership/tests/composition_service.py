"""OPT-IN TEST IMAGE ONLY: worker/broker membership over the restricted TLS DB.

No OIDC identity-resolution API, in-memory membership fallback, automatic
schema/grant changes or normal service activation. The launcher owns deadlines,
exact mounts/networks and process exit; READY is only a test diagnostic.
"""

import json
import signal
from contextlib import ExitStack
from pathlib import Path
from threading import Event, Thread

from ciq_api.source_alpha import SOURCE_TENANTS
from ciq_api.worker_authority import WorkerDenied
from ciq_api.worker_membership import LoopbackMembershipServer, PrivateMembershipServer
from ciq_api.worker_membership_store import RestrictedMembershipStore
from ciq_api.worker_transport import PrivateEndpoint, tls_context

TENANTS = {
    audience: tenant.tenant_id
    for index, tenant in enumerate(SOURCE_TENANTS)
    for audience in (f"reader:{index}:nonclinical", f"reader:{index}:medical", f"validator:{index}")
}


def check_peers(peers):
    if (
        type(peers) is not dict
        or len(peers) != 6
        or set(peers.values()) != set(TENANTS)
        or any(
            type(pin) is not str or len(pin) != 64 or any(c not in "0123456789abcdef" for c in pin)
            for pin in peers
        )
    ):
        raise ValueError("Invalid disposable membership peers")


def configuration(raw):
    if type(raw) is not dict or set(raw) != {"listen", "peers"}:
        raise ValueError("Invalid disposable membership configuration")
    check_peers(raw["peers"])
    listen = raw["listen"]
    if type(listen) is not list or len(listen) != 6 or len(set(listen)) != 6:
        raise ValueError("Invalid disposable membership listeners")
    for address in listen:
        PrivateEndpoint(address, 8443)


def build_server(*, context, peers, lookup, tenants=None, endpoint=None):
    """Same six certificate-derived tenant bindings in TLS tests and test image."""
    check_peers(peers)
    if tenants is not None and tenants != TENANTS:
        raise ValueError("Invalid disposable membership tenants")
    options = dict(context=context, peers=peers, tenants=TENANTS, lookup=lookup)
    if endpoint is None:
        return LoopbackMembershipServer(**options)
    return PrivateMembershipServer(endpoint=endpoint, **options)


def build_broker_server(index, *, context, broker_pin, lookup, endpoint=None):
    """Separate broker edge: one listener fixes one tenant, never a wire field.

    This does not add the broker to the six-worker peer map. The acceptance
    launcher must give each endpoint its own exact broker-membership network.
    """
    if type(index) is not int or index not in (0, 1):
        raise ValueError("Invalid disposable broker tenant index")
    if (
        type(broker_pin) is not str
        or len(broker_pin) != 64
        or any(c not in "0123456789abcdef" for c in broker_pin)
    ):
        raise ValueError("Invalid disposable broker pin")
    options = dict(
        context=context,
        peers={broker_pin: "broker"},
        tenants={"broker": SOURCE_TENANTS[index].tenant_id},
        lookup=lookup,
    )
    if endpoint is None:
        return LoopbackMembershipServer(**options)
    return PrivateMembershipServer(endpoint=endpoint, **options)


def broker_configuration(raw, workers):
    if type(raw) is not dict or set(raw) != {"listen", "pin"}:
        raise ValueError("Invalid disposable broker membership configuration")
    listen = raw["listen"]
    pin = raw["pin"]
    if (
        type(listen) is not list
        or len(listen) != 2
        or len(set(listen)) != 2
        or set(listen) & set(workers["listen"])
        or type(pin) is not str
        or len(pin) != 64
        or any(c not in "0123456789abcdef" for c in pin)
        or pin in workers["peers"]
    ):
        raise ValueError("Invalid disposable broker membership configuration")
    for address in listen:
        PrivateEndpoint(address, 8443)


def serve(root, raw, *, factory_builder, stopped, broker=None):
    """All binds before serving; always close factory and owned listeners.

    Factory builder is injected only for tests. The command-line path pins the
    existing verified-TLS factory; it cannot choose plaintext or memory storage.
    """
    configuration(raw)  # Invalid configuration cannot open credentials or DB.
    if broker is not None:
        broker_configuration(broker, raw)
    with ExitStack() as stack:
        if stopped.is_set():
            raise WorkerDenied("Worker access denied")
        factory = factory_builder()
        stack.callback(factory.close)
        store = RestrictedMembershipStore(factory.connect, schema="ops")
        listeners = []
        for address in raw["listen"]:
            if stopped.is_set():
                raise WorkerDenied("Worker access denied")
            context = tls_context(
                server=True,
                ca=root / "ca.pem",
                certificate=root / "identity.pem",
                private_key=root / "identity.key",
            )
            listener = build_server(
                endpoint=PrivateEndpoint(address, 8443),
                context=context,
                peers=raw["peers"],
                lookup=store.lookup,
            )
            stack.callback(listener.server_close)
            listeners.append(listener)
        for index, address in enumerate(broker["listen"] if broker is not None else ()):
            if stopped.is_set():
                raise WorkerDenied("Worker access denied")
            listener = build_broker_server(
                index,
                endpoint=PrivateEndpoint(address, 8443),
                context=tls_context(
                    server=True,
                    ca=root / "ca.pem",
                    certificate=root / "identity.pem",
                    private_key=root / "identity.key",
                ),
                broker_pin=broker["pin"],
                lookup=store.lookup,
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
    from ciq_membership_runtime.db_probe import fixed_factory

    root = Path("/run/ciq")
    raw = json.loads((root / "config.json").read_text())
    if type(raw) is not dict or set(raw) != {"listen", "peers", "broker"}:
        raise ValueError("Invalid disposable eight-edge membership configuration")
    workers = {key: raw[key] for key in ("listen", "peers")}
    configuration(workers)
    broker_configuration(raw["broker"], workers)  # None cannot select worker-only CLI startup.
    stopped = Event()
    for name in (signal.SIGTERM, signal.SIGINT):
        signal.signal(name, lambda *_: stopped.set())
    serve(root, workers, broker=raw["broker"], factory_builder=fixed_factory, stopped=stopped)


if __name__ == "__main__":
    main()
