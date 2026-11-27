"""Private dummy pipes and bounded local children; never provider/network IO."""

import base64
import hashlib
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from ciq_api import agent_https_process as process

HOST = "reviewed-account.snowflakecomputing.com"
TOKEN = "DUMMY-private-token"
BODY = b'{"synthetic":"PRIVATE facts"}'
REPLY = b'{"synthetic":"PRIVATE result"}'
REAL_POPEN = subprocess.Popen


def configured(**updates):
    values = dict(python=sys.executable, hostname=HOST, token=TOKEN,
                  request_sha256=hashlib.sha256(BODY).hexdigest(), body=BODY)
    return process.BoundedHTTPSProcess(**(values | updates))


def control(**updates):
    value = dict(hostname=HOST, token=TOKEN, request_sha256=hashlib.sha256(BODY).hexdigest(),
                 body=base64.b64encode(BODY).decode())
    return json.dumps(value | updates, separators=(",", ":")).encode()


@pytest.fixture
def child_harness(monkeypatch):
    state = {"code": "import os; os._exit(1)", "children": [], "commands": []}

    def start(argv, **kwargs):
        # The production supervisor has no script, argv or environment override.
        assert argv == (sys.executable, "-I", "-B", "-m", "ciq_api.agent_https_worker")
        assert kwargs == dict(stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, cwd="/", env={"LANG": "C.UTF-8"},
                              close_fds=True, start_new_session=True)
        state["commands"].append(argv)
        # Test-only replacement exercises real isolated Python and the real
        # supervisor without granting this test a way to contact Snowflake.
        child = REAL_POPEN((sys.executable, "-I", "-B", "-c", state["code"]), **kwargs)
        state["children"].append(child)
        return child

    monkeypatch.setattr(process.subprocess, "Popen", start)
    yield state
    for child in state["children"]:
        assert child.poll() is not None
        assert all(pipe.closed for pipe in (child.stdin, child.stdout, child.stderr))


def test_actual_worker_private_pipe_clean_environment_and_fds(child_harness, monkeypatch, tmp_path):
    secret = tmp_path / "private-parent-file"
    secret.write_text("PRIVATE file content")
    descriptor = os.open(secret, os.O_RDONLY)
    os.set_inheritable(descriptor, True)
    for key in ("DATABASE_URL", "SNOWFLAKE_TOKEN", "PYTHONPATH", "HTTPS_PROXY",
                "SSL_CERT_FILE", "SSL_CERT_DIR", "SSLKEYLOGFILE"):
        monkeypatch.setenv(key, "PRIVATE-inherited-value")
    child_harness["code"] = f"""
import os, resource
from ciq_api.agent_https_worker import main
from ciq_api.agent_https_transport import SinglePostHTTPS
def exchange(self, body, *, timeout):
    assert body == {BODY!r} and timeout == 10 and self._token == {TOKEN!r}
    assert os.getcwd() == '/'
    assert set(os.environ) <= {{'LANG', 'LC_CTYPE', '__CF_USER_TEXT_ENCODING'}}
    assert resource.getrlimit(resource.RLIMIT_CORE) == (0, 0)
    try:
        os.fstat({descriptor})
    except OSError:
        pass
    else:
        raise AssertionError('inherited descriptor')
    return {REPLY!r}
SinglePostHTTPS.exchange = exchange
os._exit(main())
"""
    try:
        transport = configured()
        assert TOKEN not in repr(transport) and "PRIVATE facts" not in repr(transport)
        assert transport.exchange(timeout=3) == REPLY
        assert transport._control is None
        assert len(child_harness["children"]) == 1
        assert TOKEN not in repr(child_harness["commands"])
    finally:
        os.close(descriptor)


@pytest.mark.parametrize("code", [
    "import time; time.sleep(20)",  # Never reads stdin.
    "import sys,time; sys.stdin.buffer.read(); time.sleep(20)",  # Stalled DNS/headers.
    "import os,time; os.close(0); os.close(1); os.close(2); time.sleep(20)",
    "import os,time; os.write(1,b'x'); time.sleep(20)",  # Partial response cannot reset clock.
])
def test_deadline_kills_stalled_child_and_no_replay(child_harness, code):
    child_harness["code"] = code
    transport = configured()
    start = time.monotonic()
    with pytest.raises(ValueError, match=f"^{process.ERROR}$"):
        transport.exchange(timeout=0.2)
    assert time.monotonic() - start < 2
    with pytest.raises(ValueError, match=f"^{process.ERROR}$"):
        transport.exchange(timeout=1)
    assert len(child_harness["children"]) == 1
    assert transport._control is None


def test_actual_worker_blocked_dns_is_killed(child_harness, tmp_path):
    marker = tmp_path / "dummy-dns-reached"
    child_harness["code"] = f"""
import os, socket, time
from pathlib import Path
from ciq_api.agent_https_worker import main
def blocked(*args, **kwargs):
    Path({str(marker)!r}).write_text('dummy-dns-reached')
    time.sleep(20)
    raise AssertionError('must not finish')
socket.getaddrinfo = blocked
os._exit(main())
"""
    with pytest.raises(ValueError, match=f"^{process.ERROR}$"):
        configured().exchange(timeout=0.4)
    assert marker.read_text() == "dummy-dns-reached"


