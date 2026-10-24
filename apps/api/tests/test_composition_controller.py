"""Journaled lifecycle with fake Docker; real TLS handlers in the end-to-end case.

No daemon, mounted ownership, physical readiness or independent watchdog proof.
"""

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from composition_controller import Controller
from guard_composition_fixture import compose
from guard_supervisor_fixture import FixtureApproval
from test_composition_launcher_journal import recovery, setup
from test_worker_guard_container_fixture import topology_fixture as topology_fixture
from test_worker_guard_mtls import assertion_key as assertion_key
from test_worker_transport import pki as pki

from ciq_api.offline_supervisor import Limits, Ready, Sample, State, SupervisorDenied
from ciq_api.source_alpha import SOURCE_TENANTS
from ciq_api.validation_worker import SummaryObservation
from ciq_api.worker_health import SECOND


def harness(tmp_path):
    launcher, engine, journal = setup(tmp_path)
    approval = FixtureApproval()
    approval.pending.add(engine.binding)
    clock = SimpleNamespace(now=0)
    cancel = Mock(return_value=True)
    controller = Controller(
        launcher,
        limits=Limits(10 * SECOND, SECOND, 3 * SECOND, 30 * SECOND, 2, 64),
        domain="fictional-test-boot",
        approval=approval,
        clock=lambda: Sample("fictional-test-boot", clock.now),
        cancel=cancel,
    )
    return SimpleNamespace(
        controller=controller,
        launcher=launcher,
        engine=engine,
        journal=journal,
        approval=approval,
        clock=clock,
        cancel=cancel,
    )


def receipts(h):
    return [Ready(h.engine.binding, s, h.launcher.owned[s.role]) for s in h.launcher.services]


def ready(h):
    h.controller.start(h.engine.binding.attempt)
    for receipt in receipts(h):
        h.controller.acknowledge(receipt)


def result(request_id="GOL024"):
    return SummaryObservation(
        request_id=request_id,
        tpa_id="TPA003",
        product_id="PROD003",
        recommendation={"state": "MISSING"},
    )


def test_complete_lifecycle_requires_eight_explicit_receipts_and_records_stops(tmp_path):
    h = harness(tmp_path)
    c = h.controller
    try:
        c.start(h.engine.binding.attempt)
        assert c.supervisor.state is State.STARTING
        for receipt in receipts(h):
            with pytest.raises(SupervisorDenied):
                c.admit("GOL024")
            c.acknowledge(receipt)
        op = c.admit("GOL024")
        assert c.complete(op, result()) == result()
        assert c.supervisor.active_count == 0
        assert not c._requests and not c._pending and not c._delivered
        assert "GOL024" not in repr(c.supervisor.audit)
        assert c.stop()
        assert c.supervisor.state is State.STOPPED
        assert c.stop()
        with pytest.raises(SupervisorDenied):
            c.start("fresh-attempt")
        report, resources = recovery(h.journal)
        assert report.fenced and {r[2] for r in resources.values()} == {"STOPPED"}
    finally:
        h.journal.close()


@pytest.mark.parametrize("fault", ["create-unknown", "connect", "start-unknown"])
def test_failed_launch_contains_allocation_missing_from_supervisor_handles(tmp_path, fault):
    h = harness(tmp_path)
    h.engine.fault = fault
    try:
        with pytest.raises(SupervisorDenied):
            h.controller.start(h.engine.binding.attempt)
        assert h.controller.closed and h.controller.supervisor.state is State.FENCED
        assert len(h.launcher.owned) == 1
        assert all(not row["State"]["Running"] for row in h.engine.rows.values())
        report, resources = recovery(h.journal)
        assert report.fenced
        assert sum(row[2] == "STOPPED" for row in resources.values()) == 1
        assert sum(row[2] == "UNKNOWN" for row in resources.values()) == 7
    finally:
        h.journal.close()


@pytest.mark.parametrize("fault", ["attempt", "incarnation", "configuration", "ports", "exited"])
def test_readiness_must_match_fresh_exact_runtime(tmp_path, fault):
    h = harness(tmp_path)
    try:
        h.controller.start(h.engine.binding.attempt)
        receipt = receipts(h)[0]
        if fault == "attempt":
            receipt = replace(receipt, binding=replace(receipt.binding, attempt="old-attempt"))
        elif fault == "incarnation":
            receipt = replace(receipt, incarnation="a" * 64)
        elif fault == "configuration":
            receipt = replace(receipt, service=replace(receipt.service, configuration="a" * 64))
        elif fault == "ports":
            h.engine.fault = "ports"
        else:
            h.engine.rows[receipt.service.role]["State"].update(
                Running=False,
                Status="exited",
                Pid=0,
            )
        with pytest.raises(SupervisorDenied):
            h.controller.acknowledge(receipt)
        assert h.controller.closed and h.controller.supervisor.state is State.FENCED
        assert all(not row["State"]["Running"] for row in h.engine.rows.values())
    finally:
        h.journal.close()


