"""Operator installation/revocation/rotation only in the exact disposable CI DB."""

import os
import sys

import pytest

if (
    sys.platform != "linux"
    or os.environ.get("GITHUB_ACTIONS") != "true"
    or os.environ.get("GITHUB_REPOSITORY") != "hulagerushikesh/cashlessiq"
    or os.environ.get("CIQ_AGENT_CONTROLLER_TEST") != "1"
):
    pytest.skip("Dedicated disposable controller privilege job required", allow_module_level=True)

import hashlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import psycopg
from psycopg import sql
from scripts.agent_controller_lifecycle import (
    CLINICAL,
    CUSTODY,
    InstallationRejected,
    audit,
    command,
    install_empty_fake,
    revoke_fake,
)
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from test_agent_controller_capture import controller_database as controller_database
from test_agent_controller_capture import engine as engine
from test_agent_controller_capture import setup as setup
from test_agent_controller_reservation import stage
from test_agent_custody_dispatch import dispatch
from test_agent_custody_recovery import expire_lease
from test_agent_custody_submission import coordinator, rows
from test_agent_ledger import ACTOR, balance
from test_agent_receipt_verifier import closed

from ciq_api.agent_contracts import AgentContractError
from ciq_api.agent_controller_capture import ControllerCapture
from ciq_api.agent_controller_reservation import ControllerReservation
from ciq_api.agent_custody_recovery import FakeCustodyRecovery
from ciq_api.agent_ledger import FakeGrantSpec
from ciq_api.agent_receipt_verifier import FakeReceiptVerifier
from ciq_api.seed import TENANT_ID


def runtime(s, login, password):
    return create_engine(
        s.admin.url.set(username=login, password=password),
        connect_args={
            "options": "-cstatement_timeout=5000 -cidle_in_transaction_session_timeout=10000",
        },
    )


@pytest.fixture
def factory(setup):
    suffix = uuid4().hex[:24]
    with setup.engine.connect() as db:
        product = db.scalar(text("SELECT current_schema()"))
    s = SimpleNamespace(
        setup=setup,
        admin=setup.engine,
        product=product,
        capture="ciq_agent_capture_" + suffix,
        receipts="ciq_agent_receipts_" + suffix,
        owner="ciq_scope_owner_" + suffix,
        receipt_owner="ciq_receipt_owner_" + suffix,
        login="ciq_scope_login_" + suffix,
        receipt_login="ciq_receipt_login_" + suffix,
        password=uuid4().hex,
        receipt_password=uuid4().hex,
    )
    with s.admin.begin() as db:
        raw = db.connection.driver_connection
        for name, password in ((s.login, s.password), (s.receipt_login, s.receipt_password)):
            raw.execute(
                sql.SQL(
                    "CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE "
                    "NOREPLICATION NOBYPASSRLS PASSWORD {}"
                ).format(sql.Identifier(name), sql.Literal(password))
            )
    s.runtime = runtime(s, s.login, s.password)
    s.observer_runtime = runtime(s, s.receipt_login, s.receipt_password)
    try:
        yield s
    finally:
        s.runtime.dispose()
        s.observer_runtime.dispose()
        with s.admin.begin() as db:
            raw = db.connection.driver_connection
            for schema in (s.receipts, s.capture):
                raw.execute(
                    sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema))
                )
            for role in (s.receipt_login, s.login, s.receipt_owner, s.owner):
                if raw.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,)).fetchone():
                    raw.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(role)))
                    raw.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


def install(s):
    with s.admin.begin() as db:
        db.execute(text("SELECT 1"))  # Start the caller-owned DB transaction.
        return install_empty_fake(
            db.connection.driver_connection,
            product=s.product,
            capture=s.capture,
            receipts=s.receipts,
            clinical=s.login,
            custody=s.receipt_login,
            clinical_definer=s.owner,
            custody_definer=s.receipt_owner,
        )


@pytest.fixture
def installed(factory):
    s = factory
    s.target = install(s)
    return s


