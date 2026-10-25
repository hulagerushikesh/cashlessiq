"""Fake Docker observations/commands only: no containers, file material or watchdog."""

import json
from copy import deepcopy
from dataclasses import replace
from ipaddress import IPv4Network
from unittest.mock import Mock

import broker_composition_service
import pytest
from composition_inventory_fixture import implementation as inv
from composition_launcher import ENTRYPOINTS, Launcher
from composition_service_fixture import service as workers
from membership_composition_fixture import service as members

from ciq_api.offline_supervisor import (
    Binding,
    Limits,
    OfflineSupervisor,
    Ready,
    Sample,
    State,
    SupervisorDenied,
    inventory,
)


def plan():
    return inv.Inventory(
        "ciq-comp-0123456789ab",
        tuple(
            (kind, "sha256:" + f"{i:064x}")
            for i, kind in enumerate(("worker", "broker", "membership"), 1)
        ),
        tuple((role, f"{i:064x}") for i, role in enumerate((*inv.ROLES, "controller"), 10)),
        tuple(
            inv.Network(edge, f"{i:064x}", f"10.80.{i}.0/29") for i, edge in enumerate(inv.EDGES, 1)
        ),
    )


@pytest.mark.parametrize("role", inv.ROLES)
def test_created_network_metadata_uses_only_verified_aliases_until_live_id_exists(role):
    p = plan()
    binding = Binding("test-attempt", p.generation, "a" * 64)
    row = container(p, role, "d" * 64, binding)
    for network in row["NetworkSettings"]["Networks"].values():
        network["NetworkID"] = ""
    assert p.check_container(role, row, running=False) == "d" * 64
    row["State"].update(Running=True, Status="running", Pid=123)
    with pytest.raises(ValueError):
        p.check_container(role, row, running=True)


@pytest.mark.parametrize("fault", ["foreign-alias", "foreign-id", "wrong-ip", "duplicate-alias"])
def test_created_network_metadata_never_adopts_foreign_or_ambiguous_attachment(fault):
    p = plan()
    row = container(p, "membership", "d" * 64, Binding("test-attempt", p.generation, "a" * 64))
    attached = row["NetworkSettings"]["Networks"]
    key = next(iter(attached))
    endpoint = attached[key]
    endpoint["NetworkID"] = ""
    if fault == "foreign-alias":
        attached["foreign"] = attached.pop(key)
    elif fault == "foreign-id":
        endpoint["NetworkID"] = "f" * 64
    elif fault == "wrong-ip":
        endpoint["IPAMConfig"]["IPv4Address"] = "10.99.0.2"
    else:
        alias = next(f"{p.prefix}-{n.edge}" for n in p.networks if n.identifier == key)
        attached[alias] = attached.pop(next(k for k in attached if k != key))
    with pytest.raises(ValueError):
        p.check_container("membership", row, running=False)


def container(p, role, cid, binding, running=False):
    primary = p.attachments(role)[0][0]
    return dict(
        Id=cid,
        Name="/" + p.name(role),
        Image=p.image(role),
        RestartCount=0,
        Config=dict(
            Entrypoint=ENTRYPOINTS[role if role in {"broker", "membership"} else "worker"],
            Cmd=[],
            Env=[],
            User="10001:10001",
            Labels={
                inv.LABEL: p.prefix,
                inv.LABEL + ".role": role,
                inv.LABEL + ".attempt": binding.attempt,
                inv.LABEL + ".fingerprint": binding.fingerprint,
            },
            OpenStdin=False,
            Tty=False,
            ExposedPorts={},
        ),
        HostConfig=dict(
            NetworkMode=primary,
            ReadonlyRootfs=True,
            Privileged=False,
            CapDrop=["ALL"],
            CapAdd=[],
            SecurityOpt=["no-new-privileges"],
            Memory=p.memory(role),
            NanoCpus=500_000_000,
            PidsLimit=32,
            RestartPolicy=dict(Name="no", MaximumRetryCount=0),
            PortBindings={},
            PublishAllPorts=False,
            Binds=[],
            PidMode="",
            IpcMode="private",
            Tmpfs={"/tmp": "rw,noexec,nosuid,size=8m,mode=1777"},
        ),
        Mounts=[
            dict(Type="volume", Name=name, Destination=dest, RW=rw)
            for name, dest, rw in p.mounts(role)
        ],
        NetworkSettings=dict(
            Networks={
                identifier: dict(
                    NetworkID=identifier,
                    IPAMConfig=dict(IPv4Address=address),
                    IPAddress=address if running else "",
                )
                for identifier, address in p.attachments(role)
            }
        ),
        State=dict(
            Running=running,
            Status="running" if running else "created",
            Pid=123 if running else 0,
            Paused=False,
            Restarting=False,
            Dead=False,
        ),
    )


