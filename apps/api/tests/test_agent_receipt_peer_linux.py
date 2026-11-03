"""Explicit disposable root supervisor; actual nonroot Linux peers, never local Docker."""

import json
import os
import re
import select
import shutil
import signal
import sqlite3
import struct
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from test_agent_receipt_verifier_offline import inventory as inventory

from ciq_api.agent_admission import FakeCheckpoint, FakeEpochPin
from ciq_api.agent_contracts import canonical_json
from ciq_api.agent_receipt_peer import MAX_PACKET

if (
    sys.platform != "linux" or os.getuid() != 0
    or os.environ.get("GITHUB_ACTIONS") != "true"
    or os.environ.get("GITHUB_REPOSITORY") != "hulagerushikesh/cashlessiq"
    or os.environ.get("CIQ_AGENT_RECEIPT_PEER_TEST") != "1"
):
    pytest.skip("Separate UID receipt peers require the explicit disposable CI job",
                allow_module_level=True)

ROOT = Path(__file__).resolve().parents[3]
CHILD = Path(__file__).with_name("receipt_peer_child.py")


def receipt(**changes):
    return FakeCheckpoint(
        tenant_id=uuid4(), request_id="SYN-PEER", operation_id=uuid4(),
        submission_id=uuid4(), digest="a" * 64,
    ).model_copy(update=changes).model_dump(mode="json")


def create_peers(request, *, pin=None):
    # /run avoids a public writable ancestor. Only this invocation is removed.
    root = Path("/run") / ("ciq-receipt-peer-" + uuid4().hex[:16])
    processes = []
    root.mkdir(mode=0o755)

    def cleanup():
        for child in reversed(processes):
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGKILL)
            child.communicate(timeout=5)
            assert child.poll() is not None
        shutil.rmtree(root)
        assert not root.exists()

    request.addfinalizer(cleanup)  # Also cleans failures BEFORE fixture yield.
    base = 200_000 + int(uuid4().hex[:5], 16)
    server_uid, custody_uid, clinical_uid, transport_uid = range(base, base + 4)
    endpoint = root / "ipc"
    endpoint.mkdir(mode=0o755)
    os.chown(endpoint, server_uid, server_uid)
    storage = root / "journal-parent"
    storage.mkdir(mode=0o700)
    os.chown(storage, server_uid, server_uid)
    secret = root / "supervisor-secret"
    secret.write_text("DUMMY-ONLY-NOT-A-CREDENTIAL")
    secret.chmod(0o600)
    config = {
        "path": str(endpoint / "peer.sock"), "directory": str(storage / "retained"),
        "pin": pin or FakeEpochPin(database_id=uuid4(), epoch_id=uuid4()).model_dump(mode="json"),
        "server_uid": server_uid, "custody_uid": custody_uid, "other_secret": str(secret),
    }

    def spawn(uid, *, interactive=False, helper=CHILD, **changes):
        child = subprocess.Popen(
            [sys.executable, str(helper)], cwd=ROOT, user=uid, group=uid, extra_groups=[],
            env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(ROOT / "apps/api/src")},
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=True,
        )
        processes.append(child)
        child.stdin.write((json.dumps({**config, **changes}) + "\n").encode())
        child.stdin.flush()
        if not interactive:
            child.stdin.close()
            child.stdin = None
        return child

    def run(uid=custody_uid, **changes):
        child = spawn(uid, **changes)
        out, err = child.communicate(timeout=8)
        detail = out.strip().decode(errors="replace")
        if not re.fullmatch(r"FAIL:[A-Za-z]+", detail):
            detail = "redacted"
        assert child.returncode == 0 and not err, "fixed receipt helper failed: " + detail
        return out.strip()

    def start(**changes):
        child = spawn(server_uid, action="server", **changes)
        assert select.select([child.stdout], [], [], 5)[0], "peer readiness timed out"
        assert child.stdout.readline() == b"READY\n", "peer did not become ready"
        return child

    def stop(child):
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGKILL)
        child.communicate(timeout=5)
        assert child.poll() is not None

    def rows():
        with sqlite3.connect(Path(config["directory"]) / "fake-receipts.sqlite3") as db:
            return db.execute("SELECT operation_id,submission_id,digest,state FROM receipt "
                              "ORDER BY submission_id").fetchall()

    assert run(server_uid, action="provision") == b"PASS"
    server = start()
    s = SimpleNamespace(**config, root=root, server=server, start=start, stop=stop,
                        run=run, spawn=spawn, rows=rows, clinical_uid=clinical_uid,
                        transport_uid=transport_uid)
    return s