def product_digest(s):
    digest = hashlib.sha256()
    with s.admin.connect() as db:
        tables = list(
            db.scalars(
                text("SELECT tablename FROM pg_tables WHERE schemaname=:schema ORDER BY tablename"),
                {"schema": s.product},
            )
        )
        assert len(tables) == 22
        for table in tables:
            digest.update(table.encode())
            raw = db.connection.driver_connection
            for (value,) in raw.execute(
                sql.SQL(
                    "SELECT row_to_json(t)::text FROM {}.{} t "
                    'ORDER BY row_to_json(t)::text COLLATE "C"'
                ).format(sql.Identifier(s.product), sql.Identifier(table))
            ):
                encoded = value.encode()
                digest.update(len(encoded).to_bytes(8, "big"))
                digest.update(encoded)
    return digest.hexdigest()


def review(s, target=None):
    with s.admin.begin() as db:
        db.execute(text("SELECT 1"))
        return audit(db.connection.driver_connection, target or s.target)


def test_forward_install_is_atomic_empty_and_has_only_exact_effective_rights(factory):
    s = factory
    before = product_digest(s)
    s.target = install(s)
    assert review(s) is None
    assert product_digest(s) == before
    for connection_engine, schema, expression in (
        (s.runtime, s.capture, "capture('REQ-FAKE-0')"),
        (s.observer_runtime, s.receipts, "inventory_fake()"),
    ):
        with connection_engine.begin() as db:
            assert db.scalar(text("SELECT session_user=current_user")) is True
        with pytest.raises(DBAPIError) as caught, connection_engine.begin() as db:
            db.execute(text(f'SELECT "{schema}".{expression}'))
        assert caught.value.orig.sqlstate == "42501"
    # A second install never adopts or replaces existing schemas/definers.
    with pytest.raises(InstallationRejected, match="fresh_role"):
        install(s)
    assert review(s) is None and product_digest(s) == before


def test_unreviewed_creator_defaults_abort_entire_install_without_partial_authority(factory):
    s = factory
    with s.admin.begin() as db:
        db.connection.driver_connection.execute(
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES FOR ROLE postgres GRANT SELECT ON TABLES TO {}"
            ).format(sql.Identifier(s.login))
        )
    before = product_digest(s)
    with pytest.raises(InstallationRejected):
        install(s)
    with s.admin.connect() as db:
        assert (
            db.scalar(
                text("SELECT count(*) FROM pg_roles WHERE rolname IN (:a,:b)"),
                {"a": s.owner, "b": s.receipt_owner},
            )
            == 0
        )
        assert (
            db.scalar(
                text("SELECT count(*) FROM pg_namespace WHERE nspname IN (:a,:b)"),
                {"a": s.capture, "b": s.receipts},
            )
            == 0
        )
        assert not db.scalar(
            text("SELECT has_database_privilege(:login,current_database(),'CONNECT')"),
            {"login": s.login},
        )
    assert product_digest(s) == before


