"""Actual PG logins + separate receipt UID + bounded fake child; opt-in CI only."""

import os
import sys

import pytest

if (
    sys.platform != "linux" or os.getuid() != 0
    or os.environ.get("GITHUB_ACTIONS") != "true"
    or os.environ.get("GITHUB_REPOSITORY") != "hulagerushikesh/cashlessiq"
    or os.environ.get("CIQ_AGENT_CONTROLLER_TEST") != "1"
    or os.environ.get("CIQ_AGENT_RECEIPT_PEER_TEST") != "1"
    or os.environ.get("CIQ_AGENT_PEER_DATABASE_TEST") != "1"
):
    pytest.skip("Combined peers require the explicit disposable CI job", allow_module_level=True)

import select
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import text
from sqlalchemy.orm import Session
from test_agent_contracts import candidate
from test_agent_controller_capture import controller_database as controller_database
from test_agent_controller_capture import engine as engine
from test_agent_controller_capture import scope as scope
from test_agent_controller_capture import setup as setup
from test_agent_controller_reservation import commands as commands
from test_agent_controller_reservation import mutate
from test_agent_custody_dispatch import dispatch as dispatch
from test_agent_custody_publication import publication as publication
from test_agent_custody_recovery import expire_lease
from test_agent_custody_recovery import recovered as recovered
from test_agent_custody_submission import custody as custody
from test_agent_custody_submission import rows
from test_agent_ledger import balance
from test_agent_receipt_peer_linux import create_peers
from test_agent_receipt_verifier import observer as observer

from ciq_api.agent_ledger_models import AgentComparison

HELPER = Path(__file__).with_name("peer_database_child.py")


def response(child):
    assert select.select([child.stdout], [], [], 8)[0], "combined helper response timed out"
    result = child.stdout.readline().strip()
    assert result in (b"READY", b"PASS", b"OK", b"DENIED"), "combined helper failed (redacted)"
    return result


@pytest.fixture
def combined(recovered, request):
    s = recovered
    peer = create_peers(request, pin=s.setup.admission.journal.pin.model_dump(mode="json"))
    work = peer.root / "custody"
    work.mkdir(mode=0o700)
    os.chown(work, peer.custody_uid, peer.custody_uid)
    settings = {
        "schema": s.receipts, "capture": s.capture, "product": s.product,
        "claim": s.claim.model_dump(mode="json"),
        "snapshot": s.setup.snapshots[0].model_dump(mode="json"),
        "candidate": candidate(s.setup.snapshots[0], s.claim.operation_id),
        "fixture": str(work / "canned.json"),
    }
    children = []

    def start(**changes):
        child = peer.spawn(
            peer.custody_uid, interactive=True, helper=HELPER, action="custody",
            runtime_url=s.observer_runtime.url.render_as_string(hide_password=False),
            **{**settings, **changes},
        )
        children.append(child)
        assert response(child) == b"READY"
        return child

    def command(name, child=None):
        target = child or children[0]
        target.stdin.write((name + "\n").encode())
        target.stdin.flush()
        return response(target)

    def comparisons():
        with Session(s.admin) as db:
            return db.query(AgentComparison).all()

    def human():
        with s.admin.connect() as db:
            return tuple(db.execute(text(
                f'SELECT row_to_json(t)::text FROM "{s.product}"."{table}" t '
                'ORDER BY row_to_json(t)::text',
            )).scalars().all() for table in (
                "submitted_case", "case_input_revision", "review_case", "review_audit",
                "review_outbox", "mvp_event", "analytics_event",
            ))

    before = human()
    # Actual separate clinical OS UID receives only its own restricted DB login.
    clinical = peer.spawn(
        peer.clinical_uid, helper=HELPER, action="clinical",
        runtime_url=s.runtime.url.render_as_string(hide_password=False), **settings,
    )
    assert response(clinical) == b"PASS"
    out, err = clinical.communicate(timeout=5)
    assert clinical.returncode == 0 and not out and not err
    state = SimpleNamespace(s=s, peer=peer, start=start, command=command,
                            comparisons=comparisons, human=human, before=before)
    yield state
    for child in children:
        if child.poll() is None:
            child.stdin.write(b"exit\n")
            child.stdin.close()
            child.stdin = None
        out, err = child.communicate(timeout=5)
        assert child.returncode == 0 and not out and not err, "combined child cleanup failed"
    assert human() == before


