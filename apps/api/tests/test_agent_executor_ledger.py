"""Disposable PostgreSQL + actual local child; separate container isolation in CI.

No local Docker startup. The local child is not claimed to be OS-sandboxed here.
The supplied test transport manufactures a canned fixture, never provider parity.
"""

import base64
import hashlib
import json
import sys
from datetime import timedelta
from pathlib import Path

import pytest
import test_agent_ledger as ledger_tests
from sqlalchemy.orm import Session
from test_agent_contracts import candidate
from test_agent_ledger import (
    ACTOR,
    balance,
    reserve,
    rows,
)
from test_agent_ledger import setup as setup

from ciq_api import agent_executor
from ciq_api.agent_contracts import AgentContractError, AgentInput
from ciq_api.agent_executor import BoundedFakeProcess, execute_fake_process
from ciq_api.agent_ledger_models import AgentAttempt, AgentComparison, AgentOperation
from ciq_api.models import Membership
from ciq_api.mvp_models import SubmittedCase
from ciq_api.review_models import ReviewCase
from ciq_api.seed import TENANT_ID

ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT / "apps/agent-transport/fake_transport.py"
HELPER = ROOT / "apps/agent-transport/tests/exchange_fixture.py"


@pytest.fixture(autouse=True)
def real_test_clock(monkeypatch):
    monkeypatch.setattr(ledger_tests, "NOW", agent_executor.datetime.now(agent_executor.UTC))


class CannedProcess:
    def __init__(self, s, directory, *, fault=None):
        self.s = s
        self.directory = directory
        self.fault = fault
        self.calls = 0
        self.child = None

    def exchange(self, raw, *, timeout):
        self.calls += 1
        request = json.loads(raw)
        # An independent connection observes the sole committed checkpoint before
        # any process starts; no DB connection/secret is passed to that child.
        attempts = rows(self.s, AgentAttempt)
        assert len(attempts) == 1
        assert str(attempts[0].submission_id) == request["submission_id"]
        assert str(attempts[0].id) == request["attempt_id"]
        assert rows(self.s, AgentOperation)[0].state == "submitting"
        assert balance(self.s) == (1, 1, 10, 0, 0)
        if self.fault == "revoke":
            with Session(self.s.engine) as db, db.begin():
                db.get(Membership, (TENANT_ID, ACTOR)).active = False
        if self.fault == "review":
            with Session(self.s.engine) as db, db.begin():
                review = db.get(ReviewCase, (TENANT_ID, "REQ-FAKE-0"))
                review.version += 1
        body = candidate(AgentInput.model_validate(request["snapshot"]), request["operation_id"])
        if self.fault == "candidate":
            body["payable_inr"] = 1
        fixture = self.directory / "canned.json"
        fixture.write_text(json.dumps({
            "request_sha256": hashlib.sha256(raw).hexdigest(),
            "candidate_base64": base64.b64encode(json.dumps(body).encode()).decode(),
        }))
        fixture.chmod(0o600)
        if self.fault in {"crash", "timeout", "oversize", "frame"}:
            code = {
                "crash": "import os; os._exit(7)",
                "timeout": "import time; time.sleep(60)",
                "oversize": "import sys; sys.stdout.write('x'*2000000)",
                "frame": "import sys; sys.stdout.write('private malformed clinical text')",
            }[self.fault]
            self.child = BoundedFakeProcess((sys.executable, "-I", "-c", code))
            timeout = min(timeout, 0.3)
        else:
            self.child = BoundedFakeProcess((
                sys.executable, "-I", str(HELPER), str(RUNTIME), str(fixture),
            ))
        return self.child.exchange(raw, timeout=timeout)


def run(s, transport, monkeypatch):
    monkeypatch.setattr(agent_executor, "_utc_now", lambda: s.clock[0])
    receipt = reserve(s)
    claim = s.ledger.claim(TENANT_ID, ACTOR, receipt.operation_id)
    return claim, execute_fake_process(s.ledger, TENANT_ID, ACTOR, claim, transport)


def test_checkpoint_before_child_and_private_publication_only(setup, tmp_path, monkeypatch):
    s = setup
    before = rows(s, SubmittedCase)[0].record
    transport = CannedProcess(s, tmp_path)
    claim, result = run(s, transport, monkeypatch)
    assert result.state == "published"
    assert transport.calls == 1
    assert len(rows(s, AgentAttempt)) == len(rows(s, AgentComparison)) == 1
    assert balance(s) == (1, 0, 0, 10, 0)
    assert rows(s, SubmittedCase)[0].record == before
    review = next(r for r in rows(s, ReviewCase) if r.request_id == "REQ-FAKE-0")
    assert review.state == "DRAFT_READY" and review.final_payable_inr is None
    with pytest.raises(AgentContractError):
        execute_fake_process(s.ledger, TENANT_ID, ACTOR, claim, transport)
    assert transport.calls == 1


