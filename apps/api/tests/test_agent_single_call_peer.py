"""Real local sockets/retention; OS identity enforcement is separately tested on Linux."""

import errno
import hashlib
import socket
import stat
import struct
import tempfile
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from ciq_api import agent_single_call_peer as peer
from ciq_api.agent_contracts import canonical_json
from ciq_api.agent_single_call_journal import (
    ReportedTokenUsage,
    ReviewedCallPin,
    SingleCallJournal,
)

DIGEST = hashlib.sha256(b"PRIVATE raw response stays in custody").hexdigest()
USAGE = ReportedTokenUsage(input_tokens=0, output_tokens=None)


def reviewed_pin():
    now = datetime.now(UTC)
    return ReviewedCallPin(
        grant_id=uuid4(), database_id=uuid4(), epoch_id=uuid4(), operation_id=uuid4(),
        submission_id=uuid4(), approval_sha256="a" * 64, binding_sha256="b" * 64,
        request_sha256="c" * 64, config_sha256="d" * 64, source_sha256="e" * 64,
        provider_identity_sha256="f" * 64, hostname="reviewed-account.snowflakecomputing.com",
        starts_at=now - timedelta(seconds=5), ends_at=now + timedelta(minutes=5),
        reserved_units=20, provider_seconds=8, max_tokens=256,
    )


def request(pin, command="issue", observation=None):
    return canonical_json({
        "version": "single-call-receipt-v1",
        "pin_sha256": hashlib.sha256(pin.canonical().encode()).hexdigest(),
        "command": command, "observation": observation,
    }).encode()


def frame(raw):
    return peer._REQUEST + struct.pack("!I", len(raw)) + raw


def denied(call):
    with pytest.raises(ValueError, match=f"^{peer.ERROR}$") as caught:
        call()
    assert caught.value.__suppress_context__


@pytest.fixture
def ipc(tmp_path, monkeypatch):
    directory = tempfile.TemporaryDirectory(prefix="ciq-call-", dir="/tmp")
    monkeypatch.setattr(peer, "ENDPOINT", Path(directory.name) / "receipt.sock")
    monkeypatch.setattr(peer, "_guard", lambda _: None)
    monkeypatch.setattr(peer, "_path", lambda **_: None)
    monkeypatch.setattr(peer, "IPC_SECONDS", 0.3)
    state = {"pin": reviewed_pin(), "auth": [], "errors": [], "threads": [], "servers": []}
    journal = SingleCallJournal.provision(tmp_path / "retained", state["pin"])
    state["journal"] = journal

    def auth(connection, uid):
        state["auth"].append(uid)
        if state.get("deny") == uid:
            raise PermissionError("PRIVATE identity diagnostic")

    monkeypatch.setattr(peer, "_peer", auth)

    def finish():
        for thread in state["threads"]:
            thread.join(2)
            assert not thread.is_alive()
        state["threads"].clear()

    def start():
        finish()
        peer.ENDPOINT.unlink(missing_ok=True)  # Only the fixture supervisor.
        server = peer.SingleCallReceiptPeer(journal)
        server.bind()
        state["servers"].append(server)

        def serve():
            try:
                server.serve_once()
            except ValueError as error:
                state["errors"].append(str(error))

        thread = threading.Thread(target=serve)
        state["threads"].append(thread)
        thread.start()
        return server

    state.update(start=start, finish=finish)
    yield state
    finish()
    assert all(error == peer.ERROR for error in state["errors"])
    for server in state["servers"]:
        assert server._listener is None
    directory.cleanup()


def test_issue_observe_and_reconstructed_status_keep_uncertainty(ipc):
    client = peer.SingleCallReceiptClient(ipc["pin"])
    ipc["start"]()
    assert client.status().phase == "ready"
    ipc["start"]()
    assert client.issue() is None
    ipc["start"]()
    assert client.observe(DIGEST, provider_run_id="opaque-id", usage=USAGE) is None
    ipc["start"]()
    status = peer.SingleCallReceiptClient(ipc["pin"]).status()
    assert status.phase == "observed" and status.uncertain_units == 20
    assert status.response_sha256 == DIGEST and status.reported_usage == USAGE
    assert sorted(set(ipc["auth"])) == [53002, 53003]
    ipc["start"]()
    denied(peer.SingleCallReceiptClient(ipc["pin"]).issue)
    assert ipc["journal"].status() == status


