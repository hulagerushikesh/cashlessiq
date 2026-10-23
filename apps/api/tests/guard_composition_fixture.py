"""Eight logical roles in one test process, not Docker/service isolation.

Canonical broker, four readers, two validators and membership share one test
world. Six worker listeners and membership use real loopback mTLS. Identity
uses signed local-test JWTs; membership storage/source/health are fictional.
No production startup, database, runtime credentials or operational acceptance.
"""

from contextlib import ExitStack, contextmanager
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

from test_source_cases import build_test_sources
from test_worker_guard_mtls import listening
from test_worker_membership import service
from test_worker_transport import context

from ciq_api.auth import LOCAL_ISSUER, JWTVerifier, issue_local_token
from ciq_api.source_alpha import SOURCE_TENANTS
from ciq_api.source_scopes import source_alpha_scopes
from ciq_api.validation_worker import OfflineValidationWorker, ValidationInputs
from ciq_api.worker_authority import Membership, WorkerDenied
from ciq_api.worker_broker import OfflineSummaryRoute, ResolvedWorkerIdentity
from ciq_api.worker_delegation import OfflineDelegatedValidator, TransportPeer
from ciq_api.worker_guard_authority import GuardedAuthority, GuardedReadRelay
from ciq_api.worker_guard_broker import GuardedSummaryBroker
from ciq_api.worker_membership import LoopbackMembershipClient
from ciq_api.worker_transport import LoopbackSummaryClient

# Fixed supervisor role -> TLS fixture name. Never derive a peer from a request.
TLS_NAMES = {
    "reader-0-nonclinical": "reader",
    "reader-0-clinical": "reader_medical",
    "reader-1-nonclinical": "reader1",
    "reader-1-clinical": "reader1_medical",
    "validator-0": "validator",
    "validator-1": "validator1",
}


