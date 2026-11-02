"""Offline fake IPC/process failures. No Docker, database, provider or credentials."""

import base64
import hashlib
import importlib.util
import json
import os
import signal
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from test_agent_contracts import capture

from ciq_api.agent_contracts import AgentContractError
from ciq_api.agent_executor import (
    MAX_CANDIDATE,
    MAX_REPLY,
    MAX_REQUEST,
    BoundedFakeProcess,
    FakeProcessRequest,
    decode_reply,
)

ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT / "apps/agent-transport/fake_transport.py"
spec = importlib.util.spec_from_file_location("fake_transport", RUNTIME)
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)
NOW = datetime.now(UTC)


def packet(**changes):
    snapshot = capture()
    return FakeProcessRequest(**{
        "operation_id": uuid4(), "attempt_id": uuid4(), "submission_id": uuid4(),
        "tenant_id": snapshot.binding.tenant_id, "config_digest": "a" * 64,
        "source_digest": "b" * 64, "deadline": NOW + timedelta(seconds=30),
        "snapshot": snapshot, **changes,
    }).wire()


def fixture(raw, candidate=b'{"synthetic":"clinical-only"}'):
    return json.dumps({
        "request_sha256": hashlib.sha256(raw).hexdigest(),
        "candidate_base64": base64.b64encode(candidate).decode(),
    }).encode()


def child(code):
    return BoundedFakeProcess((sys.executable, "-I", "-c", code))


ECHO = """
import base64, hashlib, json, sys
raw = sys.stdin.buffer.read()
sys.stdout.write(json.dumps({"protocol":"ciq-fake-process-v1",
 "request_sha256":hashlib.sha256(raw).hexdigest(),
 "candidate_base64":base64.b64encode(b'{}').decode()}))
"""


def test_exact_fixture_roundtrip_and_clinical_repr_hidden():
    raw = packet()
    response = runtime.respond(raw, fixture(raw), now=NOW)
    assert decode_reply(response, raw) == b'{"synthetic":"clinical-only"}'
    request = FakeProcessRequest.model_validate_json(raw)
    assert "member_reference" not in repr(request)
    assert "facts_json" not in repr(request)


@pytest.mark.parametrize("field", [
    "operation_id", "attempt_id", "submission_id", "tenant_id", "config_digest",
    "source_digest", "deadline", "snapshot",
])
def test_fixed_fixture_cannot_be_reused_for_any_changed_packet(field):
    raw = packet()
    changed = json.loads(raw)
    if field == "snapshot":
        changed[field]["facts_json"] = "sensitive-drift"
    elif field == "deadline":
        changed[field] = (NOW + timedelta(seconds=20)).isoformat()
    else:
        changed[field] = str(uuid4()) if field.endswith("_id") else "c" * 64
    changed_raw = json.dumps(changed).encode()
    with pytest.raises(ValueError):
        runtime.respond(changed_raw, fixture(raw), now=NOW)


@pytest.mark.parametrize("changes", [
    {"protocol": "live"}, {"credential": "secret"}, {"endpoint": "https://example.com"},
    {"command": "anything"}, {"retry": True}, {"fixture": "/other"},
    {"tenant_id": str(uuid4())}, {"source_digest": "g" * 64}, {"config_digest": 1},
    {"deadline": NOW.isoformat()}, {"deadline": (NOW + timedelta(seconds=121)).isoformat()},
    {"deadline": NOW.replace(tzinfo=None).isoformat()},
])
def test_even_repinned_fixture_does_not_accept_execution_selectors_or_bad_envelope(changes):
    request = json.loads(packet())
    request.update(changes)
    raw = json.dumps(request).encode()
    with pytest.raises((ValueError, TypeError)):
        runtime.respond(raw, fixture(raw), now=NOW)


@pytest.mark.parametrize("raw", [b"", b"[]", b"null", b"{", b"x" * (MAX_REQUEST + 1)])
def test_bad_input_unavailable(raw):
    with pytest.raises((ValueError, TypeError)):
        runtime.respond(raw, b"{}", now=NOW)


@pytest.mark.parametrize("mutation", ["duplicate", "extra", "missing", "bad64", "oversize"])
def test_fixed_fixture_shape_and_bounds(mutation):
    raw = packet()
    value = json.loads(fixture(raw))
    if mutation == "duplicate":
        payload = b'{"request_sha256":"one",' + fixture(raw)[1:]
    else:
        if mutation == "extra":
            value["credential"] = "not-allowed"
        if mutation == "missing":
            del value["request_sha256"]
        if mutation == "bad64":
            value["candidate_base64"] = "!"
        if mutation == "oversize":
            value["candidate_base64"] = base64.b64encode(b"x" * (MAX_CANDIDATE + 1)).decode()
        payload = json.dumps(value).encode()
    with pytest.raises(ValueError):
        runtime.respond(raw, payload, now=NOW)


