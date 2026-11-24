"""Custody startup faults without PostgreSQL, Docker or provider calls."""

import json
import os
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from test_agent_contracts import candidate, capture
from test_agent_executor import packet

from ciq_api import agent_canned_exchange as child
from ciq_api import agent_custody_runner as runner
from ciq_api import agent_private_file as private
from ciq_api.agent_executor import decode_reply
from ciq_api.agent_ledger import ClaimReceipt


@pytest.fixture
def values():
    return {
        "protocol": "ciq-fake-custody-v1", "database": "ciq_dummy", "database_oid": 12001,
        "login": "ciq_custody", "login_oid": 12002, "password": "PRIVATE-PASSWORD",
        "receipts_schema": "ciq_agent_receipts", "request_id": "REQ-FAKE-0",
        "claim": {"operation_id": str(uuid4()), "state": "reserved", "version": 1,
                  "fence_id": str(uuid4())},
        "epoch": {"database_id": str(uuid4()), "epoch_id": str(uuid4())},
        "receipt_uid": 10003,
    }


@pytest.mark.parametrize(("field", "value"), [
    ("protocol", "live"), ("database", "db?host=other"), ("database_oid", True),
    ("database_oid", 0), ("login", "owner;SET ROLE postgres"), ("login_oid", "12002"),
    ("password", ""), ("password", "x" * 1025), ("receipts_schema", "public"),
    ("request_id", ""), ("request_id", "x" * 121), ("receipt_uid", 0),
    ("receipt_uid", True), ("receipt_uid", 2**31), ("host", "remote"),
    ("dsn", "postgresql://private"), ("socket", "/tmp/peer"), ("command", "sh"),
    ("retry", True), ("grant", str(uuid4())), ("candidate", {}),
])
def test_plan_rejects_invalid_or_authority_selecting_fields(values, field, value):
    with pytest.raises(ValueError):
        runner.CustodyPlan.model_validate({**values, field: value})


@pytest.mark.parametrize(("field", "value"), [
    ("state", "submitting"), ("version", True), ("version", "1"), ("version", 0),
    ("version", 2_147_483_647), ("submission_id", str(uuid4())),
])
def test_startup_cannot_adopt_pending_issue_or_coerce_version(values, field, value):
    values["claim"][field] = value
    with pytest.raises(ValueError):
        runner.CustodyPlan.model_validate(values)


def test_only_private_fixed_plan_is_loaded(values, monkeypatch):
    def read(path, maximum):
        assert path == runner.PLAN and maximum == 8192
        return values
    monkeypatch.setattr(runner, "private_object", read)
    plan = runner.read_plan()
    assert "PRIVATE-PASSWORD" not in repr(plan)
    assert plan.claim.state == "reserved"


@pytest.mark.parametrize("fails", [False, True])
def test_one_original_coordinator_has_fixed_child_no_owner_fallback(values, monkeypatch, fails):
    plan = runner.CustodyPlan.model_validate(values)
    calls = []
    engine = SimpleNamespace(dispose=lambda: calls.append("disposed"))
    peer = object()

    def create(url, **options):
        assert (url.host, url.port, url.database) == ("127.0.0.1", 5432, plan.database)
        assert (url.username, url.password, url.query) == (plan.login, "PRIVATE-PASSWORD", {})
        assert options["poolclass"] is runner.NullPool
        assert options["connect_args"]["connect_timeout"] == 3
        assert "lock_timeout=2000" in options["connect_args"]["options"]
        calls.append("engine")
        return engine

    def client(path, pin, *, server_uid, custody_uid):
        assert path == runner.SOCKET and pin == plan.epoch
        assert server_uid == 10003 and custody_uid == 10002
        calls.append("peer")
        return peer

    def transport(argv):
        assert argv == (runner.sys.executable, "-I", "-B", "-m", "ciq_api.agent_canned_exchange")
        calls.append("transport")
        return "fixed-transport"

    class Original:
        def __init__(self, e, p, *, schema, request_id, claim, transport):
            assert e is engine and p is peer and schema == plan.receipts_schema
            assert request_id == plan.request_id and type(claim) is ClaimReceipt
            assert claim.model_dump() == plan.claim.model_dump() and transport == "fixed-transport"
            calls.append("original")

        def run(self):
            calls.append("run")
            if fails:
                raise ValueError("PRIVATE-SQL")

    monkeypatch.setattr(runner.os, "getuid", lambda: 10002)
    monkeypatch.setattr(runner, "create_engine", create)
    monkeypatch.setattr(runner, "FakeReceiptPeerClient", client)
    monkeypatch.setattr(runner, "BoundedFakeProcess", transport)
    monkeypatch.setattr(runner, "FakeCustodySubmission", Original)
    def listen(e, kind, check):
        assert e is engine and kind == "connect" and callable(check)
        calls.append("identity_check")
    monkeypatch.setattr(runner.event, "listen", listen)
    if fails:
        with pytest.raises(ValueError):
            runner.run_once(plan)
    else:
        assert runner.run_once(plan) is None
    assert calls == ["peer", "engine", "identity_check", "transport", "original", "run", "disposed"]


