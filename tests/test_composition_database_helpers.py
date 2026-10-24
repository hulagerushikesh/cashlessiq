"""DB coordinator against fake daemon observations, never physical acceptance."""

import pytest
from test_composition_helpers import CHANGES, containment_engine, setup

from scripts.composition_helpers import HelpersDenied
from scripts.composition_journal import fold


def test_db_install_requires_separate_readonly_nonroot_probe(tmp_path):
    helper, _engine, journal, resources = setup(tmp_path, database=True)
    try:
        assert helper.run()
        for mode in helper.modes:
            args = helper.create(mode)
            assert args[args.index("--user") + 1] == ("0:0" if mode == "install" else "10002:10002")
            mount = args[args.index("--mount") + 1]
            assert "dst=/database-material" in mount
            assert mount.endswith(",readonly") is (mode == "verify")
            assert ("--cap-add" in args) is (mode == "install")
        assert all(row[2] == "STOPPED" for row in fold(journal.events)[1].values())
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
        "unknown-create",
        "unknown-start",
        "receipt",
        "nonzero",
        "running",
        "collision",
        "duplicate-json",
        "verify-root",
        "verify-capability",
        "verify-extra-mount",
    ],
)
def test_db_uncertainty_fences_without_retry_or_adoption(tmp_path, fault):
    helper, engine, journal, resources = setup(tmp_path, database=True, fault=fault)
    try:
        with pytest.raises(HelpersDenied):
            helper.run()
        assert engine.fenced and fold(journal.events)[2]
        assert not any(a[0] in {"rm", "exec", "run", "stop"} for a in engine.calls)
        with pytest.raises(HelpersDenied):
            helper.run()
    finally:
        journal.close()
        resources.close()


@pytest.mark.parametrize("fault", ["unknown-create", "unknown-start"])
def test_db_unknown_attempt_never_becomes_verified_by_containment(tmp_path, fault):
    helper, engine, journal, resources = setup(tmp_path, database=True, fault=fault)
    try:
        with pytest.raises(HelpersDenied):
            helper.run()
        containment_engine(helper, engine)
        assert not helper.contain()
        rows = fold(journal.events)[1]
        assert rows[("container", helper.name("verify"))][2] == "UNKNOWN"
        assert rows[("container", helper.name("install"))][2] == (
            "UNKNOWN" if fault == "unknown-create" else "STOPPED"
        )
    finally:
        journal.close()
        resources.close()


@pytest.mark.parametrize("failure", ["headroom", "resources", "binding"])
def test_db_preconditions_deny_before_engine_mutation(tmp_path, failure):
    helper, engine, journal, resources = setup(tmp_path, database=True)
    try:
        if failure == "headroom":
            helper.headroom = lambda: False
        elif failure == "resources":
            resources.fence()
        else:
            (helper.staged.root / "server.key").chmod(0o444)
        with pytest.raises(HelpersDenied):
            helper.run()
        assert not any(a[0] == "create" for a in engine.calls)
    finally:
        journal.close()
        resources.close()


@pytest.mark.parametrize("failure", ["wrong-volume", "wrong-binding"])
def test_constructor_requires_database_specific_authority(tmp_path, failure):
    from dataclasses import replace

    from scripts.composition_database_helpers import DatabaseHelpers
    from scripts.composition_journal import Journal

    helper, engine, journal, resources = setup(tmp_path, database=True)
    extra = None
    try:
        staged = helper.staged
        authority = resources
        if failure == "wrong-binding":
            staged = replace(staged, expected=replace(staged.expected, fingerprint="f" * 64))
        else:
            parent = tmp_path / "other-resources"
            parent.mkdir(mode=0o700)
            extra = authority = Journal(parent, helper.plan.prefix)
            volume = helper.plan.volume("membership", "material")
            for action in ("reserve", "observe"):
                authority.record(
                    action,
                    kind="volume",
                    name=volume,
                    identity=volume if action == "observe" else None,
                    fingerprint="e" * 64,
                )
        with pytest.raises(HelpersDenied):
            DatabaseHelpers(
                helper.plan,
                staged,
                image=helper.image,
                journal=journal,
                resources=authority,
                engine=engine,
                headroom=lambda: True,
            )
        assert not engine.calls and len(journal.events) == 1
    finally:
        if extra:
            extra.close()
        journal.close()
        resources.close()
