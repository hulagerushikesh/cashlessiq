"""Inactive DB material helper coordination; never PostgreSQL startup/readiness.

Requires a separately observed exact DB material volume and fresh helper ledger.
No app/state volume may substitute. The owner still owes physical allocation/
mount proof and a PostgreSQL image enforcing the declared UID/GID.
"""

from hashlib import sha256
from typing import ClassVar

from .composition_database import DatabaseStaging
from .composition_database_volume import OWNER, request
from .composition_helpers import Helpers, require
from .composition_inventory import Inventory, canonical
from .composition_material import Staged


def fingerprint(plan):
    require(type(plan) is Inventory)
    return sha256(
        canonical(
            dict(
                prefix=plan.prefix,
                volume=plan.database_volume("material"),
                network=plan.network("member-db").identifier,
                db_address=plan.address("member-db", "db"),
                membership_address=plan.address("member-db", "membership"),
                owner=OWNER,
                destination="/database-material",
            )
        )
    ).hexdigest()


class DatabaseHelpers(Helpers):
    destination = "/database-material"
    probe_user = "10002:10002"
    entrypoint: ClassVar[list[str]] = ["python", "-m", "scripts.composition_database_volume"]

    def __init__(self, plan, staged, *, image, journal, resources, engine, headroom):
        require(type(plan) is Inventory and type(staged) is Staged)
        require(type(staged.expected) is DatabaseStaging)
        require(staged.expected.role == "database")
        require(staged.expected.fingerprint == fingerprint(plan))
        self.staged = staged
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
        return self.plan.database_volume("material")

    def material_fingerprint(self):
        return fingerprint(self.plan)

    def check_volume(self, row):
        self.plan.check_database_volume("material", row)

    def body(self, mode):
        return request(self.staged, install=mode == "install")