def test_same_receipt_and_custody_uid_denied_before_any_io(values, monkeypatch):
    monkeypatch.setattr(runner.os, "getuid", lambda: 10003)
    with pytest.raises(ValueError):
        runner.run_once(runner.CustodyPlan.model_validate(values))


@pytest.mark.parametrize("fault", [None, "guard", "plan", "run", "output"])
def test_process_reports_only_confirmed_status_or_fixed_error(monkeypatch, capfd, fault):
    calls, alarms = [], []

    def step(name):
        def run(*_):
            calls.append(name)
            if name == fault:
                raise ValueError("PRIVATE-PASSWORD-AND-CLINICAL-DATA")
        return run

    monkeypatch.setattr(runner.sys, "platform", "linux")
    monkeypatch.setattr(runner, "guard_process", step("guard"))
    monkeypatch.setattr(runner.resource, "setrlimit", lambda *_: None)
    monkeypatch.setattr(runner.signal, "signal", lambda *_: None)
    monkeypatch.setattr(runner.signal, "alarm", alarms.append)
    monkeypatch.setattr(runner, "read_plan", step("plan"))
    monkeypatch.setattr(runner, "run_once", step("run"))
    if fault == "output":
        write = runner.os.write
        def fail_stdout(fd, raw):
            if fd == 1:
                raise BrokenPipeError
            return write(fd, raw)
        monkeypatch.setattr(runner.os, "write", fail_stdout)
    assert runner.main() == (1 if fault else 0)
    out = capfd.readouterr()
    assert out.out == ("" if fault else runner.SUCCESS.decode())
    assert out.err == (runner.ERROR if fault else "")
    assert alarms[-1] == 0
    if fault != "guard":
        assert alarms == [35, 0]
    assert calls == ["guard", "plan", "run"][:
        {"guard": 1, "plan": 2}.get(fault, 3)
    ]


@pytest.mark.parametrize("fault", [None, "symlink", "hardlink", "fifo", "directory", "mode",
                                   "empty", "large", "owner", "ancestor"])
def test_private_operator_files_check_metadata_before_read(tmp_path, monkeypatch, fault):
    path = tmp_path / "plan.json"
    if fault == "fifo":
        os.mkfifo(path, 0o600)
    elif fault == "directory":
        path.mkdir()
    else:
        path.write_bytes(b"" if fault == "empty" else b"x" * (65 if fault == "large" else 32))
        path.chmod(0o644 if fault == "mode" else 0o600)
    if fault == "symlink":
        path.rename(tmp_path / "target")
        path.symlink_to(tmp_path / "target")
    elif fault == "hardlink":
        os.link(path, tmp_path / "other")
    elif fault == "owner":
        monkeypatch.setattr(private.os, "getuid", lambda: os.stat(path).st_uid + 1)
    # Retain real descriptor/file checks while avoiding macOS's /var symlink
    # and pytest's writable /tmp ancestry, which are outside this fixture.
    opened = private.directory
    def directory(parent, name, uid):
        if parent is None:
            if fault == "ancestor":
                raise ValueError("unsafe_ancestor")
            return os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
        return opened(parent, ".", uid)
    monkeypatch.setattr(private, "directory", directory)
    if fault:
        with pytest.raises((ValueError, OSError)):
            private.read_private(path, 64)
    else:
        assert private.read_private(path, 64) == b"x" * 32


@pytest.mark.parametrize("raw", [b'{"key":1,"key":2}', b"[]", b"{", b"null"])
def test_private_json_never_adopts_duplicate_or_nonobject(raw, monkeypatch):
    monkeypatch.setattr(private, "read_private", lambda *_: raw)
    with pytest.raises(ValueError):
        private.private_object(runner.PLAN, 8192)


@pytest.mark.parametrize("fault", [None, "symlink", "writable"])
def test_private_parent_rejects_actual_symlink_or_writable_directory(tmp_path, fault):
    path = tmp_path / "parent"
    path.mkdir(mode=0o700)
    if fault == "symlink":
        path.rename(tmp_path / "target")
        path.symlink_to(tmp_path / "target", target_is_directory=True)
    elif fault == "writable":
        path.chmod(0o777)
    if fault:
        with pytest.raises((OSError, ValueError)):
            private.directory(None, path, os.getuid())
    else:
        os.close(private.directory(None, path, os.getuid()))


@pytest.mark.parametrize("fault", [None, "operation", "expired", "future", "duplicate", "size"])
def test_canned_child_returns_only_one_operation_bound_synthetic_candidate(fault):
    snapshot = capture()
    raw = packet(snapshot=snapshot)
    value = json.loads(raw)
    now = datetime.now(UTC)
    body = candidate(snapshot, value["operation_id"])
    if fault == "operation":
        body["run_id"] = str(uuid4())
    elif fault == "size":
        body["extra"] = "x" * 128_001
    elif fault in {"expired", "future"}:
        value["deadline"] = (now + timedelta(seconds=-1 if fault == "expired" else 121)).isoformat()
        raw = json.dumps(value).encode()
    elif fault == "duplicate":
        raw = raw[:-1] + b',"protocol":"ciq-fake-process-v1"}'
    if fault:
        with pytest.raises(ValueError):
            child.respond(raw, body, now=now)
    else:
        assert json.loads(decode_reply(child.respond(raw, body, now=now), raw)) == body
