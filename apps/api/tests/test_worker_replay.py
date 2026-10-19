"""Temporary same-host ledger only; no secrets, source, network or startup changes."""

import multiprocessing
import sqlite3
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from ciq_api.source_alpha import SOURCE_TENANTS
from ciq_api.source_scopes import source_alpha_scopes
from ciq_api.worker_authority import (
    Membership,
    SummaryAuthority,
    WorkerDenied,
    issue_summary_assertion,
)
from ciq_api.worker_replay import SqliteReplayLedger


def consume_in_process(path: str) -> bool:
    try:
        SqliteReplayLedger(Path(path)).consume("validator", "same-nonce", 1030, 1000)
        return True
    except (sqlite3.Error, ValueError):
        return False


@pytest.fixture
def ledger_path(tmp_path):
    path = tmp_path / "replay.sqlite3"
    SqliteReplayLedger.initialize_for_offline_test(path)
    return path


def test_restart_retains_consumption(ledger_path):
    SqliteReplayLedger(ledger_path).consume("validator", "nonce", 1030, 1000)
    with pytest.raises(sqlite3.IntegrityError):
        SqliteReplayLedger(ledger_path).consume("validator", "nonce", 1030, 1000)


def test_multiprocess_single_winner(ledger_path):
    with ProcessPoolExecutor(
        max_workers=4, mp_context=multiprocessing.get_context("spawn")
    ) as pool:
        assert sum(pool.map(consume_in_process, [str(ledger_path)] * 8)) == 1


def test_capacity_shared_across_instances_and_expiry_cleanup(ledger_path):
    SqliteReplayLedger(ledger_path, capacity=1).consume("validator", "one", 1030, 1000)
    with pytest.raises(ValueError):
        SqliteReplayLedger(ledger_path, capacity=1).consume("validator", "two", 1030, 1000)
    # A full namespace must not block another fixed authority.
    SqliteReplayLedger(ledger_path, capacity=1).consume("other", "one", 1030, 1000)
    SqliteReplayLedger(ledger_path, capacity=1).consume("validator", "two", 1060, 1030)


def test_initialization_does_not_overwrite(ledger_path):
    with pytest.raises(FileExistsError):
        SqliteReplayLedger.initialize_for_offline_test(ledger_path)


def test_missing_store_is_not_recreated(tmp_path):
    path = tmp_path / "absent.sqlite3"
    with pytest.raises(sqlite3.OperationalError):
        SqliteReplayLedger(path).consume("validator", "one", 1030, 1000)
    assert not path.exists()


def test_expiry_while_consuming_is_denied():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    tenant = SOURCE_TENANTS[0].tenant_id
    member = Membership(tenant, "processor")
    state = {"now": 1000}

    class SlowLedger:
        def consume(self, namespace, nonce, expiry, now):
            state["now"] = expiry

    authority = SummaryAuthority(
        public_key=private.public_key(),
        audience="validator:tpa001",
        tenant_id=tenant,
        scopes=source_alpha_scopes(),
        membership=lambda _: member,
        clock=lambda: state["now"],
        replay=SlowLedger(),
    )
    token = issue_summary_assertion(
        private,
        subject="reviewer",
        membership=member,
        audience="validator:tpa001",
        request_id="GOL001",
        scopes=source_alpha_scopes(),
        now=1000,
    )
    with pytest.raises(WorkerDenied):
        authority.consume(token)


@pytest.mark.parametrize("failure", ["missing", "corrupt", "locked", "full", "restart"])
def test_authority_denies_storage_failures_without_fallback(ledger_path, failure):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    tenant = SOURCE_TENANTS[0].tenant_id
    member = Membership(tenant, "processor")
    arguments = dict(
        public_key=private.public_key(),
        audience="validator:tpa001",
        tenant_id=tenant,
        scopes=source_alpha_scopes(),
        membership=lambda _: member,
        clock=lambda: 1000,
    )
    token = issue_summary_assertion(
        private,
        subject="reviewer",
        membership=member,
        audience="validator:tpa001",
        request_id="GOL001",
        scopes=source_alpha_scopes(),
        now=1000,
    )
    authority = SummaryAuthority(**arguments, replay=SqliteReplayLedger(ledger_path, capacity=1))
    connection = sqlite3.connect(ledger_path)
    try:
        if failure == "missing":
            ledger_path.unlink()
        elif failure == "corrupt":
            connection.execute("DROP TABLE used_assertion")
            connection.commit()
        elif failure == "locked":
            connection.execute("BEGIN IMMEDIATE")
        else:
            authority.consume(token)
            # New authority/connection simulates restart, preserving the same ledger.
            authority = SummaryAuthority(
                **arguments, replay=SqliteReplayLedger(ledger_path, capacity=1)
            )
            if failure == "full":
                token = issue_summary_assertion(
                    private,
                    subject="reviewer",
                    membership=member,
                    audience="validator:tpa001",
                    request_id="GOL001",
                    scopes=source_alpha_scopes(),
                    now=1000,
                )
        with pytest.raises(WorkerDenied, match=r"^Worker access denied$") as error:
            authority.consume(token)
        assert error.value.__suppress_context__
    finally:
        connection.rollback()
        connection.close()
