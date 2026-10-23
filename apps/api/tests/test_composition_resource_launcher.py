"""Provisioner -> same journal -> canonical launcher, with fake daemon metadata."""

import importlib
import json

import pytest
from composition_journal_fixture import implementation as ledger
from composition_launcher import Launcher
from test_composition_launcher import FakeDocker, plan

from ciq_api.offline_supervisor import Binding, inventory

resources = importlib.import_module(ledger.__package__ + ".composition_resources")


def test_complete_resources_feed_same_attempt_launcher_without_resetting_journal(tmp_path):
    p = plan()
    parent = tmp_path / "private"
    parent.mkdir(mode=0o700)
    journal = ledger.Journal(parent, p.prefix)
    fake = FakeDocker(p)
    created = set()

    def engine(*args):
        if args[:2] in {("network", "ls"), ("volume", "ls")}:
            return ""
        if args[:2] == ("network", "create"):
            row = next(row for row in fake.networks.values() if row["Name"] == args[-1])
            created.add(row["Name"])
            return row["Id"]
        if args[:2] == ("volume", "create"):
            created.add(args[-1])
            return args[-1]
        if args[:2] == ("network", "inspect") and args[-1].startswith(p.prefix):
            assert args[-1] in created
            return json.dumps([next(r for r in fake.networks.values() if r["Name"] == args[-1])])
        if args[:2] == ("volume", "inspect"):
            assert args[-1] in created
        return fake(*args)

    batch = resources.Resources(
        prefix=p.prefix,
        images=p.images,
        pins=p.pins,
        subnets={n.edge: n.subnet for n in p.networks},
        journal=journal,
        engine=engine,
        headroom=lambda: True,
        collision_check=lambda _: True,
    )
    result = batch.provision()
    assert [(n.edge, n.identifier) for n in result.networks] == [
        (n.edge, n.identifier) for n in p.networks
    ]
    launcher = Launcher(
        p,
        engine=engine,
        material_check=lambda *args: True,
        auxiliaries={"db": "f" * 64, "controller": "e" * 64},
        journal=journal,
    )
    fake.binding = Binding("disposable-attempt", p.generation, inventory(launcher.services))
    launcher(launcher.services[0], fake.binding)
    assert not launcher.cleanup(1_000_000_000)
    journal.close()
    recovery = ledger.inspect(journal.root)
    assert recovery.fenced and len(recovery.resources) == 41
    assert sum(r[-1] == "PRESENT" for r in recovery.resources) == 33
    assert sum(r[-1] == "STOPPED" for r in recovery.resources) == 1
    assert sum(r[-1] == "UNKNOWN" for r in recovery.resources) == 7


@pytest.mark.parametrize("fault", ["partial", "fenced", "wrong-id"])
def test_launcher_refuses_incomplete_fenced_or_mismatched_resource_journal(tmp_path, fault):
    p = plan()
    parent = tmp_path / "private"
    parent.mkdir(mode=0o700)
    journal = ledger.Journal(parent, p.prefix)
    for n in p.networks:
        name = f"{p.prefix}-{n.edge}"
        journal.record("reserve", kind="network", name=name, fingerprint="a" * 64)
        if fault != "partial":
            journal.record(
                "observe",
                kind="network",
                name=name,
                fingerprint="a" * 64,
                identity="f" * 64 if fault == "wrong-id" and n == p.networks[0] else n.identifier,
            )
    for role, _ in p.pins:
        if role == "controller":
            continue
        for kind in ("material",) if role == "membership" else ("material", "state"):
            name = p.volume(role, kind)
            journal.record("reserve", kind="volume", name=name, fingerprint="a" * 64)
            journal.record("observe", kind="volume", name=name, fingerprint="a" * 64, identity=name)
    if fault == "fenced":
        journal.fence()
    fake = FakeDocker(p)
    with pytest.raises(ValueError, match="must be fresh"):
        Launcher(
            p,
            engine=fake,
            material_check=lambda *args: True,
            auxiliaries={"db": "f" * 64, "controller": "e" * 64},
            journal=journal,
        )
    assert not fake.calls
    journal.close()
