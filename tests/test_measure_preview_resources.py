"""The CI measurement wrapper must report honest samples and preserve failures."""

from __future__ import annotations

import subprocess
import threading

import pytest

from scripts.measure_preview_resources import parse_host_memory, parse_stats, sample


def stats(web: str = "100MiB", api: str = "90MiB") -> str:
    return "\n".join(
        (
            f"cashlessiq-owner-preview-web-1\t{web} / 512MiB",
            f"cashlessiq-owner-preview-api-1\t{api} / 512MiB",
            "cashlessiq-owner-preview-db-1\t48MiB / 256MiB",
            "cashlessiq-owner-preview-gateway-1\t16MiB / 128MiB",
            "unrelated-db-1\t9GiB / 10GiB",
        )
    )


def test_parse_stats_selects_preview_and_converts_units():
    assert parse_stats(stats("0.5GiB", "1024KiB")) == {
        "web": 512,
        "api": 1,
        "db": 48,
        "gateway": 16,
    }


def test_sample_keeps_command_success_and_reports_all_services(monkeypatch, capsys):
    monkeypatch.setattr(
        subprocess, "run", lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0)
    )
    assert sample(["true"], interval=0.01, read_stats=stats) == 0
    output = capsys.readouterr().out
    assert "Sampled web high: 100.0 MiB" in output
    assert "Sampling excludes the OS" in output


def test_sample_keeps_command_failure(monkeypatch):
    monkeypatch.setattr(
        subprocess, "run", lambda *_args, **_kwargs: subprocess.CompletedProcess([], 7)
    )
    assert sample(["false"], interval=0.01, read_stats=stats) == 7


def test_sample_does_not_claim_memory_evidence_if_service_missing(monkeypatch, capsys):
    monkeypatch.setattr(
        subprocess, "run", lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0)
    )
    assert (
        sample(
            ["true"],
            interval=0.01,
            read_stats=lambda: "cashlessiq-owner-preview-web-1\t1MiB / 2MiB",
        )
        == 1
    )
    assert "sampling incomplete" in capsys.readouterr().err


def meminfo(available: int = 524288, swap_free: int = 262144) -> str:
    return (
        "MemTotal: 2097152 kB\n"
        "MemFree: 16384 kB\n"  # A small free count is not the available-memory estimate.
        f"MemAvailable: {available} kB\n"
        "SwapTotal: 262144 kB\n"
        f"SwapFree: {swap_free} kB\n"
    )


def test_linux_memory_uses_available_estimate_and_reports_swap():
    assert parse_host_memory(meminfo(swap_free=131072)) == {
        "total_mib": 2048,
        "available_mib": 512,
        "swap_used_mib": 128,
    }


@pytest.mark.parametrize(
    "text",
    [
        meminfo().replace("MemAvailable:", "Missing:"),
        meminfo().replace("kB", "MB"),
        meminfo(available=3145728),
        meminfo(available=-1),
        meminfo(swap_free=524288),
        meminfo() + "MemTotal: 2097152 kB\n",
    ],
)
def test_invalid_host_counters_do_not_produce_capacity_evidence(text):
    with pytest.raises(ValueError):
        parse_host_memory(text)


def test_host_measurements_include_baseline_and_observed_headroom(monkeypatch, capsys):
    observed = threading.Event()
    reads = 0

    def read_host():
        nonlocal reads
        reads += 1
        if reads == 1:
            return meminfo()
        observed.set()
        return meminfo(available=262144, swap_free=131072)

    def run(*args, **kwargs):
        assert observed.wait(timeout=2)
        return subprocess.CompletedProcess([], 0)

    monkeypatch.setattr(subprocess, "run", run)
    assert sample(["true"], read_stats=stats, include_host=True, read_host_memory=read_host) == 0
    output = capsys.readouterr().out
    assert "Linux host usable RAM: 2048.0 MiB" in output
    assert "minimum estimated available RAM: 256.0 MiB" in output
    assert "initial swap used: 0.0 MiB" in output
    assert "swap-used high: 128.0 MiB" in output
    assert "do not establish fitness of the proposed GCP VM" in output


def test_missing_linux_host_reading_refuses_to_start_command(monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        pytest.fail("Command started despite unavailable required host counters")

    def missing():
        raise FileNotFoundError("No Linux procfs")

    monkeypatch.setattr(subprocess, "run", forbidden)
    assert sample(["true"], include_host=True, read_host_memory=missing) == 1
    assert "command was not started" in capsys.readouterr().err


def test_host_observation_failure_preserves_workflow_failure(monkeypatch, capsys):
    observed = threading.Event()
    reads = 0

    def read_host():
        nonlocal reads
        reads += 1
        if reads == 1:
            return meminfo()
        observed.set()
        return "invalid counters"

    def run(*args, **kwargs):
        assert observed.wait(timeout=2)
        return subprocess.CompletedProcess([], 7)

    monkeypatch.setattr(subprocess, "run", run)
    assert sample(["false"], read_stats=stats, include_host=True, read_host_memory=read_host) == 7
    assert "sampling incomplete" in capsys.readouterr().err