def test_issue_ack_loss_poisoned_client_and_reopened_journal_deny_reissue(ipc, monkeypatch):
    original = peer._send

    def lost(connection, marker, value, end):
        if marker == peer._RESPONSE:
            raise OSError("PRIVATE acknowledgment lost after commit")
        return original(connection, marker, value, end)

    monkeypatch.setattr(peer, "_send", lost)
    ipc["start"]()
    client = peer.SingleCallReceiptClient(ipc["pin"])
    denied(client.issue)
    denied(client.status)
    assert ipc["journal"].status().phase == "issued"
    monkeypatch.setattr(peer, "_send", original)
    ipc["start"]()
    denied(peer.SingleCallReceiptClient(ipc["pin"]).issue)
    assert ipc["journal"].status().uncertain_units == 20


def test_observe_ack_loss_keeps_original_observation(ipc, monkeypatch):
    ipc["journal"].issue(now=datetime.now(UTC))
    original = peer._send

    def lost(connection, marker, value, end):
        if marker == peer._RESPONSE:
            raise OSError("PRIVATE observation ACK")
        return original(connection, marker, value, end)

    monkeypatch.setattr(peer, "_send", lost)
    ipc["start"]()
    denied(lambda: peer.SingleCallReceiptClient(ipc["pin"]).observe(
        DIGEST, provider_run_id="original", usage=USAGE,
    ))
    status = ipc["journal"].status()
    assert status.phase == "observed" and status.provider_run_id == "original"
    monkeypatch.setattr(peer, "_send", original)
    ipc["start"]()
    denied(lambda: peer.SingleCallReceiptClient(ipc["pin"]).observe(
        "0" * 64, provider_run_id="replacement", usage=USAGE,
    ))
    assert ipc["journal"].status() == status


@pytest.mark.parametrize("uid", [53002, 53003])
def test_identity_denial_precedes_retained_mutation(ipc, uid):
    ipc["deny"] = uid
    ipc["start"]()
    denied(peer.SingleCallReceiptClient(ipc["pin"]).issue)
    assert ipc["journal"].status().phase == "ready"


@pytest.mark.parametrize("change", ["approval_sha256", "request_sha256", "epoch_id"])
def test_wrong_pin_cannot_issue_or_read_retained_status(ipc, change):
    pin = ipc["pin"].model_copy(update={change: uuid4() if change == "epoch_id" else "0" * 64})
    for command in ("issue", "status"):
        ipc["start"]()
        denied(getattr(peer.SingleCallReceiptClient(pin), command))
    assert ipc["journal"].status().phase == "ready"


@pytest.mark.parametrize("kind", ["marker", "length", "truncated", "extended", "concatenated",
                                 "duplicate", "whitespace", "extra", "clock", "shape"])
def test_bad_request_never_issues(ipc, kind):
    raw = request(ipc["pin"])
    wire = frame(raw)
    if kind == "marker":
        wire = b"WRONG"
    elif kind == "length":
        wire = peer._REQUEST + struct.pack("!I", 4097)
    elif kind == "truncated":
        wire = wire[:-1]
    elif kind == "extended":
        wire += b"extension"
    elif kind == "concatenated":
        wire *= 2
    elif kind == "duplicate":
        wire = frame(raw[:-1] + b',"command":"issue"}')
    elif kind == "whitespace":
        wire = frame(b" " + raw)
    elif kind in ("extra", "clock"):
        wire = frame(raw[:-1] + b',"now":"2026-11-27T00:00:00Z"}')
    elif kind == "shape":
        wire = frame(request(ipc["pin"], observation={
            "response_sha256": DIGEST, "provider_run_id": "opaque", "usage": USAGE.model_dump(),
        }))
    ipc["start"]()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(1)
        connection.connect(str(peer.ENDPOINT))
        try:
            connection.sendall(wire)
            connection.shutdown(socket.SHUT_WR)
            assert connection.recv(1) == b""
        except (BrokenPipeError, ConnectionResetError):
            pass
        except OSError as error:
            # Darwin can report ENOTCONN when the rejecting peer closes before
            # shutdown. The unchanged journal assertion below is still required.
            assert error.errno == errno.ENOTCONN
    assert ipc["journal"].status().phase == "ready"


