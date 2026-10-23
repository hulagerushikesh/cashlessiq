"""Real TLS broker membership edges; disposable registry/store, not live OIDC/DB."""

import json
import sys
from contextlib import ExitStack, contextmanager
from dataclasses import replace
from http.client import HTTPSConnection
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from broker_composition_fixture import SyntheticBrokerMemberships
from membership_composition_fixture import service as target
from test_membership_composition_service import config
from test_worker_membership import service
from test_worker_transport import context
from test_worker_transport import pki as pki

from ciq_api.auth import LOCAL_ISSUER, Principal
from ciq_api.source_alpha import SOURCE_TENANTS
from ciq_api.worker_authority import Membership, WorkerDenied
from ciq_api.worker_membership import MEMBERSHIP_PATH, LoopbackMembershipClient


@contextmanager
def edges(pki):
    rows = {
        (tenant.tenant_id, str(profile.user_id)): Membership(tenant.tenant_id, profile.role)
        for tenant in SOURCE_TENANTS
        for profile in tenant.profiles
    }
    lookup = Mock(side_effect=lambda user, tenant: rows.get((tenant, user)))
    lookups, ports = {}, {}
    with ExitStack() as stack:
        for index, tenant in enumerate(SOURCE_TENANTS):

            def factory(*, context, lookup, index=index, **_):
                return target.build_broker_server(
                    index, context=context, broker_pin=pki[1]["broker"][2], lookup=lookup
                )

            ports[index] = stack.enter_context(service(pki, lookup, server_factory=factory))
            lookups[tenant.tenant_id] = remote(pki, ports[index], index).lookup
        yield SyntheticBrokerMemberships(lookups), rows, lookup, ports


def remote(pki, port, index, name="broker"):
    return LoopbackMembershipClient(
        tenant_id=SOURCE_TENANTS[index].tenant_id,
        context=context(pki, name),
        port=port,
        server_pin=pki[1]["membership"][2],
        server_audience="membership:0",
    )


@pytest.mark.parametrize("index", [0, 1])
@pytest.mark.parametrize("role", ["processor", "medical_officer", "auditor"])
def test_fixed_identity_fresh_remote_role_and_revocation(pki, index, role):
    tenant = SOURCE_TENANTS[index]
    profile = next(p for p in tenant.profiles if p.role == role)
    principal = Principal(LOCAL_ISSUER, profile.subject, tenant.tenant_id)
    with edges(pki) as (resolver, rows, lookup, _):
        result = resolver.resolve(principal)
        assert result.user_id == profile.user_id
        assert result.membership == Membership(tenant.tenant_id, role)
        rows[tenant.tenant_id, str(profile.user_id)] = Membership(tenant.tenant_id, "auditor")
        assert resolver.resolve(principal).membership.role == "auditor"
        del rows[tenant.tenant_id, str(profile.user_id)]
        assert resolver.resolve(principal) is None
        assert lookup.call_count == 3
        assert all(
            c.args == (str(profile.user_id), tenant.tenant_id) for c in lookup.call_args_list
        )


@pytest.mark.parametrize("fault", ["issuer", "subject", "tenant", "object", "internal-id"])
def test_unknown_principals_never_make_network_lookup(fault):
    tenant = SOURCE_TENANTS[0]
    profile = tenant.profiles[0]
    principal = Principal(LOCAL_ISSUER, profile.subject, tenant.tenant_id)
    if fault == "object":
        principal = SimpleNamespace(**principal.__dict__)
    else:
        principal = replace(
            principal,
            **{
                "issuer": {"issuer": "urn:other"},
                "subject": {"subject": "unknown"},
                "tenant": {"tenant_id": uuid4()},
                "internal-id": {"subject": str(profile.user_id)},
            }[fault],
        )
    lookups = {t.tenant_id: Mock() for t in SOURCE_TENANTS}
    assert SyntheticBrokerMemberships(lookups).resolve(principal) is None
    for lookup in lookups.values():
        lookup.assert_not_called()


@pytest.mark.parametrize("fault", ["exception", "tenant", "role", "object"])
def test_lookup_failure_or_invalid_response_is_denial_not_missing(fault):
    tenant = SOURCE_TENANTS[0]
    value = Membership(tenant.tenant_id, "processor")
    lookup = Mock(return_value=value)
    if fault == "exception":
        lookup.side_effect = RuntimeError("private password and detail")
    elif fault == "tenant":
        lookup.return_value = Membership(SOURCE_TENANTS[1].tenant_id, "processor")
    elif fault == "role":
        lookup.return_value = Membership(tenant.tenant_id, "admin")
    else:
        lookup.return_value = SimpleNamespace(**value.__dict__)
    resolver = SyntheticBrokerMemberships({t.tenant_id: lookup for t in SOURCE_TENANTS})
    with pytest.raises(WorkerDenied, match=r"^Worker access denied$"):
        resolver.resolve(Principal(LOCAL_ISSUER, tenant.profiles[0].subject, tenant.tenant_id))


@pytest.mark.parametrize("fault", ["missing", "extra", "not-callable"])
def test_constructor_requires_exact_two_routes(fault):
    lookups = {t.tenant_id: Mock() for t in SOURCE_TENANTS}
    if fault == "missing":
        lookups.pop(SOURCE_TENANTS[0].tenant_id)
    elif fault == "extra":
        lookups[uuid4()] = Mock()
    else:
        lookups[SOURCE_TENANTS[0].tenant_id] = None
    with pytest.raises(ValueError):
        SyntheticBrokerMemberships(lookups)


