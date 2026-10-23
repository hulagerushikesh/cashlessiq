"""Separate-service test target: configuration, dependencies and exact cleanup.

Loopback composition tests exercise the same build_handler over real TLS. Tests
here do not claim a Docker build/run, process watchdog or mount/network isolation.
"""

import json
from copy import deepcopy
from threading import Event
from unittest.mock import Mock

import pytest
from composition_service_fixture import service
from cryptography.hazmat.primitives import serialization
from test_source_cases import build_test_sources
from test_worker_guard_container_fixture import topology_fixture as topology_fixture
from test_worker_guard_mtls import assertion_key as assertion_key
from test_worker_transport import pki as pki

from ciq_api.source_alpha import SOURCE_TENANTS
from ciq_api.worker_authority import WorkerDenied


def config(role):
    index, _, disclosure = service.BINDINGS[role]
    peers = (
        {"a" * 64: "broker"}
        if disclosure
        else {
            "a" * 64: f"reader:{index}:nonclinical",
            "b" * 64: f"reader:{index}:medical",
        }
    )
    raw = dict(
        role=role,
        listen=["192.168.40.2"],
        peers=peers,
        membership=dict(address="192.168.41.2", pin="c" * 64),
    )
    if disclosure:
        raw["validator"] = dict(address="192.168.42.2", pin="d" * 64)
    return raw


@pytest.mark.parametrize("role", service.BINDINGS)
def test_exact_six_service_configs_and_handler_dependencies(
    role, tmp_path, topology_fixture, assertion_key
):
    index, audience, disclosure = service.BINDINGS[role]
    assert service.configuration(config(role)) == (index, disclosure)
    topology_fixture.initialize(role, directory=tmp_path)
    guard, evidence = topology_fixture.load(directory=tmp_path)
    invoke, read = Mock(), Mock()
    handler = service.build_handler(
        role,
        public_key=assertion_key.public_key(),
        generation=topology_fixture.GENERATION,
        guard=guard,
        evidence=evidence,
        membership=Mock(),
        **({"invoke": invoke} if disclosure else {"read_inputs": read}),
    )
    assert handler.operation == ("read_detail" if disclosure else "validate_summary")
    assert handler.peer_audiences == frozenset(config(role)["peers"].values())
    assert not invoke.called and not read.called
    assert audience in {value[1] for value in service.BINDINGS.values()}
    with pytest.raises(ValueError, match="dependencies"):
        service.build_handler(
            role,
            public_key=assertion_key.public_key(),
            generation=topology_fixture.GENERATION,
            guard=guard,
            evidence=evidence,
            membership=Mock(),
            invoke=invoke,
            read_inputs=read,
        )


