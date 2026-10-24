"""Inactive owner-side composition bridge; no CLI or normal service activation.

Joins the journaled launcher to the serialized lifecycle model. The caller owns
bounded request actors, independent watchdog ticks, auxiliary DB/controller
containment and actual readiness probes. Running containers are not readiness.
No request transport executes inside these transitions; cancellation is an
explicit trusted dependency and unknown outcomes retain supervisor capacity.
"""

from contextlib import suppress

from composition_launcher import Launcher

from ciq_api.offline_supervisor import OfflineSupervisor, Ready, State, SupervisorDenied
from ciq_api.validation_worker import SummaryObservation


class Controller:
    def __init__(self, launcher, *, limits, domain, approval, clock, cancel):
        if type(launcher) is not Launcher or launcher.journal is None or not callable(cancel):
            raise SupervisorDenied()
        self.launcher = launcher
        self.limits = limits
        self._requests = {}
        self._pending = {}
        self._delivered = {}
        self._cancel_actor = cancel
        self.used = False
        self.closed = False
        self.supervisor = OfflineSupervisor(
            launcher.services,
            limits,
            domain,
            approval=approval,
            verify=launcher.verify,
            launch=launcher,
            clock=clock,
            cancel=self._cancel,
            deliver=self._deliver,
        )

    def _cancel(self, operation, grace):
        # Discard delivery eligibility before fallible external containment.
        self._pending.pop(operation.identifier, None)
        self._delivered.pop(operation.identifier, None)
        confirmed = self._cancel_actor(operation, grace) is True
        if confirmed:
            self._requests.pop(operation.identifier, None)
        return confirmed

    def _deliver(self, operation):
        self._delivered[operation.identifier] = self._pending.pop(operation.identifier)
        self._requests.pop(operation.identifier)

    def start(self, attempt):
        if self.used or self.closed:
            raise SupervisorDenied()
        self.used = True
        try:
            return self.supervisor.start(attempt)
        except Exception:
            # The launcher may own an allocation for which no handle returned
            # to the model. Always include its journaled cleanup path.
            self.stop()
            raise SupervisorDenied() from None

    def acknowledge(self, receipt):
        try:
            if (
                self.closed
                or type(receipt) is not Ready
                or receipt.binding != self.supervisor.binding
                or receipt.service not in self.launcher.services
                or not self.launcher.running(receipt.service.role, receipt.incarnation)
            ):
                raise SupervisorDenied()
            self.supervisor.acknowledge(receipt)
        except Exception:
            self._fail()
            raise SupervisorDenied() from None

    def _fail(self):
        if self.supervisor.state in (State.STARTING, State.READY):
            with suppress(Exception):
                self.supervisor.readiness_lost()
        self.stop()

    def poll(self):
        try:
            if self.closed:
                raise SupervisorDenied()
            if self.supervisor.state in (State.STARTING, State.READY) and not all(
                self.launcher.running(service.role, self.launcher.owned.get(service.role))
                for service in self.launcher.services
            ):
                raise SupervisorDenied()
            return self.supervisor.poll()
        except Exception:
            self._fail()
            raise SupervisorDenied() from None

    def admit(self, request_id):
        if self.closed or type(request_id) is not str or not 0 < len(request_id) <= 120:
            raise SupervisorDenied()
        # No bearer token, response body or source data enters the journal/audit.
        self.poll()
        operation = self.supervisor.admit()
        self._requests[operation.identifier] = (operation, request_id)
        return operation

    def complete(self, operation, result):
        try:
            expected = self._requests.get(operation.identifier)
            if self.closed or expected is None or expected[0] is not operation:
                raise SupervisorDenied()
            # Revalidate even a mutated Pydantic instance; reject extra/raw data.
            if type(result) is not SummaryObservation:
                raise SupervisorDenied()
            result = SummaryObservation.model_validate(result.model_dump())
            if result.request_id != expected[1]:
                raise SupervisorDenied()
            self.poll()
            self._pending[operation.identifier] = result
            self.supervisor.complete(operation)
            return self._delivered.pop(operation.identifier)
        except Exception:
            self._fail()
            raise SupervisorDenied() from None
        finally:
            if hasattr(operation, "identifier"):
                self._pending.pop(operation.identifier, None)
                self._delivered.pop(operation.identifier, None)

    def stop(self):
        """Contain known app/request work; never claim auxiliary exit or removal."""
        self.closed = True
        self._pending.clear()
        self._delivered.clear()
        model_clean = False
        try:
            self.supervisor.stop()
            model_clean = self.supervisor.active_count == 0
        finally:
            # This includes partial allocations the supervisor never received.
            containers_clean = self.launcher.cleanup(self.limits.stop_grace_ns)
        return model_clean and containers_clean
