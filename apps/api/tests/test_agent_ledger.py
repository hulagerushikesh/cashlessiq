"""Real disposable PostgreSQL transactions; only the gateway is fake.

No Docker is started by this suite. CI supplies the disposable database through
the existing per-test schema fixture. Clock injection never reaches a route.
"""

import ast
import json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from importlib.resources import files
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from test_agent_contracts import candidate

from ciq_api import agent_ledger
from ciq_api.agent_admission import FakeAdmissionGate
from ciq_api.agent_contracts import AgentContractError
from ciq_api.agent_ledger import FakeAgentLedger, FakeGrantSpec, operation_key
from ciq_api.agent_ledger_models import (
    AgentAttempt,
    AgentComparison,
    AgentExecutionGrant,
    AgentOperation,
)
from ciq_api.assessment import calculate, fingerprint
from ciq_api.models import AppUser, Membership, Tenant
from ciq_api.mvp_models import CaseInputRevision, MvpEvent, PolicyVersion, SubmittedCase
from ciq_api.review_models import ReviewCase
from ciq_api.seed import PROFILES, TENANT_ID

NOW = datetime(2026, 11, 2, 10, tzinfo=UTC)
CONFIG = "a" * 64
SOURCE = "b" * 64
ACTOR = UUID(PROFILES["medical_officer"][0])


@pytest.fixture
def setup(engine, monkeypatch, tmp_path):
    clock = [NOW]
    monkeypatch.setattr(agent_ledger, "_now", lambda db: clock[0])
    policy = json.loads(files("ciq_api").joinpath("fixtures/policy-template.json").read_text())
    policy_id = uuid4()
    with Session(engine) as db, db.begin():
        db.add(
            PolicyVersion(
                id=policy_id,
                tenant_id=TENANT_ID,
                product_id=policy["product_id"],
                version=policy["version"],
                author_id=ACTOR,
                command_id=uuid4(),
                fingerprint=fingerprint(policy),
                proposal=policy,
            )
        )
        db.flush()
        db.add(
            MvpEvent(
                id=uuid4(),
                tenant_id=TENANT_ID,
                actor_id=ACTOR,
                actor_role="medical_officer",
                command_id=uuid4(),
                action="policy_approve",
                subject_id=str(policy_id),
                fingerprint="0" * 64,
                payload={},
            )
        )
        for index in range(3):
            request_id = f"REQ-FAKE-{index}"
            facts = deepcopy(policy["examples"][0]["facts"])
            facts["member_reference"] = f"SYN-FAKE-{index}"
            db.add(
                SubmittedCase(
                    tenant_id=TENANT_ID,
                    request_id=request_id,
                    actor_id=ACTOR,
                    command_id=uuid4(),
                    fingerprint=fingerprint(facts),
                    policy_id=policy_id,
                    inputs=facts,
                    record=calculate(request_id, facts, policy),
                    priority="normal",
                    due_at=NOW + timedelta(hours=1),
                )
            )
            db.flush()
            db.add(
                CaseInputRevision(
                    tenant_id=TENANT_ID,
                    request_id=request_id,
                    revision=0,
                    actor_id=ACTOR,
                    inputs=facts,
                    digest=fingerprint(facts),
                )
            )
            db.add(
                ReviewCase(
                    tenant_id=TENANT_ID,
                    request_id=request_id,
                    version=0,
                    state="DRAFT_READY",
                )
            )
    ledger = FakeAgentLedger(engine)
    snapshots = [ledger.capture(TENANT_ID, ACTOR, f"REQ-FAKE-{i}") for i in range(3)]
    spec = FakeGrantSpec(
        approval_ref="FAKE TEST ONLY; no real spend approved",
        operation_keys=tuple(operation_key(s, CONFIG, SOURCE) for s in snapshots),
        config_digest=CONFIG,
        source_digest=SOURCE,
        starts_at=NOW,
        ends_at=NOW + timedelta(minutes=10),
        case_limit=3,
        concurrency_limit=3,
        units_per_attempt=10,
        unit_limit=30,
    )
    grant_id = ledger.create_fake_grant(TENANT_ID, spec)
    admission = FakeAdmissionGate.provision_empty_for_tests(engine, tmp_path / "fake-custody")
    ledger = FakeAgentLedger(engine, admission=admission)
    return SimpleNamespace(
        engine=engine,
        ledger=ledger,
        admission=admission,
        clock=clock,
        policy_id=policy_id,
        snapshots=snapshots,
        spec=spec,
        grant_id=grant_id,
    )