@pytest.mark.parametrize("mutation", [
    "wrong_request", "extra", "duplicate", "bad64", "empty", "too_big", "deep", "wrong_protocol",
])
def test_reply_failures_are_fixed_and_never_echo_clinical_data(mutation):
    raw = packet()
    value = json.loads(runtime.respond(raw, fixture(raw), now=NOW))
    if mutation == "wrong_request":
        value["request_sha256"] = "c" * 64
    if mutation == "extra":
        value["clinical-secret"] = "private"
    if mutation == "bad64":
        value["candidate_base64"] = "private!"
    if mutation == "wrong_protocol":
        value["protocol"] = "live"
    bad = json.dumps(value).encode()
    if mutation == "duplicate":
        bad = b'{"protocol":"private",' + bad[1:]
    if mutation == "empty":
        bad = b""
    if mutation == "too_big":
        bad = b"private" * MAX_REPLY
    if mutation == "deep":
        bad = b"[" * 2000 + b"]" * 2000
    with pytest.raises(AgentContractError, match=r"^invalid_fake_process_reply$"):
        decode_reply(bad, raw)


def test_actual_child_has_no_parent_credentials_and_cannot_inherit_open_fd(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", "parent-db-secret")
    monkeypatch.setenv("SNOWFLAKE_TOKEN", "parent-provider-secret")
    monkeypatch.setenv("PYTHONPATH", "/parent-sensitive")
    path = tmp_path / "private"
    path.write_text("parent-private")
    with path.open() as stream:
        os.set_inheritable(stream.fileno(), True)
        code = f"""
import os
assert not set(os.environ) & {{'DATABASE_URL','SNOWFLAKE_TOKEN','PYTHONPATH'}}
try:
 os.fstat({stream.fileno()})
except OSError:
 pass
else:
 raise RuntimeError('unexpected-inherited-fd')
""" + ECHO
        transport = child(code)
        assert transport.exchange(packet(), timeout=2) == b"{}"
        with pytest.raises(AgentContractError, match=r"^fake_transport_unavailable$"):
            transport.exchange(packet(), timeout=2)


@pytest.mark.parametrize("code", [
    "import sys; sys.stderr.write('private clinical text')",
    "import sys; sys.stdout.write('private'); sys.exit(7)",
    "import sys; sys.stdout.write('x'*2000000); sys.stdout.flush()",
    "import sys; sys.stderr.write('x'*2000000); sys.stderr.flush()",
    "import time; time.sleep(60)",
    "import sys; sys.stdout.write('malformed private response')",
    "import os,signal; os.kill(os.getpid(), signal.SIGKILL)",
])
def test_child_faults_are_bounded_and_safe(code):
    start = time.monotonic()
    with pytest.raises(AgentContractError, match=r"^fake_transport_unavailable$"):
        child(code).exchange(packet(), timeout=0.3)
    assert time.monotonic() - start < 3


@pytest.mark.parametrize("timeout", [0, -1, 11, float("nan"), float("inf"), True, "1"])
def test_invalid_budget_never_spawns(timeout):
    with pytest.raises(AgentContractError, match=r"^fake_transport_unavailable$"):
        child("raise AssertionError").exchange(packet(), timeout=timeout)


def test_missing_executable_safe_and_not_retried():
    transport = BoundedFakeProcess(("/definitely-missing-ciq-fake",))
    for _ in range(2):
        with pytest.raises(AgentContractError, match=r"^fake_transport_unavailable$"):
            transport.exchange(packet(), timeout=1)


def test_forced_timeout_kills_child_and_descendant_group(tmp_path):
    pid_file = tmp_path / "pid"
    code = f"""
import os, time
from pathlib import Path
pid = os.fork()
if pid == 0:
 Path({str(pid_file)!r}).write_text(str(os.getpid()))
 time.sleep(60)
else:
 time.sleep(60)
"""
    with pytest.raises(AgentContractError):
        child(code).exchange(packet(), timeout=0.5)
    pid = int(pid_file.read_text())
    # Linux can retain an orphan zombie until its init reaps it; it cannot run.
    proc = Path(f"/proc/{pid}/stat")
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return
    if sys.platform == "linux" and proc.is_file():
        assert proc.read_text().split()[2] == "Z"
    else:
        os.kill(pid, signal.SIGKILL)
        pytest.fail("Descendant remains alive")
