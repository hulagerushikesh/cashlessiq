"""Bounded empty PGDATA preparation/probe; no cluster initialization or readiness."""

from hashlib import sha256
from typing import ClassVar

from .composition_helpers import Helpers, require
from .composition_inventory import Inventory, canonical


class DatabaseDataHelpers(Helpers):
    modes = ("prepare", "verify")
    kind = "data"
    destination = "/database-data"
    probe_user = "10002:10002"
    entrypoint: ClassVar[list[str]] = ["python", "-m", "scripts.composition_database_data"]

    def __init__(self, plan, *, image, journal, resources, engine, headroom):
        require(type(plan) is Inventory)
        self._initialize(
            plan,
            "database",
            image=image,
            journal=journal,
            resources=resources,
            engine=engine,
            headroom=headroom,
        )

    def volume_name(self):
        return self.plan.database_volume("data")

    def material_fingerprint(self):
        return sha256(
            canonical(
                dict(
                    prefix=self.plan.prefix,
                    volume=self.volume_name(),
                    owner=[10002, 10002],
                    destination=self.destination,
                    child="pgdata",
                )
            )
        ).hexdigest()

    def check_volume(self, row):
        self.plan.check_database_volume("data", row)

    def body(self, mode):
        return canonical(dict(version=1, role=self.role, fingerprint=self.material_fingerprint()))

    def receipt(self, mode):
        return dict(
            state="PREPARED" if mode == "prepare" else "VERIFIED",
            role=self.role,
            fingerprint=self.material_fingerprint(),
        )
