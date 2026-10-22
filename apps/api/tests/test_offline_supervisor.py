"""Fake process/readiness/clock/delivery tests; no service or credential access."""

from dataclasses import replace

import pytest

from ciq_api.offline_supervisor import (
    MAX_NS,
    ROLES,
    Binding,
    Limits,
    OfflineSupervisor,
    Operation,
    Ready,
    Sample,
    Service,
    State,
    SupervisorDenied,
    inventory,
)


def services(generation="generation-a"):
    return tuple(
        Service(
            role,
            generation,
            "a" * 64,
            "b" * 64,
            None if role == "membership" else f"{generation}-{role}",
        )
        for role in sorted(ROLES)
    )


class FakeProcess:
    def __init__(self, incarnation):
        self.incarnation = incarnation
        self.stops = []
        self.confirmed = True
        self.raises = False

    def stop(self, grace):
        self.stops.append(grace)
        if self.raises:
            raise RuntimeError("sensitive adapter diagnostics")
        return self.confirmed


class FakeApproval:
    """Shared disposable authority; replacement controller cannot reuse an approval."""

    def __init__(self):
        self.pending = set()
        self.active = None
        self.retired = None
        self.calls = []

    def take(self, binding):
        self.calls.append("take")
        if binding not in self.pending:
            return False
        self.pending.remove(binding)
        self.active = binding
        return True

    def current(self, binding):
        self.calls.append("current")
        return binding == self.active

    def recovery(self, old, generation, fingerprint):
        self.calls.append("recovery")
        if self.retired != (old, generation, fingerprint):
            return False
        self.retired = None
        self.active = None
        return True


class Harness:
    def __init__(self, specs=None, approval=None, limits=None):
        self.services = services() if specs is None else specs
        self.approval = approval or FakeApproval()
        self.limits = limits or Limits(100, 30, 5, 100, 2, 16)
        self.now = Sample("boot-a", 0)
        self.calls = []
        self.processes = []
        self.cancelled = []
        self.delivered = []
        self.fail_launch = None
        self.bad_incarnation = False
        self.cancel_result = True
        self.verify_result = True
        self.cancel_hook = lambda: None
        self.delivery_hook = lambda: None
        self.controller = self.new_controller()

    def new_controller(self):
        return OfflineSupervisor(
            self.services,
            self.limits,
            "boot-a",
            approval=self.approval,
            verify=self.verify,
            launch=self.launch,
            clock=self.clock,
            cancel=self.cancel,
            deliver=self.deliver,
        )

    def verify(self, specs):
        self.calls.append("verify")
        assert specs == self.services
        return self.verify_result

    def launch(self, spec, binding):
        self.calls.append("launch")
        if spec.role == self.fail_launch:
            raise RuntimeError("private file or token must not escape")
        p = FakeProcess("same" if self.bad_incarnation else f"process-{len(self.processes)}")
        self.processes.append(p)
        return p

    def clock(self):
        self.calls.append("clock")
        return self.now

    def cancel(self, op, grace):
        self.cancelled.append((op, grace, self.controller.state))
        self.cancel_hook()
        return self.cancel_result

    def deliver(self, op):
        self.delivered.append(op)
        self.delivery_hook()

    def approve(self, attempt="attempt-a"):
        b = Binding(attempt, self.services[0].generation, inventory(self.services))
        self.approval.pending.add(b)
        return b

    def start(self):
        self.approve()
        return self.controller.start("attempt-a")

    def ack(self, index):
        return Ready(
            self.controller.binding, self.services[index], self.processes[index].incarnation
        )

    def ready(self):
        self.start()
        for i in range(8):
            self.controller.acknowledge(self.ack(i))
        assert self.controller.state is State.READY
        return self.controller


