"""Inactive disposable eight-role launch inventory; no Docker/file/secret I/O.

Trusted test provisioning supplies UUID-owned network IDs/subnets, image digests
and public certificate pins. This module never discovers, allocates, provisions
or activates resources. It is not operational custody or image attestation.
"""

import json
import re
from dataclasses import dataclass
from hashlib import sha256
from ipaddress import IPv4Network
from types import MappingProxyType

LABEL = "cashlessiq.composition-test"
READERS = tuple(f"reader-{i}-{kind}" for i in (0, 1) for kind in ("nonclinical", "clinical"))
VALIDATORS = ("validator-0", "validator-1")
ROLES = ("membership", *VALIDATORS, *READERS, "broker")
AUDIENCES = {
    "broker": "broker",
    "membership": "membership:0",
    "controller": "controller",
    **{
        r: f"reader:{i}:" + ("medical" if r.endswith("-clinical") else "nonclinical")
        for i in (0, 1)
        for r in READERS
        if r.startswith(f"reader-{i}-")
    },
    **{r: f"validator:{i}" for i, r in enumerate(VALIDATORS)},
}
# Two broker-membership edges are distinct, despite the same endpoint roles.
EDGES = {
    **{
        f"broker-r{i}{k}": ("broker", f"reader-{i}-{kind}")
        for i in (0, 1)
        for k, kind in (("n", "nonclinical"), ("m", "clinical"))
    },
    **{
        f"r{i}{k}-validator": (f"reader-{i}-{kind}", f"validator-{i}")
        for i in (0, 1)
        for k, kind in (("n", "nonclinical"), ("m", "clinical"))
    },
    **{
        f"r{i}{k}-member": (f"reader-{i}-{kind}", "membership")
        for i in (0, 1)
        for k, kind in (("n", "nonclinical"), ("m", "clinical"))
    },
    **{f"v{i}-member": (f"validator-{i}", "membership") for i in (0, 1)},
    **{f"broker-member-{i}": ("broker", "membership") for i in (0, 1)},
    "member-db": ("membership", "db"),
    "controller-broker": ("controller", "broker"),
}
AUDIENCES = MappingProxyType(AUDIENCES)
EDGES = MappingProxyType(EDGES)


def _hex(value):
    return type(value) is str and re.fullmatch(r"[a-f0-9]{64}", value) is not None


def _require(condition):
    if not condition:
        raise ValueError("Disposable composition inventory denied")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


@dataclass(frozen=True)
class Network:
    edge: str
    identifier: str
    subnet: str


