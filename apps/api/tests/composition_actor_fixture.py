"""Import exact owner-side bounded actor source without changing sys.path."""

import importlib.util
import sys
from pathlib import Path

from composition_inventory_fixture import implementation as inv

_path = Path(__file__).resolve().parents[3] / "scripts/bounded_composition_actor.py"
_spec = importlib.util.spec_from_file_location("ciq_bounded_composition_actor_test", _path)
implementation = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = implementation
_spec.loader.exec_module(implementation)


class FakeCompositionAttempt:
    """Closed fake-engine cases, NOT real Docker admission/cleanup or durable fence."""

    def __init__(self, plan):
        if type(plan) is not inv.Inventory:
            raise implementation.ActorDenied()
        self.pending = {plan.name(role): "UNKNOWN" for role in inv.ROLES}
        self.used, self.fenced, self.active = False, False, 0
        self.task = None

    def execute(self, mode, marker, *, budget_ns):
        if (
            self.used
            or mode not in {"healthy", "partial", "blocked-create", "blocked-stop", "late"}
            or not Path(marker).is_absolute()
        ):
            raise implementation.ActorDenied()
        self.used, self.active = True, 1
        try:
            self.task = implementation.BoundedActor(
                (
                    sys.executable,
                    str(Path(__file__).with_name("composition_actor_case.py")),
                    mode,
                    str(marker),
                ),
                budget_ns=budget_ns,
                grace_ns=500_000_000,
            )
            result = self.task.execute()
            if mode not in {"healthy", "partial"}:
                raise implementation.ActorDenied()
            expected = dict(
                mode=mode,
                state="STOPPED" if mode == "healthy" else "FENCED",
                owned=8 if mode == "healthy" else 1,
                stopped=8 if mode == "healthy" else 1,
                active=0,
                deliveries=1 if mode == "healthy" else 0,
            )
            if result != expected:
                raise implementation.ActorDenied()
            self.active = 0
            self.fenced = mode == "partial"
            self.pending.clear()  # Fake-case confirmation only, never Docker absence proof.
            return result
        except Exception:
            self.fenced = True
            raise implementation.ActorDenied() from None