@pytest.mark.parametrize("fault", ["crash", "timeout", "oversize", "frame"])
def test_child_failure_retains_uncertain_allowance_and_cannot_replay(
    setup, tmp_path, monkeypatch, fault,
):
    s = setup
    monkeypatch.setattr(agent_executor, "_utc_now", lambda: s.clock[0])
    receipt = reserve(s)
    claim = s.ledger.claim(TENANT_ID, ACTOR, receipt.operation_id)
    transport = CannedProcess(s, tmp_path, fault=fault)
    with pytest.raises(AgentContractError):
        execute_fake_process(s.ledger, TENANT_ID, ACTOR, claim, transport)
    assert transport.calls == 1
    assert balance(s) == (1, 1, 10, 0, 0)
    assert rows(s, AgentOperation)[0].state == "submitting"
    assert len(rows(s, AgentAttempt)) == 1 and not rows(s, AgentComparison)
    s.clock[0] += timedelta(seconds=31)
    recovered = s.ledger.recover_expired(TENANT_ID, receipt.operation_id)
    assert recovered.state == "unknown" and balance(s) == (1, 1, 0, 0, 10)
    with pytest.raises(AgentContractError):
        execute_fake_process(s.ledger, TENANT_ID, ACTOR, claim, transport)
    assert transport.calls == 1
    assert reserve(s).state == "unknown"


@pytest.mark.parametrize("fault", ["candidate", "revoke", "review"])
def test_process_result_cannot_override_fresh_clinical_validation(
    setup, tmp_path, monkeypatch, fault,
):
    transport = CannedProcess(setup, tmp_path, fault=fault)
    if fault == "revoke":
        with pytest.raises(AgentContractError, match="scope_unavailable"):
            run(setup, transport, monkeypatch)
        assert balance(setup) == (1, 1, 10, 0, 0)
    else:
        _, result = run(setup, transport, monkeypatch)
        assert result.state == ("rejected" if fault == "candidate" else "superseded")
        assert balance(setup) == (1, 0, 0, 10, 0)
    assert transport.calls == 1
    assert len(rows(setup, AgentAttempt)) == 1 and not rows(setup, AgentComparison)


def test_no_child_when_checkpoint_denied(setup, tmp_path, monkeypatch):
    transport = CannedProcess(setup, tmp_path)
    receipt = reserve(setup)
    claim = setup.ledger.claim(TENANT_ID, ACTOR, receipt.operation_id)
    with Session(setup.engine) as db, db.begin():
        db.get(Membership, (TENANT_ID, ACTOR)).active = False
    with pytest.raises(AgentContractError):
        execute_fake_process(setup.ledger, TENANT_ID, ACTOR, claim, transport)
    assert transport.calls == 0
    assert not rows(setup, AgentAttempt)


def test_local_clock_exhaustion_consumes_checkpoint_without_child(setup, tmp_path, monkeypatch):
    s = setup
    monkeypatch.setattr(agent_executor, "_utc_now", lambda: s.clock[0] + timedelta(seconds=29))
    receipt = reserve(s)
    claim = s.ledger.claim(TENANT_ID, ACTOR, receipt.operation_id)
    transport = CannedProcess(s, tmp_path)
    with pytest.raises(AgentContractError, match="fake_transport_unavailable"):
        execute_fake_process(s.ledger, TENANT_ID, ACTOR, claim, transport)
    assert transport.calls == 0 and len(rows(s, AgentAttempt)) == 1
    assert balance(s) == (1, 1, 10, 0, 0)


@pytest.mark.parametrize("field", ["config_digest", "source_digest", "deadline"])
def test_publication_cannot_change_process_pins_or_extend_effective_lease(setup, field):
    from test_agent_ledger import payload, submission

    permit = submission(setup)
    value = "c" * 64 if field.endswith("digest") else permit.deadline + timedelta(seconds=1)
    forged = permit.model_copy(update={field: value})
    with pytest.raises(AgentContractError, match="invalid_submission_receipt"):
        setup.ledger.publish_fake_result(forged, payload(permit))
    assert not rows(setup, AgentComparison)
    assert balance(setup) == (1, 1, 10, 0, 0)
    assert setup.ledger.publish_fake_result(permit, payload(permit)).state == "published"
