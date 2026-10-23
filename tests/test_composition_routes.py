"""Recorded route metadata/fake Docker only; no physical allocation."""

import json
import time
from ipaddress import IPv4Network

import pytest

from scripts.composition_routes import LIST, CollisionCheck, RoutesDenied, mac_routes

HEADER = "Routing tables\n\nInternet:\nDestination Gateway Flags Netif Expire\n"
SUBNETS = tuple(f"10.81.{i}.0/29" for i in range(1, 19))


def test_bsd_numeric_routes_expand_abbreviations_and_ignore_only_default():
    assert mac_routes(
        HEADER
        + "default 192.168.1.1 UG en0\n"
        + "127 127.0.0.1 UCS lo0\n"
        + "172.16/12 link#1 UCS en0 !\n"
        + "192.168.1 link#1 UCS en0 !\n"
        + "192.168.1.10 link#1 UH en0 42\n"
    ) == frozenset(
        IPv4Network(s)
        for s in ("127.0.0.0/8", "172.16.0.0/12", "192.168.1.0/24", "192.168.1.10/32")
    )


@pytest.mark.parametrize(
    "output",
    [
        "",
        HEADER,
        HEADER + "default 1 UG en0\n",
        HEADER + "10.81.1.1/29 link#1 U en0\n",
        HEADER + "10.81/8 link#1 U en0\n",
        HEADER + "private.host link#1 U en0\n",
        HEADER + "10.0.0.0/33 link#1 U en0\n",
        HEADER + "10.0.0.0 link#1 X en0\n",
        HEADER + "10.0.0.0\n",
        HEADER.replace("Internet:", "Internet6:") + "127 1 U lo0\n",
        HEADER + "x" * 17000,
        None,
    ],
)
def test_unknown_or_malformed_routes_deny(output):
    with pytest.raises(RoutesDenied):
        mac_routes(output)


class FakeEngine:
    def __init__(self):
        self.identifier = "a" * 64
        self.row = dict(
            Id=self.identifier, Driver="bridge", IPAM=dict(Config=[dict(Subnet="172.17.0.0/16")])
        )
        self.permitted, self.calls = [], []
        self.list_output = self.identifier + "\n"
        self.inspect_output = None
        self.changed = False

    def permit_network(self, identifier):
        self.permitted.append(identifier)

    def __call__(self, *args):
        self.calls.append(args)
        if args == LIST:
            if self.changed and self.permitted:
                return "b" * 64
            return self.list_output
        assert args == ("network", "inspect", self.identifier)
        return self.inspect_output if self.inspect_output is not None else json.dumps([self.row])


def gate(engine, routes=None):
    return CollisionCheck(
        engine,
        time.monotonic_ns() + 10_000_000_000,
        route_reader=lambda _: (
            frozenset([IPv4Network("192.168.1.0/24")]) if routes is None else routes
        ),
    )


def test_closed_read_only_scan_success_no_mutation_or_cached_approval():
    engine = FakeEngine()
    check = gate(engine)
    assert check(SUBNETS) is True
    assert engine.permitted == [engine.identifier]
    assert engine.calls == [LIST, ("network", "inspect", engine.identifier), LIST]
    engine.row["IPAM"]["Config"] = [dict(Subnet="10.0.0.0/8")]
    with pytest.raises(RoutesDenied):
        check(SUBNETS)


@pytest.mark.parametrize("subnet", ["10.0.0.0/8", "10.81.1.0/29", "10.81.1.2/32", "0.0.0.0/0"])
def test_docker_overlap_denies_including_supernet_and_host_route(subnet):
    engine = FakeEngine()
    engine.row["IPAM"]["Config"] = [dict(Subnet=subnet)]
    with pytest.raises(RoutesDenied):
        gate(engine)(SUBNETS)


def test_host_overlap_denies_without_label_or_namespace_exemption():
    with pytest.raises(RoutesDenied):
        gate(FakeEngine(), frozenset([IPv4Network("10.0.0.0/8")]))(SUBNETS)


@pytest.mark.parametrize("driver", ["host", "null"])
@pytest.mark.parametrize("config", [[], None])
def test_builtin_no_ipam_networks_accepted(driver, config):
    engine = FakeEngine()
    engine.row.update(Driver=driver, IPAM=dict(Config=config))
    assert gate(engine)(SUBNETS)


@pytest.mark.parametrize(
    "fault",
    [
        "empty",
        "duplicate",
        "short",
        "overflow",
        "identity",
        "missing",
        "bridge-empty",
        "config",
        "cidr",
        "json",
        "duplicate-key",
        "changed",
        "timeout",
    ],
)
def test_incomplete_changing_or_ambiguous_docker_observations_deny(fault):
    engine = FakeEngine()
    if fault == "empty":
        engine.list_output = ""
    elif fault == "duplicate":
        engine.list_output *= 2
    elif fault == "short":
        engine.list_output = "abcdef"
    elif fault == "overflow":
        engine.list_output = "\n".join(f"{i:064x}" for i in range(129))
    elif fault == "identity":
        engine.row["Id"] = "b" * 64
    elif fault == "missing":
        del engine.row["IPAM"]
    elif fault == "bridge-empty":
        engine.row["IPAM"]["Config"] = []
    elif fault == "config":
        engine.row["IPAM"]["Config"] = [None]
    elif fault == "cidr":
        engine.row["IPAM"]["Config"] = [dict(Subnet="10.81.1.1/29")]
    elif fault == "json":
        engine.inspect_output = "not json"
    elif fault == "duplicate-key":
        engine.inspect_output = '[{"Id":"x","Id":"y"}]'
    elif fault == "changed":
        engine.changed = True
    elif fault == "timeout":
        engine.permit_network = lambda _: (_ for _ in ()).throw(TimeoutError("private"))
    with pytest.raises(RoutesDenied, match=r"^Disposable network collision check denied$"):
        gate(engine)(SUBNETS)


def test_host_route_churn_and_expired_deadline_deny():
    engine = FakeEngine()
    check = gate(engine)
    rows = iter(
        [frozenset([IPv4Network("192.168.1.0/24")]), frozenset([IPv4Network("10.0.0.0/8")])]
    )
    check.route_reader = lambda _: next(rows)
    with pytest.raises(RoutesDenied):
        check(SUBNETS)
    engine.calls.clear()
    check.deadline_ns = time.monotonic_ns() - 1
    with pytest.raises(RoutesDenied):
        check(SUBNETS)
    assert not engine.calls


@pytest.mark.parametrize("proposed", [(), SUBNETS[:-1], list(SUBNETS), (*SUBNETS[:-1], SUBNETS[0])])
def test_invalid_proposed_layout_never_reads_engine(proposed):
    engine = FakeEngine()
    with pytest.raises(RoutesDenied):
        gate(engine)(proposed)
    assert not engine.calls


def test_host_collector_uses_fixed_bounded_empty_environment_command(monkeypatch):
    from scripts import composition_routes

    seen = {}

    class Actor:
        def __init__(self, command, **limits):
            seen.update(command=command, limits=limits)

        def execute(self):
            return {"output": HEADER + "127 127.0.0.1 U lo0\n"}

    monkeypatch.setattr(composition_routes, "BoundedActor", Actor)
    assert composition_routes.host_routes(time.monotonic_ns() + 10_000_000_000) == frozenset(
        [IPv4Network("127.0.0.0/8")]
    )
    assert seen["command"][1] == "-I"
    assert seen["command"][3:] == ("--command", "/usr/sbin/netstat", "-rn", "-f", "inet")
    assert seen["limits"] == dict(budget_ns=2_000_000_000, grace_ns=300_000_000)