def reserve(s, index=0, **changes):
    return s.ledger.reserve(
        TENANT_ID,
        ACTOR,
        f"REQ-FAKE-{index}",
        **{
            "grant_id": s.grant_id,
            "correlation_id": uuid4(),
            "config_digest": CONFIG,
            "source_digest": SOURCE,
            **changes,
        },
    )


def submission(s, index=0):
    receipt = reserve(s, index)
    claim = s.ledger.claim(TENANT_ID, ACTOR, receipt.operation_id)
    return s.ledger.begin_submission(TENANT_ID, ACTOR, claim)


def payload(permit):
    return json.dumps(candidate(permit.snapshot, permit.operation_id)).encode()


def rows(s, model):
    with Session(s.engine) as db:
        return list(db.scalars(select(model)))


def balance(s):
    with Session(s.engine) as db:
        grant = db.get(AgentExecutionGrant, (TENANT_ID, s.grant_id))
        return (
            grant.admitted,
            grant.in_flight,
            grant.reserved_units,
            grant.consumed_units,
            grant.uncertain_units,
        )


def test_commit_before_fake_io_and_publication_preserves_human_workflow(setup):
    s = setup
    permit = submission(s)
    # A different connection sees the checkpoint before the fake gateway executes.
    attempts = rows(s, AgentAttempt)
    assert len(attempts) == 1 and attempts[0].submission_id == permit.submission_id
    assert rows(s, AgentOperation)[0].state == "submitting"
    assert balance(s) == (1, 1, 10, 0, 0)
    with Session(s.engine) as db:
        before = db.get(SubmittedCase, (TENANT_ID, "REQ-FAKE-0")).record
    result = s.ledger.publish_fake_result(permit, payload(permit))
    assert result.state == "published"
    assert balance(s) == (1, 0, 0, 10, 0)
    assert len(rows(s, AgentComparison)) == 1
    with Session(s.engine) as db:
        assert db.get(SubmittedCase, (TENANT_ID, "REQ-FAKE-0")).record == before
        review = db.get(ReviewCase, (TENANT_ID, "REQ-FAKE-0"))
        assert review.version == 0 and review.final_payable_inr is None
        for table in ("review_audit", "review_outbox", "analytics_event"):
            assert db.scalar(text(f"SELECT count(*) FROM {table}")) == 0
    assert "explanation" not in result.model_dump_json()
    assert "facts_json" not in repr(permit)


def test_repeated_publication_and_enqueue_are_idempotent_after_restart(setup):
    s = setup
    permit = submission(s)
    result = s.ledger.publish_fake_result(permit, payload(permit))
    s.ledger = FakeAgentLedger(s.engine, admission=s.admission)
    assert s.ledger.publish_fake_result(permit, b"ignored duplicate") == result
    assert reserve(s) == result
    assert len(rows(s, AgentComparison)) == len(rows(s, AgentAttempt)) == 1
    assert balance(s) == (1, 0, 0, 10, 0)


def test_correlation_review_and_new_grant_do_not_buy_another_call(setup):
    s = setup
    first = reserve(s)
    with Session(s.engine) as db, db.begin():
        review = db.get(ReviewCase, (TENANT_ID, "REQ-FAKE-0"))
        review.version += 1
        review.assignee_id = ACTOR
    second_grant = s.ledger.create_fake_grant(TENANT_ID, s.spec)
    assert reserve(s, grant_id=second_grant) == first
    assert len(rows(s, AgentOperation)) == 1
    with pytest.raises(AgentContractError, match="stale_or_wrong_scope"):
        s.ledger.claim(TENANT_ID, ACTOR, first.operation_id)
    assert not rows(s, AgentAttempt)


