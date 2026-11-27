"""Explicit disposable CI only: real receipt/custody UIDs, no network or credentials."""

import os
import select
import shutil
import signal
import socket
import subprocess
import sys
from types import SimpleNamespace

import pytest

from ciq_api import agent_single_call_peer as peer

if not (
    sys.platform == "linux" and os.getuid() == 0
    and os.environ.get("GITHUB_ACTIONS") == "true"
    and os.environ.get("GITHUB_REPOSITORY") == "hulagerushikesh/cashlessiq"
    and os.environ.get("CIQ_AGENT_RECEIPT_PEER_TEST") == "1"
):
    pytest.skip("Single-call peer UID checks require disposable CI", allow_module_level=True)


@pytest.fixture
def peers(request):
    from test_agent_single_call_peer import reviewed_pin

    root = peer.ENDPOINT.parents[1]
    # Never adopt/remove an existing host path. This is a bounded test fixture.
    root.mkdir(mode=0o755)
    children = []

    def cleanup():
        for child in reversed(children):
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGKILL)
            child.communicate(timeout=3)
        shutil.rmtree(root)

    request.addfinalizer(cleanup)
    peer.ENDPOINT.parent.mkdir(mode=0o755)
    os.chown(peer.ENDPOINT.parent, 53003, 53003)
    material = None
    if getattr(request, "param", None) == "assembly":
        from single_call_fixtures import call_material
        material = call_material()
    pin = reviewed_pin() if material is None else material[2]
    # Only this fresh test parent may be written by the receipt UID.
    parent = root / "storage"
    parent.mkdir(mode=0o700)
    os.chown(parent, 53003, 53003)
    directory = parent / "retained"
    prefix = f"""
import os, resource, socket, struct, array
from pathlib import Path
from ciq_api import agent_single_call_peer as peer
from ciq_api.agent_single_call_journal import ReviewedCallPin, SingleCallJournal, ReportedTokenUsage
resource.setrlimit(resource.RLIMIT_CORE, (0,0))
pin = ReviewedCallPin.model_validate_json({pin.model_dump_json()!r})
directory = Path({str(directory)!r})
"""

    def launch(code, uid=53002, *, groups=(), extra_env=None):
        child = subprocess.Popen(
            (sys.executable, "-I", "-B", "-c", prefix + code), cwd="/",
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env={"LANG": "C.UTF-8"} | (extra_env or {}), user=uid, group=uid,
            extra_groups=groups, start_new_session=True,
        )
        children.append(child)
        return child

    def collect(child, expected):
        out, err = child.communicate(timeout=5)
        assert child.returncode == 0 and not err and out == expected, "fixed peer helper failed"

    def run(code, uid=53002, expected=b"PASS", **kwargs):
        collect(launch(code, uid, **kwargs), expected)

    run("SingleCallJournal.provision(directory, pin)\nos.write(1,b'PASS')", 53003)

    def start(*, denied=False, lost=False, attempt=False):
        peer.ENDPOINT.unlink(missing_ok=True)  # Quiescent fixture-owned endpoint only.
        code = f"""
journal = SingleCallJournal(directory, pin)
if {lost!r}:
    original = peer._send
    def lost_ack(connection, marker, value, end):
        if marker == peer._RESPONSE:
            raise OSError('DUMMY lost ACK')
        return original(connection, marker, value, end)
    peer._send = lost_ack
server = peer.SingleCallReceiptPeer(journal)
server.bind()
os.write(1,b'READY\\n')
try:
    server.serve_attempt() if {attempt!r} else server.serve_once()
    valid = {not denied!r}
except ValueError as error:
    valid = {denied!r} and str(error) == peer.ERROR
finally:
    server.close()
os.write(1,b'PASS' if valid else b'FAIL')
"""
        child = launch(code, 53003)
        assert select.select([child.stdout], [], [], 3)[0], "receipt readiness timed out"
        assert child.stdout.readline() == b"READY\n", "receipt readiness failed"
        return child

    denial = """
client = peer.SingleCallReceiptClient(pin)
try:
    client.issue()
except ValueError as error:
    assert str(error) == peer.ERROR
else:
    raise AssertionError('issue accepted')
try:
    client.status()
except ValueError as error:
    assert str(error) == peer.ERROR
else:
    raise AssertionError('failed client reused')
os.write(1,b'PASS')
"""
    return SimpleNamespace(start=start, run=run, collect=collect, launch=launch,
                           directory=directory, denial=denial, pin=pin, material=material)


def test_actual_uids_complete_lifecycle_and_reconstruction_denies_reissue(peers):
    s = peers
    for code in (
        "assert peer.SingleCallReceiptClient(pin).status().phase == 'ready'",
        "assert peer.SingleCallReceiptClient(pin).issue() is None",
        "assert peer.SingleCallReceiptClient(pin).observe('a'*64, provider_run_id='opaque', "
        "usage=ReportedTokenUsage(input_tokens=0,output_tokens=None)) is None",
        "status=peer.SingleCallReceiptClient(pin).status()\n"
        "assert status.phase == 'observed' and status.uncertain_units == 20\n"
        "assert status.reported_usage.output_tokens is None",
    ):
        server = s.start()
        s.run(code + "\nos.write(1,b'PASS')")
        s.collect(server, b"PASS")
    server = s.start(denied=True)
    s.run(s.denial)
    s.collect(server, b"PASS")


