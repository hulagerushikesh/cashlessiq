"""Two-mount initdb coordinator; independently inspected probe, no DB startup."""

from hashlib import sha256
from typing import ClassVar

from .composition_database_helpers import DatabaseHelpers
from .composition_database_volume import request
from .composition_helpers import require
from .composition_inventory import canonical
from .composition_journal import fold


class DatabaseClusterHelpers(DatabaseHelpers):
    modes = ("initialize", "verify")
    kind = "cluster"
    entrypoint: ClassVar[list[str]] = ["python", "-m", "scripts.composition_database_cluster"]

    def user(self, mode):
        return self.probe_user

    def capabilities(self, mode):
        return []

    def mounts(self, mode):
        return [
            (self.volume_name(), "/database-material", False),
            (self.plan.database_volume("data"), "/database-data", mode == "initialize"),
        ]

    def fingerprint(self, mode):
        return sha256(
            canonical(
                dict(base=super().fingerprint(mode), mounts=self.mounts(mode), user=self.user(mode))
            )
        ).hexdigest()

    def commands(self):
        return (*super().commands(), ("volume", "inspect", self.plan.database_volume("data")))

    def _volume_intention(self):
        super()._volume_intention()
        _, rows, fenced = fold(self.resources.events)
        name = self.plan.database_volume("data")
        require(
            not fenced and rows.get(("volume", name), (None, None, None))[1:] == (name, "PRESENT")
        )

    def body(self, mode):
        self.plan.check_database_volume(
            "data", self._read("volume", "inspect", self.plan.database_volume("data"))
        )
        return request(self.staged, install=False)

    def receipt(self, mode):
        return dict(
            state="INITIALIZED" if mode == "initialize" else "VERIFIED",
            role=self.role,
            fingerprint=self.material_fingerprint(),
        )