class FakeDocker:
    def __init__(self, p):
        self.p, self.calls, self.rows = p, [], {}
        self.binding = None
        self.fault = None
        self.networks = {
            n.identifier: dict(
                Id=n.identifier,
                Name=f"{p.prefix}-{n.edge}",
                Driver="bridge",
                Internal=True,
                Options={},
                Labels={inv.LABEL: p.prefix, inv.LABEL + ".edge": n.edge},
                IPAM=dict(
                    Driver="default",
                    Config=[
                        dict(
                            Subnet=n.subnet, Gateway=str(IPv4Network(n.subnet).network_address + 1)
                        )
                    ],
                ),
                Containers={},
            )
            for n in p.networks
        }
        self.volumes = {
            p.volume(role, kind): dict(
                Name=p.volume(role, kind),
                Driver="local",
                Scope="local",
                Options={},
                Labels={inv.LABEL: p.prefix, inv.LABEL + ".role": role, inv.LABEL + ".kind": kind},
            )
            for role in inv.ROLES
            for kind in (("material",) if role == "membership" else ("material", "state"))
        }

    def __call__(self, *args):
        self.calls.append(args)
        if args[:2] == ("image", "inspect"):
            kind = next(k for k, v in self.p.images if v == args[2])
            return json.dumps(
                [dict(Id=args[2], Config=dict(Entrypoint=ENTRYPOINTS[kind], Cmd=[], Env=[]))]
            )
        if args[:2] == ("network", "inspect"):
            return json.dumps([self.networks[args[2]]])
        if args[:2] == ("volume", "inspect"):
            return json.dumps([self.volumes[args[2]]])
        if args[:2] == ("container", "ls"):
            return "existing" if self.fault == "existing" else ""
        if args[0] == "create":
            role = next(r for r in inv.ROLES if self.p.name(r) == args[args.index("--name") + 1])
            cid = f"{100 + len(self.rows):064x}"
            row = container(self.p, role, cid, self.binding)
            # Retained even when the command loses its acknowledgement.
            self.rows[role] = row
            if self.fault == "create-unknown":
                raise TimeoutError("Fake Docker create completion unknown")
            return cid
        if args[:2] == ("network", "connect"):
            if self.fault == "connect":
                raise OSError("Fake attach failure")
            return ""
        if args[0] == "inspect":
            row = next(
                (r for role, r in self.rows.items() if args[1] in (r["Id"], self.p.name(role))),
                None,
            )
            if row is None or self.fault == "inspect":
                raise OSError("Fake observation unavailable")
            if self.fault == "foreign-owner":
                row = deepcopy(row)
                row["Config"]["Labels"][inv.LABEL] = "unrelated"
            if self.fault == "foreign-attempt":
                row = deepcopy(row)
                row["Config"]["Labels"][inv.LABEL + ".attempt"] = "old-attempt"
            if self.fault == "ports":
                row = deepcopy(row)
                row["HostConfig"]["PortBindings"] = {"8443/tcp": [dict(HostPort="8443")]}
            if self.fault in {"runtime-env", "runtime-command"}:
                row = deepcopy(row)
                row["Config"]["Env" if self.fault == "runtime-env" else "Cmd"] = ["unapproved"]
            return json.dumps([row])
        if args[0] == "start":
            row = next(r for r in self.rows.values() if r["Id"] == args[1])
            row["State"].update(Running=True, Status="running", Pid=123)
            for n in row["NetworkSettings"]["Networks"].values():
                n["IPAddress"] = n["IPAMConfig"]["IPv4Address"]
            if self.fault == "start-unknown":
                raise TimeoutError("Fake start completion unknown")
            return args[1]
        if args[0] == "stop":
            if self.fault == "stop-unknown":
                raise TimeoutError("Fake stop outcome unknown")
            row = next(r for r in self.rows.values() if r["Id"] == args[-1])
            row["State"].update(Running=False, Status="exited", Pid=0)
            return args[-1]
        raise AssertionError("Unexpected fake command")