def test_stable_key_excludes_only_non_computation_fields(setup):
    snap = setup.snapshots[0]
    changes = snap.model_copy(
        update={
            "binding": snap.binding.model_copy(
                update={
                    "correlation_id": uuid4(),
                    "review_version": 9,
                }
            )
        }
    )
    assert operation_key(snap, CONFIG, SOURCE) == operation_key(changes, CONFIG, SOURCE)
    for field, value in (
        ("input_revision", 1),
        ("input_digest", "c" * 64),
        ("policy_id", uuid4()),
        ("policy_version", "different"),
        ("rules_digest", "c" * 64),
        ("policy_digest", "c" * 64),
        ("evidence_digest", "c" * 64),
        ("tenant_id", uuid4()),
        ("request_id", "REQ-OTHER"),
    ):
        changed = snap.model_copy(
            update={"binding": snap.binding.model_copy(update={field: value})}
        )
        assert operation_key(snap, CONFIG, SOURCE) != operation_key(changed, CONFIG, SOURCE)
    assert operation_key(snap, CONFIG, SOURCE) != operation_key(snap, SOURCE, CONFIG)


@pytest.mark.parametrize("field", ["config_digest", "source_digest"])
def test_changed_configuration_cannot_bypass_allowlist(setup, field):
    with pytest.raises(AgentContractError, match="allowance_unavailable"):
        reserve(setup, **{field: "c" * 64})
    assert not rows(setup, AgentOperation)
    assert balance(setup) == (0, 0, 0, 0, 0)


@pytest.mark.parametrize("phase", ["before_reservation", "after_reservation", "after_claim"])
def test_pre_submission_restart_is_safe_and_expiry_releases_only_units(setup, phase):
    s = setup
    if phase == "before_reservation":
        # Simulate rollback before a reservation transaction commits.
        with pytest.raises(RuntimeError), Session(s.engine) as db, db.begin():
            db.add(
                AgentOperation(
                    tenant_id=TENANT_ID,
                    id=uuid4(),
                    actor_id=ACTOR,
                    request_id="REQ-FAKE-0",
                    grant_id=s.grant_id,
                    operation_key="0" * 64,
                    config_digest=CONFIG,
                    source_digest=SOURCE,
                    snapshot=s.snapshots[0].model_dump(mode="json"),
                    state="reserved",
                    version=0,
                    created_at=NOW,
                    deadline=NOW + timedelta(seconds=120),
                )
            )
            db.flush()
            raise RuntimeError("fake crash before commit")
        assert not rows(s, AgentOperation)
    receipt = reserve(s)
    if phase == "after_claim":
        s.ledger.claim(TENANT_ID, ACTOR, receipt.operation_id)
    s.ledger = FakeAgentLedger(s.engine, admission=s.admission)
    s.clock[0] += timedelta(seconds=120)
    expired = s.ledger.recover_expired(TENANT_ID, receipt.operation_id)
    assert expired.state == "expired"
    assert s.ledger.recover_expired(TENANT_ID, receipt.operation_id) == expired
    assert reserve(s) == expired  # no deletion/requeue bypass, even though no call happened
    assert balance(s) == (1, 0, 0, 0, 0)
    assert not rows(s, AgentAttempt)


@pytest.mark.parametrize(
    "crash", ["before_io", "during_io", "after_remote_acceptance", "after_validation"]
)
def test_submission_crash_stays_unknown_and_never_returns_second_permit(setup, crash):
    s = setup
    permit = submission(s)
    fake_calls = []
    if crash != "before_io":
        fake_calls.append(permit.submission_id)
    if crash == "after_validation":
        agent_ledger.validate_candidate(
            permit.snapshot,
            agent_ledger.AgentContext(
                binding=permit.snapshot.binding,
                tenant_active=True,
                clinical_authorized=True,
                policy_approved=True,
                review_open=True,
            ),
            permit.operation_id,
            payload(permit),
        )
    s.ledger = FakeAgentLedger(s.engine, admission=s.admission)
    s.clock[0] += timedelta(seconds=30)
    result = s.ledger.recover_expired(TENANT_ID, permit.operation_id)
    assert result.state == "unknown"
    assert balance(s) == (1, 1, 0, 0, 10)
    assert reserve(s) == result
    assert s.ledger.recover_expired(TENANT_ID, permit.operation_id) == result
    with pytest.raises(AgentContractError):
        s.ledger.claim(TENANT_ID, ACTOR, permit.operation_id)
    with pytest.raises(AgentContractError):
        s.ledger.begin_submission(TENANT_ID, ACTOR, permit)
    with pytest.raises(AgentContractError):
        s.ledger.publish_fake_result(permit, payload(permit))
    assert len(rows(s, AgentAttempt)) == 1
    assert len(fake_calls) == (crash != "before_io")
    assert not rows(s, AgentComparison)