def test_missing_eof_times_out_before_issue(ipc):
    ipc["start"]()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(1)
        connection.connect(str(peer.ENDPOINT))
        connection.sendall(frame(request(ipc["pin"])))
        assert connection.recv(1) == b""
    assert ipc["journal"].status().phase == "ready"


@pytest.mark.parametrize("digest,identifier,usage", [
    ("A" * 64, "opaque", USAGE), ("0" * 63, "opaque", USAGE),
    (DIGEST, "bad\nid", USAGE), (DIGEST, "", USAGE),
    (DIGEST, "opaque", USAGE.model_copy(update={"input_tokens": True})),
    (DIGEST, "opaque", USAGE.model_copy(update={"output_tokens": "0"})),
    (DIGEST, "opaque", {"input_tokens": 0, "output_tokens": None}),
])
def test_invalid_observation_poisoned_before_connection(ipc, digest, identifier, usage):
    client = peer.SingleCallReceiptClient(ipc["pin"])
    denied(lambda: client.observe(digest, provider_run_id=identifier, usage=usage))
    denied(client.status)
    assert not ipc["auth"] and ipc["journal"].status().phase == "ready"


def test_observation_before_issue_denied_without_change(ipc):
    ipc["start"]()
    denied(lambda: peer.SingleCallReceiptClient(ipc["pin"]).observe(
        DIGEST, provider_run_id="opaque", usage=USAGE,
    ))
    assert ipc["journal"].status().phase == "ready"


def test_bound_listener_is_single_use_and_close_preserves_endpoint(ipc):
    server = ipc["start"]()
    peer.SingleCallReceiptClient(ipc["pin"]).status()
    ipc["finish"]()
    denied(server.bind)
    denied(server.serve_once)
    server.close()
    assert peer.ENDPOINT.exists()


@pytest.mark.parametrize("digest", ["", "x" * 64, "A" * 64, None, b"0" * 64])
def test_digest_only_journal_entry_rejects_invalid_hash(ipc, digest):
    journal = ipc["journal"]
    journal.issue(now=datetime.now(UTC))
    with pytest.raises(ValueError, match=r"^single_call_journal_unavailable$"):
        journal.observe_digest(digest, provider_run_id="opaque", usage=USAGE)
    assert journal.status().phase == "issued"


@pytest.mark.parametrize("fault", ["pin", "command", "units", "timestamp", "observation",
                                  "extra", "truncated", "trailing", "oversize"])
def test_client_rejects_unassociated_or_incoherent_reply_and_stays_closed(ipc, monkeypatch, fault):
    original = peer._send

    def damaged(connection, marker, value, end):
        if marker != peer._RESPONSE:
            return original(connection, marker, value, end)
        raw = value.model_dump(mode="json")
        if fault == "pin":
            raw["pin_sha256"] = "0" * 64
        elif fault == "command":
            raw["command"] = "observe"
        elif fault == "units":
            raw["status"]["uncertain_units"] = 0
        elif fault == "timestamp":
            raw["status"]["issued_at"] = None
        elif fault == "observation":
            raw["status"]["provider_run_id"] = "unexpected"
        elif fault == "extra":
            raw["dispatch_ticket"] = "forbidden"
        body = canonical_json(raw).encode()
        wire = marker + struct.pack("!I", len(body)) + body
        if fault == "truncated":
            wire = wire[:-1]
        elif fault == "trailing":
            wire += b"extension"
        elif fault == "oversize":
            wire = marker + struct.pack("!I", 4097)
        connection.settimeout(1)
        connection.sendall(wire)
        connection.shutdown(socket.SHUT_WR)

    monkeypatch.setattr(peer, "_send", damaged)
    ipc["start"]()
    client = peer.SingleCallReceiptClient(ipc["pin"])
    denied(client.issue)
    denied(client.status)
    assert ipc["journal"].status().phase == "issued"
    assert ipc["journal"].status().uncertain_units == 20