@pytest.mark.parametrize(
    "fault",
    [
        "runtime_table",
        "runtime_column",
        "public_table",
        "public_temp",
        "connect_grant",
        "schema_create",
        "schema_grant",
        "private_execute",
        "cross_execute",
        "execute_grant",
        "outside_function",
        "global_default",
        "schema_default",
        "recipient_default",
        "definer_default",
        "private_table",
        "private_function",
        "routine_config",
        "routine_owner",
        "definer_login",
        "definer_member",
        "runtime_member",
        "runtime_grantee",
        "definer_human_column",
        "definer_human_table",
        "custody_clinical_column",
        "runtime_sequence",
        "public_private_helper",
        "private_schema_public",
    ],
)
def test_catalog_review_rejects_effective_and_additive_default_acl_drift(installed, fault):
    s = installed
    with s.admin.begin() as db:
        raw = db.connection.driver_connection
        templates = {
            "runtime_table": "GRANT SELECT ON {product}.submitted_case TO {login}",
            "runtime_column": "GRANT UPDATE(final_payable_inr) ON {product}.review_case TO {login}",
            "public_table": "GRANT SELECT ON {product}.submitted_case TO PUBLIC",
            "public_temp": "GRANT TEMP ON DATABASE {database} TO PUBLIC",
            "connect_grant": "GRANT CONNECT ON DATABASE {database} TO {login} WITH GRANT OPTION",
            "schema_create": "GRANT CREATE ON SCHEMA {product} TO {login}",
            "schema_grant": "GRANT USAGE ON SCHEMA {capture} TO {login} WITH GRANT OPTION",
            "private_execute": "GRANT EXECUTE ON FUNCTION {capture}._capture_bound(oid,text) "
            "TO {login}",
            "cross_execute": "GRANT EXECUTE ON FUNCTION {receipts}.inventory_fake() TO {login}",
            "execute_grant": "GRANT EXECUTE ON FUNCTION {capture}.capture(text) "
            "TO {login} WITH GRANT OPTION",
            "outside_function": "CREATE FUNCTION {product}.unsafe() RETURNS int LANGUAGE sql "
            "AS 'SELECT 1'; GRANT EXECUTE ON FUNCTION {product}.unsafe() TO PUBLIC",
            "global_default": "ALTER DEFAULT PRIVILEGES FOR ROLE postgres "
            "GRANT EXECUTE ON FUNCTIONS TO PUBLIC",
            "schema_default": "ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA {capture} "
            "GRANT EXECUTE ON FUNCTIONS TO PUBLIC",
            "recipient_default": "ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA {product} "
            "GRANT SELECT ON TABLES TO {login}",
            "definer_default": "ALTER DEFAULT PRIVILEGES FOR ROLE {owner} "
            "GRANT EXECUTE ON FUNCTIONS TO PUBLIC",
            "private_table": "GRANT SELECT ON {receipts}.submission_scope TO {login}",
            "private_function": "CREATE FUNCTION {capture}.unexpected() RETURNS int "
            "LANGUAGE sql AS 'SELECT 1'",
            "routine_config": "ALTER FUNCTION {capture}.capture(text) SET search_path=public",
            "routine_owner": "ALTER FUNCTION {capture}.capture(text) OWNER TO postgres",
            "definer_login": "ALTER ROLE {owner} LOGIN",
            "definer_member": "GRANT {owner} TO {receipt_owner}",
            "runtime_member": "GRANT {owner} TO {login}",
            "runtime_grantee": "GRANT {login} TO {receipt_login}",
            "definer_human_column": "GRANT UPDATE(final_payable_inr) ON {product}.review_case "
            "TO {owner}",
            "definer_human_table": "GRANT UPDATE ON {product}.review_case TO {owner}",
            "custody_clinical_column": "GRANT SELECT(inputs) ON {product}.submitted_case "
            "TO {receipt_owner}",
            "runtime_sequence": "CREATE SEQUENCE {product}.unsafe_sequence; "
            "GRANT USAGE ON {product}.unsafe_sequence TO {login}",
            "public_private_helper": "GRANT EXECUTE ON FUNCTION "
            "{receipts}._recover_fake(text,uuid,boolean) TO PUBLIC",
            "private_schema_public": "GRANT USAGE ON SCHEMA {receipts} TO PUBLIC",
        }
        raw.execute(
            sql.SQL(templates[fault]).format(
                **{
                    key: sql.Identifier(getattr(s, key))
                    for key in (
                        "product",
                        "capture",
                        "receipts",
                        "login",
                        "receipt_login",
                        "owner",
                        "receipt_owner",
                    )
                },
                database=sql.Identifier(s.target.database),
            )
        )
    with pytest.raises(InstallationRejected, match=r"^fake_installation_rejected:"):
        review(s)


@pytest.mark.parametrize("fault", ["database_oid", "clinical_oid", "custody_oid"])
def test_catalog_review_requires_exact_database_and_role_identity(installed, fault):
    s = installed
    target = (
        replace(s.target, database_oid=0)
        if fault == "database_oid"
        else replace(
            s.target,
            **{
                fault.removesuffix("_oid"): replace(
                    getattr(s.target, fault.removesuffix("_oid")),
                    oid=0,
                )
            },
        )
    )
    with pytest.raises(InstallationRejected):
        review(s, target)


