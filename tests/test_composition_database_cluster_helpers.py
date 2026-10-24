"""Two-volume initdb coordinator against fake daemon metadata only."""

import pytest
from test_composition_helpers import CHANGES, setup

from scripts.composition_helpers import HelpersDenied
from scripts.composition_journal import fold


def test_two_mount_nonroot_initializer_and_readonly_probe(tmp_path):
    helper, _engine, journal, resources = setup(tmp_path, database_cluster=True)
    try:
        assert helper.run()
        for mode in helper.modes:
            args = helper.create(mode)
            assert args[args.index("--user") + 1] == "10002:10002"
            assert "--cap-add" not in args
            mounts = [args[i + 1] for i, arg in enumerate(args) if arg == "--mount"]
            assert len(mounts) == 2
            assert mounts[0].endswith("dst=/database-material,readonly")
            assert mounts[1].endswith(",readonly") is (mode == "verify")
        assert all(row[2] == "STOPPED" for row in fold(journal.events)[1].values())
    finally:
        journal.close()
        resources.close()


@pytest.mark.parametrize(
    "fault",
    [
        *[f for f in CHANGES if f != "readonly"],
        "unknown-create",
        "unknown-start",
        "receipt",
        "nonzero",
        "running",
        "collision",
        "duplicate-json",
        "verify-root",
        "verify-capability",
    ],
)
def test_cluster_uncertainty_fences(tmp_path, fault):
    helper, engine, journal, resources = setup(tmp_path, database_cluster=True, fault=fault)
    try:
        with pytest.raises(HelpersDenied):
            helper.run()
        assert engine.fenced and fold(journal.events)[2]
        assert not any(call[0] in {"rm", "exec", "run", "stop"} for call in engine.calls)
    finally:
        journal.close()
        resources.close()


@pytest.mark.parametrize(
    "fault", ["material-writable", "data-foreign", "data-missing", "duplicate-destination"]
)
def test_both_mounts_are_independently_checked(tmp_path, fault):
    from test_composition_helpers import container

    helper, _engine, journal, resources = setup(tmp_path, database_cluster=True)
    try:
        helper.owned["initialize"] = "a" * 64
        helper.config = {"Env": ["PYTHONUNBUFFERED=1"]}
        row = container(helper, "initialize", "a" * 64)
        if fault == "material-writable":
            row["Mounts"][0]["RW"] = True
        elif fault == "data-foreign":
            row["Mounts"][1]["Name"] = "foreign"
        elif fault == "data-missing":
            row["Mounts"].pop()
        else:
            row["Mounts"][1]["Destination"] = "/database-material"
        with pytest.raises(HelpersDenied):
            helper._check(row, "initialize")
    finally:
        journal.close()
        resources.close()
