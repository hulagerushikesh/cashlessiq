"""Journaled state helper orchestration with fake daemon metadata only."""

from copy import deepcopy

import pytest
from test_composition_helpers import CHANGES, containment_engine, setup

from scripts.composition_helpers import HelpersDenied
from scripts.composition_inventory import ROLES
from scripts.composition_journal import fold
from scripts.composition_state_helpers import StateHelpers


@pytest.mark.parametrize("role", [role for role in ROLES if role != "membership"])
def test_seven_roles_require_separate_nonroot_rw_probe(tmp_path, role):
    helper, engine, journal, resources = setup(tmp_path, role, state=True)
    try:
        before = deepcopy(resources.events)
        assert helper.run()
        assert resources.events == before
        assert helper.modes == ("initialize", "verify")
        for mode in helper.modes:
            args = helper.create(mode)
            assert args[-1] == mode and ",readonly" not in args[args.index("--mount") + 1]
            assert "dst=/var/lib/ciq-replay" in args[args.index("--mount") + 1]
            assert args[args.index("--user") + 1] == (
                "0:0" if mode == "initialize" else "10001:10001"
            )
            assert ("--cap-add" in args) is (mode == "initialize")
        _, rows, fenced = fold(journal.events)
        assert not fenced and len(rows) == 2
        assert all(row[2] == "STOPPED" for row in rows.values())
        assert len([a for a in engine.calls if a[0] == "start"]) == 2
        assert helper.contain()
        with pytest.raises(HelpersDenied):
            helper.run()
    finally:
        journal.close()
        resources.close()


@pytest.mark.parametrize(
    "fault",
    [
        *CHANGES,
        "collision",
        "unknown-create",
        "unknown-start",
        "nonzero",
        "running",
        "receipt",
        "duplicate-json",
        "verify-root",
        "verify-capability",
        "verify-extra-mount",
        "verify-readonly",
        "generation",
    ],
)
def test_state_uncertainty_denies_without_retry_or_adoption(tmp_path, fault, capsys):
    helper, engine, journal, resources = setup(tmp_path, fault=fault, state=True)
    try:
        with pytest.raises(HelpersDenied):
            helper.run()
        assert engine.fenced and fold(journal.events)[2]
        assert any(row[2] != "STOPPED" for row in fold(journal.events)[1].values())
        starts = [a for a in engine.calls if a[0] == "start"]
        assert len(starts) <= (1 if not fault.startswith("verify-") else 2)
        assert not any(a[0] in {"rm", "exec", "run", "stop"} for a in engine.calls)
        assert capsys.readouterr() == ("", "")
        with pytest.raises(HelpersDenied):
            helper.run()
        assert starts == [a for a in engine.calls if a[0] == "start"]
    finally:
        journal.close()
        resources.close()


@pytest.mark.parametrize("failure", ["headroom", "resource-fenced"])
def test_state_preconditions_do_no_engine_work(tmp_path, failure):
    helper, engine, journal, resources = setup(tmp_path, state=True)
    try:
        if failure == "headroom":
            helper.headroom = lambda: False
        else:
            resources.fence()
        with pytest.raises(HelpersDenied):
            helper.run()
        assert not engine.calls and fold(journal.events)[2]
    finally:
        journal.close()
        resources.close()


@pytest.mark.parametrize("fault", ["unknown-create", "unknown-start", "nonzero", "receipt"])
def test_failed_state_helpers_keep_unattempted_verifier_unknown(tmp_path, fault):
    helper, engine, journal, resources = setup(tmp_path, fault=fault, state=True)
    try:
        with pytest.raises(HelpersDenied):
            helper.run()
        containment_engine(helper, engine)
        assert not helper.contain()
        rows = fold(journal.events)[1]
        assert rows[("container", helper.name("verify"))][2] == "UNKNOWN"
        assert rows[("container", helper.name("initialize"))][2] == (
            "UNKNOWN" if fault == "unknown-create" else "STOPPED"
        )
        assert not any(a[0] in {"rm", "exec", "run", "stop"} for a in engine.calls)
    finally:
        journal.close()
        resources.close()


@pytest.mark.parametrize("lost_stop", [False, True])
def test_state_containment_requires_fresh_exact_exit(tmp_path, lost_stop):
    helper, engine, journal, resources = setup(tmp_path, state=True)
    try:
        assert helper.run()
        for row in engine.rows.values():
            row["State"].update(Status="running", Running=True, Pid=99)
        containment_engine(helper, engine, lost_stop=lost_stop)
        assert helper.contain()
        assert len([a for a in engine.calls if a[0] == "stop"]) == 2
        assert all(row[2] == "STOPPED" for row in fold(journal.events)[1].values())
    finally:
        journal.close()
        resources.close()


@pytest.mark.parametrize("role", ["membership", "reader", "validator", "unknown"])
def test_unknown_or_membership_roles_cannot_acquire_state_authority(tmp_path, role):
    material, engine, journal, resources = setup(tmp_path)
    try:
        with pytest.raises(HelpersDenied):
            StateHelpers(
                material.plan,
                role,
                image=material.image,
                journal=journal,
                resources=resources,
                engine=engine,
                headroom=lambda: True,
            )
        assert not engine.calls and len(journal.events) == 1
    finally:
        journal.close()
        resources.close()


def test_material_volume_intention_cannot_authorize_state_volume(tmp_path):
    material, engine, journal, resources = setup(tmp_path)
    try:
        with pytest.raises(HelpersDenied):
            StateHelpers(
                material.plan,
                "broker",
                image=material.image,
                journal=journal,
                resources=resources,
                engine=engine,
                headroom=lambda: True,
            )
        assert not engine.calls and len(journal.events) == 1
    finally:
        journal.close()
        resources.close()


def test_state_headroom_rechecked_before_verifier(tmp_path):
    checks = iter([True, True, False])
    helper, engine, journal, resources = setup(tmp_path, state=True, headroom=lambda: next(checks))
    try:
        with pytest.raises(HelpersDenied):
            helper.run()
        assert len([a for a in engine.calls if a[0] == "create"]) == 1
        assert len([a for a in engine.calls if a[0] == "start"]) == 1
        assert fold(journal.events)[2]
    finally:
        journal.close()
        resources.close()


@pytest.mark.parametrize("damage", ["readonly", "foreign-mount", "journal"])
def test_state_containment_denies_uncertainty_and_checks_other_helper(tmp_path, damage):
    helper, engine, journal, resources = setup(tmp_path, state=True)
    try:
        assert helper.run()
        for row in engine.rows.values():
            row["State"].update(Status="running", Running=True, Pid=99)
        cid = helper.owned["initialize"]
        if damage == "readonly":
            engine.rows[cid]["Mounts"][0]["RW"] = False
        elif damage == "foreign-mount":
            engine.rows[cid]["Mounts"][0]["Name"] = "foreign"
        else:
            journal.failed = True
        containment_engine(helper, engine)
        assert not helper.contain()
        stopped = [args[-1] for args in engine.calls if args[0] == "stop"]
        assert helper.owned["verify"] in stopped
        assert (cid in stopped) is (damage == "journal")
    finally:
        journal.close()
        resources.close()