@pytest.fixture
def active(installed):
    s = installed
    now = datetime.now(UTC)
    s.setup.spec = FakeGrantSpec.model_validate(
        {
            **s.setup.spec.model_dump(),
            "starts_at": now - timedelta(seconds=1),
            "ends_at": now + timedelta(minutes=10),
        }
    )
    s.setup.grant_id = s.setup.ledger.create_fake_grant(TENANT_ID, s.setup.spec)
    with s.admin.begin() as db:
        raw = db.connection.driver_connection
        raw.execute(
            sql.SQL("INSERT INTO {}.principal VALUES (%s,%s,%s,%s,%s,%s,%s,true)").format(
                sql.Identifier(s.capture)
            ),
            (
                s.target.clinical.oid,
                s.login,
                TENANT_ID,
                ACTOR,
                ["REQ-FAKE-0"],
                now,
                now + timedelta(minutes=5),
            ),
        )
        pin = s.setup.admission.journal.pin
        raw.execute(
            sql.SQL("INSERT INTO {}.principal VALUES (%s,%s,%s,%s,%s,%s,true)").format(
                sql.Identifier(s.receipts)
            ),
            (
                s.target.custody.oid,
                s.receipt_login,
                pin.database_id,
                pin.epoch_id,
                now,
                now + timedelta(minutes=5),
            ),
        )
    stage(s, enabled=True)
    s.client = ControllerCapture(s.runtime, schema=s.capture)
    s.commands = ControllerReservation(s.runtime, schema=s.capture)
    s.verifier = FakeReceiptVerifier(
        s.observer_runtime, s.setup.admission.journal, schema=s.receipts
    )
    s.claim = s.commands.claim("REQ-FAKE-0", s.commands.reserve("REQ-FAKE-0"))
    with s.admin.begin() as db:
        db.connection.driver_connection.execute(
            sql.SQL("INSERT INTO {}.submission_scope VALUES (%s,%s,%s,%s,%s,%s,%s,true)").format(
                sql.Identifier(s.receipts)
            ),
            (
                s.target.custody.oid,
                "REQ-FAKE-0",
                s.target.clinical.oid,
                s.login,
                TENANT_ID,
                ACTOR,
                s.claim.operation_id,
            ),
        )
    s.custody = coordinator(s)
    s.recovery = FakeCustodyRecovery(
        s.observer_runtime,
        s.setup.admission.journal,
        schema=s.receipts,
        request_id="REQ-FAKE-0",
        operation_id=s.claim.operation_id,
    )
    return s


def revoke(s, clinical):
    with s.admin.begin() as db:
        db.execute(text("SELECT 1"))
        revoke_fake(db.connection.driver_connection, s.target, clinical=clinical)


@pytest.mark.parametrize("clinical", [True, False])
@pytest.mark.parametrize("phase", ["reserved", "prepared", "issued", "candidate"])
def test_revocation_closes_idle_sessions_and_original_pending_work_without_replay(
    active,
    clinical,
    phase,
    tmp_path,
    monkeypatch,
):
    s = dispatch.__wrapped__(active, tmp_path, monkeypatch)
    if phase != "reserved":
        s.custody.prepare()
    if phase == "issued":
        s.custody.issue()
    if phase == "candidate":
        s.custody.dispatch()
    engine = s.runtime if clinical else s.observer_runtime
    with engine.connect() as old_session:
        identity = old_session.scalar(text("SELECT pg_backend_pid()"))
        old_session.commit()
        before = product_digest(s)
        revoke(s, clinical)
        revoke(s, clinical)  # Repeating revocation never changes accounting.
        assert product_digest(s) == before and balance(s.setup) == (1, 1, 10, 0, 0)
        assert old_session.scalar(text("SELECT pg_backend_pid()")) == identity
        old_session.commit()
        schema, expr = (
            (s.capture, "capture('REQ-FAKE-0')")
            if clinical
            else (
                s.receipts,
                "inventory_fake()",
            )
        )
        with pytest.raises(DBAPIError) as caught:
            old_session.execute(text(f'SELECT "{schema}".{expr}'))
        assert caught.value.orig.sqlstate == "42501"
        old_session.rollback()
        for action in (
            s.custody.prepare,
            s.custody.issue,
            s.custody.dispatch,
            s.custody.publish,
            s.custody.heartbeat,
        ):
            closed(action)
        assert len(s.exchanges) == (phase == "candidate")
        assert product_digest(s) == before
        if clinical:
            assert s.recovery.recover() is None  # Live independent status only.
            if phase != "reserved":
                expire_lease(s)
                assert s.recovery.recover() is None
                assert rows(s)[0].state == "unknown"
                assert balance(s.setup) == (1, 1, 0, 0, 10)
        else:
            closed(s.recovery.recover)
            assert balance(s.setup) == (1, 1, 10, 0, 0)


