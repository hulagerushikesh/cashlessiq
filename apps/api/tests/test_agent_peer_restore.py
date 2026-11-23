"""Encrypted restore with retained separate-UID receipts; disposable CI only."""

import os
import sys

import pytest

if (
    sys.platform != "linux" or os.getuid() != 0
    or os.environ.get("GITHUB_ACTIONS") != "true"
    or os.environ.get("RUNNER_OS") != "Linux"
    or os.environ.get("GITHUB_REPOSITORY") != "hulagerushikesh/cashlessiq"
    or any(os.environ.get(key) != "1" for key in (
        "CIQ_AGENT_CONTROLLER_TEST", "CIQ_AGENT_RECEIPT_PEER_TEST", "CIQ_AGENT_PEER_DATABASE_TEST",
    ))
):
    pytest.skip("Restored peers require the explicit disposable CI job", allow_module_level=True)

import re
import subprocess
from contextlib import contextmanager
from datetime import timedelta

from sqlalchemy.engine import make_url
from test_agent_controller_capture import controller_database as controller_database
from test_agent_controller_capture import engine as engine
from test_agent_custody_restore import (
    assert_no_human_changes,
    current_fixture,
    old_claim,
    operation,
    rebound,
    receipt,
    reject_owner_runtime,
)
from test_agent_ledger import ACTOR, NOW, balance, payload, reserve, submission
from test_agent_ledger import setup as setup
from test_agent_ledger_recovery import receipt_digest, restored_database
from test_agent_peer_database import combined_runtime
from test_agent_receipt_peer_linux import create_peers

from ciq_api.seed import TENANT_ID


