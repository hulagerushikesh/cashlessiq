"""Real private journal + fake engine; no Docker or physical stop attestation."""

import pytest
from composition_journal_fixture import implementation as ledger
from composition_launcher import Launcher
from test_composition_launcher import FakeDocker, plan

from ciq_api.offline_supervisor import Binding, inventory


def setup(tmp_path):
    p = plan()
    parent = tmp_path.resolve() / "private"
    parent.mkdir(mode=0o700)
    journal = ledger.Journal(parent, p.prefix)
    engine = FakeDocker(p)
    instance = Launcher(
        p,
        engine=engine,
        material_check=lambda *args: True,
        auxiliaries={"controller": "e" * 64, "db": "f" * 64},
        journal=journal,
    )
    engine.binding = Binding("disposable-attempt", p.generation, inventory(instance.services))
    return instance, engine, journal


def recovery(journal):
    journal.close()
    result = ledger.inspect(journal.root)
    return result, {key[1]: (fp, cid, state) for key, fp, cid, state in result.resources}


def test_all_intentions_are_durable_before_first_engine_call(tmp_path):
    launcher, engine, journal = setup(tmp_path)
    assert not engine.calls
    result, resources = recovery(journal)
    assert not result.fenced and len(resources) == 8
    for role in launcher.plan.pins:
        if role[0] != "controller":
            assert resources[launcher.plan.name(role[0])] == (
                launcher.plan.fingerprint(role[0]),
                None,
                "UNKNOWN",
            )


def test_success_stop_is_recorded_only_after_observation_and_fence(tmp_path):
    launcher, engine, journal = setup(tmp_path)
    handles = [launcher(service, engine.binding) for service in launcher.services]
    assert all(handle.incarnation for handle in handles)
    assert launcher.cleanup(1_000_000_000)
    assert launcher.cleanup(1_000_000_000)  # No duplicate state transitions.
    journal.close()
    assert not launcher.cleanup(1_000_000_000)  # Cached fence is not writer validation.
    result, resources = recovery(journal)
    assert result.fenced and len(resources) == 8
    assert {row[2] for row in resources.values()} == {"STOPPED"}
    assert all(row[1] for row in resources.values())
    assert not any(call[0] in {"rm", "prune"} for call in engine.calls)


@pytest.mark.parametrize(
    ("fault", "state"),
    [
        ("create-unknown", "PRESENT"),
        ("inspect", "UNKNOWN"),
        ("foreign-owner", "UNKNOWN"),
        ("foreign-attempt", "UNKNOWN"),
        ("connect", "PRESENT"),
        ("start-unknown", "PRESENT"),
    ],
)
def test_launch_failure_retains_uncertainty_without_retry(tmp_path, fault, state):
    launcher, engine, journal = setup(tmp_path)
    engine.fault = fault
    with pytest.raises(ValueError, match="launch failed"):
        launcher(launcher.services[0], engine.binding)
    calls = list(engine.calls)
    with pytest.raises(ValueError, match="launch denied"):
        launcher(launcher.services[1], engine.binding)
    assert calls == engine.calls
    result, resources = recovery(journal)
    assert result.fenced
    assert resources[launcher.plan.name(launcher.services[0].role)][2] == state
    assert sum(row[2] == "UNKNOWN" for row in resources.values()) >= 7


def test_failed_stop_never_records_stopped(tmp_path):
    launcher, engine, journal = setup(tmp_path)
    launcher(launcher.services[0], engine.binding)
    engine.fault = "stop-unknown"
    assert not launcher.cleanup(1_000_000_000)
    result, resources = recovery(journal)
    assert result.fenced
    assert resources[launcher.plan.name(launcher.services[0].role)][2] == "PRESENT"


def test_closed_journal_prevents_create(tmp_path):
    launcher, engine, journal = setup(tmp_path)
    journal.close()
    # A closed journal must deny admission even though reservation succeeded.
    with pytest.raises(ValueError):
        launcher(launcher.services[0], engine.binding)
    assert not any(call[0] == "create" for call in engine.calls)