def test_expired_claim_successor_fences_old_worker_before_submission(setup):
    s = setup
    receipt = reserve(s)
    old = s.ledger.claim(TENANT_ID, ACTOR, receipt.operation_id)
    s.clock[0] += timedelta(seconds=30)
    new = s.ledger.claim(TENANT_ID, ACTOR, receipt.operation_id)
    assert new.fence_id != old.fence_id
    with pytest.raises(AgentContractError, match="expired_or_lost_run"):
        s.ledger.begin_submission(TENANT_ID, ACTOR, old)
    permit = s.ledger.begin_submission(TENANT_ID, ACTOR, new)
    assert s.ledger.publish_fake_result(permit, payload(permit)).state == "published"
    assert len(rows(s, AgentAttempt)) == 1


def test_heartbeat_cannot_extend_overall_deadline_and_stale_version_cannot_submit(setup):
    s = setup
    receipt = reserve(s)
    claim = s.ledger.claim(TENANT_ID, ACTOR, receipt.operation_id)
    for seconds in (20, 40, 60, 80, 100, 119):
        s.clock[0] = NOW + timedelta(seconds=seconds)
        renewed = s.ledger.heartbeat(TENANT_ID, ACTOR, claim)
        with pytest.raises(AgentContractError):
            s.ledger.begin_submission(TENANT_ID, ACTOR, claim)
        claim = renewed
    assert rows(s, AgentOperation)[0].lease_until == NOW + timedelta(seconds=120)
    s.clock[0] += timedelta(seconds=1)
    with pytest.raises(AgentContractError):
        s.ledger.heartbeat(TENANT_ID, ACTOR, claim)
    assert s.ledger.recover_expired(TENANT_ID, receipt.operation_id).state == "expired"


@pytest.mark.parametrize(
    "change", ["tenant", "user", "member", "role", "policy", "final", "assignee"]
)
@pytest.mark.parametrize("phase", ["claim", "submit", "publish"])
def test_fresh_authority_blocks_revoked_closed_or_unapproved_scope(setup, change, phase):
    s = setup
    receipt = reserve(s)
    claim = s.ledger.claim(TENANT_ID, ACTOR, receipt.operation_id) if phase != "claim" else None
    permit = s.ledger.begin_submission(TENANT_ID, ACTOR, claim) if phase == "publish" else None
    with Session(s.engine) as db, db.begin():
        if change == "tenant":
            db.get(Tenant, TENANT_ID).active = False
        elif change == "user":
            db.get(AppUser, ACTOR).active = False
        elif change in {"member", "role"}:
            member = db.get(Membership, (TENANT_ID, ACTOR))
            if change == "member":
                member.active = False
            else:
                member.role = "processor"
        elif change == "policy":
            db.add(
                MvpEvent(
                    id=uuid4(),
                    tenant_id=TENANT_ID,
                    actor_id=ACTOR,
                    actor_role="medical_officer",
                    command_id=uuid4(),
                    action="policy_reject",
                    subject_id=str(s.policy_id),
                    fingerprint="0" * 64,
                    payload={},
                )
            )
        else:
            review = db.get(ReviewCase, (TENANT_ID, "REQ-FAKE-0"))
            if change == "final":
                review.state = "APPROVED"
                review.final_payable_inr = 95000
            else:
                review.assignee_id = UUID(PROFILES["processor"][0])
    with pytest.raises(AgentContractError, match="scope_unavailable"):
        if phase == "claim":
            s.ledger.claim(TENANT_ID, ACTOR, receipt.operation_id)
        elif phase == "submit":
            s.ledger.begin_submission(TENANT_ID, ACTOR, claim)
        else:
            s.ledger.publish_fake_result(permit, payload(permit))
    assert not rows(s, AgentComparison)
    assert len(rows(s, AgentAttempt)) == (phase == "publish")
    if phase == "publish":
        s.clock[0] += timedelta(seconds=30)
        assert s.ledger.recover_expired(TENANT_ID, receipt.operation_id).state == "unknown"


