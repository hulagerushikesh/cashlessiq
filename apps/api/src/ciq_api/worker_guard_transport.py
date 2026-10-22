"""Explicit offline v3 pre-bind gate, never API startup or cached readiness."""

from collections.abc import Callable

from ciq_api.worker_authority import WorkerDenied
from ciq_api.worker_guard_health import OfflineHealthGuard
from ciq_api.worker_transport import LoopbackSummaryServer, PrivateEndpoint


class GuardedSummaryServer(LoopbackSummaryServer):
    def __init__(self, *, guard: OfflineHealthGuard, evidence: Callable[[], str], **configuration):
        try:
            if type(guard) is not OfflineHealthGuard:
                raise WorkerDenied("Worker access denied")
            guard.observe(evidence)
        except Exception:
            raise WorkerDenied("Worker access denied") from None
        super().__init__(**configuration)


class GuardedPrivateSummaryServer(GuardedSummaryServer):
    def __init__(self, *, endpoint: PrivateEndpoint, **configuration):
        if type(endpoint) is not PrivateEndpoint:
            raise ValueError("Invalid private worker endpoint")
        self._endpoint = endpoint
        super().__init__(**configuration)

    def _listen_address(self) -> tuple[str, int]:
        return self._endpoint.address, self._endpoint.port
