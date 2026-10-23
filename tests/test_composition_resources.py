"""Real retained journals, fake engine/headroom/routes; no physical provisioning."""

import json
import sys
import time
from copy import deepcopy
from ipaddress import IPv4Network

import pytest

from scripts.composition_engine import Engine
from scripts.composition_inventory import EDGES, ROLES
from scripts.composition_journal import Journal, inspect
from scripts.composition_resources import Resources, ResourcesDenied
from scripts.composition_routes import LIST, CollisionCheck


def setup(tmp_path, *, fault=None, headroom=lambda: True, collision=lambda _: True):
    parent = tmp_path / "private"
    parent.mkdir(mode=0o700)
    journal = Journal(parent, "ciq-comp-abcdef123456")
    calls, rows = [], {}
    resource = None

    def engine(*args):
        # Every engine operation must have all intentions durably present first.
        assert len([e for e in journal.events if e.get("action") == "reserve"]) == 33
        calls.append(args)
        kind, operation = args[:2]
        if operation == "ls":
            return resource.specs[0]["name"] if fault == "existing" else ""
        spec = next(s for s in resource.specs if s["kind"] == kind and s["name"] == args[-1])
        name = spec["name"]
        if operation == "create":
            if kind == "network":
                row = dict(
                    Name=name,
                    Id=f"{100 + len(rows):064x}",
                    Labels=dict(spec["labels"]),
                    Driver="bridge",
                    Internal=True,
                    Options={},
                    Containers={},
                    IPAM=dict(
                        Driver="default",
                        Config=[
                            dict(
                                Subnet=spec["subnet"],
                                Gateway=str(IPv4Network(spec["subnet"]).network_address + 1),
                            )
                        ],
                    ),
                )
            else:
                row = dict(
                    Name=name,
                    Labels=dict(spec["labels"]),
                    Driver="local",
                    Scope="local",
                    Options={},
                )
            rows[name] = row
            if fault == "create-unknown":
                raise TimeoutError("private daemon detail")
            return row.get("Id", name)
        assert operation == "inspect"
        row = deepcopy(rows[name])
        if fault == "foreign":
            row["Labels"] = {}
        elif fault == "inspect-unknown":
            raise TimeoutError("private daemon detail")
        elif fault == "endpoint" and kind == "network":
            row["Containers"] = {"f" * 64: {}}
        elif fault == "external" and kind == "network":
            row["Internal"] = False
        elif fault == "options" or (fault == "volume-options" and kind == "volume"):
            row["Options"] = {"unapproved": "value"}
        elif fault == "ipv6" and kind == "network":
            row["EnableIPv6"] = True
        return json.dumps([row])

    resource = Resources(
        prefix=journal.root.name,
        images=tuple(
            (kind, "sha256:" + f"{i:064x}")
            for i, kind in enumerate(("worker", "membership", "broker"), 1)
        ),
        pins=tuple((role, f"{i:064x}") for i, role in enumerate((*ROLES, "controller"), 10)),
        subnets={edge: f"10.81.{i}.0/29" for i, edge in enumerate(EDGES, 1)},
        journal=journal,
        engine=engine,
        headroom=headroom,
        collision_check=collision,
    )
    return resource, journal, calls, rows


def recover(journal):
    journal.close()
    return inspect(journal.root)


def test_all_resources_observed_before_inventory_return_no_reuse(tmp_path):
    resource, journal, calls, rows = setup(tmp_path)
    assert not calls and len(journal.events) == 1
    plan = resource.provision()
    assert len(rows) == 33 and len(plan.networks) == 18
    assert all(n.identifier == rows[f"{plan.prefix}-{n.edge}"]["Id"] for n in plan.networks)
    assert all(call in resource.commands() for call in calls)
    with pytest.raises(ResourcesDenied):
        resource.provision()
    state = recover(journal)
    assert not state.fenced and len(state.resources) == 33
    assert {r[-1] for r in state.resources} == {"PRESENT"}
    assert not any(c[1] in {"rm", "prune"} for c in calls)


def test_provisioner_inventory_is_supported_by_bounded_transport_without_io(tmp_path):
    resource, journal, calls, _ = setup(tmp_path)
    engine = Engine(
        binary=sys.executable,
        socket=str(tmp_path / "unopened.sock"),
        config=tmp_path / "unopened-config",
        commands=resource.commands(),
        deadline_ns=time.monotonic_ns() + 10_000_000_000,
    )
    assert len(engine.commands) == 68 and not engine.fenced and not calls
    assert len(journal.events) == 1
    journal.close()


