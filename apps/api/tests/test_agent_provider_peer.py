"""Real local IPC with dummy exchange; cross-UID authentication runs in Linux CI."""

import hashlib
import socket
import stat
import struct
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from ciq_api import agent_provider_peer as peer

BODY = b'{"synthetic":"PRIVATE captured request"}'
REPLY = b'{"synthetic":"PRIVATE raw reply"}'


def frame(body=BODY):
    return peer._REQUEST + struct.pack("!I", len(body)) + hashlib.sha256(body).digest() + body


@pytest.fixture
def ipc(monkeypatch):
    state = {"calls": [], "auth": [], "errors": [], "reply": REPLY}
    # The local Mac cannot assert Linux credentials. Only protocol behavior is
    # overridden here; the guarded Linux acceptance uses real kernel checks.
    # Darwin's sockaddr_un cannot hold pytest's long default temp path.
    directory = tempfile.TemporaryDirectory(prefix="ciq-peer-", dir="/tmp")
    monkeypatch.setattr(peer, "ENDPOINT", Path(directory.name) / "peer.sock")
    monkeypatch.setattr(peer, "_path", lambda **_: None)
    monkeypatch.setattr(peer, "_custody_guard", lambda: None)
    monkeypatch.setattr(peer, "provider_guard", lambda: None)

    def authenticate(connection, uid):
        state["auth"].append(uid)
        if state.get("deny") == uid:
            raise PermissionError("PRIVATE peer credential")

    monkeypatch.setattr(peer, "_peer", authenticate)

    class Attempt:
        def exchange(self, body, *, timeout):
            state["calls"].append((body, timeout))
            if state.get("fault"):
                raise ValueError("PRIVATE token/provider diagnostic")
            return state["reply"]

    monkeypatch.setattr(peer, "PrivateProviderAttempt", Attempt)
    threads, servers = [], []

    def start(*, timeout=0.5):
        server = peer.ProviderPeer()
        server.bind()
        servers.append(server)

        def serve():
            try:
                server.serve_once(timeout=timeout)
            except ValueError as error:
                state["errors"].append(str(error))

        thread = threading.Thread(target=serve)
        threads.append(thread)
        thread.start()
        return server

    state["start"] = start
    yield state
    for thread in threads:
        thread.join(2)
        assert not thread.is_alive()
    for server in servers:
        assert server._listener is None
    assert all(error == peer.ERROR for error in state["errors"])
    directory.cleanup()


@pytest.mark.parametrize("body", [BODY, b"x" * 256_000], ids=["small", "maximum"])
def test_complete_exchange_and_one_local_attempt(ipc, body):
    server = ipc["start"]()
    client = peer.ProviderPeerClient()
    assert client.exchange(body, timeout=0.5) == REPLY
    assert ipc["calls"][0][0] == body and 0 < ipc["calls"][0][1] < 0.5
    assert sorted(ipc["auth"]) == [53002, 53004]
    for retry in (lambda: client.exchange(body, timeout=0.5),
                  lambda: server.serve_once(timeout=0.5), server.bind):
        with pytest.raises(ValueError, match=f"^{peer.ERROR}$"):
            retry()
    assert len(ipc["calls"]) == 1


@pytest.mark.parametrize("wire", [
    b"", b"wrong version", peer._REQUEST + struct.pack("!I", 0),
    peer._REQUEST + struct.pack("!I", 256_001),
    peer._REQUEST + struct.pack("!I", len(BODY)) + b"x" * 32 + BODY,
    frame()[:-1], frame() + b"extension", frame() * 2,
])
def test_incomplete_or_extended_frame_never_opens_identity(ipc, wire):
    ipc["start"]()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(1)
        client.connect(str(peer.ENDPOINT))
        try:
            client.sendall(wire)
            client.shutdown(socket.SHUT_WR)
            assert client.recv(1) == b""
        except (BrokenPipeError, ConnectionResetError):
            pass
    assert not ipc["calls"]


@pytest.mark.parametrize("uid", [53002, 53004])
def test_peer_denial_happens_before_private_exchange(ipc, uid):
    ipc["deny"] = uid
    ipc["start"]()
    with pytest.raises(ValueError, match=f"^{peer.ERROR}$"):
        peer.ProviderPeerClient().exchange(BODY, timeout=0.5)
    assert not ipc["calls"]