def local_tools(service, tool, *args, **kwargs):
    """Trusted supervisor only; fixed dummy server, no Docker socket or host mount."""
    assert service == "network-free-combined"
    assert tool in {"pg_dump", "pg_restore", "createdb", "dropdb"}
    url = make_url(os.environ["TEST_DATABASE_URL"])
    assert (url.host, url.port, url.username, url.password) == (
        "127.0.0.1", 5432, "postgres", "ciq-disposable-agent-ledger",
    )
    assert re.fullmatch(r"ciq_controller_[a-f0-9]{24}", url.database)
    try:
        return subprocess.run(
            [tool, "-h", "127.0.0.1", "-p", "5432", *args],
            env={"PATH": os.environ["PATH"], "PGPASSWORD": url.password},
            check=True, timeout=30, stderr=subprocess.PIPE, **kwargs,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        raise RuntimeError("Combined disposable restore command failed (redacted)") from None


@contextmanager
def restored_peer(s, request, tmp_path, monkeypatch, *, claim=None, after_backup=None):
    with restored_database(
        s, "network-free-combined", tmp_path / "backup", owner_ledger=False,
        after_backup=after_backup, command=local_tools,
    ) as restored:
        # Source fixture transactions have finished. Hand the original external
        # history to its separate UID; no reset, backup copy or invented marker.
        pin = s.admission.journal.pin.model_dump(mode="json")
        peer = create_peers(request, pin=pin, retained=s.admission.journal.directory)
        reject_owner_runtime(monkeypatch)
        with rebound(restored) as c:
            c.claim = claim or old_claim(operation(restored))
            yield c, peer
            assert_no_human_changes(restored)


@pytest.mark.parametrize("already_claimed", [False, True])
def test_restored_peer_finishes_first_attempt_once_with_original_snapshot_and_deadline(
    setup, request, tmp_path, monkeypatch, already_claimed,
):
    s = setup
    subject = current_fixture(s)
    claim = s.ledger.claim(TENANT_ID, ACTOR, subject.operation_id) if already_claimed else None
    before = operation(s)
    with restored_peer(s, request, tmp_path, monkeypatch, claim=claim) as (c, peer):
        history = peer.rows()
        assert len(history) == 1
        c.claim = (c.commands.heartbeat("REQ-FAKE-0", claim) if claim
                   else c.commands.claim("REQ-FAKE-0", receipt(operation(c.setup))))
        with combined_runtime(c, peer) as runtime:
            runtime.start()
            for stage in ("verify", "prepare", "replacement", "dispatch", "publish"):
                assert runtime.command(stage) == (b"DENIED" if stage == "replacement" else b"OK")
            for stage in ("prepare", "dispatch", "publish", "replacement"):
                assert runtime.command(stage) == b"DENIED"
            op = operation(c.setup)
            assert op.state == "published" and op.deadline == before.deadline
            assert op.snapshot == before.snapshot and op.created_at == before.created_at
            assert len(runtime.comparisons()) == 2 and len(peer.rows()) == 2
            assert [row for row in peer.rows() if row[0] != str(subject.operation_id)] == history
            assert [row[-1] for row in peer.rows()
                    if row[0] == str(subject.operation_id)] == ["issued"]
            assert balance(c.setup) == (3, 1, 10, 20, 0)


@pytest.mark.parametrize("phase", ["checkpoint", "issued", "published", "quarantined"])
def test_old_backup_cannot_erase_later_retained_peer_history_or_refund(
    setup, request, tmp_path, monkeypatch, phase,
):
    s = setup
    baseline = submission(s, 1)
    s.ledger.publish_fake_result(baseline, payload(baseline))
    subject = reserve(s)
    reserve(s, 2)
    claim = s.ledger.claim(TENANT_ID, ACTOR, subject.operation_id)

    def after_backup():
        permit = s.ledger.begin_submission(TENANT_ID, ACTOR, claim)
        if phase in {"issued", "published"}:
            s.ledger.authorize_fake_io(permit)
        if phase == "published":
            s.ledger.publish_fake_result(permit, payload(permit))
        if phase == "quarantined":
            s.admission.journal.quarantine()

    with restored_peer(
        s, request, tmp_path, monkeypatch, claim=claim, after_backup=after_backup,
    ) as (c, peer), combined_runtime(c, peer) as runtime:
        before, digest, history = balance(c.setup), receipt_digest(c.setup), peer.rows()
        assert len(history) == 2
        runtime.start()
        assert runtime.command("verify") == b"DENIED"
        for stage in ("prepare", "dispatch", "publish", "replacement"):
            assert runtime.command(stage) == b"DENIED"
        # Independent clients/processes still see the same contradictory history.
        fresh = runtime.start()
        assert runtime.command("verify", fresh) == b"DENIED"
        assert runtime.command("recover", fresh) == runtime.command("recover", fresh) == b"OK"
        assert operation(c.setup).state == "reserved"
        assert balance(c.setup) == before == (3, 2, 20, 10, 0)
        assert receipt_digest(c.setup) == digest and peer.rows() == history
        assert len(runtime.comparisons()) == 1


@pytest.mark.parametrize("state", ["submitting", "unknown", "published"])
def test_restored_submitted_work_cannot_replay_through_fresh_coordinator(
    setup, request, tmp_path, monkeypatch, state,
):
    s = setup
    baseline = submission(s, 1)
    s.ledger.publish_fake_result(baseline, payload(baseline))
    subject = reserve(s)
    claim = s.ledger.claim(TENANT_ID, ACTOR, subject.operation_id)
    permit = s.ledger.begin_submission(TENANT_ID, ACTOR, claim)
    reserve(s, 2)
    if state == "published":
        s.ledger.publish_fake_result(permit, payload(permit))
    elif state == "unknown":
        s.clock[0] = NOW + timedelta(seconds=121)
        s.ledger.recover_expired(TENANT_ID, subject.operation_id)
    before, digest = operation(s), receipt_digest(s)
    with (
        restored_peer(s, request, tmp_path, monkeypatch, claim=claim) as (c, peer),
        combined_runtime(c, peer) as runtime,
    ):
        history = peer.rows()
        runtime.start()
        for stage in ("prepare", "dispatch", "publish", "replacement"):
            assert runtime.command(stage) == b"DENIED"
        assert runtime.command("recover") == b"OK"
        op = operation(c.setup)
        expected = "published" if state == "published" else "unknown"
        assert op.state == expected and op.deadline == before.deadline
        assert op.snapshot == before.snapshot and op.fence_id == before.fence_id
        assert runtime.command("recover") == b"OK"
        assert operation(c.setup).version == op.version
        assert receipt_digest(c.setup) == digest and peer.rows() == history
        assert balance(c.setup) == (
            (3, 1, 10, 20, 0) if state == "published" else (3, 2, 10, 10, 10)
        )