def test_server_clock_not_client_clock_controls_issue(ipc, monkeypatch):
    monkeypatch.setattr(peer, "datetime", SimpleNamespace(now=lambda _: ipc["pin"].ends_at))
    ipc["start"]()
    denied(peer.SingleCallReceiptClient(ipc["pin"]).issue)
    assert ipc["journal"].status().phase == "ready"


@pytest.mark.parametrize("loss", ["missing", "empty", "corrupt"])
def test_missing_retention_never_creates_new_authority(ipc, loss):
    path = ipc["journal"].path
    if loss == "missing":
        path.unlink()
    else:
        path.write_bytes(b"" if loss == "empty" else b"corrupt")
    ipc["start"]()
    denied(peer.SingleCallReceiptClient(ipc["pin"]).issue)
    assert not path.exists() if loss == "missing" else path.read_bytes() == (
        b"" if loss == "empty" else b"corrupt"
    )


@pytest.mark.parametrize("fault", [None, "platform", "isolated", "bytecode", "uid", "saved_uid",
                                  "gid", "saved_gid", "groups", "core", "environment"])
def test_exact_receipt_identity_guard(monkeypatch, fault):
    monkeypatch.setattr(peer, "sys", SimpleNamespace(
        platform="darwin" if fault == "platform" else "linux",
        flags=SimpleNamespace(isolated=fault != "isolated"),
        dont_write_bytecode=fault != "bytecode",
    ))
    monkeypatch.setattr(peer.os, "getresuid", lambda: (0, 0, 0) if fault == "uid" else
                        (53003, 53003, 0 if fault == "saved_uid" else 53003), raising=False)
    monkeypatch.setattr(peer.os, "getresgid", lambda: (0, 0, 0) if fault == "gid" else
                        (53003, 53003, 0 if fault == "saved_gid" else 53003), raising=False)
    monkeypatch.setattr(peer.os, "getgroups", lambda: [53002] if fault == "groups" else [])
    monkeypatch.setattr(peer.resource, "getrlimit", lambda _: (1, 1) if fault == "core" else (0, 0))
    monkeypatch.setattr(peer.os, "environ", {"DATABASE_URL": "PRIVATE"}
                        if fault == "environment" else {"LANG": "C.UTF-8"})
    if fault:
        with pytest.raises(ValueError, match=f"^{peer.ERROR}$"):
            peer._guard(53003)
    else:
        peer._guard(53003)


@pytest.mark.parametrize("fault", [None, "symlink", "writable", "owner", "mode", "missing"])
def test_receipt_endpoint_path_guards(monkeypatch, fault):
    endpoint = Path("/run/ciq-agent-single-call/ipc/receipt.sock")
    monkeypatch.setattr(peer, "ENDPOINT", endpoint)

    def details(path):
        if path == endpoint:
            if fault == "missing":
                raise FileNotFoundError
            return SimpleNamespace(st_mode=stat.S_IFSOCK | (0o600 if fault == "mode" else 0o666),
                                   st_uid=53002 if fault == "owner" else 53003)
        return SimpleNamespace(st_mode=(stat.S_IFLNK if fault == "symlink" else stat.S_IFDIR)
                               | (0o777 if fault == "writable" else 0o755), st_uid=0)

    monkeypatch.setattr(Path, "lstat", details)
    if fault:
        with pytest.raises((ValueError, FileNotFoundError)):
            peer._path(connected=True)
    else:
        peer._path(connected=True)