@pytest.mark.parametrize("reply", [b"", b"x" * 384_001, "PRIVATE"],
                         ids=["empty", "oversize", "wrong-type"])
def test_invalid_response_never_leaves_server(ipc, reply):
    ipc["reply"] = reply
    ipc["start"]()
    client = peer.ProviderPeerClient()
    with pytest.raises(ValueError, match=f"^{peer.ERROR}$"):
        client.exchange(BODY, timeout=0.5)
    assert len(ipc["calls"]) == 1


def test_uncertain_provider_failure_does_not_retry_or_expose_diagnostics(ipc, capsys):
    ipc["fault"] = True
    ipc["start"]()
    client = peer.ProviderPeerClient()
    for _ in range(2):
        with pytest.raises(ValueError, match=f"^{peer.ERROR}$"):
            client.exchange(BODY, timeout=0.5)
    assert len(ipc["calls"]) == 1 and capsys.readouterr() == ("", "")


@pytest.mark.parametrize("timeout", [True, 0, -1, 12.1, float("nan"), float("inf"), "1"])
def test_invalid_budget_consumes_client_and_bound_server(ipc, timeout):
    client = peer.ProviderPeerClient()
    server = peer.ProviderPeer()
    server.bind()
    for call in (lambda: client.exchange(BODY, timeout=timeout),
                 lambda: client.exchange(BODY, timeout=1),
                 lambda: server.serve_once(timeout=timeout),
                 lambda: server.serve_once(timeout=1)):
        with pytest.raises(ValueError, match=f"^{peer.ERROR}$"):
            call()
    assert server._listener is None and not ipc["calls"] and not ipc["auth"]


@pytest.mark.parametrize("body", [b"", b"x" * 256_001, bytearray(BODY), None],
                         ids=["empty", "oversize", "mutable", "none"])
def test_invalid_body_consumes_client_before_socket_or_credentials(ipc, body):
    client = peer.ProviderPeerClient()
    for value in (body, BODY):
        with pytest.raises(ValueError, match=f"^{peer.ERROR}$"):
            client.exchange(value, timeout=1)
    assert not ipc["auth"] and not ipc["calls"]


def test_incomplete_eof_times_out_without_identity(ipc):
    ipc["start"](timeout=0.1)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(1)
        client.connect(str(peer.ENDPOINT))
        client.sendall(frame())
        assert client.recv(1) == b""  # Missing SHUT_WR cannot be treated as EOF.
    assert not ipc["calls"]


def test_framing_time_is_deducted_before_provider_exchange(ipc):
    ipc["start"](timeout=1)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(2)
        client.connect(str(peer.ENDPOINT))
        client.sendall(frame())
        time.sleep(0.06)
        client.shutdown(socket.SHUT_WR)
        while client.recv(8192):
            pass
    assert len(ipc["calls"]) == 1 and 0 < ipc["calls"][0][1] < 0.95


def test_maximum_response_is_complete(ipc):
    ipc["reply"] = b"x" * 384_000
    ipc["start"]()
    assert peer.ProviderPeerClient().exchange(BODY, timeout=0.5) == ipc["reply"]


def test_supervisor_can_close_unused_listener_without_unlink_or_rebind(ipc):
    server = peer.ProviderPeer()
    server.bind()
    server.close()
    server.close()
    assert peer.ENDPOINT.exists() and server._listener is None
    for call in (server.bind, lambda: server.serve_once(timeout=1)):
        with pytest.raises(ValueError, match=f"^{peer.ERROR}$"):
            call()


def test_listener_accept_is_bounded_and_left_for_supervisor(ipc):
    server = ipc["start"](timeout=0.05)
    # The fixture joins its thread. Runtime must not unlink any endpoint.
    assert peer.ENDPOINT.exists()
    with pytest.raises(ValueError, match=f"^{peer.ERROR}$"):
        server.bind()