def test_fixed_attempt_pair_keeps_original_endpoint_across_provider_wait(peers):
    server = peers.start(attempt=True)
    peers.run("""
import time
client = peer.SingleCallReceiptClient(pin)
assert client.issue() is None
time.sleep(2.1)  # Beyond the per-frame budget, inside the fixed outer pair.
assert client.observe('a'*64, provider_run_id='opaque',
    usage=ReportedTokenUsage(input_tokens=None,output_tokens=None)) is None
os.write(1,b'PASS')
""")
    peers.collect(server, b"PASS")
    peers.run("assert SingleCallJournal(directory,pin).status().phase == 'observed'\n"
              "os.write(1,b'PASS')", 53003)


@pytest.mark.parametrize("command", ["status", "observe"])
def test_fixed_pair_rejects_nonissue_first_without_retention_change(peers, command):
    server = peers.start(attempt=True, denied=True)
    peers.run(f"""
client = peer.SingleCallReceiptClient(pin)
try:
    if {command!r} == 'status':
        client.status()
    else:
        client.observe('a'*64,provider_run_id='opaque',
            usage=ReportedTokenUsage(input_tokens=None,output_tokens=None))
except ValueError as error:
    assert str(error) == peer.ERROR
else:
    raise AssertionError('wrong first command accepted')
os.write(1,b'PASS')
""")
    peers.collect(server, b"PASS")
    peers.run("assert SingleCallJournal(directory,pin).status().phase == 'ready'\n"
              "os.write(1,b'PASS')", 53003)


@pytest.mark.parametrize("uid", [53001, 53002, 53004])
def test_nonreceipt_uids_cannot_read_or_replace_retention(peers, uid):
    peers.run("""
try:
    (directory/'single-call.sqlite3').read_bytes()
except PermissionError:
    pass
else:
    raise AssertionError('retention read')
try:
    (directory/'single-call.sqlite3').write_bytes(b'replacement')
except PermissionError:
    pass
else:
    raise AssertionError('retention replaced')
os.write(1,b'PASS')
""", uid)


@pytest.mark.parametrize("uid", [53001, 53004])
def test_wrong_kernel_client_uid_denied_before_mutation(peers, uid):
    server = peers.start(denied=True)
    peers.run("""
with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as connection:
    connection.settimeout(3)
    connection.connect(str(peer.ENDPOINT))
    assert connection.recv(1) == b''
os.write(1,b'PASS')
""", uid)
    peers.collect(server, b"PASS")
    peers.run("assert SingleCallJournal(directory,pin).status().phase == 'ready'\n"
              "os.write(1,b'PASS')", 53003)


def test_correct_socket_owner_but_false_kernel_server_receives_no_pins(peers):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
        listener.bind(str(peer.ENDPOINT))
        os.chown(peer.ENDPOINT, 53003, 53003)
        peer.ENDPOINT.chmod(0o666)
        listener.listen(1)
        listener.settimeout(3)
        client = peers.launch(peers.denial)
        connection, _ = listener.accept()
        with connection:
            connection.settimeout(3)
            assert connection.recv(1) == b""  # Root is not receipt UID 53003.
        peers.collect(client, b"PASS")


def test_real_cross_uid_commit_then_ack_loss_preserves_issue(peers):
    server = peers.start(denied=True, lost=True)
    peers.run(peers.denial)
    peers.collect(server, b"PASS")
    server = peers.start()
    peers.run("status=peer.SingleCallReceiptClient(pin).status()\n"
              "assert status.phase == 'issued' and status.uncertain_units == 20\n"
              "os.write(1,b'PASS')")
    peers.collect(server, b"PASS")
    server = peers.start(denied=True)
    peers.run(peers.denial)
    peers.collect(server, b"PASS")


@pytest.mark.parametrize("kind", ["descriptor", "extended", "missing-eof"])
def test_real_malformed_frames_never_mutate_retention(peers, kind):
    from test_agent_single_call_peer import frame, request

    wire = frame(request(peers.pin))
    server = peers.start(denied=True)
    peers.run(f"""
with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as connection:
    connection.settimeout(3)
    connection.connect(str(peer.ENDPOINT))
    wire={wire!r}
    try:
        if {kind!r} == 'descriptor':
            fd=os.open('/dev/null',os.O_RDONLY)
            try:
                connection.sendmsg([wire],[(socket.SOL_SOCKET,socket.SCM_RIGHTS,array.array('i',[fd]))])
            finally:
                os.close(fd)
        else:
            connection.sendall(wire + (b'extension' if {kind!r} == 'extended' else b''))
        if {kind!r} != 'missing-eof':
            connection.shutdown(socket.SHUT_WR)
        assert connection.recv(1) == b''
    except (BrokenPipeError,ConnectionResetError):
        pass
os.write(1,b'PASS')
""")
    peers.collect(server, b"PASS")
    peers.run("assert SingleCallJournal(directory,pin).status().phase == 'ready'\n"
              "os.write(1,b'PASS')", 53003)
