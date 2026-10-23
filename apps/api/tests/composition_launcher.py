"""Inactive owner-side test adapter; never imported by app/image startup.

Engine commands and material verification are injected trusted dependencies.
They MUST be run in bounded owned actors with an independent watchdog before
physical acceptance. This adapter alone does not contain a blocked Docker call.
It neither builds/provisions resources nor manufactures readiness receipts.
"""

import json

from composition_inventory_fixture import implementation as inv

from ciq_api.offline_supervisor import Binding, Service, inventory

EDGES, LABEL, ROLES, Inventory, _hex = inv.EDGES, inv.LABEL, inv.ROLES, inv.Inventory, inv._hex
ENTRYPOINTS = {
    "worker": ["python", "-m", "ciq_worker_runtime.composition_service"],
    "membership": ["python", "-m", "ciq_membership_runtime.composition_service"],
    "broker": [
        "/app/apps/api/.venv/bin/python",
        "/opt/ciq-composition/broker_composition_service.py",
    ],
}


class OwnedContainer:
    def __init__(self, launcher, role, cid):
        self._launcher, self._role, self._cid = launcher, role, cid

    @property
    def incarnation(self):
        return self._cid

    def stop(self, grace_ns):
        return self._launcher.stop(self._role, grace_ns)


class Launcher:
    def __init__(self, plan, *, engine, material_check, auxiliaries):
        if type(plan) is not Inventory or not callable(engine) or not callable(material_check):
            raise ValueError("Invalid disposable launcher")
        if (
            type(auxiliaries) is not dict
            or set(auxiliaries) != {"db", "controller"}
            or any(not _hex(cid) for cid in auxiliaries.values())
            or len(set(auxiliaries.values())) != 2
        ):
            raise ValueError("Invalid disposable auxiliary inventory")
        self.plan, self.engine, self.material_check = plan, engine, material_check
        self.auxiliaries = dict(auxiliaries)
        self.owned, self.attempted, self.allocating = {}, set(), set()
        self.binding = None
        self.closed = False
        self._image_configs = {}
        self.services = tuple(
            Service(
                role,
                plan.generation,
                plan.image(role)[7:],
                plan.fingerprint(role),
                None if role == "membership" else plan.volume(role, "state"),
            )
            for role in ROLES
        )

    def _read(self, *args):
        rows = json.loads(self.engine(*args))
        if type(rows) is not list or len(rows) != 1 or type(rows[0]) is not dict:
            raise ValueError("Invalid disposable engine observation")
        return rows[0]

    def _identity(self, role, row):
        if (
            not _hex(row.get("Id"))
            or row.get("Name") != "/" + self.plan.name(role)
            or row.get("Image") != self.plan.image(role)
            or row.get("Config", {}).get("Labels", {}).get(LABEL) != self.plan.prefix
            or row["Config"]["Labels"].get(f"{LABEL}.role") != role
        ):
            raise ValueError("Unowned disposable container")
        labels = row["Config"]["Labels"]
        if (
            self.binding is None
            or labels.get(f"{LABEL}.attempt") != self.binding.attempt
            or labels.get(f"{LABEL}.fingerprint") != self.binding.fingerprint
        ):
            raise ValueError("Unowned disposable attempt")
        return row["Id"]

    def verify(self, services):
        if services != self.services:
            return False
        try:
            for kind, identifier in self.plan.images:
                row = self._read("image", "inspect", identifier)
                if (
                    row["Id"] != identifier
                    or row["Config"]["Entrypoint"] != ENTRYPOINTS[kind]
                    or row["Config"].get("Cmd") not in (None, [])
                ):
                    return False
                self._image_configs[identifier] = inv.canonical(
                    {k: row["Config"].get(k) for k in ("Entrypoint", "Cmd", "Env")}
                )
            owners = {**self.auxiliaries, **self.owned}
            for edge in EDGES:
                self.plan.check_network(
                    edge,
                    self._read("network", "inspect", self.plan.network(edge).identifier),
                    owners,
                )
            for role in ROLES:
                for kind in ("material",) if role == "membership" else ("material", "state"):
                    self.plan.check_volume(
                        role, kind, self._read("volume", "inspect", self.plan.volume(role, kind))
                    )
                if self.material_check(role, self.plan.descriptor(role)) is not True:
                    return False
            return True
        except Exception:
            return False

    def __call__(self, service, binding):
        if (
            self.closed
            or type(service) is not Service
            or service not in self.services
            or type(binding) is not Binding
            or binding.generation != self.plan.generation
            or binding.fingerprint != inventory(self.services)
            or (self.binding is not None and binding != self.binding)
            or service.role in self.attempted
        ):
            raise ValueError("Disposable launch denied")
        self.binding = binding
        role = service.role
        self.attempted.add(role)  # Reserve exact name BEFORE the fallible create call.
        try:
            if not self.verify(self.services):
                raise ValueError("Disposable preflight denied")
            if self.engine(
                "container",
                "ls",
                "-a",
                "--filter",
                f"name=^{self.plan.name(role)}$",
                "--format",
                "{{.ID}}",
            ).strip():
                raise ValueError("Disposable name already exists")
            self.allocating.add(role)
            args = self.plan.create_arguments(role)
            cid = self.engine(
                *args[:-1],
                "--label",
                f"{LABEL}.attempt={binding.attempt}",
                "--label",
                f"{LABEL}.fingerprint={binding.fingerprint}",
                args[-1],
            ).strip()
            if not _hex(cid) or cid in self.owned.values() or cid in self.auxiliaries.values():
                raise ValueError("Invalid disposable incarnation")
            self.owned[role] = cid  # Own BEFORE network attach, inspect or start.
            for network, address in self.plan.attachments(role)[1:]:
                self.engine("network", "connect", "--ip", address, network, cid)
            row = self._read("inspect", cid)
            self._identity(role, row)
            self._runtime_config(role, row)
            if self.plan.check_container(role, row, running=False) != cid:
                raise ValueError("Disposable incarnation mismatch")
            self.engine("start", cid)
            row = self._read("inspect", cid)
            self._identity(role, row)
            self._runtime_config(role, row)
            if self.plan.check_container(role, row, running=True) != cid:
                raise ValueError("Disposable incarnation mismatch")
            return OwnedContainer(self, role, cid)
        except Exception:
            # Failed create may still have allocated a container. Never retry it
            # or infer absence from a CLI error. Reconcile by exact name+labels.
            self.closed = True
            self.reconcile(role)
            raise ValueError("Disposable launch failed; stopped review required") from None

    def _runtime_config(self, role, row):
        observed = inv.canonical({k: row["Config"].get(k) for k in ("Entrypoint", "Cmd", "Env")})
        if observed != self._image_configs.get(self.plan.image(role)):
            raise ValueError("Disposable runtime override denied")

    def reconcile(self, role):
        if role not in self.allocating:
            return False
        try:
            row = self._read("inspect", self.plan.name(role))
            cid = self._identity(role, row)
            if (
                (role in self.owned and self.owned[role] != cid)
                or cid in self.auxiliaries.values()
                or any(other != role and value == cid for other, value in self.owned.items())
            ):
                return False
            self.owned[role] = cid
            return True
        except Exception:
            return False  # Unknown, not proof of absence or permission to retry.

    def stop(self, role, grace_ns):
        self.closed = True  # A stopped/uncertain attempt can never launch replacements.
        if type(grace_ns) is not int or not 0 < grace_ns <= 30_000_000_000:
            return False
        if role not in self.owned:
            return False
        cid = self.owned[role]
        try:
            row = self._read("inspect", cid)
            if self._identity(role, row) != cid:
                return False
            if (
                row["State"].get("Running")
                or row["State"].get("Paused")
                or row["State"].get("Restarting")
            ):
                self.engine("stop", "--time", str(grace_ns // 1_000_000_000), cid)
            row = self._read("inspect", cid)
            return (
                self._identity(role, row) == cid
                and row["State"].get("Running") is False
                and row["State"].get("Pid") == 0
                and row["State"].get("Status") in {"created", "exited"}
                and not any(row["State"].get(k) for k in ("Paused", "Restarting", "Dead"))
                and row.get("RestartCount", 0) == 0
            )
        except Exception:
            return False  # Retain ownership and the caller's fence/capacity.

    def cleanup(self, grace_ns):
        """Stop known exact containers; preserve every container/volume for review.

        The external owner must reconcile ambiguous names and remove exact owned
        resources after confirmation. No prune, state deletion or automatic retry.
        """
        clean = True
        self.closed = True
        for role in tuple(self.allocating):
            if role not in self.owned and not self.reconcile(role):
                clean = False
                continue
            if not self.stop(role, grace_ns):
                clean = False
        return clean
