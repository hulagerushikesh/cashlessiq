"""Disposable broker ingress: real TLS/framing, fake source/identity/health only."""

import json
import shlex
import shutil
import subprocess
import sys
from http.client import HTTPSConnection
from pathlib import Path
from threading import Event
from unittest.mock import Mock
from uuid import uuid4

import broker_composition_service as target
import pytest
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat
from guard_composition_fixture import compose
from test_worker_guard_container_fixture import topology_fixture as topology_fixture
from test_worker_guard_mtls import assertion_key as assertion_key
from test_worker_transport import context
from test_worker_transport import pki as pki

from ciq_api.source_alpha import SOURCE_TENANTS
from ciq_api.worker_authority import WorkerDenied
from ciq_api.worker_broker import OfflineSummaryRoute
from ciq_api.worker_transport import PrivateEndpoint


def config():
    return {
        "listen": "192.168.1.2",
        "controller_pin": "a" * 64,
        "readers": {
            audience: {"address": f"192.168.{index}.2", "pin": f"{index:064x}"}
            for index, audience in enumerate(target.READERS, start=2)
        },
        "membership": [
            {"address": "192.168.6.2", "pin": "b" * 64},
            {"address": "192.168.7.2", "pin": "b" * 64},
        ],
    }


def test_private_client_uses_only_explicit_endpoint(pki):
    endpoint = PrivateEndpoint("192.168.1.2", 8443)
    client = target.PrivateBrokerClient(
        endpoint=endpoint,
        context=context(pki, "controller"),
        server_pin=pki[1]["broker"][2],
        server_audience="broker",
    )
    assert (client._host, client._port, client._path) == (
        endpoint.address,
        8443,
        target.BROKER_PATH,
    )
    with pytest.raises(ValueError):
        target.PrivateBrokerClient(endpoint="https://caller-selected.invalid")


