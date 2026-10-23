"""Shared eight-role logical composition: TLS real, storage/source/health fake.

No Docker run, restricted PostgreSQL, independent processes, supervisor readiness,
operational deadline, public HTTP app or live Snowflake acceptance is implied.
"""

import socket
from http.server import ThreadingHTTPServer

import jwt
import pytest
from guard_composition_fixture import compose
from test_worker_guard_container_fixture import topology_fixture as topology_fixture
from test_worker_guard_mtls import assertion_key as assertion_key
from test_worker_transport import context
from test_worker_transport import pki as pki

from ciq_api.offline_supervisor import ROLES
from ciq_api.source_alpha import SOURCE_TENANTS
from ciq_api.worker_authority import Membership, WorkerDenied
from ciq_api.worker_guard_state import GuardStateDenied
from ciq_api.worker_membership import LoopbackMembershipClient
from ciq_api.worker_transport import LoopbackSummaryClient


def test_both_tenants_all_roles_share_one_exact_composition(
    tmp_path, topology_fixture, pki, settings, assertion_key
):
    with compose(tmp_path, topology_fixture, pki, settings, assertion_key) as w:
        assert set(w.opened) == ROLES and len(w.opened) == 8
        assert len(w.ports) == 7 and len(w.guards) == 7
        for index, tenant in enumerate(SOURCE_TENANTS):
            for profile in tenant.profiles:
                token = w.token(index, profile.role)
                requests = ("GOL001",) if index == 0 else ("GOL024", "GOL027")
                for request in requests:
                    result = w.broker.summary(token, request)
                    assert result.tpa_id == tenant.tpa_id and result.request_id == request
                    if index == 0:
                        assert result.recommendation.state == "SAVED"
                        assert result.recommendation.payable_inr == 95000
                    else:
                        assert result.recommendation.state == "MISSING"
                        assert "payable_inr" not in result.recommendation.model_dump()
                    payload = result.model_dump_json()
                    assert all(
                        s not in payload
                        for s in (
                            '"decision_json"',
                            '"clinical_note"',
                            '"lines"',
                            '"calc"',
                            "Restricted synthetic",
                            "Sensitive synthetic",
                        )
                    )
                    reader, parent = w.captured[-1]
                    assert reader == f"reader-{index}-" + (
                        "clinical" if profile.role == "medical_officer" else "nonclinical"
                    )
                    assert jwt.decode(parent, options={"verify_signature": False})["tenant"] == str(
                        tenant.tenant_id
                    )
                    with pytest.raises(WorkerDenied):
                        w.clients[reader].summary(parent)
        assert w.reads[SOURCE_TENANTS[0].tenant_id].call_count == 3
        assert w.reads[SOURCE_TENANTS[1].tenant_id].call_count == 6
        assert w.lookup.call_count > 9  # Fresh network checks, not a fixture cache.
        ports = tuple(w.ports.values())
    # ExitStack closes actual listeners, not just references to a fake handle.
    for port in ports:
        with pytest.raises(OSError), socket.create_connection(("127.0.0.1", port), timeout=0.2):
            pytest.fail("Disposable listener remained reachable")


@pytest.mark.parametrize("index", [0, 1])
@pytest.mark.parametrize(
    "failure",
    [
        "invalid-login",
        "foreign-case",
        "revoked",
        "downgraded",
        "source-outage",
        "membership-outage",
        "broker-health",
        "reader-delivery-health",
    ],
)
def test_shared_composition_denies_without_fallback_or_cross_tenant_effect(
    tmp_path, topology_fixture, pki, settings, assertion_key, index, failure
):
    with compose(tmp_path, topology_fixture, pki, settings, assertion_key) as w:
        tenant = SOURCE_TENANTS[index]
        request = "GOL001" if index == 0 else "GOL024"
        token = w.token(index, "medical_officer")
        medical = next(p for p in tenant.profiles if p.role == "medical_officer")
        read = w.reads[tenant.tenant_id]
        if failure == "invalid-login":
            token = "not-a-session"
        elif failure == "foreign-case":
            request = "GOL024" if index == 0 else "GOL001"
        elif failure == "broker-health":
            w.evidence["broker"] = lambda: "invalid fictional health"
        elif failure == "membership-outage":
            w.lookup.side_effect = RuntimeError("private membership DB detail")
        else:

            def during_read(request_id):
                if failure == "source-outage":
                    raise RuntimeError("private source credential and payload")
                if failure in {"revoked", "downgraded"}:
                    w.members[tenant.tenant_id, str(medical.user_id)] = (
                        None if failure == "revoked" else Membership(tenant.tenant_id, "auditor")
                    )
                else:
                    w.evidence[f"reader-{index}-clinical"] = lambda: "invalid fictional health"
                return w.inputs[request_id]

            read.side_effect = during_read
        with pytest.raises(WorkerDenied, match=r"^Worker access denied$"):
            w.broker.summary(token, request)
        expected_reads = (
            1
            if failure in {"revoked", "downgraded", "source-outage", "reader-delivery-health"}
            else 0
        )
        assert read.call_count == expected_reads
        w.reads[SOURCE_TENANTS[1 - index].tenant_id].assert_not_called()
        if failure == "reader-delivery-health":
            role = f"reader-{index}-clinical"
            with pytest.raises(GuardStateDenied):
                w.guards[role].observe(lambda: "invalid fictional health")
        # Shared broker/DB outages fail closed globally. A single tenant/reader
        # failure must not poison the other tenant's independent authority state.
        if failure not in {"broker-health", "membership-outage"}:
            other = 1 - index
            result = w.broker.summary(
                w.token(other, "processor"), "GOL001" if other == 0 else "GOL024"
            )
            assert result.tpa_id == SOURCE_TENANTS[other].tpa_id


