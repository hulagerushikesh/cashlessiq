"""Dummy cross-UID IPC checks, called only after the guarded fresh CI fixture."""

import os
import select
import signal
import socket
import subprocess
import sys


def run_controls(*, runtime, private, worker, body, reply):
    if not (
        sys.platform == "linux" and os.geteuid() == 0
        and os.environ.get("GITHUB_ACTIONS") == "true"
        and os.environ.get("GITHUB_REPOSITORY") == "hulagerushikesh/cashlessiq"
        and os.environ.get("CIQ_PROVIDER_IDENTITY_TEST") == "1"
    ):
        raise SystemExit("Provider IPC acceptance requires explicit disposable Linux CI")
    # Caller has already refused host paths/occupied UIDs and staged dummy data.
    # This module has no entry point; never invoke these fixtures on an owner host.
    endpoint_dir = private / "ipc"
    endpoint_dir.mkdir(mode=0o755)
    os.chown(endpoint_dir, 53004, 53004)
    endpoint = endpoint_dir / "provider.sock"
    prefix = f"""
import os, sys, resource, socket, struct, hashlib, array
sys.path.insert(0, {str(runtime)!r})
resource.setrlimit(resource.RLIMIT_CORE, (0,0))
from ciq_api import agent_provider_peer as peer
from ciq_api import agent_provider_identity as identity
from ciq_api import agent_https_process as process
"""

    def launch(code, uid):
        return subprocess.Popen(
            (sys.executable, "-I", "-B", "-c", prefix + code),
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd="/", env={"LANG": "C.UTF-8"}, user=uid, group=uid, extra_groups=[],
            start_new_session=True,
        )

    def collect(child, expected, label):
        out, err = child.communicate(timeout=5)
        if child.returncode or out != expected or err:
            raise RuntimeError(f"Provider IPC {label} failed; private output suppressed")

    def stop(child):
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGKILL)
        child.communicate(timeout=3)

    client = f"""
attempt = peer.ProviderPeerClient()
try:
    result = attempt.exchange({body!r}, timeout=1)
    valid = result == {reply!r}
    marker = b'OK'
except ValueError as error:
    valid = str(error) == peer.ERROR
    marker = b'DENIED'
try:
    attempt.exchange({body!r}, timeout=1)
except ValueError as error:
    valid = valid and str(error) == peer.ERROR
else:
    valid = False
if valid:
    os.write(1, marker)
os._exit(0 if valid else 1)
"""
    raw_prefix = f"""
connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
connection.settimeout(1)
connection.connect({str(endpoint)!r})
body = {body!r}
frame = peer._REQUEST + struct.pack('!I', len(body)) + hashlib.sha256(body).digest() + body
"""
    raw_suffix = """
try:
    connection.shutdown(socket.SHUT_WR)
    assert connection.recv(1) == b''
except (BrokenPipeError, ConnectionResetError):
    pass
connection.close()
os.write(1, b'DENIED')
"""

    cases = [
        ("valid", 53002, client, b"OK", 1, 1),
        ("clinical", 53001, raw_prefix + raw_suffix, b"DENIED", 0, 0),
        ("receipt", 53003, raw_prefix + raw_suffix, b"DENIED", 0, 0),
        ("wrong-pin", 53002, client.replace(repr(body), repr(body + b" ")),
         b"DENIED", 0, 0),
        ("bad-digest", 53002, raw_prefix + "connection.sendall(frame[:-1] + b'!')\n"
         + raw_suffix, b"DENIED", 0, 0),
        ("extended", 53002, raw_prefix + "connection.sendall(frame + b'extension')\n"
         + raw_suffix, b"DENIED", 0, 0),
        ("oversize", 53002, raw_prefix
         + "connection.sendall(peer._REQUEST + struct.pack('!I', 256001))\n"
         + raw_suffix, b"DENIED", 0, 0),
        ("missing-eof", 53002, raw_prefix + """
connection.sendall(frame)
assert connection.recv(1) == b''
connection.close()
os.write(1, b'DENIED')
""", b"DENIED", 0, 0),
        ("descriptor", 53002, raw_prefix + """
fd = os.open('/dev/null', os.O_RDONLY)
try:
    connection.sendmsg([frame], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', [fd]))])
finally:
    os.close(fd)
""" + raw_suffix, b"DENIED", 0, 0),
        ("stalled-child", 53002, client, b"DENIED", 1, 1),
    ]
    for name, uid, code, marker, reads, spawns in cases:
        child_worker = (worker.replace(f"return {reply!r}",
                                       "__import__('time').sleep(2)\n    return " + repr(reply))
                        if name == "stalled-child" else worker)
        budget = 2 if name == "valid" else 0.4
        server = f"""
reads, spawns = [], []
original_read = identity.read_private
def read(path, maximum):
    if path == identity.IDENTITY:
        reads.append(True)
    return original_read(path, maximum)
identity.read_private = read
original_popen = process.subprocess.Popen
identity.PYTHON = sys.executable
def spawn(argv, **kwargs):
    assert argv == (sys.executable, '-I', '-B', '-m', 'ciq_api.agent_https_worker')
    spawns.append(True)
    return original_popen((sys.executable, '-I', '-B', '-c', {child_worker!r}), **kwargs)
process.subprocess.Popen = spawn
server = peer.ProviderPeer()
server.bind()
os.write(1, b'READY\\n')
try:
    server.serve_once(timeout={budget})
    valid = {marker == b'OK'!r}
except ValueError as error:
    valid = {marker != b'OK'!r} and str(error) == peer.ERROR
finally:
    server.close()
valid = valid and len(reads) == {reads} and len(spawns) == {spawns}
try:
    server.serve_once(timeout=0.4)
except ValueError as error:
    valid = valid and str(error) == peer.ERROR
else:
    valid = False
if valid:
    os.write(1, b'PASS')
os._exit(0 if valid else 1)
"""
        children = []
        try:
            provider = launch(server, 53004)
            children.append(provider)
            if not select.select([provider.stdout], [], [], 3)[0]:
                raise RuntimeError("Provider IPC readiness timed out")
            if provider.stdout.readline() != b"READY\n":
                raise RuntimeError("Provider IPC readiness failed; private output suppressed")
            custody = launch(code, uid)
            children.append(custody)
            collect(custody, marker, name + " client")
            collect(provider, b"PASS", name + " server")
        finally:
            for child in reversed(children):
                stop(child)
            # Only the guarded fixture supervisor removes its own endpoint.
            endpoint.unlink(missing_ok=True)

    # A socket with the correct path, DAC and claimed owner can still belong to
    # the wrong kernel peer. Root-created listener is deliberately NOT provider.
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
        listener.bind(str(endpoint))
        os.chown(endpoint, 53004, 53004)
        endpoint.chmod(0o666)
        listener.listen(1)
        listener.settimeout(2)
        child = launch(client, 53002)
        try:
            connection, _ = listener.accept()
            with connection:
                connection.settimeout(2)
                if connection.recv(1) != b"":
                    raise RuntimeError("Provider IPC sent request to an unauthenticated peer")
            collect(child, b"DENIED", "false-server client")
        finally:
            stop(child)
            endpoint.unlink(missing_ok=True)
    print("PASS: 11 provider IPC controls; actual peer UIDs, no PAT in custody, no network")