def launcher():
    p = plan()
    engine = FakeDocker(p)
    materials = Mock(return_value=True)
    instance = Launcher(
        p,
        engine=engine,
        material_check=materials,
        auxiliaries={"controller": "e" * 64, "db": "f" * 64},
    )
    engine.binding = Binding("disposable-attempt", p.generation, inventory(instance.services))
    return instance, engine, materials


def test_generated_configs_match_all_three_real_service_parsers():
    p = plan()
    broker_composition_service.configuration(p.config("broker"))
    member = p.config("membership")
    worker_only = {k: member[k] for k in ("listen", "peers")}
    members.configuration(worker_only)
    members.broker_configuration(member["broker"], worker_only)
    for role in (*inv.READERS, *inv.VALIDATORS):
        workers.configuration(p.config(role))
    assert len(inv.EDGES) == 18
    assert len({name for role in inv.ROLES for name, _, _ in p.mounts(role)}) == 15
    assert len({p.volume(r, "state") for r in inv.ROLES if r != "membership"}) == 7
    assert all(
        not ({"broker", v} <= set(edge)) for v in inv.VALIDATORS for edge in inv.EDGES.values()
    )
    assert [e for e, pair in inv.EDGES.items() if "db" in pair] == ["member-db"]
    assert [e for e, pair in inv.EDGES.items() if "controller" in pair] == ["controller-broker"]
    raw = p.config("broker")
    raw["readers"].clear()
    assert len(p.config("broker")["readers"]) == 4  # Copies, not mutable trust state.


@pytest.mark.parametrize(
    "fault",
    [
        "prefix",
        "generation",
        "few-images",
        "mutable-image",
        "duplicate-image",
        "few-pins",
        "duplicate-pin",
        "foreign-pin",
        "few-networks",
        "duplicate-network",
        "public",
        "overlap",
        "unknown-edge",
    ],
)
def test_invalid_inventory_refuses_without_engine_calls(fault):
    p = plan()
    changes = {}
    if fault == "prefix":
        changes["prefix"] = "cashlessiq-product"
    elif fault == "generation":
        changes["generation"] = "operational"
    elif fault == "few-images":
        changes["images"] = p.images[:-1]
    elif fault == "mutable-image":
        changes["images"] = (list(p.images[0]), *p.images[1:])
    elif fault == "duplicate-image":
        changes["images"] = tuple((k, p.images[0][1]) for k, _ in p.images)
    elif fault == "few-pins":
        changes["pins"] = p.pins[:-1]
    elif fault == "duplicate-pin":
        changes["pins"] = tuple((k, "a" * 64) for k, _ in p.pins)
    elif fault == "foreign-pin":
        changes["pins"] = ((p.pins[0][0], "invalid"), *p.pins[1:])
    elif fault == "few-networks":
        changes["networks"] = p.networks[:-1]
    else:
        first = p.networks[0]
        if fault == "duplicate-network":
            value = replace(first, identifier=p.networks[1].identifier)
        elif fault == "public":
            value = replace(first, subnet="203.0.113.0/29")
        elif fault == "overlap":
            value = replace(first, subnet=p.networks[1].subnet)
        else:
            value = replace(first, edge="all-roles")
        changes["networks"] = (value, *p.networks[1:])
    with pytest.raises(ValueError):
        replace(p, **changes)