@pytest.fixture
def peers(request):
    return create_peers(request)


def frame(s, command, selected=None, expected=(), **changes):
    raw = canonical_json({
        "version": "fake-receipt-peer-v1", "epoch": s.pin, "command": command,
        "expected": list(expected), "selected": selected, **changes,
    }).encode()
    return struct.pack("!I", len(raw)) + raw


def test_original_coordinator_peer_flow_and_no_returned_permission(peers):
    s, item = peers, receipt()
    assert s.run(action="check", expected=[]) == b"PASS"
    assert s.run(action="prepare", selected=item) == b"PASS"
    assert s.run(action="check", expected=[item]) == b"PASS"
    assert s.run(action="check_issued", expected=[item], selected=item) == b"DENIED"
    assert s.run(action="issue", selected=item) == b"PASS"
    assert s.run(action="check_issued", expected=[item], selected=item) == b"PASS"
    assert s.run(action="issue", selected=item) == b"DENIED"
    assert s.run(action="prepare", selected=item) == b"DENIED"
    assert s.rows()[0][-1] == "issued"


def test_coordinator_uses_separate_receipt_process_without_file_access(peers, inventory):
    s = peers
    material = {**inventory.raw, "epoch": s.pin}
    assert s.run(action="coordinator", material=material) == b"PASS"
    assert s.rows()[0][-1] == "issued"
    assert s.run(action="file_denials") == b"PASS"


@pytest.mark.parametrize("role", ["custody_uid", "clinical_uid", "transport_uid"])
def test_separate_principals_cannot_read_retained_file_or_supervisor_secret(peers, role):
    assert peers.run(getattr(peers, role), action="file_denials") == b"PASS"


@pytest.mark.parametrize("role", ["clinical_uid", "transport_uid"])
def test_unauthorized_real_uid_cannot_check_prepare_or_issue(peers, role):
    s, item = peers, receipt()
    for command in ("check", "prepare", "issue"):
        packet = frame(s, command, None if command == "check" else item)
        assert s.run(getattr(s, role), action="raw", raw=packet.hex()) == b"PASS"
    assert s.rows() == []
    assert s.run(action="check", expected=[]) == b"PASS"


@pytest.mark.parametrize("fault", [
    "oversize", "truncated_header", "truncated_body", "trailing", "two_frames", "zero",
    "malformed", "duplicate_key", "path_selector", "passed_fd", "wrong_epoch",
])
def test_invalid_frames_and_descriptor_handoff_do_not_mutate(peers, fault):
    s, item = peers, receipt()
    packet = frame(s, "prepare", item)
    changes = {}
    if fault == "oversize":
        packet = struct.pack("!I", MAX_PACKET + 1)
    elif fault == "truncated_header":
        packet = packet[:3]
    elif fault == "truncated_body":
        packet = packet[:-1]
    elif fault in ("trailing", "two_frames"):
        packet += b"x" if fault == "trailing" else packet
    elif fault == "zero":
        packet = b"\0" * 4
    elif fault == "malformed":
        packet = struct.pack("!I", 1) + b"{"
    elif fault == "duplicate_key":
        raw = packet[4:-1] + b',"command":"prepare"}'
        packet = struct.pack("!I", len(raw)) + raw
    elif fault == "path_selector":
        packet = frame(s, "prepare", item, path="/private/no-selector")
    elif fault == "wrong_epoch":
        packet = frame(s, "prepare", item, epoch={**s.pin, "epoch_id": str(uuid4())})
    else:
        changes["fd"] = True
    assert s.run(action="raw", raw=packet.hex(), **changes) == b"PASS"
    assert s.rows() == []
    assert s.run(action="check", expected=[]) == b"PASS"


@pytest.mark.parametrize("phase", ["prepare", "issue"])
def test_lost_acknowledgement_and_peer_restart_retain_no_replay(peers, phase):
    s, item = peers, receipt()
    if phase == "issue":
        assert s.run(action="prepare", selected=item) == b"PASS"
    assert s.run(action="raw", raw=frame(s, phase, item).hex(), drop_reply=True) == b"PASS"
    # Fresh check fences completion without interpreting EOF as failed commit.
    assert s.run(action="check", expected=[item]) == b"PASS"
    assert s.rows()[0][-1] == ("prepared" if phase == "prepare" else "issued")
    s.stop(s.server)
    Path(s.path).unlink()  # Explicit trusted supervisor cleanup AFTER termination.
    s.server = s.start()
    assert s.run(action="check", expected=[item]) == b"PASS"
    assert s.run(action=phase, selected=item) == b"DENIED"
    assert s.run(action="check", expected=[]) == b"DENIED"