def test_amendment_after_submission_cannot_publish_old_comparison_or_repurchase(setup):
    s = setup
    permit = submission(s)
    with Session(s.engine) as db, db.begin():
        case = db.get(SubmittedCase, (TENANT_ID, "REQ-FAKE-0"))
        facts = {**case.inputs, "diagnosis": "Synthetic changed diagnosis"}
        case.inputs = facts
        policy = db.get(PolicyVersion, s.policy_id)
        case.record = calculate(case.request_id, facts, policy.proposal)
        db.add(
            CaseInputRevision(
                tenant_id=TENANT_ID,
                request_id=case.request_id,
                revision=1,
                actor_id=ACTOR,
                inputs=facts,
                digest=fingerprint(facts),
            )
        )
    assert s.ledger.publish_fake_result(permit, payload(permit)).state == "superseded"
    assert not rows(s, AgentComparison)
    assert balance(s) == (1, 0, 0, 10, 0)
    with pytest.raises(AgentContractError, match="allowance_unavailable"):
        reserve(s)


@pytest.mark.parametrize(
    "body", [b"not-json", b"{}", b"x" * 128001], ids=["invalid-json", "missing-fields", "oversized"]
)
def test_rejected_output_is_not_stored_and_never_retried(setup, body, caplog):
    s = setup
    permit = submission(s)
    result = s.ledger.publish_fake_result(permit, body)
    assert result.state == "rejected" and reserve(s) == result
    assert balance(s) == (1, 0, 0, 10, 0)
    assert not rows(s, AgentComparison)
    assert "not-json" not in caplog.text and "x" * 100 not in caplog.text


def concurrent(count, action):
    barrier = Barrier(count)

    def invoke(index):
        barrier.wait(timeout=10)
        try:
            return action(index)
        except AgentContractError as error:
            return str(error)

    with ThreadPoolExecutor(max_workers=count) as pool:
        return list(pool.map(invoke, range(count)))


def test_concurrent_duplicate_enqueue_claim_and_submission_have_one_winner(setup):
    s = setup
    enqueues = concurrent(4, lambda _: reserve(s))
    assert len({r.operation_id for r in enqueues}) == 1
    operation_id = enqueues[0].operation_id
    claims = concurrent(4, lambda _: s.ledger.claim(TENANT_ID, ACTOR, operation_id))
    winners = [r for r in claims if not isinstance(r, str)]
    assert len(winners) == 1
    permits = concurrent(4, lambda _: s.ledger.begin_submission(TENANT_ID, ACTOR, winners[0]))
    winners = [r for r in permits if not isinstance(r, str)]
    assert len(winners) == 1
    fake_calls = [p.submission_id for p in winners]
    assert len(fake_calls) == len(rows(s, AgentAttempt)) == 1
    assert balance(s) == (1, 1, 10, 0, 0)
    results = concurrent(4, lambda _: s.ledger.publish_fake_result(winners[0], payload(winners[0])))
    assert len({r.version for r in results}) == 1
    assert len(rows(s, AgentComparison)) == 1
    assert balance(s) == (1, 0, 0, 10, 0)


@pytest.mark.parametrize("limit", ["concurrency_limit", "case_limit", "unit_limit"])
def test_concurrent_distinct_cases_cannot_oversubscribe_allowance(setup, limit):
    s = setup
    change = {limit: 10 if limit == "unit_limit" else 1}
    if limit == "case_limit":
        change["concurrency_limit"] = 1
    spec = FakeGrantSpec.model_validate({**s.spec.model_dump(), **change})
    s.grant_id = s.ledger.create_fake_grant(TENANT_ID, spec)
    results = concurrent(3, lambda i: reserve(s, i))
    assert len([r for r in results if not isinstance(r, str)]) == 1
    assert balance(s) == (1, 1, 10, 0, 0)


def test_unknown_cost_still_consumes_grant_and_concurrency_allowance(setup):
    s = setup
    spec = FakeGrantSpec.model_validate({**s.spec.model_dump(), "concurrency_limit": 1})
    s.grant_id = s.ledger.create_fake_grant(TENANT_ID, spec)
    permit = submission(s)
    s.clock[0] += timedelta(seconds=30)
    s.ledger.recover_expired(TENANT_ID, permit.operation_id)
    with pytest.raises(AgentContractError, match="allowance_unavailable"):
        reserve(s, 1)
    assert balance(s) == (1, 1, 0, 0, 10)