@pytest.mark.parametrize("clinical", [True, False])
def test_password_rotation_requires_separate_reauthorization_and_does_not_restore_pending_issue(
    active,
    clinical,
):
    s = active
    s.custody.prepare()
    role = s.login if clinical else s.receipt_login
    old_password = s.password if clinical else s.receipt_password
    before = product_digest(s)
    revoke(s, clinical)
    new_password = uuid4().hex
    # Trusted operator secret handling, never a returned/logged runtime argument.
    with s.admin.begin() as db:
        raw = db.connection.driver_connection
        raw.execute(
            sql.SQL("ALTER ROLE {} PASSWORD {}").format(
                sql.Identifier(role), sql.Literal(new_password)
            )
        )
        # Deliberately restore transport/command ACLs, but NEVER a binding. This
        # proves rotation/authentication alone cannot recreate authority/issue.
        raw.execute(sql.SQL("ALTER ROLE {} LOGIN").format(sql.Identifier(role)))
        raw.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(s.target.database), sql.Identifier(role)
            )
        )
        schema = s.capture if clinical else s.receipts
        raw.execute(
            sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
                sql.Identifier(schema), sql.Identifier(role)
            )
        )
        for signature in CLINICAL if clinical else CUSTODY:
            command(raw, "GRANT", schema, signature, role)
    wrong = runtime(s, role, old_password)
    rotated = runtime(s, role, new_password)
    try:
        with pytest.raises(DBAPIError), wrong.connect():
            pytest.fail("Old dummy password accepted")
        with rotated.begin() as db:
            assert (
                db.scalar(
                    text("SELECT session_user=current_user AND current_user=:role"), {"role": role}
                )
                is True
            )
        if clinical:
            with pytest.raises(AgentContractError):
                ControllerCapture(rotated, schema=s.capture).capture("REQ-FAKE-0")
        else:
            closed(FakeReceiptVerifier(rotated, s.setup.admission.journal, schema=s.receipts).check)
        closed(s.custody.issue)
        closed(s.custody.dispatch)
        # A fresh coordinator cannot adopt the old prepared external receipt.
        closed(coordinator(s).prepare)
        closed(coordinator(s).issue)
        assert product_digest(s) == before and balance(s.setup) == (1, 1, 10, 0, 0)
    finally:
        wrong.dispose()
        rotated.dispose()


@pytest.mark.parametrize("clinical", [True, False])
def test_lock_timeout_rolls_back_revocation_and_retry_after_quiescence_closes_it(active, clinical):
    s = active
    before = product_digest(s)
    with s.admin.begin() as blocker:
        blocker.execute(text("SELECT id FROM agent_admission_epoch FOR UPDATE"))
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(revoke, s, clinical)
            with pytest.raises(psycopg.errors.LockNotAvailable) as caught:
                future.result(timeout=8)
        assert caught.value.sqlstate == "55P03"
        with s.admin.connect() as db:
            role = s.target.clinical if clinical else s.target.custody
            assert (
                db.scalar(
                    text("SELECT rolcanlogin FROM pg_roles WHERE oid=:oid"), {"oid": role.oid}
                )
                is True
            )
    assert review(s) is None and product_digest(s) == before
    revoke(s, clinical)
    if clinical:
        with pytest.raises(AgentContractError):
            s.client.capture("REQ-FAKE-0")
        assert s.recovery.recover() is None
    else:
        closed(s.verifier.check)
    assert product_digest(s) == before
