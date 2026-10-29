"""The CI measurement wrapper must report honest samples and preserve failures."""

from __future__ import annotations

import subprocess

from scripts.measure_preview_resources import parse_stats, sample


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