def test_crash_in_publication_transaction_rolls_back_result_and_accounting(setup):
    s = setup
    permit = submission(s)
    with s.engine.begin() as db:
        db.execute(
            text("""CREATE FUNCTION fake_crash() RETURNS trigger AS $$
BEGIN RAISE EXCEPTION 'fake storage failure'; END; $$ LANGUAGE plpgsql;
CREATE TRIGGER fake_crash BEFORE INSERT ON agent_comparison
FOR EACH ROW EXECUTE FUNCTION fake_crash()""")
        )
    with pytest.raises(DBAPIError):
        s.ledger.publish_fake_result(permit, payload(permit))
    assert not rows(s, AgentComparison)
    assert rows(s, AgentOperation)[0].state == "submitting"
    assert balance(s) == (1, 1, 10, 0, 0)
    # Retrying local publication with the same saved output does not resubmit.
    with s.engine.begin() as db:
        db.execute(text("DROP TRIGGER fake_crash ON agent_comparison"))
    assert s.ledger.publish_fake_result(permit, payload(permit)).state == "published"
    assert len(rows(s, AgentAttempt)) == 1


@pytest.mark.parametrize(
    "table",
    [
        "agent_operation",
        "agent_attempt",
        "agent_execution_grant",
        "agent_comparison",
    ],
)
def test_receipts_cannot_be_deleted_to_enable_replacement_calls(setup, table):
    permit = submission(setup)
    setup.ledger.publish_fake_result(permit, payload(permit))
    with pytest.raises(DBAPIError), setup.engine.begin() as db:
        db.execute(text(f"DELETE FROM {table}"))


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE agent_operation SET state='reserved', version=version+1",
        "UPDATE agent_operation SET operation_key=repeat('c',64), version=version+1",
        "UPDATE agent_operation SET snapshot='{}', version=version+1",
        "UPDATE agent_operation SET deadline=deadline+interval '1 second', version=version+1",
        "UPDATE agent_operation SET version=version+2",
        "UPDATE agent_attempt SET attempt_number=2",
        "UPDATE agent_comparison SET candidate='{}'",
        "UPDATE agent_execution_grant SET unit_limit=100",
        "UPDATE agent_execution_grant SET mode='live'",
        "UPDATE agent_execution_grant SET reserved_units=-1",
        "UPDATE agent_execution_grant SET uncertain_units=100",
    ],
)
def test_database_guards_identity_limits_and_terminal_transitions(setup, statement):
    permit = submission(setup)
    setup.ledger.publish_fake_result(permit, payload(permit))
    with pytest.raises(DBAPIError), setup.engine.begin() as db:
        db.execute(text(statement))


def test_composite_foreign_keys_reject_cross_tenant_receipts_and_wrong_attempt(setup):
    s = setup
    one = submission(s)
    two = submission(s, 1)
    other = uuid4()
    with Session(s.engine) as db, db.begin():
        db.add(Tenant(id=other, name="Other fake tenant"))
    with pytest.raises(DBAPIError), Session(s.engine) as db, db.begin():
        db.add(
            AgentComparison(
                tenant_id=other,
                operation_id=one.operation_id,
                attempt_id=one.attempt_id,
                candidate={},
                published_at=NOW,
            )
        )
    with pytest.raises(DBAPIError), Session(s.engine) as db, db.begin():
        db.add(
            AgentComparison(
                tenant_id=TENANT_ID,
                operation_id=one.operation_id,
                attempt_id=two.attempt_id,
                candidate={},
                published_at=NOW,
            )
        )
    with pytest.raises(AgentContractError):
        s.ledger.claim(other, ACTOR, one.operation_id)
    with pytest.raises(AgentContractError):
        s.ledger.claim(TENANT_ID, UUID(PROFILES["processor"][0]), one.operation_id)


@pytest.mark.parametrize("seconds", [-1, 600])
def test_grant_window_blocks_admission(setup, seconds):
    setup.clock[0] = NOW + timedelta(seconds=seconds)
    with pytest.raises(AgentContractError, match="grant_unavailable"):
        reserve(setup)
    assert balance(setup) == (0, 0, 0, 0, 0)


def test_clock_rollback_and_deadline_boundary_cannot_publish(setup):
    permit = submission(setup)
    for time, error in (
        (NOW - timedelta(seconds=1), "grant_unavailable"),
        (NOW + timedelta(seconds=30), "expired_or_lost_run"),
    ):
        setup.clock[0] = time
        with pytest.raises(AgentContractError, match=error):
            setup.ledger.publish_fake_result(permit, payload(permit))
    assert not rows(setup, AgentComparison)


