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
    ("/var/lib/cashlessiq-agent", False),
    ("/var/lib/cashlessiq-agent", True),
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


@pytest.mark.parametrize("fault", [None, "compiler", "elf-class", "elf-type", "arch",
                                   "diagnostic", "exit", "stdout"])
def test_native_target_rehearsal_uses_committed_source_and_refuses_bad_output(
    monkeypatch, tmp_path, fault,
):
    import struct
    from types import SimpleNamespace
    revision = "a" * 40
    committed = b"/* selected public commit, never the checkout */\n"
    def files(selected):
        assert selected == revision
        return {"deploy/agent-controller/native/single-call-launch.c": committed}
    monkeypatch.setattr(runner.packages.release.review, "committed_files", files)
    calls = []
    def execute(command, **kwargs):
        calls.append(command)
        assert kwargs["capture_output"] and kwargs["timeout"] in (3, 20)
        if len(calls) == 1:
            assert command[0] == "/usr/bin/gcc-12"
            assert "-Werror" in command and "-fPIE" in command and "-pie" in command
            assert "-Wl,-z,relro,-z,now" in command
            assert Path(command[-3]).read_bytes() == committed
            payload = bytearray(64)
            payload[:7] = b"\x7fELF\x02\x01\x01"
            if fault == "elf-class":
                payload[4] = 1
            struct.pack_into("<HH", payload, 16, 2 if fault == "elf-type" else 3,
                             183 if fault == "arch" else 62)
            binary = Path(command[-1])
            binary.write_bytes(payload)
            binary.chmod(0o755)
            return SimpleNamespace(returncode=1 if fault == "compiler" else 0)
        assert len(command) == 1 and command[0] == str(tmp_path / "native/launch")
        assert kwargs["env"] == {"LANG": "C.UTF-8"}
        return SimpleNamespace(returncode=0 if fault == "exit" else 125,
                               stdout=b"unexpected" if fault == "stdout" else b"",
                               stderr=b"unexpected" if fault == "diagnostic" else
                               b"single_call_launch_unavailable\n")
    monkeypatch.setattr(runner.subprocess, "run", execute)
    if fault:
        with pytest.raises(ValueError, match=runner.ERROR):
            runner.native_rehearsal(tmp_path, revision)
    else:
        runner.native_rehearsal(tmp_path, revision)
        assert len(calls) == 2
    assert (tmp_path / "native/launch.c").read_bytes() == committed


def test_native_rehearsal_refuses_existing_directory_before_compile(monkeypatch, tmp_path):
    (tmp_path / "native").mkdir()
    monkeypatch.setattr(runner.packages.release.review, "committed_files", lambda _: {
        "deploy/agent-controller/native/single-call-launch.c": b"public"})
    monkeypatch.setattr(runner.subprocess, "run", lambda *a, **kw: pytest.fail("compiled"))
    with pytest.raises(FileExistsError):
        runner.native_rehearsal(tmp_path, "a" * 40)
