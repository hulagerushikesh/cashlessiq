"""Explicit bootstrap/probe coordinator; no network database service."""

from typing import ClassVar

from .composition_database_cluster_helpers import DatabaseClusterHelpers


class DatabaseBootstrapHelpers(DatabaseClusterHelpers):
    modes = ("bootstrap", "verify")
    kind = "bootstrap"
    entrypoint: ClassVar[list[str]] = ["python", "-m", "scripts.composition_database_bootstrap"]

    def mounts(self, mode):
        return [
            (self.volume_name(), "/database-material", False),
            (self.plan.database_volume("data"), "/database-data", mode == "bootstrap"),
        ]

    def receipt(self, mode):
        return dict(
            state="BOOTSTRAPPED" if mode == "bootstrap" else "VERIFIED",
            role=self.role,
            fingerprint=self.material_fingerprint(),
        )
