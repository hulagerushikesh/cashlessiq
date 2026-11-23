"""Real HTTP intent -> clinical UID claim -> separate custody/peer -> HTTP result."""

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
from uuid import uuid4

from sqlalchemy.orm import Session
from test_agent_controller_capture import controller_database as controller_database
from test_agent_controller_capture import engine as engine
from test_agent_controller_capture import scope as scope
from test_agent_controller_capture import setup as setup
from test_agent_controller_reservation import commands as commands
from test_agent_custody_publication import install as install_publication
from test_agent_custody_submission import install as install_custody
from test_agent_custody_submission import rows
from test_agent_ledger import balance
from test_agent_peer_database import HELPER, combined_runtime
from test_agent_receipt_peer_linux import create_peers
from test_agent_receipt_verifier import observer as observer
from test_agent_requested_dispatch import PATH
from test_agent_requested_dispatch import requested as requested
from test_identity import bearer

from ciq_api.agent_ledger import ClaimReceipt
from ciq_api.mvp_models import WorkJob


@pytest.mark.parametrize("valid", [True, False], ids=["published", "invalid-held"])
def test_app_request_runs_once_through_real_logins_and_separate_receipt_uid(
    requested, observer, request, settings, valid,
):
    s = requested
    assert s is observer
    peer = create_peers(request, pin=s.setup.admission.journal.pin.model_dump(mode="json"))
    # This UID receives only the clinical login and an intent ID. No owning DB,
    # custody credential or direct retained-journal fallback exists in the child.
    child = peer.spawn(
        peer.clinical_uid, helper=HELPER, action="claim_requested",
        runtime_url=s.runtime.url.render_as_string(hide_password=False),
        capture=s.capture, schema=s.receipts, product=s.product, job_id=str(s.job_id),
    )
    assert select.select([child.stdout], [], [], 8)[0], "intent claim timed out"
    line = child.stdout.readline(1024)
    assert line.startswith(b"CLAIM:") and line.endswith(b"\n"), "intent claim failed (redacted)"
    s.claim = ClaimReceipt.model_validate_json(line.removeprefix(b"CLAIM:"))
    out, err = child.communicate(timeout=5)
    assert child.returncode == 0 and not out and not err
    # Explicit trusted dummy operator step. Runtime cannot write this registry
    # or turn a browser receipt into custody authority by itself.
    install_custody(s)
    install_publication(s)
    with combined_runtime(s, peer) as c:
        changes = {}
        if not valid:
            from test_agent_contracts import candidate
            body = candidate(s.setup.snapshots[0], s.claim.operation_id)
            body["payable_inr"] = 1
            changes["candidate"] = body
        c.start(**changes)
        assert c.command("run") == (b"OK" if valid else b"DENIED")
        assert c.command("run") == c.command("dispatch") == b"DENIED"
        op, attempts = rows(s)
        assert len(attempts) == 1 and peer.rows()[0][-1] == "issued"
        view = s.http.get(PATH + "/agent-result", headers=s.headers)
        assert view.status_code == 200 and view.headers["cache-control"] == "no-store"
        assert view.json()["state"] == ("published" if valid else "submitting")
        assert view.json()["request_context"] is None
        if valid:
            assert len(c.comparisons()) == 1 and view.json()["comparison"]["payable_inr"] == 95000
            assert balance(s.setup) == (1, 0, 0, 10, 0)
        else:
            assert not c.comparisons() and view.json()["comparison"] is None
            assert balance(s.setup) == (1, 1, 10, 0, 0)
        for role in ("processor", "auditor"):
            denied = s.http.get(PATH + "/agent-result", headers=bearer(settings, role))
            assert denied.status_code == 403
        # New commands cannot adopt or retry the existing operation.
        assert s.http.post(PATH + "/agent-request", headers=s.headers, json={
            "command_id": str(uuid4()), "expected_input_revision": 0,
            "expected_review_version": 0, "synthetic_data": True,
        }).status_code == 409
        with Session(s.admin) as db:
            job = db.get(WorkJob, s.job_id)
            assert job.state == "executor_claimed" and job.attempts == 0
            assert job.result == {"operation_id": str(op.id)}
