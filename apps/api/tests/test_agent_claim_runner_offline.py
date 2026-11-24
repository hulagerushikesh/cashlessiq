"""Private-plan and process denials without a database or local container."""

import json
import os
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest

from ciq_api import agent_claim_runner as runner
from ciq_api.agent_ledger import ClaimReceipt


@pytest.fixture
def values():
    return {
        "protocol": "ciq-fake-claim-v1", "database": "ciq_dummy", "database_oid": 12001,
        "login": "ciq_clinical", "login_oid": 12002, "password": "PRIVATE-DUMMY-PASSWORD",
        "capture_schema": "ciq_agent_capture", "request_id": "REQ-FAKE-0",
        "job_id": str(uuid4()),
    }


@pytest.mark.parametrize(("field", "value"), [
    ("protocol", "live"), ("database", "db?host=other"), ("database_oid", True),
    ("database_oid", 0), ("login", "role; SET ROLE postgres"), ("login_oid", "12002"),
    ("password", ""), ("password", "x" * 1025), ("capture_schema", "public"),
    ("request_id", ""), ("request_id", "x" * 121), ("job_id", "bad"),
    ("timeout_seconds", True), ("timeout_seconds", 121), ("timeout_seconds", 0),
    ("host", "remote"), ("dsn", "postgresql://private"), ("grant_id", str(uuid4())),
    ("command", "sh"), ("retry", True),
])
def test_bad_or_authority_selecting_plan_is_denied(values, field, value):
    with pytest.raises(ValueError):
        runner.ClaimPlan.model_validate({**values, field: value})


def test_plan_repr_hides_password_and_never_supplies_authority(values):
    plan = runner.ClaimPlan.model_validate(values)
    assert values["password"] not in repr(plan)
    assert plan.password.get_secret_value() == values["password"]
    assert plan.timeout_seconds == 120


@pytest.mark.parametrize("fault", [None, "symlink", "hardlink", "fifo", "directory",
                                   "public", "empty", "large", "owner"])
def test_credential_descriptor_rejects_unsafe_file_before_read(tmp_path, monkeypatch, fault):
    path = tmp_path / "claim.json"
    if fault == "symlink":
        (tmp_path / "other").write_bytes(b"private")
        path.symlink_to(tmp_path / "other")
    elif fault == "fifo":
        os.mkfifo(path, 0o600)
    elif fault == "directory":
        path.mkdir(mode=0o600)
    else:
        path.write_bytes(b"" if fault == "empty" else b"x" * (8193 if fault == "large" else 3))
        path.chmod(0o644 if fault == "public" else 0o600)
        if fault == "hardlink":
            os.link(path, tmp_path / "alias")
    parent = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        if fault:
            # An unsafe file must never reach the read operation, including FIFO.
            monkeypatch.setattr(runner.os, "read", lambda *_: pytest.fail("unsafe_secret_read"))
            with pytest.raises((ValueError, OSError)):
                runner._read_file(parent, os.getuid() + (1 if fault == "owner" else 0))
        else:
            assert runner._read_file(parent, os.getuid()) == b"xxx"
    finally:
        os.close(parent)


@pytest.mark.parametrize("fault", [None, "symlink", "writable", "owner"])
def test_directory_walk_rejects_replaced_or_writable_ancestor(tmp_path, fault):
    path = tmp_path / "private"
    if fault == "symlink":
        path.symlink_to(tmp_path, target_is_directory=True)
    else:
        path.mkdir(mode=0o700)
        if fault == "writable":
            path.chmod(0o777)
    parent = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        if fault:
            with pytest.raises((ValueError, OSError)):
                runner._directory(parent, "private", os.getuid() + (1 if fault == "owner" else 0))
        else:
            fd = runner._directory(parent, "private", os.getuid())
            os.close(fd)
    finally:
        os.close(parent)


