"""Closed disposable actor cases. Fake Docker only; no actual engine access."""

import json
import signal
import sys
import time
from pathlib import Path

from test_composition_launcher import launcher

from ciq_api.offline_supervisor import (
    Limits,
    OfflineSupervisor,
    Ready,
    Sample,
    State,
    SupervisorDenied,
)

MODES = {"healthy", "partial", "blocked-create", "blocked-stop", "late"}


def main(mode, marker):
    if mode not in MODES:
        raise ValueError("Unknown disposable composition case")
    h, engine, _ = launcher()
    original = engine.__call__

    def mark(value):
        with Path(marker).open("x") as output:
            output.write(value)

    def command(*args):
        if (mode == "blocked-create" and args[0] == "create") or (
            mode == "blocked-stop" and args[0] == "stop"
        ):
            mark(mode)
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            time.sleep(30)  # Deliberately blocked INSIDE the adapter callback.
        return original(*args)

    h.engine = command

    class Approval:
        def take(self, binding):
            return binding == engine.binding

        def current(self, binding):
            return binding == engine.binding

    deliveries = []
    controller = OfflineSupervisor(
        h.services,
        Limits(10_000_000_000, 1_000_000_000, 3_000_000_000, 30_000_000_000, 1, 32),
        "fake-clock",
        approval=Approval(),
        verify=h.verify,
        launch=h,
        clock=lambda: Sample("fake-clock", 0),
        cancel=lambda *_: False,
        deliver=deliveries.append,
    )
    if mode == "partial":
        engine.fault = "connect"
    if mode == "partial":
        try:
            controller.start(engine.binding.attempt)
        except SupervisorDenied:
            pass
        else:
            raise AssertionError("Partial launch unexpectedly succeeded")
        engine.fault = None
        assert controller.state is State.FENCED and h.cleanup(3_000_000_000)
    else:
        controller.start(engine.binding.attempt)
        for service in h.services:
            try:
                controller.admit()
            except SupervisorDenied:
                pass
            else:
                raise AssertionError("Admitted before all-eight model readiness")
            controller.acknowledge(Ready(controller.binding, service, h.owned[service.role]))
        operation = controller.admit()
        controller.complete(operation)
        controller.stop()
        assert controller.state is State.STOPPED and len(deliveries) == 1
    value = dict(
        mode=mode,
        state=controller.state.value,
        owned=len(h.owned),
        stopped=sum(row["State"]["Running"] is False for row in engine.rows.values()),
        active=controller.active_count,
        deliveries=len(deliveries),
    )
    print(json.dumps(value), flush=True)
    if mode == "late":
        mark(mode)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        time.sleep(30)  # Valid-looking output is not completion/permission to deliver.


if __name__ == "__main__":
    if len(sys.argv) != 3 or not Path(sys.argv[2]).is_absolute():
        raise ValueError("Closed test mode and absolute disposable marker required")
    main(sys.argv[1], sys.argv[2])