def test_shared_tls_peer_pins_deny_foreign_identity_and_direct_broker_hop(
    tmp_path, topology_fixture, pki, settings, assertion_key
):
    with compose(tmp_path, topology_fixture, pki, settings, assertion_key) as w:
        token = w.token(0, "processor")
        w.broker.summary(token, "GOL001")
        parent = w.captured[-1][1]
        child = jwt.decode(parent, options={"verify_signature": False})["summary_token"]
        for index, tenant in enumerate(SOURCE_TENANTS):
            validator = "validator" if index == 0 else "validator1"
            direct = LoopbackSummaryClient(
                context=context(pki, "broker"),
                port=w.ports[f"validator-{index}"],
                server_pin=pki[1][validator][2],
                server_audience=f"validator:{index}",
                operation="validate_summary",
            )
            with pytest.raises(WorkerDenied):
                direct.summary(child)
            for role in (f"reader-{index}-nonclinical", f"reader-{index}-clinical"):
                reader = "reader" if index == 0 else "reader1"
                reader += "_medical" if role.endswith("-clinical") else ""
                foreign = LoopbackSummaryClient(
                    context=context(pki, "foreign"),
                    port=w.ports[role],
                    server_pin=pki[1][reader][2],
                    server_audience=topology_fixture.SERVICE_BINDINGS[role][1],
                    operation="read_detail",
                )
                with pytest.raises(WorkerDenied):
                    foreign.summary(parent)
            impostor = LoopbackMembershipClient(
                tenant_id=tenant.tenant_id,
                context=context(pki, "foreign"),
                port=w.ports["membership"],
                server_pin=pki[1]["membership"][2],
                server_audience="membership:0",
            )
            before = w.lookup.call_count
            with pytest.raises(WorkerDenied):
                impostor.lookup(str(tenant.profiles[0].user_id))
            assert w.lookup.call_count == before
        assert sum(read.call_count for read in w.reads.values()) == 1


@pytest.mark.parametrize("failure", ["invalid-health", "missing-state", "corrupt-state"])
def test_partial_bind_closes_previous_listeners_without_repairing_state(
    tmp_path, topology_fixture, pki, settings, assertion_key, monkeypatch, failure
):
    ports = []
    original = ThreadingHTTPServer.server_bind

    def remember_bind(server):
        original(server)
        ports.append(server.server_port)

    monkeypatch.setattr(ThreadingHTTPServer, "server_bind", remember_bind)
    failed_role = "reader-1-clinical"
    state = tmp_path / failed_role / "used.sqlite"

    def before_bind(role, guards, evidence):
        if role != failed_role:
            return
        if failure == "invalid-health":
            evidence[role] = lambda: "invalid fictional health"
        elif failure == "missing-state":
            state.unlink()
        else:
            state.write_bytes(b"disposable corruption")

    with (
        pytest.raises(WorkerDenied),
        compose(tmp_path, topology_fixture, pki, settings, assertion_key, before_bind=before_bind),
    ):
        pytest.fail("Partial composition unexpectedly admitted work")
    assert len(ports) == 6  # Membership + two validators + three readers.
    for port in ports:
        with pytest.raises(OSError), socket.create_connection(("127.0.0.1", port), timeout=0.2):
            pytest.fail("Partial startup leaked a listener")
    assert len(list(tmp_path.iterdir())) == 7  # Keep incident state, no new generation.
    if failure == "missing-state":
        assert not state.exists()
    elif failure == "corrupt-state":
        assert state.read_bytes() == b"disposable corruption"
    else:
        guard, evidence = topology_fixture.load(directory=tmp_path / failed_role)
        with pytest.raises(GuardStateDenied):
            guard.observe(evidence)