@pytest.mark.parametrize("fault", [None, "duplicate", "unknown", "list", "truncated"])
def test_fixed_path_load_is_bounded_and_strict(tmp_path, values, monkeypatch, fault):
    path = tmp_path / "claim.json"
    data = json.dumps(values)
    if fault == "duplicate":
        data = data[:-1] + ',"job_id":"' + str(uuid4()) + '"}'
    elif fault == "unknown":
        data = json.dumps({**values, "tenant_id": str(uuid4())})
    elif fault == "list":
        data = "[]"
    elif fault == "truncated":
        data = data[:-1]
    path.write_text(data)
    path.chmod(0o600)
    # Real descriptor/file checks; fixture parent ancestry is outside this test.
    monkeypatch.setattr(runner, "PLAN", path)
    opened = runner._directory
    monkeypatch.setattr(runner, "_directory", lambda p, n, u: os.open(
        path.parent, os.O_RDONLY | os.O_DIRECTORY,
    ) if p is None else opened(p, ".", u))
    if fault:
        with pytest.raises(ValueError):
            runner.read_plan()
    else:
        assert runner.read_plan().job_id == runner.ClaimPlan.model_validate(values).job_id


@pytest.mark.parametrize("row", [None, ("ciq_dummy", 12003, "ciq_clinical", 12002),
                                  ("ciq_dummy", 12001, "ciq_clinical", 12003),
                                  ("other", 12001, "ciq_clinical", 12002),
                                  ("ciq_dummy", 12001, "other", 12002)])
def test_every_physical_connection_requires_exact_pinned_identity(values, row):
    class Raw:
        rolled_back = False

        @contextmanager
        def cursor(self):
            yield self

        def execute(self, statement):
            assert "pg_auth_members" in statement and "rolsuper" in statement

        def fetchone(self):
            return row

        def rollback(self):
            self.rolled_back = True

    raw = Raw()
    with pytest.raises(ValueError):
        runner._identity(raw, runner.ClaimPlan.model_validate(values))
    assert not raw.rolled_back


def test_fixed_single_claim_and_engine_disposal_even_on_failure(values, monkeypatch):
    calls = []
    plan = runner.ClaimPlan.model_validate(values)
    engine = SimpleNamespace(dispose=lambda: calls.append("disposed"))

    def create(url, **options):
        assert url.host == "127.0.0.1" and url.port == 5432 and not url.query
        assert url.username == plan.login and url.password == values["password"]
        assert options["poolclass"] is runner.NullPool
        assert options["connect_args"]["connect_timeout"] == 3
        calls.append("engine")
        return engine

    def listen(e, kind, check):
        assert e is engine and kind == "connect" and callable(check)
        calls.append("identity_check_installed")

    class Reservation:
        def __init__(self, e, *, schema):
            assert e is engine and schema == plan.capture_schema

        def claim_requested(self, request, job, *, timeout_seconds):
            assert (request, job, timeout_seconds) == (plan.request_id, plan.job_id, 120)
            calls.append("claim")
            raise ValueError("PRIVATE-DRIVER-ERROR")

    monkeypatch.setattr(runner, "create_engine", create)
    monkeypatch.setattr(runner.event, "listen", listen)
    monkeypatch.setattr(runner, "ControllerReservation", Reservation)
    with pytest.raises(ValueError):
        runner.claim_once(plan)
    assert calls == ["engine", "identity_check_installed", "claim", "disposed"]


