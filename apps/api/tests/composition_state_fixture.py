"""Inactive disposable seven-state gate; host tests, not mounted-volume proof.

Uses the existing frozen-time test initializer explicitly, once. Reload is
verification only. No normal startup, Docker calls, credentials or recovery.
"""

import os
import stat
from pathlib import Path

from composition_inventory_fixture import implementation as inv


class StatesDenied(ValueError):
    def __init__(self):
        super().__init__("Disposable composition state denied; retain outcome for review")


def require(value):
    if not value:
        raise StatesDenied()


class States:
    def __init__(self, plan, root, fixture):
        require(type(plan) is inv.Inventory and isinstance(root, Path) and root.is_absolute())
        self.plan, self.root, self.fixture = plan, root, fixture
        self.roles = tuple(role for role in inv.ROLES if role != "membership")
        require(set(self.roles) == set(fixture.SERVICE_BINDINGS))
        self.used = False
        self.identity = self._directory(root)

    def _directory(self, path):
        info = path.lstat()
        require(stat.S_ISDIR(info.st_mode))
        require(info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o700)
        return info.st_dev, info.st_ino

    def path(self, role):
        require(type(role) is str and role in self.roles)
        return self.root / self.plan.volume(role, "state")

    def _root(self):
        require(self._directory(self.root) == self.identity)

    def initialize(self):
        """Explicit empty-root attempt only; any partial state is left intact."""
        require(not self.used)
        self.used = True
        try:
            self._root()
            require(not list(self.root.iterdir()))
            for role in self.roles:
                self._root()
                directory = self.path(role)
                directory.mkdir(mode=0o700)
                self.fixture.initialize(role, directory=directory, generation=self.plan.generation)
            return True
        except Exception:
            raise StatesDenied() from None

    def verify(self, staged):
        """Reload all existing authorities; never initialize, replace or heal.

        The caller still owes independent mounted UID checks, bounded execution
        and container readiness. Frozen health is explicitly fictional. All
        static/SQLite checks precede health observations, which may persist
        canonical high-water marks; this is not a read-only filesystem probe.
        """
        try:
            self._root()
            require(type(staged) is dict and set(staged) == set(inv.ROLES))
            require(
                {p.name for p in self.root.iterdir()} == {self.path(r).name for r in self.roles}
            )
            identities = set()
            guards = []
            for role in inv.ROLES:
                require(staged[role].verify(role, self.plan.fingerprint(role)) is True)
                if role == "membership":
                    continue
                directory = self.path(role)
                identity = self._directory(directory)
                require(identity not in identities)
                identities.add(identity)
                require(
                    {p.name for p in directory.iterdir()} == {"used.sqlite", "public-guard.json"}
                )
                for name, mode in (("used.sqlite", 0o600), ("public-guard.json", 0o400)):
                    info = (directory / name).lstat()
                    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1)
                    require(info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == mode)
                    require(0 < info.st_size <= 262144)
                guard, evidence = self.fixture.load(directory=directory)
                require(guard._config.authority == self.fixture.authority_for(role))
                require(guard._config.assertion_generation == self.plan.generation)
                guard.inspect()
                guards.append((guard, evidence))
                require(self._directory(directory) == identity)
            self._root()
            for guard, evidence in guards:
                guard.observe(evidence)
            return True
        except Exception:
            raise StatesDenied() from None
