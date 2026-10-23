"""Real logical-role TLS composition under the fake-clock lifecycle model.

No independent actors, Docker launch, DB, watchdog or operational SLA evidence.
"""

import socket
from contextlib import contextmanager
from dataclasses import replace

import pytest
from guard_composition_fixture import compose
from guard_supervisor_fixture import SupervisedWorld
from test_worker_guard_container_fixture import topology_fixture as topology_fixture
from test_worker_guard_mtls import assertion_key as assertion_key
from test_worker_transport import pki as pki

from ciq_api.offline_supervisor import State, SupervisorDenied
from ciq_api.source_alpha import SOURCE_TENANTS
from ciq_api.worker_authority import WorkerDenied
from ciq_api.worker_health import SECOND


@contextmanager
def supervised(*args):
    with compose(*args) as world:
        h = SupervisedWorld(world)
        try:
            yield h
        finally:
            h.stop()
            h.assert_inactive()


def unreachable(ports):
    for port in ports:
        with pytest.raises(OSError), socket.create_connection(("127.0.0.1", port), timeout=0.2):
            pytest.fail("Stopped disposable listener remained reachable")


def test_all_eight_ready_before_any_shared_result_and_stop_closes_listeners(
    tmp_path, topology_fixture, pki, settings, assertion_key
):
    with supervised(tmp_path, topology_fixture, pki, settings, assertion_key) as h:
        w, c = h.world, h.controller
        token = w.token(0, "processor")
        with pytest.raises(SupervisorDenied):
            h.run(token, "GOL001")
        assert not w.captured
        h.start()
        for service in h.services[:-1]:
            c.acknowledge(h.receipt(service.role))
            with pytest.raises(SupervisorDenied):
                h.run(token, "GOL001")
        assert c.state is State.STARTING and not w.captured
        c.acknowledge(h.receipt(h.services[-1].role))
        assert c.state is State.READY
        for index, tenant in enumerate(SOURCE_TENANTS):
            for profile in tenant.profiles:
                result = h.run(w.token(index, profile.role), "GOL001" if index == 0 else "GOL024")
                assert result.tpa_id == tenant.tpa_id
                assert result.recommendation.state == ("SAVED" if index == 0 else "MISSING")
        assert len(h.deliveries) == 6 and c.active_count == 0
        assert not h._pending and not h._delivered
        assert all("95000" not in repr(row) for row in c.audit)
        for receipt in h.deliveries:
            with pytest.raises(SupervisorDenied):
                c.complete(receipt)
        h.stop()
        assert c.state is State.STOPPED
        unreachable(w.ports.values())
        with pytest.raises(SupervisorDenied):
            h.run(token, "GOL001")


@pytest.mark.parametrize("fault", ["stale-attempt", "wrong-incarnation", "wrong-config"])
def test_stale_readiness_never_opens_admission(
    tmp_path, topology_fixture, pki, settings, assertion_key, fault
):
    with supervised(tmp_path, topology_fixture, pki, settings, assertion_key) as h:
        h.start()
        receipt = h.receipt("broker")
        if fault == "stale-attempt":
            receipt = replace(receipt, binding=replace(receipt.binding, attempt="other-attempt"))
        elif fault == "wrong-incarnation":
            receipt = replace(receipt, incarnation="other-incarnation")
        else:
            receipt = replace(receipt, service=replace(receipt.service, configuration="f" * 64))
        with pytest.raises(SupervisorDenied):
            h.controller.acknowledge(receipt)
        for service in h.services:
            if service.role != "broker":
                h.controller.acknowledge(h.receipt(service.role))
        with pytest.raises(SupervisorDenied):
            h.run(h.world.token(0, "processor"), "GOL001")
        assert not h.world.captured and not h.deliveries


@pytest.mark.parametrize("failure", ["expired", "stopped", "readiness-lost", "approval-lost"])
def test_validated_result_cannot_escape_late_or_closed_delivery(
    tmp_path, topology_fixture, pki, settings, assertion_key, failure
):
    with supervised(tmp_path, topology_fixture, pki, settings, assertion_key) as h:
        h.start()
        h.ready()

        def close_delivery():
            if failure == "expired":
                h.now += SECOND
            elif failure == "stopped":
                h.stop()
            elif failure == "readiness-lost":
                h.controller.readiness_lost()
            else:
                h.approval.active = None

        with pytest.raises(SupervisorDenied):
            h.run(h.world.token(0, "processor"), "GOL001", after_result=close_delivery)
        assert h.world.reads[SOURCE_TENANTS[0].tenant_id].call_count == 1
        assert not h.deliveries and not h._pending and not h._delivered
        unreachable(h.world.ports.values())


def test_unconfirmed_cancellation_retains_capacity_and_fence(
    tmp_path, topology_fixture, pki, settings, assertion_key
):
    with supervised(tmp_path, topology_fixture, pki, settings, assertion_key) as h:
        h.start()
        h.ready()
        h.cancel_confirmed = False

        def expire():
            h.now += SECOND

        with pytest.raises(SupervisorDenied):
            h.run(h.world.token(0, "processor"), "GOL001", after_result=expire)
        assert h.controller.state is State.FENCED and h.controller.active_count == 1
        assert not h.deliveries and not h._pending
        unreachable(h.world.ports.values())
        with pytest.raises(SupervisorDenied):
            h.controller.admit()
        h.cancel_confirmed = True
        h.stop()
        assert h.controller.state is State.FENCED and h.controller.active_count == 0


def test_source_failure_stops_test_world_without_recommendation_or_retry(
    tmp_path, topology_fixture, pki, settings, assertion_key
):
    with supervised(tmp_path, topology_fixture, pki, settings, assertion_key) as h:
        h.start()
        h.ready()
        read = h.world.reads[SOURCE_TENANTS[0].tenant_id]
        read.side_effect = RuntimeError("private source detail")
        with pytest.raises(WorkerDenied, match=r"^Worker access denied$"):
            h.run(h.world.token(0, "processor"), "GOL001")
        read.assert_called_once_with("GOL001")
        assert not h.deliveries and not h._pending
        unreachable(h.world.ports.values())


def test_partial_adoption_fences_known_handles_and_outer_scope_closes_the_rest(
    tmp_path, topology_fixture, pki, settings, assertion_key
):
    with supervised(tmp_path, topology_fixture, pki, settings, assertion_key) as h:
        h.fail_at = "reader-0-clinical"
        with pytest.raises(SupervisorDenied):
            h.start()
        assert h.controller.state is State.FENCED
        assert all(handle.stopped for handle in h.handles.values())
        assert not h.world.captured and not h.deliveries
        ports = tuple(h.world.ports.values())
        # These listeners predate model adoption: the outer fixture is their
        # cleanup owner. This is explicitly NOT a container-launch acceptance.
    unreachable(ports)
