"""Opt-in bounded host/Docker IPv4 collision gate; no allocation/free-pool search.

Snapshots are conservative admission evidence, not an atomic route reservation.
The trusted owner must keep the host/daemon stable throughout physical acceptance.
No namespace/label exception: existing owned networks also count as collisions.
"""

import json
import re
import sys
import time
from ipaddress import IPv4Network, ip_network
from pathlib import Path

from .bounded_composition_actor import BoundedActor

LIST = ("network", "ls", "--no-trunc", "--format", "{{.ID}}")
COMMANDS = (LIST, ("network", "inspect", "{network}"))


class RoutesDenied(ValueError):
    def __init__(self):
        super().__init__("Disposable network collision check denied")


def mac_routes(output):
    """Closed numeric `netstat -rn -f inet` format; default route is not a conflict."""
    if type(output) is not str or len(output) > 16384:
        raise RoutesDenied()
    lines = [line.split() for line in output.splitlines() if line.strip()]
    if (
        len(lines) < 4
        or lines[:2] != [["Routing", "tables"], ["Internet:"]]
        or lines[2] != ["Destination", "Gateway", "Flags", "Netif", "Expire"]
    ):
        raise RoutesDenied()
    result = set()
    for row in lines[3:]:
        if len(row) not in (4, 5) or "U" not in row[2]:
            raise RoutesDenied()
        destination = row[0]
        if destination == "default":
            continue
        # BSD abbreviates 10/8, 172.16/16, 192.168.1/24; explicit CIDRs
        # may abbreviate their address too. Reject rather than infer host bits.
        match = re.fullmatch(r"(\d+(?:\.\d+){0,3})(?:/(\d{1,2}))?", destination)
        if not match:
            raise RoutesDenied()
        address, bits = match.groups()
        parts = address.split(".")
        bits = int(bits) if bits is not None else len(parts) * 8
        try:
            result.add(IPv4Network(".".join(parts + ["0"] * (4 - len(parts))) + f"/{bits}"))
        except ValueError:
            raise RoutesDenied() from None
    if not result:
        raise RoutesDenied()
    return frozenset(result)


def host_routes(deadline_ns):
    """Mac collector remains the default; Linux selection is explicit."""
    return _collect(deadline_ns, ("/usr/sbin/netstat", "-rn", "-f", "inet"), mac_routes)


def linux_routes(output):
    """Numeric `ip -j -4 route show table all`, including local/VPN routes.

    Ignore only the explicit default route. Unknown, ambiguous, empty or
    noncanonical destinations deny rather than silently omit occupied ranges.
    """
    try:
        if type(output) is not str or len(output) > 16384:
            raise RoutesDenied()
        rows = json.loads(output, object_pairs_hook=_unique)
        if type(rows) is not list or not 1 <= len(rows) <= 256:
            raise RoutesDenied()
        result = set()
        for row in rows:
            if type(row) is not dict or type(row.get("dst")) is not str:
                raise RoutesDenied()
            destination = row["dst"]
            if destination == "default":
                continue
            network = IPv4Network(destination, strict=True)
            if destination not in {str(network), str(network.network_address)}:
                raise RoutesDenied()
            if network.prefixlen == 0:
                raise RoutesDenied()
            result.add(network)
        if not result:
            raise RoutesDenied()
        return frozenset(result)
    except Exception:
        raise RoutesDenied() from None


def linux_host_routes(deadline_ns):
    """Bounded Linux observation only; does not activate the full allocator."""
    return _collect(
        deadline_ns, ("/usr/sbin/ip", "-j", "-4", "route", "show", "table", "all"), linux_routes
    )


def _collect(deadline_ns, command, parser):
    """Bounded read-only host command with empty environment and no shell."""
    budget = min(2_000_000_000, deadline_ns - time.monotonic_ns() - 2_000_000_000)
    result = BoundedActor(
        (
            sys.executable,
            "-I",
            str(Path(__file__).with_name("composition_engine.py").resolve()),
            "--command",
            *command,
        ),
        budget_ns=budget,
        grace_ns=300_000_000,
    ).execute()
    if set(result) != {"output"}:
        raise RoutesDenied()
    return parser(result["output"])


def _ids(output):
    if type(output) is not str or len(output) > 16384:
        raise RoutesDenied()
    rows = output.splitlines()
    if (
        not 1 <= len(rows) <= 128
        or len(set(rows)) != len(rows)
        or any(re.fullmatch("[a-f0-9]{64}", row) is None for row in rows)
    ):
        raise RoutesDenied()
    return frozenset(rows)


def _unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise RoutesDenied()
        value[key] = item
    return value


class CollisionCheck:
    """Resources callback; engine must use COMMANDS and the same overall deadline.

    route_reader is injectable only for offline tests. Real collection defaults
    to bounded netstat. No cached success, own-network exemption or retry.
    """

    def __init__(self, engine, deadline_ns, *, route_reader=host_routes):
        self.engine, self.deadline_ns, self.route_reader = engine, deadline_ns, route_reader

    def __call__(self, subnets):
        try:
            if type(self.deadline_ns) is not int or time.monotonic_ns() >= self.deadline_ns:
                raise RoutesDenied()
            if type(subnets) is not tuple or len(subnets) != 18:
                raise RoutesDenied()
            proposed = tuple(IPv4Network(s) for s in subnets)
            if any(a.overlaps(b) for i, a in enumerate(proposed) for b in proposed[i + 1 :]):
                raise RoutesDenied()
            host = self.route_reader(self.deadline_ns)
            if (
                type(host) is not frozenset
                or not host
                or any(type(n) is not IPv4Network or n.prefixlen == 0 for n in host)
            ):
                raise RoutesDenied()
            existing = _ids(self.engine(*LIST))
            occupied = set(host)
            for identifier in sorted(existing):
                self.engine.permit_network(identifier)
                rows = json.loads(
                    self.engine("network", "inspect", identifier), object_pairs_hook=_unique
                )
                if (
                    type(rows) is not list
                    or len(rows) != 1
                    or type(rows[0]) is not dict
                    or rows[0].get("Id") != identifier
                ):
                    raise RoutesDenied()
                row = rows[0]
                configs = row["IPAM"]["Config"]
                # Docker Desktop represents the built-in host/none networks'
                # absent IPAM as null. Only these two non-IPAM drivers qualify.
                if configs is None and row.get("Driver") in {"host", "null"}:
                    configs = []
                if type(configs) is not list or len(configs) > 32:
                    raise RoutesDenied()
                if not configs and row.get("Driver") not in {"host", "null"}:
                    raise RoutesDenied()
                for config in configs:
                    subnet = ip_network(config["Subnet"])
                    if subnet.version == 4:
                        occupied.add(subnet)
            if (
                _ids(self.engine(*LIST)) != existing
                or self.route_reader(self.deadline_ns) != host
                or time.monotonic_ns() >= self.deadline_ns
                or any(p.overlaps(n) for p in proposed for n in occupied)
            ):
                raise RoutesDenied()
            return True
        except Exception:
            raise RoutesDenied() from None