def test_client_rejects_wrong_kernel_server_uid_even_with_expected_path_owner(peers):
    s = peers
    # Trusted test root changes path metadata only; running server UID is intact.
    # Metadata alone must not authorize receipt payload disclosure.
    os.chown(Path(s.path).parent, s.transport_uid, s.transport_uid)
    os.chown(s.path, s.transport_uid, s.transport_uid)
    assert s.run(action="check", expected=[], server_uid=s.transport_uid) == b"DENIED"
    assert s.rows() == []


def test_wrong_epoch_and_closed_custody_never_fall_back_or_create(peers):
    s = peers
    assert s.run(action="check", pin={**s.pin, "epoch_id": str(uuid4())}) == b"DENIED"
    with sqlite3.connect(Path(s.directory) / "fake-receipts.sqlite3") as db:
        db.execute("UPDATE identity SET state='closed' WHERE id=1")
    assert s.run(action="check", expected=[]) == b"DENIED"
    assert s.rows() == []


def test_missing_retained_file_is_not_initialized_by_peer(peers):
    s = peers
    target = Path(s.directory) / "fake-receipts.sqlite3"
    target.unlink()
    assert s.run(action="prepare", selected=receipt()) == b"DENIED"
    assert not target.exists()


def test_request_without_half_close_is_bounded_and_cannot_prepare(peers):
    # Child's raw action always half closes, so use a fixed slow client here.
    s = peers
    code = """
import json, socket, sys, time
c=json.loads(sys.stdin.read())
with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
 s.connect(c['path'])
 s.sendall(bytes.fromhex(c['raw']))
 time.sleep(2.3)
 assert s.recv(3) != b'OK\\n'
"""
    start = time.monotonic()
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=ROOT,
        input=json.dumps({"path": s.path, "raw": frame(s, "prepare", receipt()).hex()}).encode(),
        user=s.custody_uid, group=s.custody_uid, extra_groups=[],
        env={"PATH": "/usr/bin:/bin"}, capture_output=True, timeout=5,
    )
    assert result.returncode == 0 and not result.stdout and not result.stderr
    assert time.monotonic() - start < 5
    assert s.rows() == []
    assert s.run(action="check", expected=[]) == b"PASS"


@pytest.mark.parametrize("fault", ["missing", "writable_parent", "symlink", "same_uid"])
def test_client_construction_rejects_unsafe_endpoint_without_mutation(peers, fault):
    s = peers
    changes = {}
    if fault == "missing":
        changes["path"] = str(Path(s.path).with_name("missing.sock"))
    elif fault == "writable_parent":
        Path(s.path).parent.chmod(0o777)
    elif fault == "symlink":
        link = Path(s.path).with_name("link.sock")
        link.symlink_to(s.path)
        changes["path"] = str(link)
    else:
        changes["server_uid"] = s.custody_uid
    assert s.run(action="check", expected=[], **changes) == b"DENIED"
    assert s.rows() == []


def test_stale_socket_is_never_unlinked_or_adopted_by_bind(peers):
    s = peers
    before = Path(s.path).lstat()
    assert s.run(s.server_uid, action="bind_denied") == b"DENIED"
    assert Path(s.path).lstat().st_ino == before.st_ino
    assert s.run(action="check", expected=[]) == b"PASS"


@pytest.mark.parametrize("fault", ["malformed", "trailing", "empty"])
def test_bad_ack_closes_client_but_retains_committed_marker(peers, fault):
    s, item = peers, receipt()
    s.stop(s.server)
    Path(s.path).unlink()
    s.server = s.start(reply_fault=fault)
    assert s.run(action="prepare", selected=item) == b"DENIED"
    assert s.rows()[0][-1] == "prepared"
    s.stop(s.server)
    Path(s.path).unlink()
    s.server = s.start()
    assert s.run(action="check", expected=[item]) == b"PASS"
    assert s.run(action="prepare", selected=item) == b"DENIED"


def test_concurrent_separate_clients_can_issue_only_once(peers):
    s, item = peers, receipt()
    assert s.run(action="prepare", selected=item) == b"PASS"
    children = [s.spawn(s.custody_uid, action="issue", selected=item) for _ in range(2)]
    replies = []
    for child in children:
        out, err = child.communicate(timeout=8)
        assert child.returncode == 0 and not err
        replies.append(out.strip())
    assert sorted(replies) == [b"DENIED", b"PASS"]
    assert s.rows()[0][-1] == "issued"
