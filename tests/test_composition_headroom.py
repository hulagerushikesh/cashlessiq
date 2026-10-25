"""Linux admission observations, deterioration and ambiguity; no daemon I/O."""

import json
import time
from dataclasses import replace
from types import SimpleNamespace

import pytest

from scripts import composition_headroom as target

MEMORY = "MemTotal: 8388608 kB\nMemAvailable: 6291456 kB\nSwapTotal: 2048 kB\nSwapFree: 1024 kB\n"
PSI = (
    "some avg10=0.00 avg60=0.00 avg300=0.00 total=100\n"
    "full avg10=0.00 avg60=0.00 avg300=0.00 total=50\n"
)


def gate(tmp_path, monkeypatch, *, fault=None, running=True):
    monkeypatch.setattr(target.sys, "platform", "linux")
    monkeypatch.setattr(target.os, "sched_getaffinity", lambda _: {0, 1, 2, 3}, raising=False)
    monkeypatch.setattr(
        target.os, "statvfs", lambda _: SimpleNamespace(f_bavail=20 * target.GIB, f_frsize=1)
    )
    observations = {"meminfo": MEMORY, "pressure/memory": PSI, "loadavg": "0.30 0.10 0.10 1/100 42"}
    monkeypatch.setattr(target, "proc", lambda name, _: observations[name])
    calls = []
    identifier = "a" * 64

    def engine(*args):
        calls.append(args)
        if args == target.INFO:
            return json.dumps(dict(memory=8 * target.GIB, cpus=4, running=int(running)))
        if args == target.LIST:
            return (
                ("b" * 64 if fault == "changed" and calls.count(target.LIST) > 1 else identifier)
                if running
                else ""
            )
        assert args == target.STATS
        row = dict(id=identifier, memory="100MiB / 128MiB")
        if fault == "foreign":
            row["id"] = "b" * 64
        elif fault == "over-limit":
            row["memory"] = "129MiB / 128MiB"
        return "" if fault == "missing" else json.dumps(row)

    return (
        target.LinuxHeadroom(engine, time.monotonic_ns() + 30_000_000_000, tmp_path),
        observations,
        calls,
    )


def test_fresh_linux_sample_and_no_cached_success(tmp_path, monkeypatch):
    check, observations, calls = gate(tmp_path, monkeypatch)
    assert check() is True
    assert check.samples == 1 and check.last.docker_used_bytes == 100 * 1024**2
    assert check.last.swap_used_bytes == 1024**2
    observations["meminfo"] = MEMORY.replace("6291456", "1024")
    with pytest.raises(target.HeadroomDenied):
        check()
    assert check.last is None and check.samples == 1 and calls.count(target.INFO) == 2


def test_empty_host_is_observed_without_running_stats(tmp_path, monkeypatch):
    check, _, calls = gate(tmp_path, monkeypatch, running=False)
    assert check() is True and check.last.running_containers == 0
    assert calls == [target.INFO, target.LIST, target.LIST]


@pytest.mark.parametrize("fault", ["changed", "foreign", "over-limit", "missing"])
def test_inconsistent_or_partial_docker_observations_deny(tmp_path, monkeypatch, fault):
    check, _, _ = gate(tmp_path, monkeypatch, fault=fault)
    with pytest.raises(target.HeadroomDenied):
        check()
    assert check.last is None and check.samples == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("host_cpus", 1),
        ("docker_cpus", 1),
        ("host_memory_bytes", 2 * target.GIB),
        ("docker_memory_bytes", 2 * target.GIB),
        ("available_memory_bytes", target.GIB),
        ("docker_used_bytes", 7 * target.GIB),
        ("load_one_minute", 4),
        ("memory_some_avg10", 6),
        ("memory_full_avg10", 2),
        ("disk_free_bytes", target.GIB),
    ],
)
def test_admission_limits_are_independent(tmp_path, monkeypatch, field, value):
    check, _, _ = gate(tmp_path, monkeypatch)
    assert check() is True
    assert target.blockers(replace(check.last, **{field: value}))


@pytest.mark.parametrize(
    "output",
    [
        "",
        "MemTotal: 1 kB",
        MEMORY + "MemTotal: 1 kB\n",
        MEMORY.replace("kB", "MB"),
        MEMORY.replace("SwapFree: 1024", "SwapFree: 4096"),
    ],
)
def test_missing_duplicate_or_invalid_memory_evidence_denies(output):
    with pytest.raises(target.HeadroomDenied):
        target.memory(output)


@pytest.mark.parametrize(
    "output",
    [
        "",
        PSI.splitlines()[0],
        PSI + PSI,
        PSI.replace("0.00", "nan"),
        PSI.replace("some avg10=0.00", "some avg10=101.00"),
    ],
)
def test_missing_ambiguous_or_invalid_pressure_denies(output):
    with pytest.raises(target.HeadroomDenied):
        target.pressure(output)


def test_expired_deadline_refuses_before_observation(tmp_path, monkeypatch):
    check, _, calls = gate(tmp_path, monkeypatch)
    check.deadline_ns = time.monotonic_ns() - 1
    with pytest.raises(target.HeadroomDenied):
        check()
    assert not calls


def test_proc_reader_uses_fixed_bounded_command(monkeypatch):
    seen = {}

    class Actor:
        def __init__(self, command, **limits):
            seen.update(command=command, limits=limits)

        def execute(self):
            return {"output": MEMORY}

    monkeypatch.setattr(target, "BoundedActor", Actor)
    assert target.proc("meminfo", time.monotonic_ns() + 10_000_000_000) == MEMORY
    assert seen["command"][3:] == ("--command", "/bin/cat", "/proc/meminfo")
    assert seen["limits"] == dict(budget_ns=2_000_000_000, grace_ns=300_000_000)
    with pytest.raises(target.HeadroomDenied):
        target.proc("../private", time.monotonic_ns() + 10_000_000_000)
