"""Fresh-host collision, static-unit delivery and no-activation failure boundaries."""

import json
import stat
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import prepare_agent_host as host


@pytest.mark.parametrize("platform,uid", [("darwin", 0), ("linux", 501)])
def test_unsupported_host_refuses_before_input_or_account_commands(monkeypatch, platform, uid):
    monkeypatch.setattr(host.runtime.sys, "platform", platform)
    monkeypatch.setattr(host.runtime.os, "geteuid", lambda: uid)
    monkeypatch.setattr(host.runtime.release.review, "committed_files",
                        lambda *_: pytest.fail("Git source read"))
    monkeypatch.setattr(host, "run", lambda *_a, **_k: pytest.fail("Host command"))
    with pytest.raises(ValueError):
        host.prepare("a" * 40, "b" * 64)


@pytest.fixture
def unit_parent(tmp_path, monkeypatch):
    parent = tmp_path / "units"
    parent.mkdir()
    monkeypatch.setattr(host, "UNIT_PATHS", (parent,))
    monkeypatch.setattr(host, "protected", lambda *_a: None)
    return parent


@pytest.mark.parametrize("entry", [
    "ciq-agent-claim.service", "ciq-agent-custody.service.d", "service.d",
    "ciq-.service.d", "ciq-agent-.service.d",
    "multi-user.target.wants/ciq-agent-receipt.service",
    "unrelated.service.requires/ciq-agent-claim.service",
    "unrelated.service.upholds/ciq-agent-custody.service",
])
def test_existing_units_dropins_and_dangling_boot_links_refuse(unit_parent, entry):
    target = unit_parent / entry
    target.parent.mkdir(exist_ok=True)
    target.symlink_to("/missing-owner-state")
    with pytest.raises(ValueError, match=host.ERROR):
        host.fresh_units()
    assert target.is_symlink()  # Never unlink/repair an existing entry.


def test_alias_or_redirected_dependency_directory_refuses(unit_parent):
    alias = unit_parent / "other.service"
    alias.symlink_to("ciq-agent-claim.service")
    with pytest.raises(ValueError, match=host.ERROR):
        host.fresh_units()
    alias.unlink()
    (unit_parent / "multi-user.target.wants").symlink_to("/other")
    with pytest.raises(ValueError, match=host.ERROR):
        host.fresh_units()


def test_fresh_unit_paths_pass_without_mutation(unit_parent):
    (unit_parent / "unrelated.service").write_bytes(b"owner")
    host.fresh_units()
    assert list(p.name for p in unit_parent.iterdir()) == ["unrelated.service"]


@pytest.mark.parametrize("fault", [None, "loaded", "active", "pid", "job", "extra", "duplicate"])
def test_manager_requires_missing_inactive_process_free_units(monkeypatch, fault):
    monkeypatch.setattr(Path, "read_text", lambda *_: "systemd\n")
    fields = {"LoadState": "loaded" if fault == "loaded" else "not-found",
              "ActiveState": "active" if fault == "active" else "inactive",
              "SubState": "dead", "MainPID": "51" if fault == "pid" else "0",
              "ControlPID": "0", "Job": "12 job" if fault == "job" else ""}
    if fault == "extra":
        fields["Unreviewed"] = "1"
    data = "".join(k + "=" + v + "\n" for k, v in fields.items()).encode()
    if fault == "duplicate":
        data += b"MainPID=0\n"
    monkeypatch.setattr(host, "run", lambda *_a, **_k: SimpleNamespace(stdout=data))
    if fault is None:
        host.manager_inactive(missing=True)
    else:
        with pytest.raises(ValueError, match=host.ERROR):
            host.manager_inactive(missing=True)


@pytest.mark.parametrize("failure", [None, "accounts", "analyze", "postflight"])
def test_fresh_preparation_writes_only_reviewed_units_and_late_receipt(
    tmp_path, monkeypatch, failure,
):
    root, units = tmp_path / "install", tmp_path / "units"
    root.mkdir()
    units.mkdir()
    monkeypatch.setattr(host.runtime, "INSTALL", root)
    monkeypatch.setattr(host, "UNITS", units)
    expected = {f"ciq-agent-{r}.service": ("reviewed " + r).encode()
                for r in host.runtime.ROLES}
    monkeypatch.setattr(host, "preflight", lambda *_: expected)
    monkeypatch.setattr(host, "protected", lambda *_: None)
    monkeypatch.setattr(host, "identities", lambda: None)
    monkeypatch.setattr(host, "fresh_units", lambda: None)
    monkeypatch.setattr(host, "absent", lambda p: pytest.fail("Unexpected private state")
                        if p.exists() or p.is_symlink() else None)
    commands = []

    def run(*args):
        assert not (root / "agent-host.json").exists()
        commands.append(args)
        assert args[0] in {"/usr/sbin/groupadd", "/usr/sbin/useradd", "/usr/bin/systemd-analyze"}
        if args[0] == "/usr/sbin/useradd":
            assert args[args.index("--password") + 1] == "!"
            assert args[args.index("--shell") + 1] == "/usr/sbin/nologin"
            assert "--no-create-home" in args and "SUB_UID_COUNT=0" in args
        if args[0] == "/usr/bin/systemd-analyze":
            assert args[1:3] == ("verify", "--man=no")
            assert {Path(p).name: Path(p).read_bytes() for p in args[3:]} == expected
            if failure == "analyze":
                raise ValueError(host.ERROR)
        elif failure == "accounts":
            raise ValueError(host.ERROR)

    def postflight():
        assert {p.name: p.read_bytes() for p in units.iterdir()} == expected
        if failure == "postflight":
            raise ValueError(host.ERROR)

    monkeypatch.setattr(host, "run", run)
    monkeypatch.setattr(host, "manager_inactive", postflight)
    if failure:
        with pytest.raises(ValueError, match=host.ERROR):
            host.prepare("a" * 40, "b" * 64)
        assert not (root / "agent-host.json").exists()
        if failure == "postflight":
            assert len(list(units.iterdir())) == 3  # No automatic destructive rollback.
    else:
        host.prepare("a" * 40, "b" * 64)
        receipt = json.loads((root / "agent-host.json").read_bytes())
        assert receipt["activation"] == "disabled"
        assert receipt["identities"] == dict(host.runtime.ACCOUNTS)
        assert receipt["units"] == {n: host.runtime.release.review.sha256(v)
                                    for n, v in expected.items()}
    assert root.is_dir()


