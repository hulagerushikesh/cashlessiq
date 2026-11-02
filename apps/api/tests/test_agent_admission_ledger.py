"""Default-closed PostgreSQL gate + separately retained fake SQLite custody.

Only disposable CI supplies PostgreSQL. No provider, cloud service or local
Docker startup. The independent journal is not part of the PostgreSQL backup.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from test_agent_ledger import ACTOR, TENANT_ID, balance, payload, reserve, rows, submission
from test_agent_ledger import setup as setup

from ciq_api.agent_admission import (
    ERROR,
    FakeAdmissionGate,
    FakeEpochPin,
    FakeReceiptJournal,
)
from ciq_api.agent_contracts import AgentContractError
from ciq_api.agent_executor import execute_fake_process
from ciq_api.agent_ledger import FakeAgentLedger
from ciq_api.agent_ledger_models import AgentAdmissionEpoch, AgentAttempt, AgentOperation


def closed(call):
    with pytest.raises(AgentContractError, match=f"^{ERROR}$"):
        call()


def claimed(s):
    operation = reserve(s)
    return s.ledger.claim(TENANT_ID, ACTOR, operation.operation_id)


class NeverProcess:
    def exchange(self, *args, **kwargs):
        pytest.fail("Quarantined/recovered checkpoint must not start a child")


def test_default_constructor_is_quarantined_despite_a_valid_fake_grant(setup):
    s = setup
    s.ledger = FakeAgentLedger(s.engine)
    closed(lambda: reserve(s))
    assert not rows(s, AgentOperation) and not rows(s, AgentAttempt)
    assert balance(s) == (0, 0, 0, 0, 0)


def test_migration_creates_no_epoch_and_missing_anchor_is_closed(engine, tmp_path):
    with Session(engine) as db:
        assert not list(db.scalars(text("SELECT id FROM agent_admission_epoch")))
    pin = FakeEpochPin(database_id=uuid4(), epoch_id=uuid4())
    journal = FakeReceiptJournal.provision(tmp_path / "orphan", pin)
    ledger = FakeAgentLedger(engine, admission=FakeAdmissionGate(journal))
    with Session(engine) as db, db.begin():
        closed(lambda: ledger._admit(db))
    journal.check(())


@pytest.mark.parametrize("fault", ["database_id", "epoch_id", "missing", "closed"])
def test_bad_custody_denies_before_reservation_or_child(setup, fault):
    s = setup
    claim = claimed(s)
    original = s.admission.journal
    if fault in {"database_id", "epoch_id"}:
        pin = original.pin.model_copy(update={fault: uuid4()})
        s.ledger.admission = FakeAdmissionGate(FakeReceiptJournal(original.directory, pin))
    elif fault == "missing":
        original.path.unlink()
    else:
        original.quarantine()
    for action in (
        lambda: reserve(s, 1),
        lambda: s.ledger.claim(TENANT_ID, ACTOR, claim.operation_id),
        lambda: s.ledger.heartbeat(TENANT_ID, ACTOR, claim),
        lambda: execute_fake_process(s.ledger, TENANT_ID, ACTOR, claim, NeverProcess()),
    ):
        closed(action)
    assert not rows(s, AgentAttempt)
    assert balance(s) == (1, 1, 10, 0, 0)


def test_fake_bootstrap_cannot_rebind_existing_anchor_or_reset_history(setup, tmp_path):
    s = setup
    first = s.admission.journal.pin
    closed(lambda: FakeAdmissionGate.provision_empty_for_tests(s.engine, tmp_path / "replacement"))
    assert not (tmp_path / "replacement").exists()
    permit = submission(s)
    closed(lambda: FakeAdmissionGate.provision_empty_for_tests(s.engine, tmp_path / "new-epoch"))
    assert s.admission.journal.pin == first
    assert s.ledger.publish_fake_result(permit, payload(permit)).state == "published"


def test_epoch_identity_is_append_only_and_fake_only(setup):
    s = setup
    for sql in (
        "DELETE FROM agent_admission_epoch",
        "UPDATE agent_admission_epoch SET epoch_id=gen_random_uuid()",
        "UPDATE agent_admission_epoch SET database_id=gen_random_uuid()",
        "UPDATE agent_admission_epoch SET mode='live'",
        "INSERT INTO agent_admission_epoch SELECT 2,mode,database_id,epoch_id "
        "FROM agent_admission_epoch",
    ):
        with pytest.raises(DBAPIError), s.engine.begin() as db:
            db.execute(text(sql))
    assert len(rows(s, AgentAdmissionEpoch)) == 1
    assert reserve(s).state == "reserved"


def test_crash_after_external_prepare_before_local_commit_quarantines_all_admission(
    setup, monkeypatch,
):
    s = setup
    claim = claimed(s)
    prepare = s.admission.prepare

    def crash(db, attempt):
        prepare(db, attempt)  # Independently committed; SQL transaction rolls back below.
        raise RuntimeError("synthetic crash before local commit")

    monkeypatch.setattr(s.admission, "prepare", crash)
    with pytest.raises(RuntimeError, match="synthetic crash"):
        s.ledger.begin_submission(TENANT_ID, ACTOR, claim)
    assert not rows(s, AgentAttempt)
    assert rows(s, AgentOperation)[0].state == "reserved"
    # Even an unrelated case/new coordinator cannot spend through contradictory custody.
    s.ledger = FakeAgentLedger(s.engine, admission=s.admission)
    closed(lambda: reserve(s, 1))
    closed(lambda: s.ledger.begin_submission(TENANT_ID, ACTOR, claim))
    assert balance(s) == (1, 1, 10, 0, 0)


def test_failed_external_prepare_rolls_back_local_checkpoint(setup, monkeypatch):
    s = setup
    claim = claimed(s)

    def unavailable(_):
        raise AgentContractError(ERROR)

    monkeypatch.setattr(s.admission.journal, "prepare", unavailable)
    closed(lambda: s.ledger.begin_submission(TENANT_ID, ACTOR, claim))
    assert not rows(s, AgentAttempt)
    assert balance(s) == (1, 1, 10, 0, 0)
    assert rows(s, AgentOperation)[0].state == "reserved"


def test_crash_after_local_commit_before_issue_never_rehydrates_permission(setup):
    s = setup
    permit = submission(s)
    s.ledger = FakeAgentLedger(s.engine, admission=FakeAdmissionGate(
        FakeReceiptJournal(s.admission.journal.directory, s.admission.journal.pin),
    ))
    with pytest.raises(AgentContractError, match="automatic_retry_forbidden"):
        s.ledger.authorize_fake_io(permit)
    with pytest.raises(AgentContractError):
        execute_fake_process(s.ledger, TENANT_ID, ACTOR, permit, NeverProcess())
    assert balance(s) == (1, 1, 10, 0, 0)
    s.clock[0] += timedelta(seconds=31)
    assert s.ledger.recover_expired(TENANT_ID, permit.operation_id).state == "unknown"
    assert balance(s) == (1, 1, 0, 0, 10)


def test_crash_after_issue_before_io_is_never_reissued_or_refunded(setup):
    s = setup
    permit = submission(s)
    s.ledger.authorize_fake_io(permit)
    with pytest.raises(AgentContractError, match="automatic_retry_forbidden"):
        s.ledger.authorize_fake_io(permit)
    s.ledger = FakeAgentLedger(s.engine, admission=s.admission)
    with pytest.raises(AgentContractError):
        s.ledger.authorize_fake_io(permit)
    s.clock[0] += timedelta(seconds=31)
    assert s.ledger.recover_expired(TENANT_ID, permit.operation_id).state == "unknown"
    assert balance(s) == (1, 1, 0, 0, 10)


def test_lost_external_receipts_block_publication_but_status_recovery_retains_cost(setup):
    s = setup
    permit = submission(s)
    s.ledger.authorize_fake_io(permit)
    s.admission.journal.path.unlink()
    closed(lambda: s.ledger.publish_fake_result(permit, payload(permit)))
    closed(lambda: reserve(s, 1))
    s.clock[0] += timedelta(seconds=31)
    assert s.ledger.recover_expired(TENANT_ID, permit.operation_id).state == "unknown"
    assert balance(s) == (1, 1, 0, 0, 10)
    assert not s.admission.journal.path.exists()


@pytest.mark.parametrize("field", ["config_digest", "source_digest", "submission_id", "deadline"])
def test_issue_rechecks_exact_permit_and_consumes_even_forged_local_request(setup, field):
    s = setup
    permit = submission(s)
    value = (
        "c" * 64 if field.endswith("digest") else
        permit.deadline + timedelta(seconds=1) if field == "deadline" else uuid4()
    )
    with pytest.raises(AgentContractError):
        s.ledger.authorize_fake_io(permit.model_copy(update={field: value}))
    if field != "submission_id":
        # A forged request with the real submission ID sacrifices local permission.
        with pytest.raises(AgentContractError):
            s.ledger.authorize_fake_io(permit)
    assert balance(s) == (1, 1, 10, 0, 0)


def test_parallel_fresh_coordinators_cannot_issue_another_instances_permit(setup):
    s = setup
    permit = submission(s)
    barrier = Barrier(2)

    def issue(ledger):
        barrier.wait(timeout=10)
        try:
            ledger.authorize_fake_io(permit)
            return "ok"
        except AgentContractError:
            return "denied"

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(issue, s.ledger)
        other = pool.submit(issue, FakeAgentLedger(s.engine, admission=s.admission))
        assert sorted([first.result(timeout=20), other.result(timeout=20)]) == ["denied", "ok"]


def test_issue_rechecks_clinical_revocation_before_persisting_io_permission(setup):
    from ciq_api.models import Membership

    s = setup
    permit = submission(s)
    with Session(s.engine) as db, db.begin():
        db.get(Membership, (TENANT_ID, ACTOR)).active = False
    with pytest.raises(AgentContractError, match="scope_unavailable"):
        s.ledger.authorize_fake_io(permit)
    assert balance(s) == (1, 1, 10, 0, 0)