@pytest.mark.parametrize("code", [
    "import os; os._exit(0)",
    "import os; os.write(1,b'PRIVATE response'); os._exit(1)",
    "import os; os.write(2,b'PRIVATE token/server diagnostic'); os._exit(0)",
    "import os; os.write(1,b'x'*384001)",
    # Descendant holds pipes after original exits; supervisor kills its group.
    "import os,time; pid=os.fork(); time.sleep(20) if pid==0 else os._exit(0)",
])
def test_private_failures_bounds_and_inherited_pipe_holder(child_harness, code, capsys):
    child_harness["code"] = code
    with pytest.raises(ValueError) as error:
        configured().exchange(timeout=0.4)
    assert str(error.value) == process.ERROR
    assert error.value.__suppress_context__
    assert capsys.readouterr() == ("", "")


def test_complete_input_and_maximum_response(child_harness):
    child_harness["code"] = """
import os, sys
from ciq_api.agent_https_process import decode_control
_, body = decode_control(sys.stdin.buffer.read())
assert len(body) == 256000
response = memoryview(b'x'*384000)
while response:
    response = response[os.write(1, response):]
"""
    body = b"x" * 256_000
    transport = configured(body=body, request_sha256=hashlib.sha256(body).hexdigest(),
                           token="x" * 8192)
    assert transport.exchange(timeout=3) == b"x" * 384_000


def test_concurrent_attempts_spawn_once(child_harness):
    child_harness["code"] = "import sys,os; sys.stdin.buffer.read(); os.write(1,b'{}')"
    transport = configured()

    def exchange():
        try:
            return transport.exchange(timeout=3)
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: exchange(), range(2)))
    assert sorted(results, key=lambda item: item is None) == [b"{}", None]
    assert len(child_harness["children"]) == 1


@pytest.mark.parametrize("timeout", [True, None, "1", 0, -1, 12.01, float("nan"), float("inf")])
def test_bad_budget_consumed_without_spawn(child_harness, timeout):
    transport = configured()
    with pytest.raises(ValueError, match=f"^{process.ERROR}$"):
        transport.exchange(timeout=timeout)
    with pytest.raises(ValueError):
        transport.exchange(timeout=1)
    assert not child_harness["children"] and transport._control is None


def test_spawn_failure_is_not_retried(child_harness, monkeypatch):
    attempts = []

    def fail(*args, **kwargs):
        attempts.append(True)
        raise OSError("PRIVATE spawn detail")

    monkeypatch.setattr(process.subprocess, "Popen", fail)
    transport = configured()
    for _ in range(2):
        with pytest.raises(ValueError, match=f"^{process.ERROR}$"):
            transport.exchange(timeout=1)
    assert len(attempts) == 1


def test_cleanup_error_remains_fixed_and_closes_pipes(child_harness, monkeypatch):
    child_harness["code"] = "import sys; sys.stdin.buffer.read()"

    def denied(*args):
        # This child has already exited; exercise denial without leaving any
        # process running or suppressing a real cleanup obligation.
        child_harness["children"][0].wait(timeout=1)
        raise PermissionError("PRIVATE kernel diagnostic")

    monkeypatch.setattr(process.os, "killpg", denied)
    with pytest.raises(ValueError, match=f"^{process.ERROR}$"):
        configured().exchange(timeout=3)


@pytest.mark.parametrize("updates", [
    {"python": "python"}, {"python": "/private\0python"}, {"python": None},
    {"hostname": "localhost"}, {"token": "PRIVATE\nheader"},
    {"request_sha256": "a" * 64}, {"body": bytearray(BODY)}, {"body": b""},
    {"body": b"x" * 256_001},
])
def test_invalid_configuration_never_spawns(child_harness, updates):
    with pytest.raises(ValueError, match=f"^{process.ERROR}$"):
        configured(**updates)
    assert not child_harness["children"]


@pytest.mark.parametrize("raw", [
    b"", b"x" * 352_001, b"\xff", b"null", b"[]", b"{}", b"{" * 10000,
    control()[:-1] + b',"token":"other"}',
    control()[:-1] + b',"extra":true}',
    control(body="!"), control(body=""), control(body=True),
    control(hostname="localhost"), control(request_sha256="a" * 64),
])
def test_invalid_control_never_constructs_exchange(raw):
    with pytest.raises(ValueError, match=f"^{process.ERROR}$"):
        process.decode_control(raw)


def test_actual_worker_rejects_malformed_control_without_output():
    result = subprocess.run(
        (sys.executable, "-I", "-B", "-m", "ciq_api.agent_https_worker"),
        input=b'{"token":"PRIVATE"}', capture_output=True, cwd="/",
        env={"LANG": "C.UTF-8"}, timeout=3,
    )
    assert result.returncode == 1 and result.stdout == b"" and result.stderr == b""


def test_worker_rejects_inherited_ca_override_without_output():
    result = subprocess.run(
        (sys.executable, "-I", "-B", "-m", "ciq_api.agent_https_worker"),
        input=b"", capture_output=True, cwd="/",
        env={"LANG": "C.UTF-8", "SSL_CERT_FILE": "PRIVATE-ca-file"}, timeout=3,
    )
    assert result.returncode == 1 and result.stdout == b"" and result.stderr == b""