@pytest.mark.parametrize(
    "field,value",
    [
        ("mode", "live"),
        ("case_limit", True),
        ("concurrency_limit", 0),
        ("units_per_attempt", "10"),
        ("unit_limit", 0),
        ("ends_at", NOW),
    ],
)
def test_fake_grant_cannot_admit_live_or_unbounded_allowance(setup, field, value):
    with pytest.raises(ValidationError):
        FakeGrantSpec.model_validate({**setup.spec.model_dump(), field: value})


def test_all_agent_tables_migrate_and_ledger_remains_unwired(engine):
    with engine.connect() as db:
        tables = set(
            db.scalars(text("SELECT tablename FROM pg_tables WHERE schemaname=current_schema()"))
        )
        assert {
            m.__tablename__
            for m in (
                AgentOperation,
                AgentExecutionGrant,
                AgentAttempt,
                AgentComparison,
            )
        } <= tables
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == "0005_agent_admission"
    package = Path(agent_ledger.__file__).parent
    for name in ("main.py", "jobs.py", "local_worker.py", "reviews.py", "mvp.py"):
        tree = ast.parse((package / name).read_text())
        imports = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        assert not any(n and "agent_ledger" in n for n in imports)
    tree = ast.parse(Path(agent_ledger.__file__).read_text())
    imports = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    assert not any(n and n.startswith(("snowflake", "requests", "httpx")) for n in imports)


def replacement_grant(s, *, config=CONFIG, source=SOURCE):
    snapshots = [s.ledger.capture(TENANT_ID, ACTOR, f"REQ-FAKE-{i}") for i in range(3)]
    spec = FakeGrantSpec.model_validate(
        {
            **s.spec.model_dump(),
            "operation_keys": tuple(operation_key(item, config, source) for item in snapshots),
            "config_digest": config,
            "source_digest": source,
        }
    )
    return s.ledger.create_fake_grant(TENANT_ID, spec)


@pytest.mark.parametrize("field", ["config_digest", "source_digest"])
@pytest.mark.parametrize(
    "phase", ["reserved", "claimed", "submitting", "unknown", "published", "rejected"]
)
def test_changed_mapping_or_configuration_cannot_repurchase_existing_work(setup, phase, field):
    s = setup
    original = reserve(s)
    if phase != "reserved":
        claim = s.ledger.claim(TENANT_ID, ACTOR, original.operation_id)
        if phase != "claimed":
            permit = s.ledger.begin_submission(TENANT_ID, ACTOR, claim)
            if phase in {"published", "rejected"}:
                s.ledger.publish_fake_result(
                    permit, payload(permit) if phase == "published" else b"{}"
                )
            elif phase == "unknown":
                s.clock[0] += timedelta(seconds=30)
                s.ledger.recover_expired(TENANT_ID, original.operation_id)
    before = balance(s)
    attempts = [(row.id, row.submission_id) for row in rows(s, AgentAttempt)]
    comparisons = [row.candidate for row in rows(s, AgentComparison)]
    config = "c" * 64 if field == "config_digest" else CONFIG
    source = "c" * 64 if field == "source_digest" else SOURCE
    grant_id = replacement_grant(s, config=config, source=source)
    with pytest.raises(AgentContractError, match=r"^mapping_replacement_requires_review$"):
        reserve(s, grant_id=grant_id, config_digest=config, source_digest=source)
    assert balance(s) == before
    assert [(row.id, row.submission_id) for row in rows(s, AgentAttempt)] == attempts
    assert [row.candidate for row in rows(s, AgentComparison)] == comparisons
    assert len(rows(s, AgentOperation)) == 1
    with Session(s.engine) as db:
        grant = db.get(AgentExecutionGrant, (TENANT_ID, grant_id))
        assert (grant.admitted, grant.in_flight, grant.reserved_units) == (0, 0, 0)


@pytest.mark.parametrize("field", ["config_digest", "source_digest"])
def test_only_expired_never_submitted_reservation_can_change_mapping(setup, field):
    s = setup
    original = reserve(s)
    s.ledger.claim(TENANT_ID, ACTOR, original.operation_id)
    s.clock[0] += timedelta(seconds=121)
    assert s.ledger.recover_expired(TENANT_ID, original.operation_id).state == "expired"
    config = "c" * 64 if field == "config_digest" else CONFIG
    source = "c" * 64 if field == "source_digest" else SOURCE
    grant_id = replacement_grant(s, config=config, source=source)
    replacement = reserve(s, grant_id=grant_id, config_digest=config, source_digest=source)
    claim = s.ledger.claim(TENANT_ID, ACTOR, replacement.operation_id)
    permit = s.ledger.begin_submission(TENANT_ID, ACTOR, claim)
    assert s.ledger.publish_fake_result(permit, payload(permit)).state == "published"
    assert len(rows(s, AgentAttempt)) == 1
    assert balance(s) == (1, 0, 0, 0, 0)