def test_actual_logins_peer_and_child_publish_once_without_owner_fallback(combined):
    c = combined
    original = rows(c.s)[0]
    c.start()
    for stage in ("verify", "prepare", "replacement", "dispatch", "heartbeat", "publish"):
        assert c.command(stage) == (b"DENIED" if stage == "replacement" else b"OK")
    for stage in ("dispatch", "publish", "prepare", "replacement"):
        assert c.command(stage) == b"DENIED"
    after, attempts = rows(c.s)
    assert after.state == "published" and after.deadline == original.deadline
    assert after.fence_id == original.fence_id and len(attempts) == 1
    assert len(c.comparisons()) == 1 and c.peer.rows()[0][-1] == "issued"
    assert balance(c.s.setup) == (1, 0, 0, 10, 0)


@pytest.mark.parametrize("fault", ["clinical", "assignment", "membership"])
def test_revoked_scope_after_prepare_denies_before_child_without_refund(combined, fault):
    c = combined
    c.start()
    assert c.command("prepare") == b"OK"
    statement = {
        "clinical": f'UPDATE "{c.s.capture}".principal SET enabled=false',
        "assignment": f'UPDATE "{c.s.receipts}".submission_scope SET enabled=false',
        "membership": "UPDATE tenant_membership SET active=false",
    }[fault]
    mutate(c.s, statement)
    assert c.command("dispatch") == b"DENIED"
    assert c.command("dispatch") == b"DENIED"
    assert not c.comparisons() and c.peer.rows()[0][-1] == "prepared"
    assert len(rows(c.s)[1]) == 1 and balance(c.s.setup) == (1, 1, 10, 0, 0)


@pytest.mark.parametrize("stage", ["prepare", "dispatch"])
def test_lost_peer_ack_retains_marker_and_never_replays_or_refunds(combined, stage):
    c = combined
    c.start()
    if stage == "dispatch":
        assert c.command("prepare") == b"OK"
    c.peer.stop(c.peer.server)
    Path(c.peer.path).unlink()
    c.peer.server = c.peer.start(reply_fault="empty",
                               reply_command="prepare" if stage == "prepare" else "issue")
    assert c.command(stage) == b"DENIED"
    assert c.command("dispatch") == b"DENIED"
    assert not c.comparisons()
    retained = c.peer.rows()
    assert len(retained) == 1, "lost_ack_committed_marker_missing"
    assert retained[0][-1] == ("prepared" if stage == "prepare" else "issued")
    assert len(rows(c.s)[1]) == (0 if stage == "prepare" else 1)
    assert balance(c.s.setup) == (1, 1, 10, 0, 0)


def test_restarted_coordinator_cannot_adopt_prepared_or_issued_work(combined):
    c = combined
    first = c.start()
    assert c.command("prepare", first) == b"OK"
    second = c.start()
    assert c.command("dispatch", second) == b"DENIED"
    assert c.command("dispatch", first) == b"OK"
    assert c.command("publish", second) == b"DENIED"
    assert c.command("publish", first) == b"OK"
    assert len(rows(c.s)[1]) == len(c.comparisons()) == 1


@pytest.mark.parametrize("available", [True, False])
def test_expired_submitted_work_recovers_unknown_even_when_peer_is_down(combined, available):
    c = combined
    c.start()
    assert c.command("prepare") == c.command("dispatch") == b"OK"
    if not available:
        c.peer.stop(c.peer.server)
    expire_lease(c.s)
    assert c.command("recover") == c.command("recover") == b"OK"
    assert c.command("publish") == c.command("dispatch") == b"DENIED"
    assert rows(c.s)[0].state == "unknown" and not c.comparisons()
    assert len(rows(c.s)[1]) == 1 and balance(c.s.setup) == (1, 1, 0, 0, 10)


def test_peer_down_before_checkpoint_does_not_create_attempt_or_use_direct_journal(combined):
    c = combined
    c.start()
    c.peer.stop(c.peer.server)
    assert c.command("prepare") == b"DENIED"
    assert not rows(c.s)[1] and not c.comparisons() and not c.peer.rows()
    assert balance(c.s.setup) == (1, 1, 10, 0, 0)


def test_invalid_child_money_cannot_publish_through_actual_peer_and_database(combined):
    c = combined
    body = candidate(c.s.setup.snapshots[0], c.s.claim.operation_id)
    body["payable_inr"] = 1
    c.start(candidate=body)
    assert c.command("prepare") == c.command("dispatch") == b"OK"
    assert c.command("publish") == c.command("publish") == b"DENIED"
    assert c.peer.rows()[0][-1] == "issued" and not c.comparisons()
    assert balance(c.s.setup) == (1, 1, 10, 0, 0)
