"""Target OS/CI refusal and inactive installation boundaries; no Docker needed."""

from pathlib import Path

import pytest

from scripts import test_agent_debian_package as runner


@pytest.mark.parametrize("fault", ["platform", "uid", "actions", "repository", "optin"])
def test_optins_precede_target_inspection_and_all_mutation(monkeypatch, fault):
    monkeypatch.setattr(runner.sys, "platform", "linux" if fault != "platform" else "darwin")
    monkeypatch.setattr(runner.os, "geteuid", lambda: 1 if fault == "uid" else 0)
    for name, value, label in (
        ("GITHUB_ACTIONS", "true", "actions"),
        ("GITHUB_REPOSITORY", "hulagerushikesh/cashlessiq", "repository"),
        ("CIQ_AGENT_DEBIAN_PACKAGE_TEST", "1", "optin"),
    ):
        monkeypatch.setenv(name, "wrong" if fault == label else value)
    monkeypatch.setattr(runner.platform, "freedesktop_os_release",
                        lambda: pytest.fail("Host inspected"))
    monkeypatch.setattr(runner.packages, "install", lambda _: pytest.fail("Runtime installed"))
    with pytest.raises(SystemExit, match=runner.ERROR):
        runner.main()


@pytest.mark.parametrize("fault", ["distro", "version", "arch", "libc"])
def test_wrong_target_denies_before_runtime_inspection(monkeypatch, fault):
    monkeypatch.setattr(runner.sys, "platform", "linux")
    monkeypatch.setattr(runner.os, "geteuid", lambda: 0)
    for name, value in (("GITHUB_ACTIONS", "true"),
                        ("GITHUB_REPOSITORY", "hulagerushikesh/cashlessiq"),
                        ("CIQ_AGENT_DEBIAN_PACKAGE_TEST", "1")):
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(runner.platform, "freedesktop_os_release", lambda: {
        "ID": "ubuntu" if fault == "distro" else "debian",
        "VERSION_ID": "13" if fault == "version" else "12"})
    monkeypatch.setattr(runner.platform, "machine", lambda: "aarch64" if fault == "arch"
                        else "x86_64")
    monkeypatch.setattr(runner.platform, "libc_ver", lambda: ("glibc", "2.39") if fault == "libc"
                        else ("glibc", "2.36"))
    monkeypatch.setattr(runner, "verify_inactive", lambda: pytest.fail("Runtime inspected"))
    with pytest.raises(ValueError, match=runner.ERROR):
        runner.guard()


def missing(_key):
    raise KeyError


@pytest.fixture
def inactive(monkeypatch):
    lookups = ((runner.packages.pwd, "getpwnam"), (runner.packages.pwd, "getpwuid"),
               (runner.packages.policy.grp, "getgrnam"),
               (runner.packages.policy.grp, "getgrgid"))
    for owner, name in lookups:
        monkeypatch.setattr(owner, name, missing)
    monkeypatch.setattr(Path, "exists", lambda _: False)
    monkeypatch.setattr(Path, "is_symlink", lambda _: False)
    return lookups


@pytest.mark.parametrize("index", range(4))
def test_existing_identity_blocks_inactive_receipt(monkeypatch, inactive, index):
    owner, name = inactive[index]
    monkeypatch.setattr(owner, name, lambda _: object())
    with pytest.raises(ValueError, match=runner.ERROR):
        runner.verify_inactive()


@pytest.mark.parametrize("path,symlink", [
    ("/run/ciq-agent-claim", False),
    ("/run/ciq-agent-supervisor", False),
    ("/etc/systemd/system/ciq-agent-claim.service", False),
    ("/run/systemd/system/ciq-agent-custody.service", True),
    ("/usr/lib/systemd/system/ciq-agent-receipt.service", True),
    ("/lib/systemd/system/ciq-agent-receipt.service", False),
])
def test_private_paths_and_unit_entries_including_dangling_links_deny_receipt(
    monkeypatch, inactive, path, symlink,
):
    monkeypatch.setattr(Path, "is_symlink" if symlink else "exists", lambda p: str(p) == path)
    with pytest.raises(ValueError, match=runner.ERROR):
        runner.verify_inactive()


def test_no_agent_state_passes_without_identity_or_service_creation(inactive):
    runner.verify_inactive()
