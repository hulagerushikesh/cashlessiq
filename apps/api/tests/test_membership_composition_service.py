"""Six-worker membership test target: fixed scopes and owned lifecycle cleanup.

Actual shared TLS tests use the same server builder. Factory/lifecycle tests use
injected doubles; they do not establish Docker or restricted PostgreSQL acceptance.
"""

from threading import Event
from unittest.mock import Mock

import pytest
from membership_composition_fixture import service
from test_worker_transport import context
from test_worker_transport import pki as pki

from ciq_api.source_alpha import SOURCE_TENANTS
from ciq_api.worker_authority import WorkerDenied


def config():
    return dict(
        listen=[f"192.168.{i}.2" for i in range(1, 7)],
        peers={f"{i:064x}": audience for i, audience in enumerate(service.TENANTS, start=1)},
    )


def test_six_peers_map_to_two_exact_tenants(pki):
    raw = config()
    service.configuration(raw)
    assert len(service.TENANTS) == 6
    assert set(service.TENANTS.values()) == {tenant.tenant_id for tenant in SOURCE_TENANTS}
    for index, tenant in enumerate(SOURCE_TENANTS):
        assert service.TENANTS[f"reader:{index}:medical"] == tenant.tenant_id
        assert service.TENANTS[f"reader:{index}:nonclinical"] == tenant.tenant_id
        assert service.TENANTS[f"validator:{index}"] == tenant.tenant_id
    # Uses the canonical real TLS server; construction alone does no lookup.
    lookup = Mock()
    server = service.build_server(
        context=context(pki, "membership", server=True), peers=raw["peers"], lookup=lookup
    )
    try:
        assert server._tenants == service.TENANTS
        assert server._lookup is lookup
        lookup.assert_not_called()
    finally:
        server.server_close()


@pytest.mark.parametrize(
    "fault",
    [
        "missing-peer",
        "extra-peer",
        "broker",
        "foreign-tenant",
        "wrong-disclosure",
        "bad-pin",
        "extra-setting",
        "empty-listen",
        "few-listen",
        "extra-listen",
        "duplicate-listen",
        "public-listen",
        "caller-tenant",
        "memory-fallback",
    ],
)
def test_invalid_config_never_opens_factory_or_listener(tmp_path, monkeypatch, fault):
    raw = config()
    first = next(iter(raw["peers"]))
    if fault == "missing-peer":
        del raw["peers"][first]
    elif fault == "extra-peer":
        raw["peers"]["a" * 64] = "broker"
    elif fault == "broker":
        raw["peers"][first] = "broker"
    elif fault == "foreign-tenant":
        raw["peers"][first] = "reader:2:nonclinical"
    elif fault == "wrong-disclosure":
        raw["peers"][first] = "reader:0:clinical"
    elif fault == "bad-pin":
        raw["peers"]["invalid"] = raw["peers"].pop(first)
    elif fault == "extra-setting":
        raw["assertion_signer"] = "forbidden"
    elif fault == "empty-listen":
        raw["listen"] = []
    elif fault == "few-listen":
        raw["listen"].pop()
    elif fault == "extra-listen":
        raw["listen"].append("192.168.7.2")
    elif fault == "duplicate-listen":
        raw["listen"][1] = raw["listen"][0]
    elif fault == "public-listen":
        raw["listen"][0] = "0.0.0.0"
    elif fault == "caller-tenant":
        raw["tenant"] = str(SOURCE_TENANTS[0].tenant_id)
    else:
        raw["memory_fallback"] = True
    factory, listener = Mock(), Mock()
    monkeypatch.setattr(service, "build_server", listener)
    with pytest.raises(ValueError):
        service.serve(tmp_path, raw, factory_builder=factory, stopped=Event())
    factory.assert_not_called()
    listener.assert_not_called()
    assert not list(tmp_path.iterdir())