@pytest.mark.parametrize(
    "fault", ["late", "approval", "stopped", "wrong-case", "raw", "copied-op", "runtime"]
)
def test_closed_or_mismatched_results_never_deliver(tmp_path, fault):
    h = harness(tmp_path)
    try:
        ready(h)
        op = h.controller.admit("GOL024")
        response = result()
        if fault == "late":
            h.clock.now = SECOND
        elif fault == "approval":
            h.approval.active = None
        elif fault == "stopped":
            h.controller.stop()
        elif fault == "wrong-case":
            response = result("GOL001")
        elif fault == "raw":
            response = response.model_dump() | {"clinical_note": "must not deliver"}
        elif fault == "runtime":
            h.engine.rows["validator-1"]["State"].update(Running=False, Status="exited", Pid=0)
        else:
            op = replace(op)
        with pytest.raises(SupervisorDenied):
            h.controller.complete(op, response)
        assert not h.controller._pending and not h.controller._delivered
        assert not any(row[-1] == "delivered" for row in h.controller.supervisor.audit)
        assert h.controller.closed
    finally:
        h.journal.close()


def test_unknown_request_cancellation_retains_capacity_after_containers_stop(tmp_path):
    h = harness(tmp_path)
    try:
        ready(h)
        op = h.controller.admit("GOL024")
        h.cancel.return_value = False
        h.clock.now = SECOND
        with pytest.raises(SupervisorDenied):
            h.controller.poll()
        assert not h.controller.stop()
        assert h.controller.supervisor.active_count == 1
        assert op.identifier in h.controller._requests
        assert all(not row["State"]["Running"] for row in h.engine.rows.values())
        h.cancel.return_value = True
        assert h.controller.stop()
        assert h.controller.supervisor.state is State.FENCED
        assert h.controller.supervisor.active_count == 0
        assert not h.controller._requests
    finally:
        h.journal.close()


def test_closed_journal_prevents_launch_and_does_not_report_clean(tmp_path):
    h = harness(tmp_path)
    h.journal.close()
    with pytest.raises(SupervisorDenied):
        h.controller.start(h.engine.binding.attempt)
    assert not any(args[0] == "create" for args in h.engine.calls)
    assert not h.controller.stop()


def test_journaled_controller_delivers_real_tls_chain_for_both_tenants_all_roles(
    tmp_path,
    topology_fixture,
    pki,
    settings,
    assertion_key,
):
    h = harness(tmp_path)
    world_root = tmp_path / "world"
    world_root.mkdir()
    try:
        with compose(world_root, topology_fixture, pki, settings, assertion_key) as world:
            ready(h)
            for index, tenant in enumerate(SOURCE_TENANTS):
                for profile in tenant.profiles:
                    request_id = "GOL001" if index == 0 else "GOL024"
                    operation = h.controller.admit(request_id)
                    observed = world.broker.summary(world.token(index, profile.role), request_id)
                    delivered = h.controller.complete(operation, observed)
                    assert delivered.tpa_id == tenant.tpa_id
                    assert delivered.recommendation.state == ("SAVED" if index == 0 else "MISSING")
            assert h.controller.supervisor.active_count == 0
            assert sum(row[-1] == "delivered" for row in h.controller.supervisor.audit) == 6
            assert h.controller.stop()
            # The outer world owns real loopback listener closure; fake engine
            # stop observations above are not proof those listeners exited.
    finally:
        h.controller.stop()
        h.journal.close()


def test_lost_stop_confirmation_retains_fence_and_never_reports_cleanup(tmp_path):
    h = harness(tmp_path)
    try:
        ready(h)
        h.engine.fault = "stop-unknown"
        assert not h.controller.stop()
        assert h.controller.supervisor.state is State.FENCED
        assert all(row["State"]["Running"] for row in h.engine.rows.values())
        h.engine.fault = None
        assert h.controller.stop()
        assert h.controller.supervisor.state is State.FENCED
        with pytest.raises(SupervisorDenied):
            h.controller.admit("GOL024")
    finally:
        h.journal.close()


def test_duplicate_result_cannot_be_delivered_twice(tmp_path):
    h = harness(tmp_path)
    try:
        ready(h)
        op = h.controller.admit("GOL024")
        h.controller.complete(op, result())
        with pytest.raises(SupervisorDenied):
            h.controller.complete(op, result())
        assert sum(row[-1] == "delivered" for row in h.controller.supervisor.audit) == 1
        assert h.controller.closed
    finally:
        h.journal.close()