@pytest.mark.parametrize("phase", ["submitting", "unknown"])
def test_uncertain_execution_cannot_be_relabelled_as_an_input_amendment(setup, phase):
    s = setup
    permit = submission(s)
    if phase == "unknown":
        s.clock[0] += timedelta(seconds=30)
        s.ledger.recover_expired(TENANT_ID, permit.operation_id)
    with Session(s.engine) as db, db.begin():
        case = db.get(SubmittedCase, (TENANT_ID, "REQ-FAKE-0"))
        facts = {**case.inputs, "diagnosis": "Synthetic amendment"}
        case.inputs = facts
        case.record = calculate(case.request_id, facts, db.get(PolicyVersion, s.policy_id).proposal)
        db.add(
            CaseInputRevision(
                tenant_id=TENANT_ID,
                request_id=case.request_id,
                revision=1,
                actor_id=ACTOR,
                inputs=facts,
                digest=fingerprint(facts),
            )
        )
    new_grant = replacement_grant(s)
    with pytest.raises(AgentContractError, match=r"^unresolved_execution$"):
        reserve(s, grant_id=new_grant)
    assert len(rows(s, AgentOperation)) == len(rows(s, AgentAttempt)) == 1
    assert not rows(s, AgentComparison)


def test_concurrent_cross_configuration_reservations_have_one_winner(setup):
    s = setup
    new_grant = replacement_grant(s, config="c" * 64)
    barrier = Barrier(2)

    def admit(config, grant):
        barrier.wait(timeout=10)
        try:
            return reserve(s, grant_id=grant, config_digest=config)
        except AgentContractError as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        one = pool.submit(admit, CONFIG, s.grant_id)
        two = pool.submit(admit, "c" * 64, new_grant)
        results = [one.result(timeout=20), two.result(timeout=20)]
    assert results.count("mapping_replacement_requires_review") == 1
    winner = next(result for result in results if not isinstance(result, str))
    claim = s.ledger.claim(TENANT_ID, ACTOR, winner.operation_id)
    s.ledger.begin_submission(TENANT_ID, ACTOR, claim)
    assert len(rows(s, AgentOperation)) == len(rows(s, AgentAttempt)) == 1
    assert sum(grant.admitted for grant in rows(s, AgentExecutionGrant)) == 1


def test_submission_rechecks_old_cross_mapping_reservations_without_writing_checkpoint(setup):
    s = setup
    first = reserve(s)
    new_grant = replacement_grant(s, source="c" * 64)
    # Simulate an old database containing reservations admitted by the previous
    # implementation. SQL guards preserve both; the new permit boundary must
    # fail closed rather than assuming reserve() was the only possible writer.
    with Session(s.engine) as db, db.begin():
        db.add(
            AgentOperation(
                tenant_id=TENANT_ID,
                id=uuid4(),
                request_id="REQ-FAKE-0",
                actor_id=ACTOR,
                grant_id=new_grant,
                operation_key=operation_key(s.snapshots[0], CONFIG, "c" * 64),
                config_digest=CONFIG,
                source_digest="c" * 64,
                snapshot=s.snapshots[0].model_dump(mode="json"),
                state="reserved",
                version=0,
                created_at=NOW,
                deadline=NOW + timedelta(seconds=120),
            )
        )
        grant = db.get(AgentExecutionGrant, (TENANT_ID, new_grant))
        grant.admitted = grant.in_flight = 1
        grant.reserved_units = 10
    claim = s.ledger.claim(TENANT_ID, ACTOR, first.operation_id)
    with pytest.raises(AgentContractError, match=r"^mapping_replacement_requires_review$"):
        s.ledger.begin_submission(TENANT_ID, ACTOR, claim)
    assert not rows(s, AgentAttempt)
    assert not rows(s, AgentComparison)
    assert all(row.state == "reserved" for row in rows(s, AgentOperation))
