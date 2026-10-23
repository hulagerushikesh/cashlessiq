"""Explicit disposable network/volume provisioning; no automatic entrypoint.

Caller supplies test images/pins/subnets, a fresh journal and bounded engine.
Headroom and host/Docker-route collision checks are mandatory injected gates.
No discovery of a free subnet, removal, adoption, retry or credential I/O.
This requires a trusted exclusive UUID namespace, not hostile same-owner races.
"""

import json
from contextlib import suppress
from hashlib import sha256
from ipaddress import IPv4Network

from .composition_inventory import EDGES, LABEL, ROLES, Inventory, Network, _hex, canonical


class ResourcesDenied(ValueError):
    def __init__(self):
        super().__init__("Disposable provisioning denied; retained resources require review")


class Resources:
    def __init__(
        self, *, prefix, images, pins, subnets, journal, engine, headroom, collision_check
    ):
        if (
            type(subnets) is not dict
            or set(subnets) != set(EDGES)
            or not all(callable(fn) for fn in (engine, headroom, collision_check))
        ):
            raise ResourcesDenied()
        # Placeholder IDs validate the PUBLIC layout only. Never sent to Docker
        # or returned as allocated identities. Actual IDs come from inspection.
        self.layout = Inventory(
            prefix,
            images,
            pins,
            tuple(Network(edge, f"{i:064x}", subnets[edge]) for i, edge in enumerate(EDGES, 1)),
        )
        if journal.events != [{"version": 1, "prefix": prefix}]:
            raise ResourcesDenied()
        self.journal, self.engine = journal, engine
        self.headroom, self.collision_check = headroom, collision_check
        self.specs = tuple(
            [
                dict(
                    kind="network",
                    name=f"{prefix}-{n.edge}",
                    edge=n.edge,
                    subnet=n.subnet,
                    labels={LABEL: prefix, LABEL + ".edge": n.edge},
                )
                for n in self.layout.networks
            ]
            + [
                dict(
                    kind="volume",
                    name=self.layout.volume(role, kind),
                    role=role,
                    volume_kind=kind,
                    labels={LABEL: prefix, LABEL + ".role": role, LABEL + ".kind": kind},
                )
                for role in ROLES
                for kind in (("material",) if role == "membership" else ("material", "state"))
            ]
        )
        self.attempted, self.observed = set(), {}
        self.used, self.closed = False, False

    def _record(self, action, spec, identity=None):
        self.journal.record(
            action,
            kind=spec["kind"],
            name=spec["name"],
            identity=identity,
            fingerprint=sha256(canonical(spec)).hexdigest(),
        )

    def create_arguments(self, spec):
        args = [
            spec["kind"],
            "create",
            "--driver",
            "bridge" if spec["kind"] == "network" else "local",
        ]
        for key, value in sorted(spec["labels"].items()):
            args.extend(("--label", f"{key}={value}"))
        if spec["kind"] == "network":
            args.extend(
                (
                    "--internal",
                    "--subnet",
                    spec["subnet"],
                    "--gateway",
                    str(IPv4Network(spec["subnet"]).network_address + 1),
                )
            )
        return (*args, spec["name"])

    def commands(self):
        """Closed transport inventory, containing no secret or authority material."""
        return (
            ("network", "ls", "--format", "{{.Name}}"),
            ("volume", "ls", "--format", "{{.Name}}"),
            *(self.create_arguments(s) for s in self.specs),
            *((s["kind"], "inspect", s["name"]) for s in self.specs),
        )

    def _observe(self, spec, acknowledgement=None):
        rows = json.loads(self.engine(spec["kind"], "inspect", spec["name"]))
        if type(rows) is not list or len(rows) != 1 or type(rows[0]) is not dict:
            raise ResourcesDenied()
        row = rows[0]
        if row.get("Name") != spec["name"] or row.get("Labels") != spec["labels"]:
            raise ResourcesDenied()
        if spec["kind"] == "volume":
            self.layout.check_volume(spec["role"], spec["volume_kind"], row)
            identity = row["Name"]
        else:
            identity = row.get("Id")
            if not _hex(identity) or any(identity == cid for cid in self.observed.values()):
                raise ResourcesDenied()
            # Reuse canonical topology validation with just this actual full ID.
            networks = tuple(
                Network(n.edge, identity if n.edge == spec["edge"] else n.identifier, n.subnet)
                for n in self.layout.networks
            )
            actual = Inventory(self.layout.prefix, self.layout.images, self.layout.pins, networks)
            actual.check_network(spec["edge"], row, {})  # No endpoint may exist yet.
            if row.get("Attachable") or row.get("Ingress") or row.get("EnableIPv6"):
                raise ResourcesDenied()
        if acknowledgement is not None and acknowledgement != identity:
            raise ResourcesDenied()
        self._record("observe", spec, identity)
        self.observed[spec["name"]] = identity
        return identity

    def provision(self):
        if self.used or self.closed:
            raise ResourcesDenied()
        self.used = True
        try:
            # Durable intentions for ALL 33 objects precede even discovery.
            for spec in self.specs:
                self._record("reserve", spec)
            if (
                self.headroom() is not True
                or self.collision_check(tuple(n.subnet for n in self.layout.networks)) is not True
            ):
                raise ResourcesDenied()
            wanted = {s["name"] for s in self.specs}
            for kind in ("network", "volume"):
                existing = self.engine(kind, "ls", "--format", "{{.Name}}")
                if wanted.intersection(existing.splitlines()):
                    raise ResourcesDenied()
            for spec in self.specs:
                self.journal.check()
                if self.headroom() is not True:
                    raise ResourcesDenied()
                self.attempted.add(spec["name"])  # Before unknown daemon mutation.
                acknowledgement = self.engine(*self.create_arguments(spec)).strip()
                self._observe(spec, acknowledgement)
            return Inventory(
                self.layout.prefix,
                self.layout.images,
                self.layout.pins,
                tuple(
                    Network(n.edge, self.observed[f"{self.layout.prefix}-{n.edge}"], n.subnet)
                    for n in self.layout.networks
                ),
            )
        except Exception:
            self.closed = True
            with suppress(Exception):
                self.journal.fence()
            # Exact attempted UUID names/labels only. Inspection failure cannot
            # mean absence or release an UNKNOWN reservation. Never retry create.
            for spec in self.specs:
                if spec["name"] in self.attempted and spec["name"] not in self.observed:
                    with suppress(Exception):
                        self._observe(spec)
            raise ResourcesDenied() from None