@pytest.mark.parametrize(
    "fault",
    ["create-unknown", "foreign", "inspect-unknown", "endpoint", "external", "options", "ipv6"],
)
def test_ambiguous_or_foreign_resources_fence_without_retry_or_removal(tmp_path, fault):
    resource, journal, calls, _ = setup(tmp_path, fault=fault)
    with pytest.raises(ResourcesDenied, match="retained resources"):
        resource.provision()
    assert resource.closed
    before = list(calls)
    with pytest.raises(ResourcesDenied):
        resource.provision()
    assert calls == before
    assert sum(c[1] == "create" for c in calls) == 1
    state = recover(journal)
    assert state.fenced and len(state.resources) == 33
    # Lost create ack may reconcile ONLY an exact independently observed object.
    assert sum(r[-1] == "PRESENT" for r in state.resources) == (fault == "create-unknown")
    assert all(r[-1] in {"PRESENT", "UNKNOWN"} for r in state.resources)


@pytest.mark.parametrize("gate", ["headroom", "collision", "existing"])
def test_preflight_refusal_never_mutates_engine(tmp_path, gate):
    resource, journal, calls, _ = setup(
        tmp_path,
        fault="existing" if gate == "existing" else None,
        headroom=lambda: gate != "headroom",
        collision=lambda _: gate != "collision",
    )
    with pytest.raises(ResourcesDenied):
        resource.provision()
    assert not any(c[1] == "create" for c in calls)
    state = recover(journal)
    assert state.fenced and {r[-1] for r in state.resources} == {"UNKNOWN"}


def test_headroom_deterioration_retains_preceding_objects(tmp_path):
    samples = iter([True, True, False])
    resource, journal, calls, _ = setup(tmp_path, headroom=lambda: next(samples))
    with pytest.raises(ResourcesDenied):
        resource.provision()
    assert sum(c[1] == "create" for c in calls) == 1
    state = recover(journal)
    assert sum(r[-1] == "PRESENT" for r in state.resources) == 1
    assert state.fenced


def test_failed_durable_reservation_prevents_all_engine_io(tmp_path, monkeypatch):
    resource, journal, calls, _ = setup(tmp_path)
    monkeypatch.setattr(
        journal, "record", lambda *a, **kw: (_ for _ in ()).throw(OSError("private"))
    )
    with pytest.raises(ResourcesDenied):
        resource.provision()
    assert not calls
    journal.close()


@pytest.mark.parametrize("conflict", [False, True])
def test_real_collision_gate_composes_with_provisioning_journal(tmp_path, conflict):
    class Metadata:
        def permit_network(self, identifier):
            assert identifier == "a" * 64

        def __call__(self, *args):
            if args == LIST:
                return "a" * 64
            return json.dumps(
                [
                    dict(
                        Id="a" * 64,
                        Driver="bridge",
                        IPAM=dict(Config=[dict(Subnet="172.17.0.0/16")]),
                    )
                ]
            )

    check = CollisionCheck(
        Metadata(),
        time.monotonic_ns() + 10_000_000_000,
        route_reader=lambda _: frozenset(
            [IPv4Network("10.0.0.0/8" if conflict else "192.168.1.0/24")]
        ),
    )
    resource, journal, calls, _ = setup(tmp_path, collision=check)
    if conflict:
        with pytest.raises(ResourcesDenied):
            resource.provision()
        assert not calls
        assert {r[-1] for r in recover(journal).resources} == {"UNKNOWN"}
    else:
        assert len(resource.provision().networks) == 18
        assert {r[-1] for r in recover(journal).resources} == {"PRESENT"}


def test_volume_options_refused_after_networks_without_fallback(tmp_path):
    resource, journal, calls, _ = setup(tmp_path, fault="volume-options")
    with pytest.raises(ResourcesDenied):
        resource.provision()
    assert sum(c[:2] == ("volume", "create") for c in calls) == 1
    state = recover(journal)
    assert state.fenced
    assert sum(r[-1] == "PRESENT" for r in state.resources) == 18
    assert all(r[-1] == "UNKNOWN" for r in state.resources if r[0][0] == "volume")


def test_observation_fsync_failure_never_allows_next_creation(tmp_path, monkeypatch):
    resource, journal, calls, _ = setup(tmp_path)
    write = journal._write

    def fail(data):
        if b'"action":"observe"' in data:
            raise OSError("private write detail")
        write(data)

    monkeypatch.setattr(journal, "_write", fail)
    with pytest.raises(ResourcesDenied):
        resource.provision()
    assert journal.failed and resource.closed
    assert sum(c[1] == "create" for c in calls) == 1
    state = recover(journal)
    assert {r[-1] for r in state.resources} == {"UNKNOWN"}
