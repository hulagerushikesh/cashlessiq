"""Source/CI boundary checks; real supervision runs only on disposable Linux."""

import configparser
from pathlib import Path
from types import SimpleNamespace

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
        "TimeoutStartSec": "5s",
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
            "/var/lib/cashlessiq-agent/receipts/retained",
        }
    else:
        assert "ReadWritePaths" not in service
        assert service["IPAddressAllow"] == "127.0.0.1/32"
        assert "-/var/lib/cashlessiq-agent" in service["InaccessiblePaths"].split()


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


@pytest.mark.parametrize("automatic_group", [False, True])
def test_owned_identity_cleanup_handles_userdel_removing_private_group(
    monkeypatch, automatic_group,
):
    users, groups = {"owned": 53001}, {"owned": 53001}
    calls = []

    def user(name):
        return SimpleNamespace(pw_uid=users[name], pw_gid=users[name])

    def group(name):
        return SimpleNamespace(gr_gid=groups[name])

    def run(command, name):
        calls.append((command, name))
        if command == "userdel":
            users.pop(name)
            if automatic_group:
                groups.pop(name)
        elif command == "groupdel":
            groups.pop(name)
        else:
            pytest.fail("Unexpected mutation")

    monkeypatch.setattr(runner.pwd, "getpwnam", user)
    monkeypatch.setattr(runner.grp, "getgrnam", group)
    monkeypatch.setattr(runner, "run", run)
    runner.retire_accounts([("owned", 53001)])
    assert not users and not groups
    assert calls == [("userdel", "owned")] + ([] if automatic_group else [("groupdel", "owned")])


@pytest.mark.parametrize("fault", ["replaced-user", "replaced-group", "delete-failed"])
def test_identity_cleanup_preserves_replacements_and_attempts_other_owned_names(monkeypatch, fault):
    users = {"good-a": 53001, "bad": 53002, "good-b": 53003}
    groups = users.copy()
    if fault == "replaced-user":
        users["bad"] = 60000
    if fault == "replaced-group":
        groups["bad"] = 60000
    calls = []

    monkeypatch.setattr(runner.pwd, "getpwnam", lambda name: SimpleNamespace(
        pw_uid=users[name], pw_gid=users[name],
    ))
    monkeypatch.setattr(runner.grp, "getgrnam", lambda name: SimpleNamespace(gr_gid=groups[name]))

    def run(command, name):
        calls.append((command, name))
        if name == "bad" and fault == "delete-failed":
            raise RuntimeError("dummy failure")
        (users if command == "userdel" else groups).pop(name)

    monkeypatch.setattr(runner, "run", run)
    with pytest.raises(RuntimeError, match="cleanup unconfirmed"):
        runner.retire_accounts([("good-a", 53001), ("bad", 53002), ("good-b", 53003)])
    assert "good-a" not in users and "good-b" not in users
    assert "good-a" not in groups and "good-b" not in groups
    if fault == "replaced-user":
        assert ("userdel", "bad") not in calls and users["bad"] == 60000
    if fault == "replaced-group":
        assert ("groupdel", "bad") not in calls and groups["bad"] == 60000