def test_closed_image_source_set_imports_without_normal_api_or_source_gateway(tmp_path):
    root = Path(__file__).resolve().parents[3]
    dockerfile = (root / "apps/api/Dockerfile.broker-test").read_text()
    sources = [
        part
        for line in dockerfile.splitlines()
        if line.startswith("COPY ")
        for part in shlex.split(line)[1:-1]
        if part.startswith("apps/api/src/ciq_api/")
    ]
    package = tmp_path / "ciq_api"
    package.mkdir()
    for name in sources:
        shutil.copyfile(root / name, package / Path(name).name)
    for name in ("broker_composition_service.py", "broker_composition_fixture.py"):
        shutil.copyfile(Path(__file__).parent / name, tmp_path / name)
    shutil.copyfile(
        root / "apps/worker/tests/guard_mtls_fixture.py", tmp_path / "guard_mtls_fixture.py"
    )
    probe = """
import importlib.util
from pathlib import Path
import sys
import broker_composition_service
import guard_mtls_fixture
import ciq_api.worker_guard_broker
assert Path(ciq_api.worker_guard_broker.__file__).parent == Path(sys.argv[1]) / 'ciq_api'
for name in ('main', 'db', 'source_cases', 'snowflake_reads', 'worker_membership_store'):
    assert importlib.util.find_spec('ciq_api.' + name) is None, name
print('PASS: closed synthetic broker source set imports; no normal API/source gateway')
"""
    result = subprocess.run(
        [sys.executable, "-c", probe, str(tmp_path)],
        cwd=tmp_path,
        env={"PYTHONPATH": str(tmp_path), "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("PASS: closed synthetic broker source set imports")


@pytest.mark.parametrize(
    "fault",
    [
        "extra",
        "missing",
        "public",
        "controller",
        "few-readers",
        "foreign-reader",
        "duplicate-pin",
        "bad-pin",
        "few-members",
        "many-members",
        "duplicate-address",
        "reader-member-pin",
        "controller-reader-pin",
        "controller-member-pin",
        "caller-tenant",
    ],
)
def test_config_refuses_before_credentials_or_network(tmp_path, monkeypatch, fault):
    raw = config()
    first = next(iter(raw["readers"]))
    if fault == "extra":
        raw["signer"] = "/unapproved"
    elif fault == "missing":
        del raw["controller_pin"]
    elif fault == "public":
        raw["listen"] = "0.0.0.0"
    elif fault == "controller":
        raw["controller_pin"] = "bad"
    elif fault == "few-readers":
        del raw["readers"][first]
    elif fault == "foreign-reader":
        raw["readers"]["reader:2:medical"] = raw["readers"].pop(first)
    elif fault == "duplicate-pin":
        for row in raw["readers"].values():
            row["pin"] = "f" * 64
    elif fault == "bad-pin":
        raw["readers"][first]["pin"] = "BAD"
    elif fault == "few-members":
        raw["membership"].pop()
    elif fault == "many-members":
        raw["membership"].append(dict(raw["membership"][0]))
    elif fault == "duplicate-address":
        raw["membership"][0]["address"] = raw["listen"]
    elif fault == "reader-member-pin":
        raw["membership"][0]["pin"] = raw["readers"][first]["pin"]
    elif fault == "controller-reader-pin":
        raw["readers"][first]["pin"] = raw["controller_pin"]
    elif fault == "controller-member-pin":
        raw["membership"][0]["pin"] = raw["controller_pin"]
    else:
        raw["membership"][0]["tenant"] = str(SOURCE_TENANTS[0].tenant_id)
    tls, reader, member = Mock(), Mock(), Mock()
    monkeypatch.setattr(target, "tls_context", tls)
    monkeypatch.setattr(target, "PrivateSummaryClient", reader)
    monkeypatch.setattr(target, "PrivateMembershipClient", member)
    with pytest.raises(ValueError):
        target.prepare(tmp_path, raw, guard=Mock(), evidence=Mock(), generation="test")
    for dependency in (tls, reader, member):
        dependency.assert_not_called()
    assert not list(tmp_path.iterdir())


def test_prepare_pins_four_readers_two_memberships_without_db_or_ambient_auth(
    tmp_path, monkeypatch, pki, assertion_key
):
    raw = config()
    (tmp_path / "local-auth.json").write_text(json.dumps({"secret": "test-only-local-secret" * 3}))
    (tmp_path / "signer.pem").write_bytes(
        assertion_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
    )
    shutil.copyfile(pki[0], tmp_path / "ca.pem")
    shutil.copyfile(pki[1]["broker"][0], tmp_path / "identity.pem")
    shutil.copyfile(pki[1]["broker"][1], tmp_path / "identity.key")
    monkeypatch.setenv("CIQ_AUTH_MODE", "oidc")
    monkeypatch.setenv("CIQ_OIDC_JWKS_URL", "https://must-not-contact.invalid")
    reader = Mock()
    member = Mock()
    handler = Mock()
    monkeypatch.setattr(target, "PrivateSummaryClient", reader)
    monkeypatch.setattr(target, "PrivateMembershipClient", member)
    monkeypatch.setattr(target, "build_handler", handler)
    result, tls = target.prepare(tmp_path, raw, guard=Mock(), evidence=Mock(), generation="test")
    assert result is handler.return_value and tls(True).verify_mode
    assert reader.call_count == 4 and member.call_count == 2
    for call, (audience, row) in zip(reader.call_args_list, raw["readers"].items(), strict=True):
        assert call.kwargs["endpoint"] == PrivateEndpoint(row["address"], 8443)
        assert call.kwargs["server_audience"] == audience
        assert call.kwargs["operation"] == "read_detail"
    for call, tenant in zip(member.call_args_list, SOURCE_TENANTS, strict=True):
        assert call.kwargs["tenant_id"] == tenant.tenant_id
    settings = handler.call_args.kwargs["settings"]
    assert settings.auth_mode == "local" and not hasattr(settings, "database_url")
    assert not hasattr(settings, "oidc_jwks_url")
    reader.return_value.summary.assert_not_called()
    member.return_value.lookup.assert_not_called()


@pytest.mark.parametrize(
    "fault",
    [
        "missing-auth",
        "short-auth",
        "extra-auth",
        "missing-signer",
        "wrong-key",
        "small-key",
        "ec-key",
    ],
)
def test_missing_or_invalid_material_never_creates_routes(tmp_path, monkeypatch, fault):
    secret = {"secret": "disposable" * 5}
    if fault == "short-auth":
        secret["secret"] = "short"
    if fault == "extra-auth":
        secret["issuer"] = "unapproved"
    if fault != "missing-auth":
        (tmp_path / "local-auth.json").write_text(json.dumps(secret))
    if fault == "wrong-key":
        (tmp_path / "signer.pem").write_text("not a private key")
    elif fault in {"small-key", "ec-key"}:
        key = (
            rsa.generate_private_key(public_exponent=65537, key_size=1024)
            if fault == "small-key"
            else ec.generate_private_key(ec.SECP256R1())
        )
        (tmp_path / "signer.pem").write_bytes(
            key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
        )
    clients = Mock()
    monkeypatch.setattr(target, "PrivateSummaryClient", clients)
    with pytest.raises((ValueError, FileNotFoundError)):
        target.prepare(tmp_path, config(), guard=Mock(), evidence=Mock(), generation="test")
    clients.assert_not_called()


@pytest.mark.parametrize("fault", ["missing", "extra", "audience", "validator", "foreign-tenant"])
def test_handler_requires_exact_four_canonical_routes(monkeypatch, fault):
    routes = {
        (tenant, disclosure): OfflineSummaryRoute(audience, Mock(), validator)
        for audience, (tenant, disclosure, validator) in target.READERS.items()
    }
    first = next(iter(routes))
    if fault == "missing":
        del routes[first]
    elif fault == "extra":
        routes[first[0], "unknown"] = routes[first]
    elif fault == "foreign-tenant":
        routes[uuid4(), first[1]] = routes.pop(first)
    else:
        row = routes[first]
        routes[first] = OfflineSummaryRoute(
            "wrong" if fault == "audience" else row.audience,
            row.invoke,
            "wrong" if fault == "validator" else row.validator_audience,
        )
    constructor = Mock()
    monkeypatch.setattr(target, "GuardedSummaryBroker", constructor)
    with pytest.raises(ValueError):
        target.build_handler(
            settings=Mock(),
            lookups=Mock(),
            routes=routes,
            private_key=Mock(),
            guard=Mock(),
            evidence=Mock(),
            generation="test",
        )
    constructor.assert_not_called()


@pytest.mark.parametrize(
    "fault", [None, "prepare", "bind", "thread", "wait", "stop-before", "stop-bind", "stop-thread"]
)
def test_service_owns_listener_and_suppresses_partial_ready(tmp_path, monkeypatch, capsys, fault):
    prepare = Mock(return_value=(Mock(), Mock()))
    listener = Mock()
    constructor = Mock(return_value=listener)
    thread = Mock()
    stopped = (
        Event()
        if fault in {"stop-before", "stop-bind", "stop-thread"}
        else Mock(is_set=Mock(return_value=False))
    )
    if fault == "stop-before":
        stopped.set()
    if fault == "prepare":
        prepare.side_effect = RuntimeError("injected prepare failure")
    elif fault == "bind":
        constructor.side_effect = OSError("injected bind failure")
    elif fault == "thread":
        thread.start.side_effect = RuntimeError("injected thread failure")
    elif fault == "wait":
        stopped.wait.side_effect = RuntimeError("injected wait failure")
    elif fault == "stop-bind":
        constructor.side_effect = lambda **_: (stopped.set(), listener)[1]
    elif fault == "stop-thread":
        thread.start.side_effect = stopped.set
    monkeypatch.setattr(target, "prepare", prepare)
    monkeypatch.setattr(target, "PrivateBrokerServer", constructor)
    monkeypatch.setattr(target, "Thread", Mock(return_value=thread))

    def run():
        target.serve(
            tmp_path, config(), guard=Mock(), evidence=Mock(), generation="test", stopped=stopped
        )

    if fault is None:
        run()
    else:
        with pytest.raises((WorkerDenied, RuntimeError, OSError)):
            run()
    assert capsys.readouterr().out == ("READY\n" if fault in {None, "wait"} else "")
    assert listener.server_close.call_count == (
        0 if fault in {"stop-before", "prepare", "bind"} else 1
    )
    assert listener.shutdown.call_count == (1 if fault in {None, "wait", "stop-thread"} else 0)


@pytest.mark.parametrize("name", ["reader", "validator", "foreign", "broker"])
def test_noncontroller_certs_denied_before_broker_work(
    tmp_path, topology_fixture, pki, settings, assertion_key, name
):
    with compose(tmp_path, topology_fixture, pki, settings, assertion_key) as w:
        client = target.BrokerClient(
            context=context(pki, name),
            port=w.ports["broker"],
            server_pin=pki[1]["broker"][2],
            server_audience="broker",
        )
        with pytest.raises(WorkerDenied):
            client.summary(w.token(0, "processor"), "GOL001")
        assert not w.captured and not w.lookup.called


@pytest.mark.parametrize(
    "fault",
    ["tenant", "role", "destination", "signer", "missing", "bad-nonce", "duplicate", "wrong-path"],
)
def test_strict_broker_wire_cannot_choose_authority(
    tmp_path, topology_fixture, pki, settings, assertion_key, fault
):
    with compose(tmp_path, topology_fixture, pki, settings, assertion_key) as w:
        message = dict(token=w.token(0, "processor"), request_id="GOL001", nonce=str(uuid4()))
        if fault in {"tenant", "role", "destination", "signer"}:
            message[fault] = "injected"
        elif fault == "missing":
            message.pop("request_id")
        elif fault == "bad-nonce":
            message["nonce"] = "invalid"
        body = json.dumps(message)
        if fault == "duplicate":
            body = body[:-1] + ',"request_id":"GOL024"}'
        connection = HTTPSConnection(
            "127.0.0.1", w.ports["broker"], context=context(pki, "controller"), timeout=3
        )
        try:
            connection.request(
                "POST",
                "/wrong" if fault == "wrong-path" else target.BROKER_PATH,
                body,
                headers={"Content-Type": "application/json"},
            )
            response = connection.getresponse()
            assert response.status == 403 and response.getheader("Cache-Control") == "no-store"
            assert response.read() == b'{"error":"Worker access denied"}'
        finally:
            connection.close()
        assert not w.captured and not w.lookup.called


@pytest.mark.parametrize("fault", [None, "nonce", "case", "extra", "raw"])
def test_client_rejects_unbound_or_widened_response(pki, fault):
    client = target.BrokerClient(
        context=context(pki, "controller"),
        port=1,
        server_pin=pki[1]["broker"][2],
        server_audience="broker",
    )

    def exchange(message):
        result = dict(
            nonce=message["nonce"],
            summary=dict(
                request_id="GOL024",
                tpa_id="TPA003",
                product_id="NIA-001",
                recommendation=dict(state="MISSING"),
            ),
        )
        target.Response.model_validate(result)  # Baseline must be valid before tampering.
        if fault == "nonce":
            result["nonce"] = str(uuid4())
        elif fault == "case":
            result["summary"]["request_id"] = "GOL027"
        elif fault == "extra":
            result["tenant"] = "injected"
        elif fault == "raw":
            result["summary"]["clinical_note"] = "must not deliver"
        return result

    client._exchange = exchange
    if fault is None:
        assert client.summary("synthetic-session", "GOL024").recommendation.state == "MISSING"
    else:
        with pytest.raises(WorkerDenied):
            client.summary("synthetic-session", "GOL024")
