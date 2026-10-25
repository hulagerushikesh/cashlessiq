"""Provisioner -> same journal -> canonical launcher, with fake daemon metadata."""

import importlib
import json

import pytest
from composition_journal_fixture import implementation as ledger
from composition_launcher import Launcher
from test_composition_launcher import FakeDocker, plan

from ciq_api.offline_supervisor import Binding, inventory

resources = importlib.import_module(ledger.__package__ + ".composition_resources")


def provision(tmp_path, *, database=False):
    p = plan()
    parent = tmp_path / "private"
    parent.mkdir(mode=0o700)
    journal = ledger.Journal(parent, p.prefix)
    fake = FakeDocker(p)
    if database:
        for kind in ("material", "data"):
            name = p.database_volume(kind)
            fake.volumes[name] = dict(
                Name=name,
                Driver="local",
                Scope="local",
                Options={},
                Labels={
                    resources.LABEL: p.prefix,
                    resources.LABEL + ".role": "database",
                    resources.LABEL + ".kind": kind,
                },
            )
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
        database=database,
    )
    result = batch.provision()
    assert [(n.edge, n.identifier) for n in result.networks] == [
        (n.edge, n.identifier) for n in p.networks
    ]
    return p, journal, fake, engine


@pytest.mark.parametrize("database", [False, True])
def test_complete_resources_feed_same_attempt_launcher_without_resetting_journal(
    tmp_path, database
):
    p, journal, fake, engine = provision(tmp_path, database=database)
    launcher = Launcher(
        p,
        engine=engine,
        material_check=lambda *args: True,
        auxiliaries={"db": "f" * 64, "controller": "e" * 64},
        journal=journal,
        database=database,
    )
    fake.binding = Binding("disposable-attempt", p.generation, inventory(launcher.services))
    launcher(launcher.services[0], fake.binding)
    assert not launcher.cleanup(1_000_000_000)
    journal.close()
    recovery = ledger.inspect(journal.root)
    assert recovery.fenced and len(recovery.resources) == (43 if database else 41)
    assert sum(r[-1] == "PRESENT" for r in recovery.resources) == (35 if database else 33)
    assert sum(r[-1] == "STOPPED" for r in recovery.resources) == 1
    assert sum(r[-1] == "UNKNOWN" for r in recovery.resources) == 7


@pytest.mark.parametrize("database", [False, True])
def test_database_selection_must_match_observed_resource_batch(tmp_path, database):
    p, journal, fake, engine = provision(tmp_path, database=database)
    before = list(journal.events)
    fake.calls.clear()
    with pytest.raises(ValueError, match="must be fresh"):
        Launcher(
            p,
            engine=engine,
            material_check=lambda *args: True,
            auxiliaries={"db": "f" * 64, "controller": "e" * 64},
            journal=journal,
            database=not database,
        )
    assert journal.events == before and not fake.calls
    journal.close()


@pytest.mark.parametrize("empty", [False, True])
def test_database_requires_observed_resources_not_a_missing_or_header_only_journal(tmp_path, empty):
    p = plan()
    parent = tmp_path / "private"
    parent.mkdir(mode=0o700)
    journal = ledger.Journal(parent, p.prefix) if empty else None
    fake = FakeDocker(p)
    try:
        with pytest.raises(ValueError):
            Launcher(
                p,
                engine=fake,
                material_check=lambda *args: True,
                auxiliaries={"db": "f" * 64, "controller": "e" * 64},
                journal=journal,
                database=True,
            )
        assert not fake.calls
        if journal is not None:
            assert len(journal.events) == 1
    finally:
        if journal is not None:
            journal.close()


@pytest.mark.parametrize("kind", ["material", "data"])
@pytest.mark.parametrize("fault", ["foreign-label", "options", "missing"])
def test_database_volume_drift_prevents_application_creation(tmp_path, kind, fault):
    p, journal, fake, engine = provision(tmp_path, database=True)
    name = p.database_volume(kind)
    if fault == "foreign-label":
        fake.volumes[name]["Labels"][resources.LABEL] = "unrelated"
    elif fault == "options":
        fake.volumes[name]["Options"] = {"device": "/unapproved"}
    else:
        del fake.volumes[name]
    launcher = Launcher(
        p,
        engine=engine,
        material_check=lambda *args: True,
        auxiliaries={"db": "f" * 64, "controller": "e" * 64},
        journal=journal,
        database=True,
    )
    binding = Binding("disposable-attempt", p.generation, inventory(launcher.services))
    assert launcher.verify(launcher.services) is False
    with pytest.raises(ValueError, match="Disposable launch failed; stopped review required"):
        launcher(launcher.services[0], binding)
    assert not fake.rows and not any(call[0] == "create" for call in fake.calls)
    assert launcher.closed
    journal.close()
    recovery = ledger.inspect(journal.root)
    assert recovery.fenced
    # Preflight refusal must not turn observed DB volumes into stopped/removed.
    assert all(r[-1] == "PRESENT" for r in recovery.resources if r[0][0] != "container")


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