def test_construction_has_no_io_and_all_eight_launch_stop_by_full_incarnation():
    h, engine, materials = launcher()
    assert not engine.calls and not materials.called
    assert h.verify(h.services)
    handles = [h(service, engine.binding) for service in h.services]
    assert len({handle.incarnation for handle in handles}) == 8
    assert all(len(handle.incarnation) == 64 for handle in handles)
    for handle in handles:
        assert handle.stop(3_000_000_000)
    assert h.cleanup(3_000_000_000)
    assert all(row["State"]["Status"] == "exited" for row in engine.rows.values())
    assert not any(c[0] in {"rm", "run", "build", "prune"} for c in engine.calls)
    with pytest.raises(ValueError):
        h(h.services[0], engine.binding)


@pytest.mark.parametrize(
    "fault",
    [
        "existing",
        "create-unknown",
        "connect",
        "inspect",
        "ports",
        "start-unknown",
        "foreign-owner",
        "foreign-attempt",
        "runtime-env",
        "runtime-command",
    ],
)
def test_failed_launch_retains_exact_ownership_and_never_retries(fault):
    h, engine, _ = launcher()
    engine.fault = fault
    first = h.services[0]
    with pytest.raises(ValueError):
        h(first, engine.binding)
    assert first.role in h.attempted
    assert h.closed
    with pytest.raises(ValueError):
        h(h.services[1], engine.binding)  # No replacement work after a failed launch.
    with pytest.raises(ValueError):
        h(first, engine.binding)
    if fault == "existing":
        assert not h.owned and not any(c[0] in {"create", "start", "stop"} for c in engine.calls)
    elif fault in {"create-unknown", "connect", "ports", "start-unknown"}:
        assert first.role in h.owned
    engine.fault = None
    if fault != "existing":
        assert h.cleanup(3_000_000_000)
    assert not any(c[0] in {"rm", "prune"} for c in engine.calls)


@pytest.mark.parametrize("fault", ["unknown", "foreign-owner", "foreign-attempt"])
def test_unconfirmed_stop_retains_model_capacity_and_fence(fault):
    h, engine, _ = launcher()

    class Approval:
        def take(self, b):
            return b == engine.binding

        def current(self, b):
            return b == engine.binding

    c = OfflineSupervisor(
        h.services,
        Limits(10_000_000_000, 1_000_000_000, 3_000_000_000, 30_000_000_000, 1, 32),
        "fake-clock",
        approval=Approval(),
        verify=h.verify,
        launch=h,
        clock=lambda: Sample("fake-clock", 0),
        cancel=lambda *_: False,
        deliver=Mock(),
    )
    c.start(engine.binding.attempt)
    for s in h.services:
        c.acknowledge(Ready(c.binding, s, h.owned[s.role]))
    c.admit()
    engine.fault = "stop-unknown" if fault == "unknown" else fault
    c.stop()
    assert c.state is State.FENCED and c.active_count == 1
    assert len(h.owned) == 8
    with pytest.raises(SupervisorDenied):
        c.admit()
    engine.fault = None
    assert h.cleanup(3_000_000_000)
    c.stop()
    assert c.state is State.FENCED and c.active_count == 1  # Unknown operation is not cancelled.


@pytest.mark.parametrize("role", inv.ROLES)
@pytest.mark.parametrize(
    "field",
    [
        "mount",
        "network",
        "readonly",
        "privileged",
        "user",
        "restart",
        "socket",
        "port",
        "cpu",
        "incarnation",
    ],
)
def test_prestart_metadata_mismatch_denies_without_start(role, field):
    h, engine, _ = launcher()
    row = container(h.plan, role, "a" * 64, engine.binding)
    if field == "mount":
        row["Mounts"][0]["Name"] = h.plan.volume(
            "broker" if role != "broker" else "membership", "material"
        )
    elif field == "network":
        next(iter(row["NetworkSettings"]["Networks"].values()))["NetworkID"] = "f" * 64
    elif field == "readonly":
        row["HostConfig"]["ReadonlyRootfs"] = False
    elif field == "privileged":
        row["HostConfig"]["Privileged"] = True
    elif field == "user":
        row["Config"]["User"] = "0:0"
    elif field == "restart":
        row["HostConfig"]["RestartPolicy"]["Name"] = "always"
    elif field == "socket":
        row["Mounts"].append(
            dict(Type="bind", Name="socket", Destination="/var/run/docker.sock", RW=True)
        )
    elif field == "port":
        row["HostConfig"]["PortBindings"] = {"8443/tcp": []}
    elif field == "cpu":
        row["HostConfig"]["NanoCpus"] = 0
    else:
        row["Id"] = "invalid"
    with pytest.raises(ValueError):
        h.plan.check_container(role, row, running=False)
    assert not engine.calls