def test_wrong_tenant_map_cannot_override_certificate_scope(pki):
    raw = config()
    tenants = dict(service.TENANTS)
    tenants["reader:0:medical"] = SOURCE_TENANTS[1].tenant_id
    lookup = Mock()
    with pytest.raises(ValueError, match="tenants"):
        service.build_server(
            context=context(pki, "membership", server=True),
            peers=raw["peers"],
            lookup=lookup,
            tenants=tenants,
        )
    lookup.assert_not_called()


@pytest.mark.parametrize("fault", [None, "factory", "store", "tls", 0, 3, 5, "wait", "thread"])
def test_membership_lifecycle_closes_its_factory_and_owned_sockets(
    tmp_path, monkeypatch, capsys, fault
):
    factory = Mock()
    builder = Mock(return_value=factory)
    store = Mock()
    store_builder = Mock(return_value=store)
    monkeypatch.setattr(service, "RestrictedMembershipStore", store_builder)
    tls = Mock()
    monkeypatch.setattr(service, "tls_context", tls)
    if fault == "factory":
        builder.side_effect = WorkerDenied("Worker access denied")
    if fault == "store":
        store_builder.side_effect = RuntimeError("injected store failure")
    if fault == "tls":
        tls.side_effect = RuntimeError("injected TLS failure")
    owned, threads = [], []

    def listener(**kwargs):
        assert kwargs["lookup"] is store.lookup
        assert kwargs["peers"] == config()["peers"]
        if len(owned) == fault:
            raise OSError("injected bind failure")
        value = Mock()
        owned.append(value)
        return value

    def thread(**kwargs):
        value = Mock()
        if fault == "thread":
            value.start.side_effect = RuntimeError("injected thread failure")
        threads.append(value)
        return value

    monkeypatch.setattr(service, "build_server", listener)
    monkeypatch.setattr(service, "Thread", thread)
    stopped = Mock(is_set=Mock(return_value=False))
    if fault == "wait":
        stopped.wait.side_effect = RuntimeError("injected wait failure")

    def run():
        service.serve(tmp_path, config(), factory_builder=builder, stopped=stopped)

    if fault is None:
        run()
    else:
        with pytest.raises((WorkerDenied, OSError, RuntimeError)):
            run()
    assert capsys.readouterr().out == ("READY\n" if fault in {None, "wait"} else "")
    builder.assert_called_once_with()
    assert factory.close.call_count == (0 if fault == "factory" else 1)
    factory.connect.assert_not_called()  # Factory is owned; no prefetch/cache introduced.
    for value in owned:
        value.server_close.assert_called_once_with()
        assert value.shutdown.call_count == (1 if fault in {None, "wait"} else 0)
    for value in threads:
        value.start.assert_called_once_with()
        assert value.join.call_count == (1 if fault in {None, "wait"} else 0)


@pytest.mark.parametrize("stop_at", [0, 1, 6, "thread"])
def test_membership_stop_during_startup_suppresses_ready(tmp_path, monkeypatch, capsys, stop_at):
    factory, owned, threads = Mock(), [], []
    builder = Mock(return_value=factory)
    monkeypatch.setattr(service, "RestrictedMembershipStore", Mock())
    monkeypatch.setattr(service, "tls_context", Mock())
    stopped = Event()
    if stop_at == 0:
        stopped.set()

    def listener(**_):
        value = Mock()
        owned.append(value)
        if len(owned) == stop_at:
            stopped.set()
        return value

    def thread(**_):
        value = Mock()
        value.start.side_effect = stopped.set
        threads.append(value)
        return value

    monkeypatch.setattr(service, "build_server", listener)
    monkeypatch.setattr(service, "Thread", thread)
    with pytest.raises(WorkerDenied):
        service.serve(tmp_path, config(), factory_builder=builder, stopped=stopped)
    assert capsys.readouterr().out == ""
    assert builder.call_count == (0 if stop_at == 0 else 1)
    assert factory.close.call_count == builder.call_count
    assert len(owned) == (6 if stop_at == "thread" else stop_at)
    for value in owned:
        value.server_close.assert_called_once_with()
    if threads:
        assert len(threads) == 1
        threads[0].join.assert_called_once_with(4)
        owned[0].shutdown.assert_called_once_with()