def test_journal_cannot_be_reused_by_another_launcher(tmp_path):
    launcher, engine, journal = setup(tmp_path)
    with pytest.raises(ValueError, match="must be fresh"):
        Launcher(
            launcher.plan,
            engine=engine,
            material_check=lambda *args: True,
            auxiliaries=launcher.auxiliaries,
            journal=journal,
        )
    assert not engine.calls
    journal.close()


def test_partial_launch_cleanup_does_not_erase_unresolved_reservations(tmp_path):
    launcher, engine, journal = setup(tmp_path)
    launcher(launcher.services[0], engine.binding)
    assert not launcher.cleanup(1_000_000_000)
    result, resources = recovery(journal)
    assert result.fenced
    assert sum(row[2] == "UNKNOWN" for row in resources.values()) == 7
    assert sum(row[2] == "STOPPED" for row in resources.values()) == 1


@pytest.mark.parametrize("stage", ["reserve", "observe", "stopped", "fence"])
def test_durable_write_failure_denies_progress_and_retains_resources(tmp_path, monkeypatch, stage):
    if stage == "reserve":
        p = plan()
        parent = tmp_path.resolve() / "private"
        parent.mkdir(mode=0o700)
        journal = ledger.Journal(parent, p.prefix)
        engine = FakeDocker(p)
        instance = None
    else:
        instance, engine, journal = setup(tmp_path)
        if stage in {"stopped", "fence"}:
            instance(instance.services[0], engine.binding)

    original = journal._write

    def fail_write(data):
        if b'"action":"' + stage.encode() + b'"' in data:
            raise OSError("private engine detail must not escape")
        original(data)

    monkeypatch.setattr(journal, "_write", fail_write)
    if stage == "reserve":
        with pytest.raises(ledger.JournalDenied) as error:
            Launcher(
                p,
                engine=engine,
                material_check=lambda *args: True,
                auxiliaries={"controller": "e" * 64, "db": "f" * 64},
                journal=journal,
            )
        assert "private engine detail" not in str(error.value)
        assert not engine.calls
    elif stage == "observe":
        with pytest.raises(ValueError, match="launch failed"):
            instance(instance.services[0], engine.binding)
        assert not any(c[0] == "start" or c[:2] == ("network", "connect") for c in engine.calls)
    else:
        assert not instance.cleanup(1_000_000_000)
        # Journal failure must not prevent containment of the exact known actor.
        assert engine.rows[instance.services[0].role]["State"]["Running"] is False
    assert journal.failed
    result, resources = recovery(journal)
    assert all(row[2] not in {"STOPPED", "REMOVED"} for row in resources.values())
    # Only the fence already persisted BEFORE a stopped-record failure survives.
    assert result.fenced is (stage == "stopped")


def test_replaced_journal_denies_before_any_engine_read(tmp_path):
    launcher, engine, journal = setup(tmp_path)
    record = journal.root / "events.jsonl"
    record.rename(journal.root / "retained.jsonl")
    record.write_bytes(b"replacement")
    with pytest.raises(ValueError, match="launch failed"):
        launcher(launcher.services[0], engine.binding)
    assert not engine.calls
    journal.close()


def test_foreign_journal_header_denies_without_engine_io(tmp_path):
    p = plan()
    parent = tmp_path.resolve() / "private"
    parent.mkdir(mode=0o700)
    journal = ledger.Journal(parent, "ciq-comp-111111111111")
    engine = FakeDocker(p)
    with pytest.raises(ValueError, match="must be fresh"):
        Launcher(
            p,
            engine=engine,
            material_check=lambda *args: True,
            auxiliaries={"controller": "e" * 64, "db": "f" * 64},
            journal=journal,
        )
    assert not engine.calls
    journal.close()
