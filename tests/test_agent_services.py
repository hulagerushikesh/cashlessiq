"""Source/CI boundary checks; real supervision runs only on disposable Linux."""

import configparser
from pathlib import Path

import pytest

from scripts import test_agent_services as runner

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("role,seconds,memory,module,user", [
    ("claim", 25, 128, "agent_claim_runner", "clinical"),
    ("custody", 40, 192, "agent_custody_runner", "custody"),
    ("receipt", 65, 128, "agent_receipt_runner", "receipt"),
])
def test_manual_fixed_unit_preserves_identity_and_whole_cgroup_cleanup(
    role, seconds, memory, module, user,
):
    config = configparser.ConfigParser(interpolation=None)
    config.read(runner.SOURCES / f"ciq-agent-{role}.service.example")
    assert set(config.sections()) == {"Unit", "Service"}
    assert set(config["Unit"]) == {"description"}  # No dependency activation.
    service = config["Service"]
    assert service["User"] == service["Group"] == "ciq-agent-" + user
    assert service["ExecStart"] == (
        "/usr/bin/env -i PATH=/usr/bin:/bin LANG=C.UTF-8 "
        "/opt/cashlessiq-agent/venv/bin/python -I -B -m ciq_api." + module
    )
    for key, expected in {
        "Type": "exec", "Restart": "no", "KillMode": "control-group",
        "SendSIGKILL": "yes", "FinalKillSignal": "SIGKILL", "TimeoutStopSec": "2s",
        "RuntimeMaxSec": str(seconds) + "s", "MemoryMax": str(memory) + "M",
        "MemorySwapMax": "0", "CPUQuota": "25%", "TasksMax": "16",
        "LimitNOFILE": "64", "LimitCORE": "0", "OOMPolicy": "kill",
        "NoNewPrivileges": "yes", "CapabilityBoundingSet": "", "AmbientCapabilities": "",
        "ProtectSystem": "strict", "ProtectHome": "yes", "PrivateDevices": "yes",
        "ProtectControlGroups": "yes", "RestrictNamespaces": "yes",
        "StandardInput": "null", "IPAddressDeny": "any",
    }.items():
        assert service[key] == expected
    assert not any(k.startswith(("execstartpre", "execstop", "execcondition", "environmentfile",
                                 "runtimedirectory", "statedirectory", "loadcredential"))
                   for k in service)
    if role == "receipt":
        assert "IPAddressAllow" not in service
        assert set(service["ReadWritePaths"].split()) == {
            "/run/ciq-agent-receipts/ipc",
            "/run/ciq-agent-receipts/journal-parent/retained",
        }
    else:
        assert "ReadWritePaths" not in service
        assert service["IPAddressAllow"] == "127.0.0.1/32"


@pytest.mark.parametrize("fault", ["platform", "uid", "actions", "repo", "optin"])
def test_ci_guard_denies_before_host_reads_or_mutation(monkeypatch, fault):
    monkeypatch.setattr(runner.sys, "platform", "linux" if fault != "platform" else "darwin")
    monkeypatch.setattr(runner.os, "geteuid", lambda: 1 if fault == "uid" else 0)
    for key, value, bad in (
        ("GITHUB_ACTIONS", "true", "actions"),
        ("GITHUB_REPOSITORY", "hulagerushikesh/cashlessiq", "repo"),
        ("CIQ_AGENT_SERVICE_TEST", "1", "optin"),
    ):
        monkeypatch.setenv(key, "wrong" if fault == bad else value)
    monkeypatch.setattr(Path, "read_text", lambda *_: pytest.fail("Guard read host state"))
    with pytest.raises(SystemExit, match="explicit disposable"):
        runner.guard()


def test_no_deployment_or_automatic_activation():
    for path in (ROOT / "deploy/gcp-preview").glob("*"):
        if path.is_file():
            assert "ciq-agent-claim.service" not in path.read_text()
    source = (ROOT / "scripts/test_agent_services.py").read_text()
    assert '"enable"' not in source and '"restart"' not in source
    assert "shutil.rmtree(path)" in source and '"prune"' not in source
    assert "sudo -n env GITHUB_ACTIONS=true" in (ROOT / ".github/workflows/product.yml").read_text()