@dataclass(frozen=True)
class Inventory:
    """Pure public inventory; only UUID-owned test volume names, never host paths."""

    prefix: str
    images: tuple[tuple[str, str], ...]
    pins: tuple[tuple[str, str], ...]
    networks: tuple[Network, ...]
    generation: str = "disposable-v3-generation"

    def __post_init__(self):
        _require(type(self.prefix) is str and re.fullmatch(r"ciq-comp-[a-f0-9]{12}", self.prefix))
        _require(self.generation == "disposable-v3-generation")
        _require(type(self.images) is tuple and len(self.images) == 3)
        _require(all(type(item) is tuple and len(item) == 2 for item in self.images))
        _require({k for k, _ in self.images} == {"broker", "worker", "membership"})
        _require(
            all(type(v) is str and v.startswith("sha256:") and _hex(v[7:]) for _, v in self.images)
        )
        _require(len({v for _, v in self.images}) == 3)
        _require(type(self.pins) is tuple and len(self.pins) == 9)
        _require(all(type(item) is tuple and len(item) == 2 for item in self.pins))
        _require({k for k, _ in self.pins} == set(ROLES) | {"controller"})
        _require(all(_hex(v) for _, v in self.pins) and len({v for _, v in self.pins}) == 9)
        _require(type(self.networks) is tuple and len(self.networks) == 18)
        _require(all(type(n) is Network for n in self.networks))
        _require({n.edge for n in self.networks} == set(EDGES))
        _require(all(_hex(n.identifier) for n in self.networks))
        _require(len({n.identifier for n in self.networks}) == 18)
        subnets = []
        for n in self.networks:
            _require(type(n.subnet) is str)
            subnet = IPv4Network(n.subnet, strict=True)
            _require(str(subnet) == n.subnet and 16 <= subnet.prefixlen <= 29)
            _require(
                any(
                    subnet.subnet_of(IPv4Network(r))
                    for r in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
                )
            )
            _require(not any(subnet.overlaps(other) for other in subnets))
            subnets.append(subnet)

    def name(self, role):
        _require(role in set(ROLES) | {"controller", "db"})
        return f"{self.prefix}-{role}"

    def volume(self, role, kind):
        _require(role in ROLES and kind in {"material", "state"})
        _require(kind != "state" or role != "membership")
        return f"{self.name(role)}-{kind}"

    def database_volume(self, kind):
        _require(kind in {"material", "data"})
        return f"{self.name('db')}-{kind}"

    def check_database_volume(self, kind, row):
        _require(row["Name"] == self.database_volume(kind))
        _require(row["Driver"] == "local" and row["Scope"] == "local")
        _require(not row.get("Options"))
        _require(
            row["Labels"]
            == {
                LABEL: self.prefix,
                LABEL + ".role": "database",
                LABEL + ".kind": kind,
            }
        )

    def network(self, edge):
        _require(edge in EDGES)
        return next(n for n in self.networks if n.edge == edge)

    def address(self, edge, role):
        _require(edge in EDGES and role in EDGES[edge])
        network = self.network(edge)
        # Provisioner reserves gateway .1; endpoints .2/.3 are explicit, not DNS.
        return str(IPv4Network(network.subnet).network_address + 2 + EDGES[edge].index(role))

    def attachments(self, role):
        _require(role in set(ROLES) | {"controller", "db"})
        return tuple(
            (self.network(edge).identifier, self.address(edge, role))
            for edge in EDGES
            if role in EDGES[edge]
        )

    def config(self, role):
        _require(role in ROLES)
        pins = dict(self.pins)

        def target(edge, peer):
            return {"address": self.address(edge, peer), "pin": pins[peer]}

        if role == "broker":
            return dict(
                listen=self.address("controller-broker", "broker"),
                controller_pin=pins["controller"],
                readers={
                    AUDIENCES[f"reader-{i}-{kind}"]: target(f"broker-r{i}{k}", f"reader-{i}-{kind}")
                    for i in (0, 1)
                    for k, kind in (("n", "nonclinical"), ("m", "clinical"))
                },
                membership=[target(f"broker-member-{i}", "membership") for i in (0, 1)],
            )
        if role == "membership":
            worker_edges = [
                edge
                for edge, (left, right) in EDGES.items()
                if right == role and left in (*READERS, *VALIDATORS)
            ]
            return dict(
                listen=[self.address(edge, role) for edge in worker_edges],
                peers={pins[peer]: AUDIENCES[peer] for peer in (*READERS, *VALIDATORS)},
                broker=dict(
                    listen=[self.address(f"broker-member-{i}", role) for i in (0, 1)],
                    pin=pins["broker"],
                ),
            )
        if role in READERS:
            index = int(role.split("-")[1])
            kind = "m" if role.endswith("-clinical") else "n"
            return dict(
                role=role,
                listen=[self.address(f"broker-r{index}{kind}", role)],
                peers={pins["broker"]: "broker"},
                validator=target(f"r{index}{kind}-validator", f"validator-{index}"),
                membership=target(f"r{index}{kind}-member", "membership"),
            )
        index = int(role[-1])
        return dict(
            role=role,
            listen=[self.address(f"r{index}{kind}-validator", role) for kind in ("n", "m")],
            peers={
                pins[f"reader-{index}-{kind}"]: AUDIENCES[f"reader-{index}-{kind}"]
                for kind in ("nonclinical", "clinical")
            },
            membership=target(f"v{index}-member", "membership"),
        )

    def image(self, role):
        _require(role in ROLES)
        return dict(self.images)[role if role in {"broker", "membership"} else "worker"]

    def mounts(self, role):
        _require(role in ROLES)
        rows = [(self.volume(role, "material"), "/run/ciq", False)]
        if role != "membership":
            rows.append((self.volume(role, "state"), "/var/lib/ciq-replay", True))
        return tuple(rows)

    def memory(self, role):
        _require(role in ROLES)
        return (192 if role == "broker" else 128) * 1024**2

    def descriptor(self, role):
        return dict(
            role=role,
            name=self.name(role),
            image=self.image(role),
            own_pin=dict(self.pins)[role],
            generation=self.generation,
            config=self.config(role),
            attachments=self.attachments(role),
            network_specs=[
                (n.edge, n.identifier, n.subnet) for n in self.networks if role in EDGES[n.edge]
            ],
            mounts=self.mounts(role),
            memory=self.memory(role),
            cpu_nanos=500_000_000,
            pids=32,
            uid="10001:10001",
            readonly=True,
            tmpfs={"/tmp": "rw,noexec,nosuid,size=8m,mode=1777"},
        )

    def fingerprint(self, role):
        return sha256(canonical(self.descriptor(role))).hexdigest()

    def create_arguments(self, role):
        """Stopped container only; no volume/network creation or entrypoint override."""
        first_id, address = self.attachments(role)[0]
        args = [
            "create",
            "--name",
            self.name(role),
            "--label",
            f"{LABEL}={self.prefix}",
            "--label",
            f"{LABEL}.role={role}",
            "--network",
            first_id,
            "--ip",
            address,
            "--read-only",
            "--user",
            "10001:10001",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--memory",
            str(self.memory(role)),
            "--cpus",
            "0.5",
            "--pids-limit",
            "32",
            "--restart",
            "no",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=8m,mode=1777",
        ]
        for volume, destination, writable in self.mounts(role):
            args += [
                "--mount",
                f"type=volume,src={volume},dst={destination}" + ("" if writable else ",readonly"),
            ]
        return tuple([*args, self.image(role)])

    def check_volume(self, role, kind, row):
        _require(row["Name"] == self.volume(role, kind))
        _require(row["Driver"] == "local" and row["Scope"] == "local" and not row.get("Options"))
        _require(row.get("Labels", {}).get(LABEL) == self.prefix)
        _require(row["Labels"].get(f"{LABEL}.role") == role)
        _require(row["Labels"].get(f"{LABEL}.kind") == kind)

    def check_network(self, edge, row, owners):
        """owners is independently registered role -> full CID, never auto-adopted."""
        n = self.network(edge)
        _require(row["Id"] == n.identifier and row["Name"] == f"{self.prefix}-{edge}")
        _require(row.get("Labels", {}).get(LABEL) == self.prefix)
        _require(row["Labels"].get(f"{LABEL}.edge") == edge)
        _require(row["Driver"] == "bridge" and row["Internal"] is True and not row.get("Options"))
        _require(row["IPAM"]["Driver"] == "default")
        _require(
            row["IPAM"]["Config"]
            == [{"Subnet": n.subnet, "Gateway": str(IPv4Network(n.subnet).network_address + 1)}]
        )
        for cid, endpoint in row.get("Containers", {}).items():
            role = next((r for r, owned in owners.items() if owned == cid), None)
            _require(_hex(cid) and role in EDGES[edge])
            _require(endpoint["Name"] == self.name(role))
            _require(
                endpoint["IPv4Address"]
                == self.address(edge, role) + f"/{IPv4Network(n.subnet).prefixlen}"
            )

    def check_container(self, role, row, *, running):
        """Engine metadata check, not file custody, health or readiness attestation."""
        _require(type(running) is bool and _hex(row["Id"]))
        _require(row["Name"] == "/" + self.name(role) and row["Image"] == self.image(role))
        config, host, state = row["Config"], row["HostConfig"], row["State"]
        _require(config.get("Labels", {}).get(LABEL) == self.prefix)
        _require(config["Labels"].get(f"{LABEL}.role") == role and config["User"] == "10001:10001")
        _require(
            not config.get("OpenStdin") and not config.get("Tty") and not config.get("ExposedPorts")
        )
        _require(host["ReadonlyRootfs"] is True and host["Privileged"] is False)
        _require(host["CapDrop"] == ["ALL"] and not host.get("CapAdd") and not host.get("Devices"))
        _require(
            not any(
                host.get(k) for k in ("DeviceCgroupRules", "DeviceRequests", "Sysctls", "GroupAdd")
            )
        )
        _require(host["SecurityOpt"] == ["no-new-privileges"])
        _require(
            host["Memory"] == self.memory(role)
            and host["NanoCpus"] == 500_000_000
            and host["PidsLimit"] == 32
        )
        _require(host["RestartPolicy"] == {"Name": "no", "MaximumRetryCount": 0})
        _require(
            not host.get("PortBindings")
            and not host.get("PublishAllPorts")
            and not host.get("Binds")
        )
        _require(host.get("PidMode", "") == "" and host.get("IpcMode") == "private")
        _require(
            not host.get("VolumesFrom") and not host.get("Links") and not host.get("ExtraHosts")
        )
        _require(host["Tmpfs"] == {"/tmp": "rw,noexec,nosuid,size=8m,mode=1777"})
        _require(host["NetworkMode"] == self.attachments(role)[0][0])
        mounts = row["Mounts"]
        _require(len(mounts) == len(self.mounts(role)))
        _require(
            {(m["Name"], m["Destination"], m["RW"]) for m in mounts if m["Type"] == "volume"}
            == set(self.mounts(role))
        )
        attached = row["NetworkSettings"]["Networks"]
        _require(type(attached) is dict and len(attached) == len(self.attachments(role)))
        # Docker may leave the primary NetworkID empty until first start. Bind
        # its configured key to the already independently inspected plan; never
        # accept an empty ID after start or infer an arbitrary network identity.
        aliases = {
            alias: network.identifier
            for network in self.networks
            if role in EDGES[network.edge]
            for alias in (network.identifier, f"{self.prefix}-{network.edge}")
        }
        configured = set()
        for name, endpoint in attached.items():
            _require(name in aliases and type(endpoint) is dict)
            identifier = aliases[name]
            _require(
                endpoint["NetworkID"] == identifier or (not running and endpoint["NetworkID"] == "")
            )
            configured.add((identifier, endpoint["IPAMConfig"]["IPv4Address"]))
        _require(configured == set(self.attachments(role)))
        _require(
            state["Running"] is running
            and not state.get("Paused")
            and not state.get("Restarting")
            and not state.get("Dead")
        )
        _require(row.get("RestartCount", 0) == 0)
        _require(type(state["Pid"]) is int and state["Pid"] >= 0)
        if running:
            _require(type(state["Pid"]) is int and state["Pid"] > 0)
            _require(
                {(n["NetworkID"], n["IPAddress"]) for n in attached.values()}
                == set(self.attachments(role))
            )
        else:
            _require(state["Status"] == "created" and state["Pid"] == 0)
        return row["Id"]