@contextmanager
def compose(root, f, pki, settings, assertion_key, *, before_bind=None):
    """Explicit disposable fixture; construction cannot open the normal app DB."""
    scopes = source_alpha_scopes()
    guards, evidence, members, identities = {}, {}, {}, {}
    for role in f.SERVICE_BINDINGS:
        directory = root / role
        directory.mkdir()
        f.initialize(role, directory=directory)
        guards[role], evidence[role] = f.load(directory=directory)
    for tenant in SOURCE_TENANTS:
        for profile in tenant.profiles:
            members[tenant.tenant_id, str(profile.user_id)] = Membership(
                tenant.tenant_id, profile.role
            )
            identities[tenant.tenant_id, profile.subject] = profile.user_id

    def lookup(subject, tenant):
        return members.get((tenant, subject))

    lookup_spy = Mock(side_effect=lookup)

    def resolve(principal):
        if principal.issuer != LOCAL_ISSUER:
            return None
        user_id = identities.get((principal.tenant_id, principal.subject))
        member = lookup(str(user_id), principal.tenant_id)
        return ResolvedWorkerIdentity(user_id, member) if user_id and member else None

    _, _, _, records, details = build_test_sources()
    inputs = {
        case.request_id: ValidationInputs(
            case,
            deepcopy(details[case.request_id]["decision"]),
            deepcopy(details[case.request_id]["evidence"]),
        )
        for rows in records.values()
        for case in rows
    }
    reads = {
        tenant.tenant_id: Mock(side_effect=lambda request_id: deepcopy(inputs[request_id]))
        for tenant in SOURCE_TENANTS
    }
    captured, clients, ports, opened, closers = [], {}, {}, [], {}

    def summary_client(port, caller, target, audience, operation):
        return LoopbackSummaryClient(
            context=context(pki, caller),
            port=port,
            server_pin=pki[1][target][2],
            server_audience=audience,
            operation=operation,
        )

    def reader_callback(relay):
        def read(token, *, peer):
            if type(peer) is not TransportPeer or peer.audience != "broker":
                raise WorkerDenied("Worker access denied")
            return relay.summary(token)

        return read

    def route_invoke(role, client):
        def invoke(token):
            captured.append((role, token))
            return client.summary(token)

        return invoke

    with ExitStack() as stack:

        def own_listener(role, manager):
            # Each exact test listener can be closed by the model adapter;
            # the outer stack remains a final cleanup owner on partial failure.
            owned = stack.enter_context(ExitStack())
            port = owned.enter_context(manager)
            closers[role] = owned.close
            return port

        tenants = {
            audience: SOURCE_TENANTS[index].tenant_id
            for index, audience in (f.SERVICE_BINDINGS[role] for role in TLS_NAMES)
        }
        peers = {pki[1][name][2]: f.SERVICE_BINDINGS[role][1] for role, name in TLS_NAMES.items()}
        ports["membership"] = own_listener(
            "membership", service(pki, lookup_spy, tenants=tenants, peers=peers)
        )
        opened.append("membership")
        memberships = {
            role: LoopbackMembershipClient(
                tenant_id=SOURCE_TENANTS[f.SERVICE_BINDINGS[role][0]].tenant_id,
                context=context(pki, name),
                port=ports["membership"],
                server_pin=pki[1]["membership"][2],
                server_audience="membership:0",
            )
            for role, name in TLS_NAMES.items()
        }

        def authority(role, **configuration):
            index, audience = f.SERVICE_BINDINGS[role]
            return GuardedAuthority(
                public_key=assertion_key.public_key(),
                generation=f.GENERATION,
                tenant_id=SOURCE_TENANTS[index].tenant_id,
                scopes=scopes,
                audience=audience,
                membership=memberships[role].lookup,
                guard=guards[role],
                evidence=lambda: evidence[role](),
                **configuration,
            )

        def listen(role, callback, allowed_peers, operation):
            if before_bind:
                before_bind(role, guards, evidence)
            ports[role] = own_listener(
                role,
                listening(
                    pki,
                    TLS_NAMES[role],
                    guards[role],
                    lambda: evidence[role](),
                    callback,
                    allowed_peers,
                    operation,
                ),
            )
            opened.append(role)

        for index, tenant in enumerate(SOURCE_TENANTS):
            role = f"validator-{index}"
            readers = {
                f"reader:{index}:nonclinical": "nonclinical",
                f"reader:{index}:medical": "medical",
            }
            validator = authority(role, readers=readers)
            endpoint = OfflineDelegatedValidator(
                validator,
                OfflineValidationWorker(
                    authority=validator,
                    scope=scopes.get(tenant.tenant_id),
                    read_inputs=reads[tenant.tenant_id],
                ),
            )
            allowed = {
                pki[1][TLS_NAMES[reader]][2]: f.SERVICE_BINDINGS[reader][1]
                for reader in TLS_NAMES
                if reader.startswith("reader-") and f.SERVICE_BINDINGS[reader][0] == index
            }
            listen(role, endpoint.validate, allowed, "validate_summary")

        routes = {}
        for role, name in TLS_NAMES.items():
            if not role.startswith("reader-"):
                continue
            index, audience = f.SERVICE_BINDINGS[role]
            disclosure = "medical" if role.endswith("-clinical") else "nonclinical"
            validator_role = f"validator-{index}"
            validator_audience = f"validator:{index}"
            validator_client = summary_client(
                ports[validator_role],
                name,
                TLS_NAMES[validator_role],
                validator_audience,
                "validate_summary",
            )
            relay = GuardedReadRelay(
                authority=authority(role, disclosure=disclosure),
                validator_audience=validator_audience,
                invoke=validator_client.summary,
            )
            listen(role, reader_callback(relay), {pki[1]["broker"][2]: "broker"}, "read_detail")
            parent = summary_client(ports[role], "broker", name, audience, "read_detail")
            clients[role] = parent
            routes[SOURCE_TENANTS[index].tenant_id, disclosure] = OfflineSummaryRoute(
                audience,
                route_invoke(role, parent),
                validator_audience,
            )
        broker = GuardedSummaryBroker(
            verifier=JWTVerifier(settings),
            memberships=SimpleNamespace(resolve=resolve),
            scopes=scopes,
            routes=routes,
            private_key=assertion_key,
            generation=f.GENERATION,
            guard=guards["broker"],
            evidence=lambda: evidence["broker"](),
        )
        opened.append("broker")  # In-process issuer, not an HTTP listener.
        closers["broker"] = lambda: None
        yield SimpleNamespace(
            broker=broker,
            members=members,
            reads=reads,
            inputs=inputs,
            captured=captured,
            clients=clients,
            guards=guards,
            evidence=evidence,
            lookup=lookup_spy,
            ports=ports,
            opened=opened,
            memberships=memberships,
            close_role=lambda role: closers[role](),
            token=lambda index, role: issue_local_token(
                settings,
                next(p.subject for p in SOURCE_TENANTS[index].profiles if p.role == role),
                SOURCE_TENANTS[index].tenant_id,
            ),
        )