def test_broker_cannot_enter_worker_membership_allowlist(pki):
    lookup = Mock()
    peers = {f"{index:064x}": audience for index, audience in enumerate(target.TENANTS, start=1)}
    with (
        service(
            pki, lookup, peers=peers, tenants=target.TENANTS, server_factory=target.build_server
        ) as port,
        pytest.raises(WorkerDenied),
    ):
        remote(pki, port, 0).lookup(str(SOURCE_TENANTS[0].profiles[0].user_id))
    lookup.assert_not_called()


@pytest.mark.parametrize("index", [0, 1])
@pytest.mark.parametrize("name", ["reader", "validator", "foreign"])
def test_worker_and_foreign_certs_cannot_enter_broker_edges(pki, index, name):
    with edges(pki) as (_, _, lookup, ports), pytest.raises(WorkerDenied):
        remote(pki, ports[index], index, name).lookup(
            str(SOURCE_TENANTS[index].profiles[0].user_id)
        )
    lookup.assert_not_called()


@pytest.mark.parametrize("index", [0, 1])
def test_broker_endpoint_cannot_select_other_tenant(pki, index):
    with edges(pki) as (_, _, lookup, ports):
        foreign = SOURCE_TENANTS[1 - index]
        # This reaches only the endpoint's fixed tenant, not the supplied client tenant.
        with pytest.raises(WorkerDenied):
            remote(pki, ports[index], 1 - index).lookup(str(foreign.profiles[0].user_id))
        assert lookup.call_args.args == (
            str(foreign.profiles[0].user_id),
            SOURCE_TENANTS[index].tenant_id,
        )


@pytest.mark.parametrize("index", [0, 1])
@pytest.mark.parametrize("field", ["tenant", "role", "issuer"])
def test_wire_cannot_supply_identity_or_authority_fields(pki, index, field):
    with edges(pki) as (_, _, lookup, ports):
        connection = HTTPSConnection(
            "127.0.0.1", ports[index], context=context(pki, "broker"), timeout=3
        )
        try:
            connection.request(
                "POST",
                MEMBERSHIP_PATH,
                json.dumps({"subject": str(uuid4()), "nonce": str(uuid4()), field: "injected"}),
                headers={"Content-Type": "application/json"},
            )
            response = connection.getresponse()
            assert response.status == 403
            assert response.read() == b'{"error":"Worker access denied"}'
        finally:
            connection.close()
    lookup.assert_not_called()


@pytest.mark.parametrize("fault", [None, 0, 1])
def test_eight_endpoint_lifecycle_owns_partial_broker_bind(tmp_path, monkeypatch, capsys, fault):
    factory = Mock()
    monkeypatch.setattr(target, "RestrictedMembershipStore", Mock())
    monkeypatch.setattr(target, "tls_context", Mock())
    owned = []

    def worker(**_):
        listener = Mock()
        owned.append(listener)
        return listener

    def broker(index, **_):
        if index == fault:
            raise OSError("disposable broker bind failure")
        return worker()

    monkeypatch.setattr(target, "build_server", worker)
    monkeypatch.setattr(target, "build_broker_server", broker)
    monkeypatch.setattr(target, "Thread", Mock())
    stopped = Mock(is_set=Mock(return_value=False))

    def run():
        target.serve(
            tmp_path,
            config(),
            factory_builder=lambda: factory,
            stopped=stopped,
            broker={"listen": ["192.168.10.2", "192.168.11.2"], "pin": "f" * 64},
        )

    if fault is None:
        run()
    else:
        with pytest.raises(OSError):
            run()
    assert len(owned) == (8 if fault is None else 6 + fault)
    for listener in owned:
        listener.server_close.assert_called_once_with()
        assert listener.shutdown.call_count == (1 if fault is None else 0)
    factory.close.assert_called_once_with()
    assert capsys.readouterr().out == ("READY\n" if fault is None else "")


@pytest.mark.parametrize(
    "fault", ["missing", "extra", "overlap", "duplicate", "pin", "worker-pin", "public"]
)
def test_bad_broker_config_refuses_before_credentials(tmp_path, fault):
    raw = {"listen": ["192.168.10.2", "192.168.11.2"], "pin": "f" * 64}
    if fault == "missing":
        raw.pop("pin")
    elif fault == "extra":
        raw["tenant"] = str(SOURCE_TENANTS[0].tenant_id)
    elif fault == "overlap":
        raw["listen"][0] = config()["listen"][0]
    elif fault == "duplicate":
        raw["listen"][1] = raw["listen"][0]
    elif fault == "pin":
        raw["pin"] = "invalid"
    elif fault == "worker-pin":
        raw["pin"] = next(iter(config()["peers"]))
    else:
        raw["listen"][0] = "0.0.0.0"
    factory = Mock()
    with pytest.raises(ValueError):
        target.serve(tmp_path, config(), broker=raw, factory_builder=factory, stopped=Event())
    factory.assert_not_called()
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("broker", [None, {}, {"listen": [], "pin": "f" * 64}])
def test_command_line_cannot_fall_back_to_worker_only(tmp_path, monkeypatch, broker):
    raw = {**config(), "broker": broker}
    (tmp_path / "config.json").write_text(json.dumps(raw))
    factory = Mock()
    monkeypatch.setitem(
        sys.modules, "ciq_membership_runtime.db_probe", SimpleNamespace(fixed_factory=factory)
    )
    monkeypatch.setattr(target, "Path", lambda _: tmp_path)
    with pytest.raises(ValueError):
        target.main()
    factory.assert_not_called()


@pytest.mark.parametrize("index", [-1, 2, True, "0"])
def test_broker_builder_rejects_noncanonical_indices_before_binding(index):
    with pytest.raises(ValueError):
        target.build_broker_server(index, context=None, broker_pin="f" * 64, lookup=Mock())