def test_construction_inactive_and_adapters_not_called():
    h = Harness()
    assert h.controller.state is State.STOPPED
    assert not h.calls and not h.approval.calls
    for action in (h.controller.admit, h.controller.poll, lambda: h.controller.complete(None)):
        with pytest.raises(SupervisorDenied):
            action()
    h.controller.stop()
    assert not h.calls and not h.approval.calls


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "extra",
        "duplicate",
        "role",
        "generation",
        "artifact",
        "configuration",
        "state",
        "shared-state",
        "membership-state",
        "list",
        "object",
    ],
)
def test_inventory_fails_before_any_adapter(fault):
    specs = list(services())
    if fault == "missing":
        specs.pop()
    elif fault == "extra":
        specs.append(specs[0])
    elif fault == "duplicate":
        specs[1] = specs[0]
    elif fault == "role":
        specs[0] = replace(specs[0], role="unreviewed")
    elif fault == "generation":
        specs[0] = replace(specs[0], generation="other")
    elif fault in ("artifact", "configuration"):
        specs[0] = replace(specs[0], **{fault: "not-a-hash"})
    elif fault == "state":
        specs[0] = replace(specs[0], authority_state=None)
    elif fault == "shared-state":
        specs[-1] = replace(specs[-1], authority_state=specs[0].authority_state)
    elif fault == "membership-state":
        i = next(i for i, s in enumerate(specs) if s.role == "membership")
        specs[i] = replace(specs[i], authority_state="forbidden")
    elif fault == "object":
        specs[0] = object()
    specs = specs if fault == "list" else tuple(specs)
    h = Harness(specs)
    with pytest.raises(SupervisorDenied):
        h.controller.start("attempt-a")
    assert h.controller.state is State.FENCED
    assert not h.calls and not h.approval.calls


@pytest.mark.parametrize("field", list(Limits.__dataclass_fields__))
@pytest.mark.parametrize("value", [True, 1.5, -1, 0, MAX_NS + 1])
def test_limits_strict_mandatory_integers(field, value):
    with pytest.raises(SupervisorDenied):
        replace(Limits(100, 30, 5, 100, 2, 16), **{field: value})


@pytest.mark.parametrize("changes", [{"operation_ns": 30_000_000_001}, {"audit_capacity": 4097}])
def test_limits_do_not_extend_capability_or_unbound_audit(changes):
    with pytest.raises(SupervisorDenied):
        replace(Limits(100, 30, 5, 100, 2, 16), **changes)


def test_approval_and_verification_before_any_launch():
    h = Harness()
    with pytest.raises(SupervisorDenied):
        h.controller.start("attempt-a")
    assert not h.calls
    h = Harness()
    h.verify_result = False
    with pytest.raises(SupervisorDenied):
        h.start()
    assert h.calls == ["verify"]
    assert h.controller.state is State.FENCED


def test_all_eight_matching_acknowledgements_required():
    h = Harness()
    h.start()
    assert len(h.processes) == 8
    for i in range(7):
        h.controller.acknowledge(h.ack(i))
        with pytest.raises(SupervisorDenied):
            h.controller.admit()
    h.controller.acknowledge(h.ack(7))
    assert h.controller.admit().deadline_ns == 30


@pytest.mark.parametrize(
    "fault",
    [
        "duplicate",
        "attempt",
        "generation",
        "fingerprint",
        "incarnation",
        "artifact",
        "configuration",
        "object",
    ],
)
def test_stale_foreign_duplicate_ack_does_not_open_barrier(fault):
    h = Harness()
    h.start()
    ack = h.ack(0)
    if fault == "duplicate":
        h.controller.acknowledge(ack)
    elif fault in ("attempt", "generation", "fingerprint"):
        ack = replace(ack, binding=replace(ack.binding, **{fault: "foreign"}))
    elif fault == "incarnation":
        ack = replace(ack, incarnation="foreign")
    elif fault in ("artifact", "configuration"):
        ack = replace(ack, service=replace(ack.service, **{fault: "c" * 64}))
    else:
        ack = object()
    with pytest.raises(SupervisorDenied):
        h.controller.acknowledge(ack)
    assert h.controller.state is State.STARTING
    assert not h.delivered


@pytest.mark.parametrize("uncertain", [False, True])
def test_partial_launch_cleanup_and_sticky_fence(uncertain):
    h = Harness()
    h.fail_launch = h.services[3].role
    original = h.launch

    def launch(spec, binding):
        p = original(spec, binding)
        p.confirmed = not uncertain
        return p

    h.controller._launch = launch
    with pytest.raises(SupervisorDenied, match=r"^Offline supervisor denied$"):
        h.start()
    assert len(h.processes) == 3
    assert all(p.stops == [5] for p in h.processes)
    assert h.controller.state is State.FENCED
    h.controller.stop()
    assert h.controller.state is State.FENCED
    with pytest.raises(SupervisorDenied):
        h.controller.start("attempt-b")


def test_duplicate_incarnation_owned_before_cleanup():
    h = Harness()
    h.bad_incarnation = True
    with pytest.raises(SupervisorDenied):
        h.start()
    assert len(h.processes) == 2
    assert all(p.stops for p in h.processes)


