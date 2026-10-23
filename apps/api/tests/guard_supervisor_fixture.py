"""Test-only model bridge adopting an already-created loopback TLS world.

No process/container launch, watchdog or operational startup is implemented.
The model serializes admission/delivery; closures stop actual test listeners.
Clock, approval and cancellation confirmation are explicitly fictional. A
failed request stops this fixture world; this is not product outage policy.
"""

from hashlib import sha256
from uuid import uuid4

from ciq_api.offline_supervisor import (
    Binding,
    Limits,
    OfflineSupervisor,
    Ready,
    Sample,
    Service,
    State,
    SupervisorDenied,
    inventory,
)
from ciq_api.worker_health import SECOND


class FixtureApproval:
    def __init__(self):
        self.pending = set()
        self.active = None

    def take(self, binding):
        if binding not in self.pending:
            return False
        self.pending.remove(binding)
        self.active = binding
        return True

    def current(self, binding):
        return binding == self.active

    def recovery(self, *_):
        return False


class ListenerHandle:
    def __init__(self, close):
        self.incarnation = uuid4().hex
        self._close = close
        self.stopped = False

    def stop(self, _grace):
        if not self.stopped:
            self._close()
            self.stopped = True
        return True


class SupervisedWorld:
    """run() is supervised; raw world access stays trusted test internals.

    The lifecycle ledger receives opaque receipts, not summary payloads.
    This fixture is not an isolation boundary around its own Python caller.
    """

    def __init__(self, world):
        self.world = world
        self.now = 0
        self.approval = FixtureApproval()
        self.handles = {}
        self.cancel_confirmed = True
        self.fail_at = None
        self.deliveries = []
        self._pending = {}
        self._delivered = {}
        # Test markers only, NOT measured image/configuration attestations.
        self.services = tuple(
            Service(
                role,
                "disposable-v3-generation",
                sha256(b"fixture-artifact").hexdigest(),
                (
                    world.guards[role]._config.fingerprint
                    if role != "membership"
                    else sha256(b"fixture-membership").hexdigest()
                ),
                None if role == "membership" else f"fixture-{role}",
            )
            for role in world.opened
        )
        self.controller = OfflineSupervisor(
            self.services,
            Limits(10 * SECOND, SECOND, 3 * SECOND, 30 * SECOND, 2, 64),
            "fictional-test-boot",
            approval=self.approval,
            verify=lambda services: services == self.services,
            launch=self._adopt,
            clock=lambda: Sample("fictional-test-boot", self.now),
            cancel=self._cancel,
            deliver=self._deliver,
        )

    def _adopt(self, service, _binding):
        if service.role == self.fail_at:
            raise RuntimeError("Injected test listener adoption failure")
        handle = ListenerHandle(lambda: self.world.close_role(service.role))
        self.handles[service.role] = handle
        return handle

    def _cancel(self, operation, _grace):
        self._pending.pop(operation.identifier, None)
        self._delivered.pop(operation.identifier, None)
        return self.cancel_confirmed

    def _deliver(self, operation):
        self._delivered[operation.identifier] = self._pending.pop(operation.identifier)
        self.deliveries.append(operation)

    def start(self):
        binding = Binding("fixture-attempt", self.services[0].generation, inventory(self.services))
        self.approval.pending.add(binding)
        return self.controller.start(binding.attempt)

    def receipt(self, role):
        service = next(s for s in self.services if s.role == role)
        return Ready(self.controller.binding, service, self.handles[role].incarnation)

    def ready(self):
        for service in self.services:
            self.controller.acknowledge(self.receipt(service.role))

    def run(self, token, request_id, *, after_result=lambda: None):
        operation = self.controller.admit()
        try:
            result = self.world.broker.summary(token, request_id)
            self._pending[operation.identifier] = result
            after_result()
            self.controller.complete(operation)
            return self._delivered.pop(operation.identifier)
        except Exception:
            # No retry or conversion of an outage/expired result into MISSING.
            # The real operational actor/cancellation design remains separate.
            self.controller.stop()
            raise
        finally:
            self._pending.pop(operation.identifier, None)
            self._delivered.pop(operation.identifier, None)

    def stop(self):
        self.controller.stop()
        self._pending.clear()
        self._delivered.clear()

    def assert_inactive(self):
        if self.controller.state not in {State.STOPPED, State.FENCED}:
            raise SupervisorDenied()