def test_material_or_resource_failure_cannot_launch():
    h, engine, materials = launcher()
    materials.return_value = False
    with pytest.raises(ValueError):
        h(h.services[0], engine.binding)
    assert not any(c[0] in {"create", "start"} for c in engine.calls)
    assert h.cleanup(3_000_000_000)


@pytest.mark.parametrize(
    "fault",
    [
        "image-id",
        "entrypoint",
        "extra-command",
        "external-network",
        "network-label",
        "network-gateway",
        "unregistered-container",
        "volume-driver",
        "volume-bind-option",
        "volume-owner",
        "volume-kind",
    ],
)
def test_resource_preflight_mismatch_prevents_create(fault):
    h, engine, _ = launcher()
    original = engine.__call__

    def tampered(*args):
        result = original(*args)
        if args[:2] == ("image", "inspect") and fault in {
            "image-id",
            "entrypoint",
            "extra-command",
        }:
            rows = json.loads(result)
            if fault == "image-id":
                rows[0]["Id"] = "sha256:" + "0" * 64
            elif fault == "entrypoint":
                rows[0]["Config"]["Entrypoint"] = ["python", "-m", "ciq_api.main"]
            else:
                rows[0]["Config"]["Cmd"] = ["unexpected"]
            return json.dumps(rows)
        if args[:2] == ("network", "inspect") and fault in {
            "external-network",
            "network-label",
            "network-gateway",
            "unregistered-container",
        }:
            rows = json.loads(result)
            row = rows[0]
            if fault == "external-network":
                row["Internal"] = False
            elif fault == "network-label":
                row["Labels"][inv.LABEL] = "unrelated"
            elif fault == "network-gateway":
                row["IPAM"]["Config"][0]["Gateway"] = "10.99.0.1"
            else:
                row["Containers"] = {"9" * 64: dict(Name="unrelated", IPv4Address="10.99.0.2/29")}
            return json.dumps(rows)
        if args[:2] == ("volume", "inspect") and fault.startswith("volume-"):
            rows = json.loads(result)
            row = rows[0]
            if fault == "volume-driver":
                row["Driver"] = "external"
            elif fault == "volume-bind-option":
                row["Options"] = {"type": "none", "o": "bind", "device": "/unrelated"}
            elif fault == "volume-owner":
                row["Labels"][inv.LABEL] = "unrelated"
            else:
                row["Labels"][inv.LABEL + ".kind"] = "other"
            return json.dumps(rows)
        return result

    h.engine = tampered
    assert not h.verify(h.services)
    with pytest.raises(ValueError):
        h(h.services[0], engine.binding)
    assert not any(c[0] in {"create", "start", "stop"} for c in engine.calls)


def test_descriptor_binds_own_public_pin_and_network_subnet():
    p = plan()
    changed = replace(
        p, pins=tuple((role, "8" * 64 if role == "broker" else pin) for role, pin in p.pins)
    )
    assert p.fingerprint("broker") != changed.fingerprint("broker")
    changed = replace(
        p,
        networks=tuple(
            replace(n, subnet="10.80.1.0/28") if n.edge == p.networks[0].edge else n
            for n in p.networks
        ),
    )
    assert p.fingerprint("broker") != changed.fingerprint("broker")


@pytest.mark.parametrize("fault", ["foreign-owner", "foreign-attempt", "inspect"])
def test_uncertain_identity_is_never_stopped_or_removed(fault):
    h, engine, _ = launcher()
    handle = h(h.services[0], engine.binding)
    engine.fault = fault
    before = len(engine.calls)
    assert handle.stop(3_000_000_000) is False
    assert not any(c[0] in {"stop", "rm"} for c in engine.calls[before:])
    assert handle.incarnation in h.owned.values()
