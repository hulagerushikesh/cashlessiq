"""Inactive DB material helper coordination; never PostgreSQL startup/readiness.

Requires a separately observed exact DB material volume and fresh helper ledger.
No app/state volume may substitute. The owner still owes resource allocation,
physical mount proof and a PostgreSQL image enforcing the declared UID/GID.
"""

from hashlib import sha256
from typing import ClassVar

from .composition_database import DatabaseStaging
from .composition_database_volume import OWNER, request
from .composition_helpers import Helpers, require
from .composition_inventory import LABEL, Inventory, canonical
from .composition_material import Staged


def fingerprint(plan):
    require(type(plan) is Inventory)
    return sha256(
        canonical(
            dict(
                prefix=plan.prefix,
                volume=plan.name("db") + "-material",
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
        return self.plan.name("db") + "-material"

    def material_fingerprint(self):
        return fingerprint(self.plan)

    def check_volume(self, row):
        require(row["Name"] == self.volume_name())
        require(row["Driver"] == "local" and row["Scope"] == "local")
        require(not row.get("Options"))
        require(
            row["Labels"]
            == {
                LABEL: self.plan.prefix,
                f"{LABEL}.role": "database",
                f"{LABEL}.kind": "material",
            }
        )

    def body(self, mode):
        return request(self.staged, install=mode == "install")