@pytest.mark.parametrize("fault", ["guard", "file", "db", "output"])
def test_failed_process_never_logs_private_exception_or_receipt(monkeypatch, capsys, fault):
    receipt = ClaimReceipt(operation_id=uuid4(), state="reserved", version=1, fence_id=uuid4())
    calls = []

    def step(name, value=None):
        def run(*_):
            calls.append(name)
            if name == fault:
                raise ValueError("PRIVATE-PASSWORD-AND-SQL")
            return value
        return run

    monkeypatch.setattr(runner, "guard_process", step("guard"))
    monkeypatch.setattr(runner.resource, "setrlimit", lambda *_: None)
    monkeypatch.setattr(runner.signal, "signal", lambda *_: None)
    monkeypatch.setattr(runner.signal, "alarm", lambda *_: None)
    monkeypatch.setattr(runner, "read_plan", step("file", object()))
    monkeypatch.setattr(runner, "claim_once", step("db", receipt))
    if fault == "output":
        monkeypatch.setattr(runner.os, "write", step("output"))
    assert runner.main() == 1
    out = capsys.readouterr()
    assert not out.out and out.err == runner.ERROR
    stages = ["guard", "file", "db", "output"]
    assert calls == stages[:stages.index(fault) + 1]


def test_confirmed_claim_outputs_only_receipt_and_disarms_alarm(monkeypatch, capfd):
    receipt = ClaimReceipt(operation_id=uuid4(), state="reserved", version=1, fence_id=uuid4())
    alarms = []
    monkeypatch.setattr(runner.sys, "platform", "linux")
    monkeypatch.setattr(runner, "guard_process", lambda: None)
    monkeypatch.setattr(runner.resource, "setrlimit", lambda *_: None)
    monkeypatch.setattr(runner.signal, "signal", lambda *_: None)
    monkeypatch.setattr(runner.signal, "alarm", alarms.append)
    monkeypatch.setattr(runner, "read_plan", lambda: object())
    monkeypatch.setattr(runner, "claim_once", lambda _: receipt)
    assert runner.main() == 0
    out = capfd.readouterr()
    assert out.out == receipt.model_dump_json() + "\n" and not out.err
    assert alarms == [20, 0]


@pytest.mark.parametrize("fault", [None, "platform", "isolation", "bytecode", "argv", "root",
                                   "saved_uid", "saved_gid", "groups", "environment", "caps",
                                   "new_privs"])
def test_process_requires_clean_nonroot_identity_before_reading_plan(monkeypatch, fault):
    monkeypatch.setattr(runner.sys, "platform", "darwin" if fault == "platform" else "linux")
    monkeypatch.setattr(runner.sys, "flags", SimpleNamespace(isolated=fault != "isolation"))
    monkeypatch.setattr(runner.sys, "dont_write_bytecode", fault != "bytecode")
    monkeypatch.setattr(runner.sys, "argv", ["runner", "secret"] if fault == "argv" else ["runner"])
    monkeypatch.setattr(runner.os, "getuid", lambda: 0 if fault == "root" else 10001)
    monkeypatch.setattr(runner.os, "getgid", lambda: 10001)
    monkeypatch.setattr(runner.os, "getresuid", lambda: (
        10001, 10001, 0 if fault == "saved_uid" else 10001,
    ), raising=False)
    monkeypatch.setattr(runner.os, "getresgid", lambda: (
        10001, 10001, 0 if fault == "saved_gid" else 10001,
    ), raising=False)
    monkeypatch.setattr(runner.os, "getgroups", lambda: [10002] if fault == "groups" else [])
    monkeypatch.setattr(runner.os, "environ", {"PGHOST": "alternate"}
                        if fault == "environment" else {
                            "PATH": "/usr/bin:/bin", "LC_CTYPE": "C.UTF-8",
                        })
    status = "NoNewPrivs: 1\nCapInh: 0\nCapPrm: 0\nCapEff: 0\nCapAmb: 0\n"
    if fault == "caps":
        status = status.replace("CapPrm: 0", "CapPrm: 1")
    elif fault == "new_privs":
        status = status.replace("NoNewPrivs: 1", "NoNewPrivs: 0")
    monkeypatch.setattr(runner.Path, "read_text", lambda *_: status)
    if fault:
        with pytest.raises(ValueError):
            runner.guard_process()
    else:
        assert runner.guard_process() is None