@pytest.mark.parametrize("wire", [
    b"wrong", peer._RESPONSE + b"x" * 32,
    peer._RESPONSE + hashlib.sha256(BODY).digest() + struct.pack("!I", 0),
    peer._RESPONSE + hashlib.sha256(BODY).digest() + struct.pack("!I", 384_001),
    peer._RESPONSE + hashlib.sha256(BODY).digest() + struct.pack("!I", len(REPLY)) + REPLY[:-1],
    peer._RESPONSE + hashlib.sha256(BODY).digest() + struct.pack("!I", len(REPLY))
    + REPLY + b"extension",
])
def test_client_rejects_bad_or_unassociated_response(ipc, wire):
    # Rogue scripted endpoint tests strict client parsing, not provider identity.
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
        listener.bind(str(peer.ENDPOINT))
        listener.listen(1)
        errors = []

        def serve():
            try:
                connection, _ = listener.accept()
                with connection:
                    connection.settimeout(1)
                    while connection.recv(8192):
                        pass
                    connection.sendall(wire)
            except OSError as error:
                errors.append(type(error))

        thread = threading.Thread(target=serve)
        thread.start()
        try:
            with pytest.raises(ValueError, match=f"^{peer.ERROR}$"):
                peer.ProviderPeerClient().exchange(BODY, timeout=0.5)
        finally:
            thread.join(2)
        assert not thread.is_alive()


@pytest.mark.parametrize("values", [(0, 53004, 53004), (1, 53002, 53004), (1, 53004, 0)])
def test_kernel_peer_identity_requires_pid_uid_and_gid(monkeypatch, values):
    monkeypatch.setattr(peer, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setattr(peer.socket, "SO_PEERCRED", 17, raising=False)
    connection = SimpleNamespace(getsockopt=lambda *args: struct.pack("3i", *values))
    with pytest.raises(ValueError, match=f"^{peer.ERROR}$"):
        peer._peer(connection, 53004)


@pytest.mark.parametrize("flags,ancillary", [(socket.MSG_CTRUNC, []), (0, [(1, 1, b"fd")])])
def test_passed_descriptors_rejected_without_installation(flags, ancillary):
    connection = SimpleNamespace(settimeout=lambda _: None,
                                 recvmsg=lambda *args: (b"x", ancillary, flags, None))
    with pytest.raises(ValueError, match=f"^{peer.ERROR}$"):
        peer._read(connection, 1, peer._end(1))


@pytest.mark.parametrize("fault", [None, "symlink", "writable", "owner", "mode", "missing"])
def test_fixed_endpoint_path_guards(monkeypatch, fault):
    endpoint = Path("/run/ciq-agent-provider/ipc/provider.sock")
    monkeypatch.setattr(peer, "ENDPOINT", endpoint)

    def details(path):
        if path == endpoint:
            if fault == "missing":
                raise FileNotFoundError
            return SimpleNamespace(st_mode=stat.S_IFSOCK | (0o600 if fault == "mode" else 0o666),
                                   st_uid=53002 if fault == "owner" else 53004)
        return SimpleNamespace(st_mode=(stat.S_IFLNK if fault == "symlink" else stat.S_IFDIR)
                               | (0o777 if fault == "writable" else 0o755), st_uid=0)

    monkeypatch.setattr(Path, "lstat", details)
    if fault:
        with pytest.raises((ValueError, FileNotFoundError)):
            peer._path(connected=True)
    else:
        peer._path(connected=True)


@pytest.mark.parametrize("fault", [None, "platform", "isolated", "bytecode", "uid", "saved_uid",
                                  "gid", "saved_gid", "groups", "core", "environment"])
def test_custody_exact_identity(monkeypatch, fault):
    monkeypatch.setattr(peer, "sys", SimpleNamespace(
        platform="darwin" if fault == "platform" else "linux",
        flags=SimpleNamespace(isolated=fault != "isolated"),
        dont_write_bytecode=fault != "bytecode",
    ))
    monkeypatch.setattr(peer.os, "getresuid", lambda: (0, 0, 0) if fault == "uid" else
                        (53002, 53002, 0 if fault == "saved_uid" else 53002), raising=False)
    monkeypatch.setattr(peer.os, "getresgid", lambda: (0, 0, 0) if fault == "gid" else
                        (53002, 53002, 0 if fault == "saved_gid" else 53002), raising=False)
    monkeypatch.setattr(peer.os, "getgroups", lambda: [53004] if fault == "groups" else [])
    monkeypatch.setattr(peer.resource, "getrlimit", lambda _: (1, 1) if fault == "core" else (0, 0))
    monkeypatch.setattr(peer.os, "environ", {"DATABASE_URL": "PRIVATE"}
                        if fault == "environment" else {"LANG": "C.UTF-8"})
    if fault:
        with pytest.raises(ValueError, match=f"^{peer.ERROR}$"):
            peer._custody_guard()
    else:
        peer._custody_guard()
