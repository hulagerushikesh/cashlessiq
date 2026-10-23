"""Inactive disposable state helper coordinator; no normal startup or recovery.

Reuses exact material-helper inspection, bounded transport, journal and explicit
containment. Only the closed state image contract/mount/request differ. Fresh
state-volume ownership is a trusted caller precondition, not receipt evidence.
"""

from typing import ClassVar

from .composition_helpers import Helpers, require
from .composition_inventory import ROLES, Inventory, canonical


class StateHelpers(Helpers):
    modes = ("initialize", "verify")
    kind = "state"
    destination = "/var/lib/ciq-replay"
    entrypoint: ClassVar[list[str]] = [
        "/app/apps/api/.venv/bin/python",
        "/opt/ciq-composition/composition_state_volume.py",
    ]

    def __init__(self, plan, role, *, image, journal, resources, engine, headroom):
        require(type(plan) is Inventory and type(role) is str and role in ROLES)
        require(role != "membership")
        self._initialize(
            plan,
            role,
            image=image,
            journal=journal,
            resources=resources,
            engine=engine,
            headroom=headroom,
        )

    def writable(self, mode):
        # Canonical health validation may persist high-water marks on read-back.
        return True

    def body(self, mode):
        return canonical(dict(version=1, role=self.role, generation=self.plan.generation))

    def receipt(self, mode):
        return dict(
            state="INITIALIZED" if mode == "initialize" else "VERIFIED",
            role=self.role,
            generation=self.plan.generation,
        )
