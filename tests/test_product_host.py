"""Resource observation tests use fake metrics, never the test host or Docker."""

import subprocess
from dataclasses import replace
from types import SimpleNamespace

import pytest

from scripts import check_product_host as host


def healthy():
    return host.Snapshot(8 * host.GIB, 8, 1, 0, 2.0, 20 * host.GIB, 4 * host.GIB, 8, host.GIB, 4)


@pytest.mark.parametrize(
    "changes",
    [
        {"pressure_level": 2},
        {"pressure_level": 4},
        {"pressure_level": 0},
        {"host_memory_bytes": 4 * host.GIB},
        {"host_cpus": 1},
        {"docker_cpus": 1},
        {"load_one_minute": 7.0},
        {"disk_free_bytes": host.GIB},
        {"docker_memory_bytes": 2 * host.GIB},
        {"docker_used_bytes": 3 * host.GIB},
    ],
)
def test_conservative_blockers(changes):
    assert host.blockers(replace(healthy(), **changes))


def test_high_historical_swap_alone_is_not_a_current_pressure_measure():
    assert not host.blockers(replace(healthy(), swap_used_bytes=9 * host.GIB))


@pytest.mark.parametrize("text", ["nanGiB", "-1MB", "4XB", "3.5", "infGB", "12MB secret"])
def test_unknown_resource_units_fail_closed(text):
    with pytest.raises(ValueError):
        host._bytes(text)


def test_units_are_not_confused():
    assert host._bytes("1GiB") == host.GIB
    assert host._bytes("1GB") == 1_000_000_000
    assert host._bytes("8.5M") == 8_912_896
    assert host._bytes("0.1B") == 1


def fake_observations(monkeypatch, *, stats="1GiB / 4GiB", running=1):
    monkeypatch.setattr(host.sys, "platform", "darwin")
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        assert kwargs == dict(check=True, capture_output=True, text=True, timeout=4)
        if command[0] == "sysctl":
            value = (
                "8589934592\n8\n1"
                if command[1] == "-n"
                else "vm.swapusage: total = 1024.00M used = 8.50M free = 1015.50M (encrypted)"
            )
        else:
            assert command[:2] in (("docker", "info"), ("docker", "stats"))
            value = (
                f'{{"memory":4294967296,"cpus":8,"running":{running}}}'
                if command[1] == "info"
                else stats
            )
        return SimpleNamespace(stdout=value)

    monkeypatch.setattr(host.subprocess, "run", run)
    monkeypatch.setattr(host.os, "getloadavg", lambda: (2.0, 2.0, 2.0))
    monkeypatch.setattr(host.shutil, "disk_usage", lambda _: SimpleNamespace(free=20 * host.GIB))
    return calls


def test_collection_is_metrics_only_and_bounded(monkeypatch):
    calls = fake_observations(monkeypatch)
    snapshot = host.require_headroom()
    assert snapshot.docker_used_bytes == host.GIB
    assert snapshot.swap_used_bytes == 8_912_896
    assert len(calls) == 4
    assert all("inspect" not in call and "build" not in call for call in calls)
    assert host.main() == 0


@pytest.mark.parametrize("stats,running", [("1GiB / 4GiB", 2), ("bad", 1)])
def test_inventory_race_or_malformed_stats_refuses(monkeypatch, stats, running):
    fake_observations(monkeypatch, stats=stats, running=running)
    assert host.main() == 2


@pytest.mark.parametrize("failure", [OSError("hidden"), subprocess.TimeoutExpired("hidden", 4)])
def test_observation_failure_is_redacted(monkeypatch, capsys, failure):
    def collect():
        raise failure

    monkeypatch.setattr(host, "collect", collect)
    assert host.main() == 2
    assert "hidden" not in capsys.readouterr().out


def test_pressure_blocks_admission_without_mutating_host(monkeypatch, capsys):
    monkeypatch.setattr(host, "collect", lambda: replace(healthy(), pressure_level=2))
    with pytest.raises(RuntimeError, match="pressure"):
        host.require_headroom()
    assert host.main() == 2
    assert "DEFER" in capsys.readouterr().out


def test_unsupported_host_refuses_before_commands(monkeypatch):
    monkeypatch.setattr(host.sys, "platform", "linux")
    assert host.main() == 2
