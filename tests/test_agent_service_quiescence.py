"""Stopped-service evidence failures; no actual systemd, Docker or credentials."""

from types import SimpleNamespace

import pytest

from scripts import agent_service_quiescence as check

UNIT = "ciq-agent-custody.service"


def stopped():
    return dict(zip(check.FIELDS, (
        UNIT, "loaded", "inactive", "dead", "0", "0", "", "", "a" * 32,
        "0", "control-group", "no",
    ), strict=True))


def response(values=None):
    return SimpleNamespace(returncode=0, stderr="", stdout="".join(
        key + "=" + value + "\n" for key, value in (values or stopped()).items()
    ))


@pytest.mark.parametrize("field,value", [
    ("Id", "other.service"), ("LoadState", "not-found"), ("ActiveState", "active"),
    ("SubState", "stop-sigkill"), ("MainPID", "123"), ("ControlPID", "234"),
    ("Job", "55 /org/freedesktop/systemd1/job/55"), ("NRestarts", "1"),
    ("Restart", "always"), ("KillMode", "process"),
    ("ControlGroup", "/system.slice/../other"), ("InvocationID", "invalid"),
])
def test_snapshot_rejects_live_ambiguous_or_wrong_service(monkeypatch, field, value):
    values = stopped()
    values[field] = value
    monkeypatch.setattr(check.subprocess, "run", lambda *_, **__: response(values))
    with pytest.raises(ValueError, match="private state must be retained"):
        check.snapshot(UNIT)


@pytest.mark.parametrize("fault", ["missing", "duplicate", "extra", "oversize", "error"])
def test_snapshot_rejects_incomplete_or_failed_inspection(monkeypatch, fault):
    result = response()
    if fault == "missing":
        result.stdout = result.stdout.replace("Job=\n", "")
    elif fault == "duplicate":
        result.stdout += "MainPID=0\n"
    elif fault == "extra":
        result.stdout += "PRIVATE=secret\n"
    elif fault == "oversize":
        result.stdout += "x" * 8193
    else:
        result.returncode, result.stderr = 1, "PRIVATE"
    monkeypatch.setattr(check.subprocess, "run", lambda *_, **__: result)
    with pytest.raises(ValueError) as error:
        check.snapshot(UNIT)
    assert "PRIVATE" not in str(error.value)


def test_snapshot_inspection_is_bounded_read_only_and_has_clean_environment(monkeypatch):
    def run(argv, **options):
        assert argv == ["/usr/bin/systemctl", "show", "--all", "--no-pager",
                        "--property=" + ",".join(check.FIELDS), "--", UNIT]
        assert options == dict(stdin=check.subprocess.DEVNULL, capture_output=True,
                               text=True, timeout=3,
                               env={"PATH": "/usr/bin:/bin", "LANG": "C"})
        return response()

    monkeypatch.setattr(check.subprocess, "run", run)
    assert check.snapshot(UNIT) == stopped()


@pytest.mark.parametrize("content", [
    b"", b"populated 1\nfrozen 0\n", b"populated 0\npopulated 0\n",
    b"frozen 0\n", b"populated 0 extra\n", b"populated 0\n" + b"x" * 4097,
    b"populated 0\n\xff",
])
def test_cgroup_events_must_prove_recursive_emptiness(tmp_path, monkeypatch, content):
    monkeypatch.setattr(check, "CGROUP", str(tmp_path))
    group = tmp_path / UNIT
    group.mkdir()
    (group / "cgroup.events").write_bytes(content)
    with pytest.raises((ValueError, UnicodeError)):
        check.empty_group(UNIT)


@pytest.mark.parametrize("fault", ["missing-events", "symlink-events", "symlink-group"])
def test_existing_group_without_readable_direct_events_is_not_retired(
    tmp_path, monkeypatch, fault,
):
    monkeypatch.setattr(check, "CGROUP", str(tmp_path))
    group = tmp_path / UNIT
    if fault == "symlink-group":
        group.symlink_to(tmp_path, target_is_directory=True)
    else:
        group.mkdir()
        if fault == "symlink-events":
            (group / "cgroup.events").symlink_to(tmp_path / "absent")
    with pytest.raises(OSError):
        check.empty_group(UNIT)


def test_empty_and_retired_group_both_accepted_but_missing_slice_is_not(tmp_path, monkeypatch):
    monkeypatch.setattr(check, "CGROUP", str(tmp_path))
    check.empty_group(UNIT)
    group = tmp_path / UNIT
    group.mkdir()
    (group / "cgroup.events").write_text("populated 0\nfrozen 0\n")
    check.empty_group(UNIT)
    monkeypatch.setattr(check, "CGROUP", str(tmp_path / "missing"))
    with pytest.raises(FileNotFoundError):
        check.empty_group(UNIT)


@pytest.mark.parametrize("fault", ["platform", "uid", "unit", "path", "option"])
def test_unsupported_host_or_unit_refused_before_inspection(monkeypatch, fault):
    monkeypatch.setattr(check.sys, "platform", "darwin" if fault == "platform" else "linux")
    monkeypatch.setattr(check.os, "geteuid", lambda: 1 if fault == "uid" else 0)
    monkeypatch.setattr(check, "snapshot", lambda *_: pytest.fail("Host inspection occurred"))
    unit = {"unit": "wrong.socket", "path": "../wrong.service",
            "option": "--wrong.service"}.get(fault, UNIT)
    with pytest.raises(ValueError, match="private state must be retained"):
        check.verify_stopped(unit)


@pytest.mark.parametrize("changed", [False, True])
def test_two_stable_snapshots_surround_cgroup_evidence(monkeypatch, capsys, changed):
    monkeypatch.setattr(check.sys, "platform", "linux")
    monkeypatch.setattr(check.os, "geteuid", lambda: 0)
    after = stopped()
    if changed:
        after["InvocationID"] = "b" * 32
    replies = iter([stopped(), after])
    seen = []

    def snapshot(unit):
        seen.append(("snapshot", unit))
        return next(replies)

    monkeypatch.setattr(check, "snapshot", snapshot)
    monkeypatch.setattr(check, "empty_group", lambda u: seen.append(("cgroup", u)))
    if changed:
        with pytest.raises(ValueError, match="private state must be retained"):
            check.verify_stopped(UNIT)
    else:
        assert check.verify_stopped(UNIT) is None
    assert seen == [("snapshot", UNIT), ("cgroup", UNIT), ("snapshot", UNIT)]
    assert capsys.readouterr() == ("", "")


def test_private_inspection_exception_is_suppressed(monkeypatch, capsys):
    monkeypatch.setattr(check.sys, "platform", "linux")
    monkeypatch.setattr(check.os, "geteuid", lambda: 0)

    def fail(_):
        raise RuntimeError("PRIVATE")

    monkeypatch.setattr(check, "snapshot", fail)
    with pytest.raises(ValueError) as error:
        check.verify_stopped(UNIT)
    assert str(error.value) == check.ERROR and error.value.__suppress_context__
    assert capsys.readouterr() == ("", "")