def test_existing_target_is_never_overwritten_after_review(tmp_path, monkeypatch):
    root, units = tmp_path / "install", tmp_path / "units"
    root.mkdir()
    units.mkdir()
    owner = units / "ciq-agent-claim.service"
    owner.write_bytes(b"owner")
    monkeypatch.setattr(host.runtime, "INSTALL", root)
    monkeypatch.setattr(host, "UNITS", units)
    monkeypatch.setattr(host, "preflight", lambda *_: {owner.name: b"new"})
    monkeypatch.setattr(host, "identities", lambda: None)
    monkeypatch.setattr(host, "fresh_units", lambda: None)
    monkeypatch.setattr(host, "run", lambda *_: None)
    with pytest.raises(FileExistsError):
        host.prepare("a" * 40, "b" * 64)
    assert owner.read_bytes() == b"owner" and not (root / "agent-host.json").exists()


@pytest.mark.parametrize("fault", ["writable", "foreign", "symlink", "hardlink", "setuid"])
def test_unprotected_installed_input_is_rejected(monkeypatch, fault):
    mode = stat.S_IFLNK | 0o777 if fault == "symlink" else stat.S_IFREG | 0o644
    if fault == "writable":
        mode |= 0o020
    if fault == "setuid":
        mode |= 0o4000
    monkeypatch.setattr(Path, "lstat", lambda _: SimpleNamespace(
        st_mode=mode, st_uid=501 if fault == "foreign" else 0,
        st_nlink=2 if fault == "hardlink" else 1))
    with pytest.raises(ValueError, match=host.ERROR):
        host.protected(Path("installed-input"), False)


@pytest.mark.parametrize("fault", ["uid", "home", "shell", "shadow", "members", "supplement"])
def test_locked_identity_audit_refuses_unexpected_access(monkeypatch, fault):
    name, uid = "ciq-agent-clinical", 53001
    user = SimpleNamespace(pw_uid=1 if fault == "uid" else uid, pw_gid=uid,
                           pw_dir="/home/service" if fault == "home" else "/nonexistent",
                           pw_shell="/bin/sh" if fault == "shell" else "/usr/sbin/nologin")
    group = SimpleNamespace(gr_gid=uid, gr_mem=["owner"] if fault == "members" else [])
    monkeypatch.setattr(host.runtime, "ACCOUNTS", ((name, uid),))
    monkeypatch.setattr(host.runtime.pwd, "getpwnam", lambda _: user)
    monkeypatch.setattr(host.runtime.pwd, "getpwuid", lambda _: user)
    monkeypatch.setattr(host.runtime.grp, "getgrnam", lambda _: group)
    monkeypatch.setattr(host.runtime.grp, "getgrgid", lambda _: group)
    monkeypatch.setattr(host.runtime.grp, "getgrall", lambda: [SimpleNamespace(
        gr_mem=[name] if fault == "supplement" else [])])
    monkeypatch.setitem(sys.modules, "spwd", SimpleNamespace(getspnam=lambda _: SimpleNamespace(
        sp_pwdp="hash" if fault == "shadow" else "!")))
    with pytest.raises(ValueError, match=host.ERROR):
        host.identities()


def test_install_receipt_mismatch_refuses_before_installed_code_or_host_mutation(
    tmp_path, monkeypatch,
):
    root = tmp_path / "install"
    root.mkdir()
    monkeypatch.setattr(host.runtime, "INSTALL", root)
    monkeypatch.setattr(host.runtime, "host_guard", lambda: None)
    monkeypatch.setattr(host.runtime, "inactive", lambda: None)
    monkeypatch.setattr(host, "protected", lambda *_: None)
    monkeypatch.setattr(host, "fresh_units", lambda: None)
    monkeypatch.setattr(host, "manager_inactive", lambda **_: None)
    monkeypatch.setattr(host.runtime.python_bundle, "expected",
                        lambda _: ("python", {"sha256": "c" * 64}, b""))
    (root / "agent-install.json").write_bytes(b'{"activation":"enabled"}')
    monkeypatch.setattr(host.runtime, "installed", lambda _: pytest.fail("Code executed"))
    monkeypatch.setattr(host, "run", lambda *_a, **_k: pytest.fail("Host mutated"))
    with pytest.raises(ValueError, match=host.ERROR):
        host.prepare("a" * 40, "b" * 64)
