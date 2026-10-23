"""Real private files/process death, no Docker or engine attestation."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.bounded_composition_actor import ActorDenied, BoundedActor
from scripts.composition_journal import Journal, JournalDenied, inspect
from scripts.composition_material import ROLES

PREFIX = "ciq-comp-abcdef123456"
FP = "a" * 64
CID = "b" * 64
NAME = PREFIX + "-broker"


def create(tmp_path):
    parent = tmp_path / "private"
    parent.mkdir(mode=0o700)
    return Journal(parent, PREFIX)


def record(journal, action="reserve", kind="container", identity=None, **kwargs):
    journal.record(action, kind=kind, name=NAME, identity=identity, fingerprint=FP, **kwargs)


@pytest.mark.parametrize("kind", ["container", "network", "volume", "image"])
def test_reservation_and_exact_lifecycle_persist(tmp_path, kind):
    journal = create(tmp_path)
    identity = NAME if kind == "volume" else "sha256:" + CID if kind == "image" else CID
    record(journal, kind=kind)
    record(journal, "observe", kind, identity)
    if kind == "container":
        record(journal, "stopped", kind, identity)
    record(journal, "removed", kind, identity)
    root = journal.root
    journal.close()
    recovered = inspect(root)
    assert recovered.resources == (((kind, NAME), FP, identity, "REMOVED"),)
    assert recovered.prefix == PREFIX and not recovered.fenced
    assert root.stat().st_mode & 0o777 == 0o700
    assert (root / "events.jsonl").stat().st_mode & 0o777 == 0o600


def test_independent_recovery_after_abrupt_writer_death(tmp_path):
    parent = tmp_path / "private"
    parent.mkdir(mode=0o700)
    code = (
        "import os; from pathlib import Path; "
        "from scripts.composition_journal import Journal; "
        f"j=Journal(Path({str(parent)!r}), {PREFIX!r}); "
        f"j.record('reserve',kind='container',name={NAME!r},fingerprint={FP!r}); "
        "os._exit(7)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).resolve().parents[1],
        env={},
        capture_output=True,
        timeout=5,
    )
    assert result.returncode == 7 and result.stdout == result.stderr == b""
    snapshot = inspect(parent / PREFIX)
    assert snapshot.resources == ((("container", NAME), FP, None, "UNKNOWN"),)
    assert not snapshot.fenced  # UNKNOWN still requires reconciliation, not absence.
    with pytest.raises(JournalDenied):
        Journal(parent, PREFIX)  # No reuse/replacement writer, even after death.


def test_fence_retained_but_observations_can_be_recorded(tmp_path):
    journal = create(tmp_path)
    record(journal)
    journal.fence()
    record(journal, "observe", identity=CID)
    record(journal, "stopped", identity=CID)
    journal.close()
    assert inspect(journal.root).fenced


@pytest.mark.parametrize(
    "fault",
    [
        "duplicate",
        "foreign-name",
        "bad-kind",
        "bad-fingerprint",
        "unknown-observe",
        "changed-id",
        "remove-running",
        "observe-twice",
        "reserve-fenced",
        "fence-twice",
    ],
)
def test_invalid_transition_permanently_closes_writer(tmp_path, fault):
    journal = create(tmp_path)
    record(journal)
    if fault in {"changed-id", "remove-running", "observe-twice"}:
        record(journal, "observe", identity=CID)
    if fault in {"reserve-fenced", "fence-twice"}:
        journal.fence()
    actions = {
        "duplicate": lambda: record(journal),
        "foreign-name": lambda: journal.record(
            "reserve", kind="volume", name="unrelated", fingerprint=FP
        ),
        "bad-kind": lambda: record(journal, kind="secret"),
        "bad-fingerprint": lambda: journal.record(
            "reserve", kind="volume", name=NAME, fingerprint="private-payload"
        ),
        "unknown-observe": lambda: journal.record(
            "observe", kind="volume", name=NAME, identity=NAME, fingerprint=FP
        ),
        "changed-id": lambda: record(journal, "stopped", identity="c" * 64),
        "remove-running": lambda: record(journal, "removed", identity=CID),
        "observe-twice": lambda: record(journal, "observe", identity=CID),
        "reserve-fenced": lambda: record(journal, kind="volume"),
        "fence-twice": journal.fence,
    }
    before = (journal.root / "events.jsonl").read_bytes()
    with pytest.raises(JournalDenied, match="retained resources"):
        actions[fault]()
    with pytest.raises(JournalDenied):
        journal.fence()
    assert (journal.root / "events.jsonl").read_bytes() == before
    journal.close()


@pytest.mark.parametrize(
    "fault",
    [
        "truncated",
        "duplicate-json",
        "mode",
        "hardlink",
        "symlink",
        "fifo",
        "extra",
        "root-mode",
        "root-symlink",
    ],
)
def test_corrupt_or_insecure_recovery_never_repairs(tmp_path, fault):
    journal = create(tmp_path)
    record(journal)
    journal.close()
    path = journal.root / "events.jsonl"
    if fault == "truncated":
        path.write_bytes(path.read_bytes()[:-1])
    elif fault == "duplicate-json":
        path.write_bytes(b'{"version":1,"version":1,"prefix":"' + PREFIX.encode() + b'"}\n')
    elif fault == "mode":
        path.chmod(0o644)
    elif fault == "hardlink":
        os.link(path, tmp_path / "alias")
    elif fault in {"symlink", "fifo"}:
        path.unlink()
        if fault == "symlink":
            path.symlink_to(tmp_path / "not-owned")
        else:
            os.mkfifo(path, 0o600)
    elif fault == "extra":
        (journal.root / "extra").touch()
    elif fault == "root-mode":
        journal.root.chmod(0o755)
    else:
        moved = journal.root.with_name("moved")
        journal.root.rename(moved)
        journal.root.symlink_to(moved, target_is_directory=True)
    with pytest.raises(JournalDenied):
        inspect(journal.root)


def test_reader_denied_while_writer_holds_lock(tmp_path):
    journal = create(tmp_path)
    try:
        with pytest.raises(JournalDenied):
            inspect(journal.root)
    finally:
        journal.close()
    assert inspect(journal.root).resources == ()


def test_partial_append_failure_retains_unknown_and_prevents_retry(tmp_path, monkeypatch):
    journal = create(tmp_path)
    record(journal)
    real_write = os.write

    def broken(fd, data):
        real_write(fd, data[:12])
        raise OSError("private engine error must not escape")

    monkeypatch.setattr(os, "write", broken)
    with pytest.raises(JournalDenied):
        record(journal, "observe", identity=CID)
    monkeypatch.setattr(os, "write", real_write)
    with pytest.raises(JournalDenied):
        journal.fence()
    journal.close()
    with pytest.raises(JournalDenied):
        inspect(journal.root)  # No salvage, repair or silent truncation.


@pytest.mark.parametrize("fault", ["file-replaced", "directory-replaced", "modified"])
def test_writer_denies_external_replacement(tmp_path, fault):
    journal = create(tmp_path)
    record(journal)
    path = journal.root / "events.jsonl"
    if fault == "file-replaced":
        payload = path.read_bytes()
        path.unlink()
        path.touch(mode=0o600)
        path.write_bytes(payload)
    elif fault == "directory-replaced":
        journal.root.rename(journal.root.with_name("moved"))
        journal.root.mkdir(mode=0o700)
    else:
        path.write_bytes(path.read_bytes() + b'{"action":"fence"}\n')
    try:
        with pytest.raises(JournalDenied):
            record(journal, "observe", identity=CID)
    finally:
        journal.close()


@pytest.mark.parametrize("mode", ["completed", "blocked", "late"])
def test_reservations_survive_bounded_actor_outcome(tmp_path, mode):
    # Fake engine workload only. Its marker represents an uncertain mutation,
    # not a Docker container. Actor death never promotes UNKNOWN to stopped.
    journal = create(tmp_path)
    for role in ROLES:
        journal.record("reserve", kind="container", name=PREFIX + "-" + role, fingerprint=FP)
    marker = tmp_path / "fake-mutation"
    code = (
        "import time; from pathlib import Path; "
        f"Path({str(marker)!r}).write_text('fake-only'); "
        'print(\'{"state":"fake-completed"}\',flush=True); '
        + ("time.sleep(60)" if mode in {"blocked", "late"} else "pass")
    )
    if mode == "blocked":
        code = code.replace("print(", "time.sleep(60); print(")
    task = BoundedActor((sys.executable, "-c", code), budget_ns=1_000_000_000, grace_ns=500_000_000)
    try:
        if mode == "completed":
            assert task.execute() == {"state": "fake-completed"}
        else:
            with pytest.raises(ActorDenied):
                task.execute()
            journal.fence()
        assert marker.read_text() == "fake-only"
        assert task.actor_reaped and task.watcher_reaped
    finally:
        journal.close()
    recovered = inspect(journal.root)
    assert recovered.fenced == (mode != "completed")
    assert len(recovered.resources) == 8
    assert all(item[-2:] == (None, "UNKNOWN") for item in recovered.resources)
    # Even a successful process result cannot attest resource identity/exit.


def test_failed_durable_reservation_never_reaches_mutation(tmp_path, monkeypatch):
    journal = create(tmp_path)
    reached = []

    def fail(_):
        raise OSError("private filesystem detail")

    monkeypatch.setattr(os, "fsync", fail)
    with pytest.raises(JournalDenied):
        record(journal)
        reached.append("fake-engine-create")
    assert not reached and journal.failed
    journal.close()


def test_short_writes_are_completed_before_return(tmp_path, monkeypatch):
    journal = create(tmp_path)
    real_write = os.write
    monkeypatch.setattr(os, "write", lambda fd, data: real_write(fd, data[:3]))
    record(journal)
    journal.close()
    assert inspect(journal.root).resources[0][-1] == "UNKNOWN"


def test_identity_cannot_be_assigned_to_two_reservations(tmp_path):
    journal = create(tmp_path)
    record(journal)
    record(journal, "observe", identity=CID)
    other = PREFIX + "-membership"
    journal.record("reserve", kind="container", name=other, fingerprint=FP)
    try:
        with pytest.raises(JournalDenied):
            journal.record("observe", kind="container", name=other, identity=CID, fingerprint=FP)
    finally:
        journal.close()


def test_recovery_does_not_adopt_renamed_generation(tmp_path):
    journal = create(tmp_path)
    record(journal)
    journal.close()
    renamed = journal.root.with_name("ciq-comp-000000000000")
    journal.root.rename(renamed)
    with pytest.raises(JournalDenied):
        inspect(renamed)


@pytest.mark.parametrize("fault", ["symlink", "public", "bad-prefix"])
def test_creation_denies_insecure_parent_before_journal_creation(tmp_path, fault):
    parent = tmp_path / "private"
    parent.mkdir(mode=0o700)
    target = parent
    if fault == "symlink":
        target = tmp_path / "alias"
        target.symlink_to(parent, target_is_directory=True)
    elif fault == "public":
        parent.chmod(0o755)
    with pytest.raises(JournalDenied):
        Journal(target, "unrelated" if fault == "bad-prefix" else PREFIX)
    assert list(parent.iterdir()) == []