@pytest.mark.parametrize(
    "fault", ["bool", "float", "negative", "overflow", "domain", "rollback", "gap", "exception"]
)
def test_bad_clock_fences_and_closes_pending_delivery(fault):
    h = Harness()
    c = h.ready()
    op = c.admit()
    if fault == "exception":
        c._clock = lambda: (_ for _ in ()).throw(RuntimeError("secret"))
    else:
        value = {
            "bool": True,
            "float": 0.1,
            "negative": -1,
            "overflow": MAX_NS + 1,
            "domain": 1,
            "rollback": 1,
            "gap": 101,
        }[fault]
        if fault == "rollback":
            h.now = Sample("boot-a", 2)
            c.poll()
        h.now = Sample("wrong" if fault == "domain" else "boot-a", value)
    with pytest.raises(SupervisorDenied):
        c.complete(op)
    assert c.state is State.FENCED and not h.delivered
    assert all(p.stops for p in h.processes)


def test_startup_exclusive_deadline():
    h = Harness()
    h.start()
    h.now = Sample("boot-a", 100)
    with pytest.raises(SupervisorDenied):
        h.controller.acknowledge(h.ack(0))
    assert h.controller.state is State.FENCED


@pytest.mark.parametrize("phase", ["startup", "operation"])
def test_deadline_overflow_fences(phase):
    h = Harness(limits=Limits(1, 30, 5, 100, 2, 16))
    h.now = Sample("boot-a", MAX_NS if phase == "startup" else MAX_NS - 20)
    with pytest.raises(SupervisorDenied):
        h.start() if phase == "startup" else h.ready().admit()
    assert h.controller.state is State.FENCED


def test_capacity_receipt_identity_and_exactly_once_completion():
    h = Harness()
    c = h.ready()
    one, two = c.admit(), c.admit()
    with pytest.raises(SupervisorDenied):
        c.admit()
    with pytest.raises(SupervisorDenied):
        c.complete(replace(one))  # Equal fields are not an owned receipt.
    c.complete(one)
    with pytest.raises(SupervisorDenied):
        c.complete(one)
    assert c.active_count == 1 and h.delivered == [one]
    c.complete(two)
    assert c.active_count == 0


@pytest.mark.parametrize("time,delivered", [(29, True), (30, False), (31, False)])
def test_operation_deadline_is_exclusive(time, delivered):
    h = Harness()
    c = h.ready()
    op = c.admit()
    h.now = Sample("boot-a", time)
    if delivered:
        c.complete(op)
        assert h.delivered == [op]
    else:
        with pytest.raises(SupervisorDenied):
            c.complete(op)
        assert h.cancelled == [(op, 5, State.DRAINING)]
        assert not h.delivered and c.active_count == 0
        assert c.state is State.READY


def test_slow_cancellation_rechecks_other_deadlines():
    h = Harness(limits=Limits(100, 30, 20, 100, 2, 16))
    c = h.ready()
    c.admit()
    h.now = Sample("boot-a", 10)
    second = c.admit()
    h.now = Sample("boot-a", 30)
    h.cancel_hook = lambda: setattr(h, "now", Sample("boot-a", 40))
    with pytest.raises(SupervisorDenied):
        c.complete(second)
    assert len(h.cancelled) == 2 and not h.delivered


def test_gate_loss_and_slow_gate_are_checked_before_delivery():
    h = Harness()
    c = h.ready()
    op = c.admit()
    h.approval.active = None
    with pytest.raises(SupervisorDenied):
        c.complete(op)
    assert c.state is State.FENCED and not h.delivered
    h = Harness()
    c = h.ready()
    op = c.admit()
    current = h.approval.current

    def slow(binding):
        h.now = Sample("boot-a", 30)
        return current(binding)

    h.approval.current = slow
    with pytest.raises(SupervisorDenied):
        c.complete(op)
    assert not h.delivered


@pytest.mark.parametrize("fault", ["false", "exception"])
def test_unknown_cancellation_fences_and_retains_capacity(fault):
    h = Harness()
    c = h.ready()
    op = c.admit()
    if fault == "false":
        h.cancel_result = False
    else:
        h.cancel_hook = lambda: (_ for _ in ()).throw(RuntimeError("secret"))
    h.now = Sample("boot-a", 30)
    with pytest.raises(SupervisorDenied):
        c.complete(op)
    assert c.state is State.FENCED and c.active_count == 1
    with pytest.raises(SupervisorDenied):
        c.admit()
    with pytest.raises(SupervisorDenied):
        c.recover(services("generation-b"))
    assert not h.delivered


