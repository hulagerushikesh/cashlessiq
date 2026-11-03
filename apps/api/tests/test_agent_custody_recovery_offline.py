"""Recovery control flow with real retained custody, no database/server."""

import copy
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.exc import DBAPIError
from test_agent_receipt_verifier_offline import closed
from test_agent_receipt_verifier_offline import inventory as inventory

from ciq_api.agent_admission import FakeCheckpoint
from ciq_api.agent_custody_recovery import FakeCustodyRecovery


class Engine:
    def __init__(self, raw):
        self.raw = copy.deepcopy(raw)
        self.calls = []
        self.active = False
        self.observe_error = self.write_error = self.commit_error = False

    @contextmanager
    def begin(self):
        self.active = True
        self.calls.append("begin")
        try:
            yield self
            if self.commit_error:
                raise DBAPIError("private commit", {}, ValueError("private"))
            self.calls.append("commit")
        except BaseException:
            self.calls.append("rollback")
            raise
        finally:
            self.active = False

    @contextmanager
    def begin_nested(self):
        assert self.active
        self.calls.append("savepoint")
        try:
            yield
            self.calls.append("release")
        except BaseException:
            self.calls.append("rollback_savepoint")
            raise

    def scalar(self, statement, params=None):
        assert self.active
        if "inventory_fake()" in str(statement):
            assert params is None
            self.calls.append("observe")
            if self.observe_error:
                raise DBAPIError("private observer", {}, ValueError("private"))
            return self.raw
        assert set(params) == {"request", "operation"}
        self.calls.append("verified" if "recover_verified_fake" in str(statement) else "status")
        if self.write_error:
            raise DBAPIError("private recovery", {}, ValueError("private"))


@pytest.fixture
def recovery(inventory):
    s = inventory
    s.engine = Engine(s.raw)
    s.params = {"request_id": "SYN-PRIVATE", "operation_id": s.checkpoint.operation_id}
    # Typed checkpoint UUID is already validated; do not accept strings publicly.
    return SimpleNamespace(**vars(s))


def make(s, **changes):
    return FakeCustodyRecovery(s.engine, s.journal, **{**s.params, **changes})


@pytest.mark.parametrize("phase", ["empty", "prepared", "issued"])
def test_independent_full_history_on_same_transaction_before_verified_command(recovery, phase):
    s = recovery
    if phase == "empty":
        s.engine.raw["entries"] = []
    else:
        s.journal.prepare(s.checkpoint)
        if phase == "issued":
            s.journal.issue(s.checkpoint)
    before = s.journal.path.read_bytes()
    assert make(s).recover() is None
    assert s.engine.calls == ["begin", "savepoint", "observe", "release", "verified", "commit"]
    assert s.journal.path.read_bytes() == before


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "closed",
        "forgotten",
        "missing_local",
        "wrong_epoch",
        "malformed",
        "sql",
    ],
)
def test_unavailable_or_disagreeing_history_only_calls_status_without_journal_repair(
    recovery, fault
):
    s = recovery
    s.journal.prepare(s.checkpoint)
    if fault == "missing":
        s.journal.path.unlink()
    elif fault == "closed":
        s.journal.quarantine()
    elif fault == "forgotten":
        s.journal.prepare(
            FakeCheckpoint(
                tenant_id=uuid4(),
                request_id="OTHER-TENANT",
                operation_id=uuid4(),
                submission_id=uuid4(),
                digest="d" * 64,
            )
        )
    elif fault == "missing_local":
        s.engine.raw["entries"] = []
    elif fault == "wrong_epoch":
        s.engine.raw["epoch"]["epoch_id"] = str(uuid4())
    elif fault == "malformed":
        s.engine.raw["private"] = True
    else:
        s.engine.observe_error = True
    before = s.journal.path.read_bytes() if s.journal.path.exists() else None
    assert make(s).recover() is None
    assert s.engine.calls == [
        "begin",
        "savepoint",
        "observe",
        "rollback_savepoint",
        "status",
        "commit",
    ]
    assert (s.journal.path.read_bytes() if s.journal.path.exists() else None) == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("request_id", ""),
        ("request_id", None),
        ("request_id", "x" * 121),
        ("operation_id", str(uuid4())),
        ("operation_id", None),
        ("schema", "public"),
        ("schema", "ciq_agent_receipts;SELECT 1"),
    ],
)
def test_invalid_trusted_configuration_denies_before_connecting(recovery, field, value):
    closed(lambda: make(recovery, **{field: value}))
    assert not recovery.engine.calls


@pytest.mark.parametrize("verified", [True, False])
@pytest.mark.parametrize("fault", ["write_error", "commit_error"])
def test_safe_errors_no_automatic_retry_or_external_custody_writes(recovery, verified, fault):
    s = recovery
    s.engine.raw["entries"] = []
    s.engine.observe_error = not verified
    setattr(s.engine, fault, True)
    before = s.journal.path.read_bytes()
    closed(make(s).recover)
    assert s.engine.calls.count("begin") == 1 and s.engine.calls[-1] == "rollback"
    assert s.journal.path.read_bytes() == before and not s.engine.active


def test_recovery_has_no_caller_history_flag_or_candidate_parameter(recovery):
    command = make(recovery)
    with pytest.raises(TypeError):
        command.recover(verified=True)
    assert not recovery.engine.calls