@pytest.mark.parametrize(
    "fault",
    [
        "unknown-role",
        "broker",
        "membership",
        "foreign-peer",
        "missing-peer",
        "extra-peer",
        "extra-setting",
        "public-listen",
        "duplicate-listen",
        "no-listen",
        "too-many-listen",
        "bad-pin",
        "public-target",
        "target-extra",
        "missing-validator",
        "validator-extra",
    ],
)
def test_bad_service_config_never_loads_keys_or_binds(tmp_path, monkeypatch, fault):
    raw = config("reader-0-clinical")
    if fault in {"unknown-role", "broker", "membership"}:
        raw["role"] = {"unknown-role": "reader-0-medical"}.get(fault, fault)
    elif fault == "foreign-peer":
        raw["peers"] = {"a" * 64: "reader:1:medical"}
    elif fault == "missing-peer":
        raw["peers"] = {}
    elif fault == "extra-peer":
        raw["peers"]["b" * 64] = "broker"
    elif fault == "extra-setting":
        raw["assertion_signer"] = "forbidden"
    elif fault == "public-listen":
        raw["listen"] = ["0.0.0.0"]
    elif fault == "duplicate-listen":
        raw["listen"] *= 2
    elif fault == "no-listen":
        raw["listen"] = []
    elif fault == "too-many-listen":
        raw["listen"] = [f"192.168.40.{i}" for i in range(1, 5)]
    elif fault == "bad-pin":
        raw["membership"]["pin"] = "opaque"
    elif fault == "public-target":
        raw["membership"]["address"] = "203.0.113.1"
    elif fault == "target-extra":
        raw["membership"]["tenant"] = "caller-selected"
    elif fault == "missing-validator":
        del raw["validator"]
    else:
        raw = config("validator-0")
        raw["validator"] = dict(address="192.168.42.2", pin="d" * 64)
    listener = Mock()
    monkeypatch.setattr(service, "GuardedPrivateSummaryServer", listener)
    with pytest.raises(ValueError):
        service.serve(tmp_path, raw, guard=Mock(), evidence=Mock(), generation="g", stopped=Event())
    listener.assert_not_called()
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("role", service.BINDINGS)
def test_preparation_keeps_readers_source_free_and_pins_tenant(
    role, tmp_path, monkeypatch, pki, assertion_key
):
    index, _, disclosure = service.BINDINGS[role]
    (tmp_path / "verify.pem").write_bytes(
        assertion_key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    # Use actual TLS material, but construction performs no network operation.
    (tmp_path / "ca.pem").write_bytes(pki[0].read_bytes())
    cert, key, _ = pki[1]["reader"]
    (tmp_path / "identity.pem").write_bytes(cert.read_bytes())
    (tmp_path / "identity.key").write_bytes(key.read_bytes())
    factory = Mock(return_value="handler")
    monkeypatch.setattr(service, "build_handler", factory)
    handler, _ = service.prepare(
        tmp_path, config(role), guard=Mock(), evidence=Mock(), generation="g"
    )
    assert handler == "handler"
    kwargs = factory.call_args.kwargs
    # Bound method belongs to a fixed-tenant TLS client; no request-supplied tenant.
    assert kwargs["membership"].__self__._tenant == SOURCE_TENANTS[index].tenant_id
    if disclosure:
        assert "read_inputs" not in kwargs and "invoke" in kwargs
        assert not (tmp_path / "source.json").exists()
    else:
        assert "invoke" not in kwargs
        read = kwargs["read_inputs"]
        with pytest.raises(FileNotFoundError):
            read("GOL001" if index == 0 else "GOL024")
        _, _, _, records, details = build_test_sources()
        case = records[SOURCE_TENANTS[index].tenant_id][0]
        row = dict(
            case=case.model_dump(mode="json"),
            decisions=deepcopy(details[case.request_id]["decision"]),
            evidence=deepcopy(details[case.request_id]["evidence"]),
        )
        source = tmp_path / "source.json"
        source.write_text(json.dumps({case.request_id: row}))
        assert read(case.request_id).case == case
        row["case"]["tpa_id"] = SOURCE_TENANTS[1 - index].tpa_id
        source.write_text(json.dumps({case.request_id: row}))
        with pytest.raises(WorkerDenied):
            read(case.request_id)


@pytest.mark.parametrize("failure", [None, 0, 1, 2, "wait"])
def test_partial_bind_and_stop_close_only_owned_listeners(tmp_path, monkeypatch, capsys, failure):
    raw = config("reader-0-nonclinical")
    raw["listen"] = ["192.168.40.2", "192.168.41.2", "192.168.42.2"]
    handler = service.Handler(Mock(), "read_detail", frozenset({"broker"}))
    monkeypatch.setattr(service, "prepare", Mock(return_value=(handler, Mock())))
    created, threads = [], []

    def listener(**kwargs):
        if len(created) == failure:
            raise OSError("injected bind failure")
        value = Mock()
        value.address = kwargs["endpoint"].address
        created.append(value)
        return value

    def thread(**kwargs):
        value = Mock()
        threads.append(value)
        return value

    monkeypatch.setattr(service, "GuardedPrivateSummaryServer", listener)
    monkeypatch.setattr(service, "Thread", thread)
    stopped = Mock(is_set=Mock(return_value=False))
    if failure == "wait":
        stopped.wait.side_effect = RuntimeError("injected wait failure")

    def call():
        service.serve(tmp_path, raw, guard=Mock(), evidence=Mock(), generation="g", stopped=stopped)

    if failure is None:
        call()
    else:
        with pytest.raises(OSError if type(failure) is int else RuntimeError):
            call()
    output = capsys.readouterr().out
    assert output == ("READY\n" if failure is None or failure == "wait" else "")
    assert len(threads) == (3 if failure is None or failure == "wait" else 0)
    for value in created:
        value.server_close.assert_called_once_with()
        assert value.shutdown.call_count == (1 if threads else 0)
    for value in threads:
        value.start.assert_called_once_with()
        value.join.assert_called_once_with(4)


@pytest.mark.parametrize("stop_at", [0, 1, 3, "thread"])
def test_stop_during_startup_never_announces_readiness(tmp_path, monkeypatch, capsys, stop_at):
    raw = config("reader-0-nonclinical")
    raw["listen"] = ["192.168.40.2", "192.168.41.2", "192.168.42.2"]
    handler = service.Handler(Mock(), "read_detail", frozenset({"broker"}))
    monkeypatch.setattr(service, "prepare", Mock(return_value=(handler, Mock())))
    stopped = Event()
    if stop_at == 0:
        stopped.set()
    created, threads = [], []

    def listener(**_):
        value = Mock()
        created.append(value)
        if len(created) == stop_at:
            stopped.set()
        return value

    def thread(**_):
        value = Mock()
        value.start.side_effect = stopped.set
        threads.append(value)
        return value

    monkeypatch.setattr(service, "GuardedPrivateSummaryServer", listener)
    monkeypatch.setattr(service, "Thread", thread)
    with pytest.raises(WorkerDenied):
        service.serve(tmp_path, raw, guard=Mock(), evidence=Mock(), generation="g", stopped=stopped)
    assert capsys.readouterr().out == ""
    assert len(created) == (3 if stop_at == "thread" else stop_at)
    for value in created:
        value.server_close.assert_called_once_with()
    assert len(threads) == (1 if stop_at == "thread" else 0)
    if threads:
        threads[0].join.assert_called_once_with(4)
        created[0].shutdown.assert_called_once_with()