@pytest.mark.parametrize("fault", ["readiness", "stop", "delivery", "stop-exception"])
def test_delivery_never_reopens_after_shutdown_or_fault(fault):
    h = Harness()
    c = h.ready()
    op = c.admit()
    if fault == "readiness":
        c.readiness_lost()
    elif fault == "delivery":
        h.delivery_hook = lambda: (_ for _ in ()).throw(RuntimeError("secret"))
        with pytest.raises(SupervisorDenied):
            c.complete(op)
    else:
        h.processes[0].raises = fault == "stop-exception"
        c.stop()
    count = len(h.delivered)
    with pytest.raises(SupervisorDenied):
        c.complete(op)
    with pytest.raises(SupervisorDenied):
        c.acknowledge(h.ack(0))
    assert len(h.delivered) == count
    assert c.state is (State.STOPPED if fault == "stop" else State.FENCED)
    c.stop()
    assert all(p.stops for p in h.processes)


def test_replacement_has_no_automatic_approval_or_startup():
    h = Harness()
    h.ready()
    replacement = h.new_controller()
    assert replacement.state is State.STOPPED
    before = len(h.processes)
    with pytest.raises(SupervisorDenied):
        replacement.start("attempt-a")
    assert len(h.processes) == before


def test_recovery_requires_stopped_retired_new_domain_and_fresh_start_approval(tmp_path):
    h = Harness()
    c = h.ready()
    old_op = c.admit()
    old_ack = h.ack(0)
    old_binding = c.binding
    # Disposable evidence files belong to the operator, never the controller.
    preserved = tmp_path / "old-state"
    preserved.write_bytes(b"old guard and incident evidence")
    h.processes[0].confirmed = False
    c.readiness_lost()
    new = services("generation-b")
    h.approval.retired = (old_binding, "generation-b", inventory(new))
    with pytest.raises(SupervisorDenied):
        c.recover(new)
    assert "recovery" not in h.approval.calls
    h.processes[0].confirmed = True
    c.stop()
    with pytest.raises(SupervisorDenied):
        c.recover(services())
    reused = tuple(
        replace(n, authority_state=o.authority_state) for n, o in zip(new, services(), strict=True)
    )
    with pytest.raises(SupervisorDenied):
        c.recover(reused)
    h.approval.retired = None
    with pytest.raises(SupervisorDenied):
        c.recover(new)
    h.approval.retired = (old_binding, "generation-b", inventory(new))
    c.recover(new)
    assert c.state is State.STOPPED and not c.binding
    assert preserved.read_bytes() == b"old guard and incident evidence"
    with pytest.raises(SupervisorDenied):
        c.admit()
    h.services = new
    h.approve("attempt-b")
    h.processes.clear()
    c.start("attempt-b")
    with pytest.raises(SupervisorDenied):
        c.acknowledge(old_ack)
    for i in range(8):
        c.acknowledge(h.ack(i))
    with pytest.raises(SupervisorDenied):
        c.complete(old_op)
    fresh = c.admit()
    c.complete(fresh)
    assert h.delivered == [fresh]
    assert preserved.read_bytes() == b"old guard and incident evidence"


def test_audit_bounded_generic_no_payload_and_no_retry_on_delivery_error():
    h = Harness(limits=Limits(100, 30, 5, 100, 2, 3))
    c = h.ready()
    for _ in range(10):
        c.complete(c.admit())
    assert len(c.audit) == 3
    assert all(len(row) == 5 for row in c.audit)
    assert "secret" not in repr(c.audit)
    assert not h.cancelled
    assert not any(isinstance(v, Operation) for row in c.audit for v in row)


def test_clean_stop_is_idempotent_but_restart_needs_new_approval_and_attempt():
    h = Harness()
    c = h.ready()
    c.stop()
    c.stop()
    assert all(p.stops == [5] for p in h.processes)
    with pytest.raises(SupervisorDenied):
        c.start("attempt-a")
    h.approve("attempt-b")
    c.start("attempt-b")
    assert c.state is State.STARTING


@pytest.mark.parametrize("adapter", ["verify", "take", "current", "launch", "clock"])
def test_adapter_exceptions_are_generic_and_cleanup_known_handles(adapter):
    h = Harness()
    h.approve()

    def fail(*_):
        raise RuntimeError("private diagnostic with credentials")

    if adapter in ("take", "current"):
        setattr(h.approval, adapter, fail)
    else:
        setattr(h.controller, f"_{adapter}", fail)
    with pytest.raises(SupervisorDenied, match=r"^Offline supervisor denied$") as error:
        h.controller.start("attempt-a")
    assert error.value.__suppress_context__
    assert h.controller.state is State.FENCED
    assert all(p.stops for p in h.processes)
    assert "private" not in repr(h.controller.audit)


def test_incarnation_property_failure_keeps_handle_owned_for_cleanup():
    h = Harness()

    class BadProcess(FakeProcess):
        @property
        def incarnation(self):
            raise RuntimeError("private")

    p = BadProcess.__new__(BadProcess)
    p.stops, p.raises, p.confirmed = [], False, True
    h.controller._launch = lambda *_: p
    with pytest.raises(SupervisorDenied):
        h.start()
    assert p.stops == [5]


@pytest.mark.parametrize("fault", ["deadline", "approval"])
def test_later_startup_failure_stops_earlier_handles(fault):
    h = Harness()
    original = h.launch

    def late(spec, binding):
        p = original(spec, binding)
        if len(h.processes) == 3:
            if fault == "deadline":
                h.now = Sample("boot-a", 100)
            else:
                h.approval.active = None
        return p

    h.controller._launch = late
    with pytest.raises(SupervisorDenied):
        h.start()
    assert len(h.processes) == 3
    assert all(p.stops for p in h.processes)
    assert h.controller.state is State.FENCED


def test_stop_during_startup_closes_admission_before_cancellation():
    h = Harness()
    h.start()
    h.controller.stop()
    assert h.controller.state is State.STOPPED
    assert all(p.stops == [5] for p in h.processes)
    with pytest.raises(SupervisorDenied):
        h.controller.acknowledge(h.ack(0))


@pytest.mark.parametrize("attempt", ["", "with spaces", "a" * 65, True, 42])
def test_invalid_attempt_has_no_effect(attempt):
    h = Harness()
    with pytest.raises(SupervisorDenied):
        h.controller.start(attempt)
    assert h.controller.state is State.STOPPED
    assert not h.calls and not h.approval.calls


def test_unconfirmed_work_can_be_confirmed_later_but_fence_is_sticky():
    h = Harness()
    c = h.ready()
    c.admit()
    h.cancel_result = False
    c.stop()
    assert c.state is State.FENCED and c.active_count == 1
    h.cancel_result = True
    c.stop()
    assert c.state is State.FENCED and c.active_count == 0
    with pytest.raises(SupervisorDenied):
        c.start("attempt-b")


def test_recovery_adapter_error_leaves_fence_and_state_unchanged():
    h = Harness()
    c = h.ready()
    c.readiness_lost()
    old = c.binding

    def fail(*_):
        raise RuntimeError("private recovery detail")

    h.approval.recovery = fail
    with pytest.raises(SupervisorDenied, match=r"^Offline supervisor denied$"):
        c.recover(services("generation-b"))
    assert c.state is State.FENCED and c.binding == old


def test_inventory_fingerprint_is_order_independent_and_configuration_bound():
    original = services()
    assert inventory(original) == inventory(tuple(reversed(original)))
    changed = (replace(original[0], configuration="c" * 64), *original[1:])
    assert inventory(original) != inventory(changed)


@pytest.mark.parametrize("action", ["stop", "cancel"])
def test_observed_stop_grace_overrun_fences_even_if_callback_claims_success(action):
    h = Harness()
    c = h.ready()
    op = c.admit()
    if action == "cancel":
        h.now = Sample("boot-a", 30)
        h.cancel_hook = lambda: setattr(h, "now", Sample("boot-a", 35))
        with pytest.raises(SupervisorDenied):
            c.complete(op)
    else:
        original = h.processes[-1].stop

        def slow(grace):
            h.now = Sample("boot-a", 5)
            return original(grace)

        h.processes[-1].stop = slow
        c.stop()
    assert c.state is State.FENCED
    assert not h.delivered
    assert all(p.stops for p in h.processes)


def test_cleanup_continues_all_handles_even_when_clock_is_unavailable():
    h = Harness()
    c = h.ready()
    c._clock = lambda: (_ for _ in ()).throw(RuntimeError("private clock error"))
    c.stop()
    assert c.state is State.FENCED
    assert all(p.stops == [5] for p in h.processes)
