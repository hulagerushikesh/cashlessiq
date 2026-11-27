"""Actual protected single-call PostgreSQL commands, disposable opted-in CI only.

Provider work remains synthetic through actual local sockets/retained SQLite.
This does NOT install a runtime, contact Snowflake, use credentials or spend.
"""

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
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace
from uuid import uuid4

from psycopg import sql
from single_call_fixtures import call_material
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from test_agent_controller_capture import controller_database as controller_database
from test_agent_controller_capture import engine as engine
from test_agent_controller_capture import scope as scope
from test_agent_controller_capture import setup as setup
from test_agent_ledger import ACTOR
from test_agent_single_call_custody import assembly as assembly

from ciq_api import agent_single_call_custody as assembly_module
from ciq_api import agent_single_call_product as product
from ciq_api.agent_contracts import AgentContext, AgentContractError, canonical_json
from ciq_api.agent_provider_peer import ReviewedProviderPeerClient
from ciq_api.agent_single_call_peer import SingleCallReceiptClient
from ciq_api.agent_single_call_results import single_call_result
from ciq_api.models import Membership
from ciq_api.mvp_models import CaseInputRevision, MvpEvent, SubmittedCase
from ciq_api.review_models import ReviewCase
from ciq_api.seed import TENANT_ID

PACKAGE = Path(__file__).resolve().parents[3] / "deploy/agent-controller/single-call.sql"
SIGNATURES = ("checkpoint(uuid)", "publication_context(uuid)", "publish(uuid,jsonb,jsonb)")


@pytest.fixture
def single_call_material(scope):
    return call_material(snapshot=scope.client.capture("REQ-FAKE-0"))


@pytest.fixture
def installed(scope, single_call_material):
    s = scope
    snapshot, config, pin, _ = single_call_material
    suffix, password = uuid4().hex[:24], uuid4().hex
    owner, login, schema = (
        "ciq_call_owner_" + suffix, "ciq_call_login_" + suffix, "ciq_agent_single_call_" + suffix,
    )
    runtime = None
    try:
        with s.admin.begin() as db:
            raw = db.connection.driver_connection
            raw.execute(sql.SQL(PACKAGE.read_text()).format(
                owner=sql.Identifier(owner), calls=sql.Identifier(schema),
                capture=sql.Identifier(s.capture), product=sql.Identifier(s.product),
            ))
            raw.execute(sql.SQL(
                "CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE "
                "NOREPLICATION NOBYPASSRLS PASSWORD {}"
            ).format(sql.Identifier(login), sql.Literal(password)))
            raw.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(s.admin.url.database), sql.Identifier(login),
            ))
            raw.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
                sql.Identifier(schema), sql.Identifier(login),
            ))
            for signature in SIGNATURES:
                raw.execute(sql.SQL("GRANT EXECUTE ON FUNCTION {}.{} TO {}").format(
                    sql.Identifier(schema), sql.SQL(signature), sql.Identifier(login),
                ))
            raw.execute(sql.SQL(
                "INSERT INTO {}.installation(slot,database_oid,database_name,database_id,epoch_id) "
                "SELECT 1,oid,datname,%s,%s FROM pg_database WHERE datname=current_database()"
            ).format(sql.Identifier(schema)), (pin.database_id, pin.epoch_id))
            raw.execute(sql.SQL(
                "INSERT INTO {}.authorization(slot,operation_id,custody_oid,custody_name,"
                "clinical_oid,clinical_name,tenant_id,actor_id,request_id,"
                "pin,pin_sha256,snapshot,config) "
                "SELECT 1,%s,r.oid,r.rolname,c.oid,c.rolname,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb "
                "FROM pg_roles r,pg_roles c WHERE r.rolname=%s AND c.rolname=%s"
            ).format(sql.Identifier(schema)), (
                pin.operation_id, TENANT_ID, ACTOR, snapshot.binding.request_id, pin.canonical(),
                hashlib.sha256(pin.canonical().encode()).hexdigest(),
                canonical_json(snapshot.model_dump(mode="json")),
                canonical_json(config.model_dump(mode="json")), login, s.login,
            ))
        runtime = create_engine(s.admin.url.set(username=login, password=password), connect_args={
            "options": "-cstatement_timeout=5000 -cidle_in_transaction_session_timeout=10000",
        })
        yield SimpleNamespace(scope=s, admin=s.admin, runtime=runtime, schema=schema, owner=owner,
                              login=login, snapshot=snapshot, pin=pin)
    finally:
        if runtime is not None:
            runtime.dispose()
        with s.admin.begin() as db:
            raw = db.connection.driver_connection
            raw.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))
            for role in (login, owner):
                if raw.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,)).fetchone():
                    raw.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(role)))
                    raw.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


@pytest.fixture
def ready(installed):
    s = installed
    with s.admin.begin() as db:
        db.execute(text(f'UPDATE "{s.schema}".installation SET enabled=true'))
        db.execute(text(f'UPDATE "{s.schema}".authorization SET enabled=true'))
    return s


def invoke(s, name="checkpoint", *, db=None):
    statement = text(f'SELECT "{s.schema}".{name}(:operation)')
    if db is not None:
        return db.scalar(statement, {"operation": s.pin.operation_id})
    with s.runtime.begin() as connection:
        return invoke(s, name, db=connection)


def rows(s):
    with s.admin.connect() as db:
        return db.execute(text(
            f'SELECT phase, (SELECT count(*) FROM "{s.schema}".comparison) '
            f'FROM "{s.schema}".authorization'
        )).one()


def denied(call):
    with pytest.raises(AgentContractError, match=f"^{product.ERROR}$") as failure:
        call()
    assert failure.value.__suppress_context__


def make(s, a):
    return product.ProductSingleCall(s.runtime, schema=s.schema, operation_id=s.pin.operation_id,
        receipt=SingleCallReceiptClient(s.pin),
        provider=ReviewedProviderPeerClient(a.journal.pin_sha256))


@pytest.fixture
def integrated(ready, assembly, monkeypatch):
    s, a = ready, assembly
    # Offline fixture normally supplies a deterministic clock. This acceptance
    # uses real DB/wall/monotonic time across connection, locks and peer calls.
    monkeypatch.setattr(assembly_module, "monotonic", time.monotonic)
    monkeypatch.setattr(assembly_module, "datetime", datetime)
    exchange = ReviewedProviderPeerClient.exchange

    def checked_exchange(client, body, *, timeout):
        assert rows(s) == ("checkpointed", 0)  # Already committed, another connection.
        assert s.runtime.pool.checkedout() == 0  # No clinical connection during I/O.
        return exchange(client, body, timeout=timeout)

    monkeypatch.setattr(ReviewedProviderPeerClient, "exchange", checked_exchange)
    return s, a


def test_default_disabled_package_does_not_authorize_work(installed):
    with pytest.raises(DBAPIError) as failure:
        invoke(installed)
    assert failure.value.orig.sqlstate == "42501"
    assert rows(installed) == ("staged", 0)


@pytest.fixture
def reader(ready):
    s, runtime = ready, None
    name, password = "ciq_advisory_reader_" + uuid4().hex[:24], uuid4().hex
    try:
        with s.admin.begin() as db:
            raw = db.connection.driver_connection
            raw.execute(sql.SQL("CREATE ROLE {} LOGIN NOINHERIT PASSWORD {} ").format(
                sql.Identifier(name), sql.Literal(password),
            ))
            raw.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(s.admin.url.database), sql.Identifier(name),
            ))
            raw.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
                sql.Identifier(s.schema), sql.Identifier(name),
            ))
            raw.execute(sql.SQL("GRANT EXECUTE ON FUNCTION {}.read_advisory(uuid,uuid,text) TO {}")
                        .format(sql.Identifier(s.schema), sql.Identifier(name)))
            raw.execute(sql.SQL("INSERT INTO {}.reader(slot,login_oid,login_name) "
                                "SELECT 1,oid,rolname FROM pg_roles WHERE rolname=%s")
                        .format(sql.Identifier(s.schema)), (name,))
        runtime = create_engine(s.admin.url.set(username=name, password=password))
        yield SimpleNamespace(target=s, runtime=runtime, name=name)
    finally:
        if runtime is not None:
            runtime.dispose()
        with s.admin.begin() as db:
            raw = db.connection.driver_connection
            raw.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(name)))
            raw.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(name)))


def read_advisory(reader, *, actor=ACTOR, tenant=TENANT_ID, request="REQ-FAKE-0"):
    with reader.runtime.begin() as db:
        return db.scalar(text(f'SELECT "{reader.target.schema}".read_advisory('
                              ':tenant,:actor,:request)'),
                         dict(tenant=tenant, actor=actor, request=request))


def enable_reader(reader):
    with reader.target.admin.begin() as db:
        db.execute(text(f'UPDATE "{reader.target.schema}".reader SET enabled=true'))


def test_api_reader_is_separately_default_disabled_and_never_consumes_checkpoint(reader):
    assert read_advisory(reader) is None
    enable_reader(reader)
    row = read_advisory(reader)
    assert row["phase"] == "staged" and row["candidate"] is None
    assert not {"pin", "pin_sha256", "config", "observation", "custody_oid"} & row.keys()
    assert rows(reader.target) == ("staged", 0)


@pytest.mark.parametrize("foreign", ["actor", "tenant", "request"])
def test_reader_arguments_scope_the_private_row(reader, foreign):
    enable_reader(reader)
    params = {foreign: "OTHER" if foreign == "request" else uuid4()}
    assert read_advisory(reader, **params) is None
    assert rows(reader.target) == ("staged", 0)


@pytest.mark.parametrize("change", ["disabled", "inherit", "oid", "name", "installation"])
def test_reader_identity_and_revocation_are_checked_on_every_read(reader, change):
    enable_reader(reader)
    s = reader.target
    with s.admin.begin() as db:
        if change == "disabled":
            db.execute(text(f'UPDATE "{s.schema}".reader SET enabled=false'))
        elif change == "inherit":
            db.connection.driver_connection.execute(sql.SQL("ALTER ROLE {} INHERIT")
                                                   .format(sql.Identifier(reader.name)))
        elif change in {"oid", "name"}:
            column, value = ("login_oid", 1) if change == "oid" else ("login_name", "missing")
            db.execute(text(f'UPDATE "{s.schema}".reader SET {column}=:value'), {"value": value})
        else:
            db.execute(text(f'UPDATE "{s.schema}".installation SET enabled=false'))
    assert read_advisory(reader) is None


def test_reader_has_no_execution_table_or_identity_authority(reader):
    enable_reader(reader)
    s = reader.target
    statements = [
        *(f'SELECT "{s.schema}".{name}(:operation)' for name in
          ("checkpoint", "publication_context")),
        f'SELECT "{s.schema}".publish(:operation,\'{{}}\'::jsonb,\'{{}}\'::jsonb)',
        f'SELECT * FROM "{s.schema}".authorization',
        f'UPDATE "{s.schema}".reader SET enabled=true',
        f'CREATE TABLE "{s.schema}".forbidden(id integer)',
        f'SET ROLE "{s.login}"',
    ]
    for statement in statements:
        with pytest.raises(DBAPIError), reader.runtime.begin() as db:
            db.execute(text(statement), {"operation": s.pin.operation_id})
    with pytest.raises(DBAPIError), s.runtime.begin() as db:
        db.execute(text(f'SELECT "{s.schema}".read_advisory(:tenant,:actor,:request)'),
                   dict(tenant=TENANT_ID, actor=ACTOR, request="REQ-FAKE-0"))
    assert rows(s) == ("staged", 0)


def test_actual_advisory_can_be_read_repeatedly_without_receipt_or_product_mutation(
    reader, integrated,
):
    s, a = integrated
    assert reader.target is s
    enable_reader(reader)
    make(s, a).run()
    before, commands = a.journal.status(), list(a.state["commands"])
    for _ in range(3):
        row = read_advisory(reader)
        current = AgentContext(binding=s.snapshot.binding, tenant_active=True,
                               clinical_authorized=True, policy_approved=True, review_open=True)
        view = single_call_result(row, current, ACTOR)
        assert view.state == "published" and view.comparison.payable_inr == 95000
        assert view.execution_profile == "reviewed-single-call"
        assert a.journal.status() == before and a.state["commands"] == commands
        assert rows(s) == ("published", 1)


def test_restricted_checkpoint_returns_exact_protected_material_once(ready):
    row = invoke(ready)
    projection, pin, _ = product._material(row, ready.pin.operation_id)
    assert pin == ready.pin and projection.snapshot == ready.snapshot
    assert (projection.deadline - projection.checked_at).total_seconds() <= 18
    assert rows(ready) == ("checkpointed", 0)
    with pytest.raises(DBAPIError):
        invoke(ready)


def test_original_adapter_publishes_once_without_human_or_fake_ledger_changes(integrated):
    s, a = integrated
    with s.admin.connect() as db:
        before = [db.scalar(text(f'SELECT count(*) FROM "{table}"')) for table in
                  ("mvp_event", "review_audit", "review_outbox", "analytics_event")]
    run = make(s, a)
    assert run.run() is None
    assert rows(s) == ("published", 1) and len(a.state["calls"]) == 1
    assert a.journal.status().phase == "observed" and a.journal.status().uncertain_units == 20
    with s.admin.connect() as db:
        saved = db.execute(text(f'SELECT candidate,observation FROM "{s.schema}".comparison')).one()
        assert saved.candidate["binding"] == s.snapshot.binding.model_dump(mode="json")
        assert saved.observation["response_sha256"] == a.journal.status().response_sha256
        assert [db.scalar(text(f'SELECT count(*) FROM "{table}"')) for table in
                ("mvp_event", "review_audit", "review_outbox", "analytics_event")] == before
        assert db.scalar(text("SELECT count(*) FROM agent_operation")) == 0
        assert db.scalar(text("SELECT count(*) FROM agent_comparison")) == 0
        assert db.scalar(text("SELECT version FROM review_case WHERE request_id='REQ-FAKE-0'")) == 0
    for action in (run.run, run.dispatch, run.publish, make(s, a).run):
        denied(action)
    assert len(a.state["calls"]) == 1


@pytest.mark.parametrize("change", ["revoke", "final", "revision", "review_version", "disable"])
def test_fresh_publication_denies_changed_clinical_or_owner_authority(integrated, change):
    s, a = integrated
    run = make(s, a)
    run.dispatch()
    with Session(s.admin) as db, db.begin():
        if change == "revoke":
            db.get(Membership, (TENANT_ID, ACTOR)).active = False
        elif change == "final":
            db.get(ReviewCase, (TENANT_ID, "REQ-FAKE-0")).state = "APPROVED"
        elif change == "review_version":
            db.get(ReviewCase, (TENANT_ID, "REQ-FAKE-0")).version += 1
        elif change == "revision":
            facts = db.get(SubmittedCase, (TENANT_ID, "REQ-FAKE-0")).inputs
            db.add(CaseInputRevision(
                tenant_id=TENANT_ID, request_id="REQ-FAKE-0", revision=1,
                actor_id=ACTOR, inputs=facts, digest=s.snapshot.binding.input_digest,
            ))
        else:
            db.execute(text(f'UPDATE "{s.schema}".authorization SET enabled=false'))
    denied(run.publish)
    denied(run.publish)
    assert rows(s) == ("checkpointed", 0) and a.journal.status().phase == "observed"
    assert len(a.state["calls"]) == 1


@pytest.mark.parametrize("fault,phase,calls", [
    ("issue-before", "ready", 0), ("issue-ack", "issued", 0),
    ("provider", "issued", 1), ("observe-ack", "observed", 1),
])
def test_database_checkpoint_does_not_reconstruct_failed_or_ambiguous_peer_work(
    integrated, fault, phase, calls,
):
    s, a = integrated
    a.state["fault"] = fault
    denied(make(s, a).run)
    a.state["fault"] = None
    denied(make(s, a).run)
    assert rows(s) == ("checkpointed", 0) and a.journal.status().phase == phase
    assert len(a.state["calls"]) == calls


@pytest.mark.parametrize("target", ["custody_name", "custody_oid", "clinical_name", "clinical_oid",
                                    "pin", "pin_sha256", "snapshot", "config"])
def test_owner_cannot_rewrite_staged_pins_in_place(ready, target):
    with pytest.raises(DBAPIError) as failure, ready.admin.begin() as db:
        value = {"custody_name": "'missing'", "custody_oid": "0", "clinical_name": "'missing'",
                 "clinical_oid": "0", "pin": "'{}'", "pin_sha256": "repeat('0',64)",
                 "snapshot": "'{}'::jsonb", "config": "'{}'::jsonb"}[target]
        db.execute(text(f'UPDATE "{ready.schema}".authorization SET {target}={value}'))
    assert failure.value.orig.sqlstate == "42501"


@pytest.mark.parametrize("target", ["epoch_id", "database_id", "database_oid", "database_name",
                                    "enabled"])
def test_wrong_or_disabled_installation_denies_before_checkpoint(ready, target):
    with ready.admin.begin() as db:
        value = {"epoch_id": f"'{uuid4()}'", "database_id": f"'{uuid4()}'", "database_oid": "0",
                 "database_name": "'missing'", "enabled": "false"}[target]
        db.execute(text(f'UPDATE "{ready.schema}".installation SET {target}={value}'))
    with pytest.raises(DBAPIError):
        invoke(ready)
    assert rows(ready) == ("staged", 0)


def test_competing_authenticated_checkpoints_have_one_winner(ready):
    barrier = Barrier(2)

    def compete():
        barrier.wait(3)
        try:
            invoke(ready)
            return True
        except DBAPIError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(compete) for _ in range(2)]
        assert sorted(f.result(timeout=6) for f in futures) == [False, True]
    assert rows(ready) == ("checkpointed", 0)


def test_revocation_waits_for_admission_transaction_and_denies_later_publication(ready):
    with ready.runtime.begin() as db, ThreadPoolExecutor(max_workers=1) as pool:
        invoke(ready, db=db)

        def revoke():
            with ready.admin.begin() as admin:
                admin.execute(text("SET LOCAL lock_timeout='150ms'"))
                admin.execute(text(f'UPDATE "{ready.schema}".authorization SET enabled=false'))

        with pytest.raises(DBAPIError) as failure:
            pool.submit(revoke).result(timeout=3)
        assert failure.value.orig.sqlstate == "55P03"
    with ready.admin.begin() as db:
        db.execute(text(f'UPDATE "{ready.schema}".authorization SET enabled=false'))
    with pytest.raises(DBAPIError):
        invoke(ready, "publication_context")


def test_sql_checkpoint_rollback_is_not_an_external_issue(ready):
    with ready.runtime.begin() as db:
        invoke(ready, db=db)
        db.rollback()
    assert rows(ready) == ("staged", 0)
    invoke(ready)
    assert rows(ready) == ("checkpointed", 0)


@pytest.mark.parametrize("phase", ["checkpointed", "published"])
def test_consumed_phases_cannot_have_null_deadline_or_publication_time(ready, phase):
    if phase == "published":
        invoke(ready)
    with pytest.raises(DBAPIError) as failure, ready.admin.begin() as db:
        update = ("phase='checkpointed',checkpoint_at=clock_timestamp(),deadline=NULL"
                  if phase == "checkpointed" else "phase='published',published_at=NULL")
        db.execute(text(f'UPDATE "{ready.schema}".authorization SET {update}'))
    assert failure.value.orig.sqlstate == "23514"


def test_checkpoint_commit_exception_never_reaches_independent_issue(integrated):
    s, a = integrated

    def fail_commit(_db):
        raise OSError("PRIVATE unknown commit")

    event.listen(s.runtime, "commit", fail_commit)
    try:
        denied(make(s, a).dispatch)
    finally:
        event.remove(s.runtime, "commit", fail_commit)
    assert a.journal.status().phase == "ready" and not a.state["commands"]


@pytest.mark.parametrize("change", ["tenant", "user", "member", "processor", "final"])
def test_no_issue_when_current_clinical_authority_is_denied(integrated, change):
    from ciq_api.models import AppUser, Tenant

    s, a = integrated
    with Session(s.admin) as db, db.begin():
        if change == "tenant":
            db.get(Tenant, TENANT_ID).active = False
        elif change == "user":
            db.get(AppUser, ACTOR).active = False
        elif change == "member":
            db.get(Membership, (TENANT_ID, ACTOR)).active = False
        elif change == "processor":
            db.get(Membership, (TENANT_ID, ACTOR)).role = "processor"
        else:
            db.get(ReviewCase, (TENANT_ID, "REQ-FAKE-0")).state = "APPROVED"
    denied(make(s, a).run)
    assert rows(s) == ("staged", 0) and not a.state["commands"]


@pytest.mark.parametrize("change", ["rename", "inherit", "membership"])
def test_changed_custody_role_identity_or_privilege_invalidates_admission(ready, change):
    s = ready
    alternate = "ciq_alternate_" + uuid4().hex[:24]
    renamed, alternate_engine = alternate + "_renamed", None
    try:
        with s.admin.begin() as db:
            raw = db.connection.driver_connection
            raw.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(alternate)))
            if change == "rename":
                raw.execute(sql.SQL("ALTER ROLE {} RENAME TO {}").format(
                    sql.Identifier(s.login), sql.Identifier(renamed),
                ))
            elif change == "inherit":
                raw.execute(sql.SQL("ALTER ROLE {} INHERIT").format(sql.Identifier(s.login)))
            else:
                raw.execute(sql.SQL("GRANT {} TO {}").format(
                    sql.Identifier(alternate), sql.Identifier(s.login),
                ))
        if change == "rename":
            alternate_engine = create_engine(s.runtime.url.set(username=renamed))
            with pytest.raises(DBAPIError), alternate_engine.begin() as db:
                invoke(s, db=db)
        else:
            with pytest.raises(DBAPIError):
                invoke(s)
        assert rows(s) == ("staged", 0)
    finally:
        if alternate_engine is not None:
            alternate_engine.dispose()
        with s.admin.begin() as db:
            raw = db.connection.driver_connection
            if raw.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (renamed,)).fetchone():
                raw.execute(sql.SQL("ALTER ROLE {} RENAME TO {}").format(
                    sql.Identifier(renamed), sql.Identifier(s.login),
                ))
            raw.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(alternate)))
            raw.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(alternate)))


def test_independent_retained_issue_blocks_a_restored_product_checkpoint(integrated):
    s, a = integrated
    make(s, a).dispatch()
    retained = a.journal.status()
    assert retained.phase == "observed" and len(a.state["calls"]) == 1
    # Owned destructive restore simulation in the disposable database ONLY.
    # Actual backups must quarantine admission, never run this reset procedure.
    with s.admin.begin() as db:
        raw = db.connection.driver_connection
        raw.execute(sql.SQL("ALTER TABLE {}.authorization DISABLE TRIGGER USER").format(
            sql.Identifier(s.schema),
        ))
        raw.execute(sql.SQL("UPDATE {}.authorization SET phase='staged',checkpoint_at=NULL,"
                            "deadline=NULL,published_at=NULL").format(sql.Identifier(s.schema)))
        raw.execute(sql.SQL("ALTER TABLE {}.authorization ENABLE TRIGGER USER").format(
            sql.Identifier(s.schema),
        ))
    denied(make(s, a).run)
    assert rows(s) == ("checkpointed", 0) and a.journal.status() == retained
    assert len(a.state["calls"]) == 1


def test_capture_window_is_rechecked_after_waiting_for_clinical_locks(ready):
    s = ready
    with s.admin.begin() as db:
        db.execute(text(f'UPDATE "{s.scope.capture}".principal SET '
                        "starts_at=clock_timestamp()-interval '1 second', "
                        "ends_at=clock_timestamp()+interval '400 milliseconds'"))
    with s.admin.begin() as db, ThreadPoolExecutor(max_workers=1) as pool:
        db.execute(text("SELECT id FROM tenant WHERE id=:tenant FOR UPDATE"), {"tenant": TENANT_ID})
        future = pool.submit(invoke, s)
        time.sleep(0.65)
        db.commit()
        with pytest.raises(DBAPIError):
            future.result(timeout=4)
    assert rows(s) == ("staged", 0)


def test_custody_has_only_three_commands_and_no_table_ddl_or_identity_privileges(ready):
    s = ready
    with s.admin.connect() as db:
        raw = db.connection.driver_connection
        assert raw.execute(
            "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname IN (%s,%s,%s) AND c.relkind IN ('r','p','v','m') AND "
            "(has_table_privilege(%s,c.oid,"
            "'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER') "
            "OR has_any_column_privilege(%s,c.oid,'SELECT,INSERT,UPDATE,REFERENCES'))",
            (s.schema, s.scope.capture, s.scope.product, s.login, s.login),
        ).fetchone() == (0,)
        functions = raw.execute(
            "SELECT p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
            "WHERE n.nspname=%s AND has_function_privilege(%s,p.oid,'EXECUTE') ORDER BY p.proname",
            (s.schema, s.login),
        ).fetchall()
        assert functions == [("checkpoint",), ("publication_context",), ("publish",)]
        assert raw.execute(
            "SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace, "
            "LATERAL aclexplode(p.proacl) a WHERE n.nspname=%s AND a.grantee=0", (s.schema,),
        ).fetchone() == (0,)
    for statement in (
        f'SELECT * FROM "{s.schema}".authorization',
        f'DELETE FROM "{s.schema}".comparison',
        f'TRUNCATE "{s.schema}".authorization',
        f'SELECT "{s.schema}"._context(\'{s.pin.operation_id}\',\'staged\')',
        f'SELECT "{s.scope.capture}"._capture_bound(0,\'REQ-FAKE-0\')',
        f'UPDATE "{s.scope.product}".review_case SET final_payable_inr=1',
        'CREATE TABLE public.unexpected(id int)', 'CREATE TEMP TABLE unexpected(id int)',
        f'SET ROLE "{s.owner}"', f'SET ROLE "{s.scope.login}"',
    ):
        with pytest.raises(DBAPIError) as failure, s.runtime.begin() as db:
            db.execute(text(statement))
        assert failure.value.orig.sqlstate == "42501"


def test_session_gucs_and_role_switch_do_not_select_a_clinical_identity(ready):
    s = ready
    with s.runtime.begin() as db:
        db.execute(text("SET LOCAL ciq.tenant_id='attacker'; SET LOCAL ciq.actor_id='attacker'; "
                        "SET LOCAL search_path=pg_temp,public"))
        assert invoke(s, db=db)["clinical"]["tenant_id"] == str(TENANT_ID)
    with s.scope.runtime.begin() as db, pytest.raises(DBAPIError) as failure:
        invoke(s, "publication_context", db=db)
    assert failure.value.orig.sqlstate == "42501"


def test_invalid_clinical_answer_is_observed_but_not_persisted(integrated):
    s, a = integrated
    response = json.loads(a.state["raw"])
    candidate = json.loads(response["content"][0]["text"])
    candidate["payable_inr"] = 1
    response["content"][0]["text"] = canonical_json(candidate)
    a.state["raw"] = canonical_json(response).encode()
    denied(make(s, a).run)
    assert rows(s) == ("checkpointed", 0) and a.journal.status().phase == "observed"


def test_human_policy_rejection_after_dispatch_blocks_publication(integrated):
    s, a = integrated
    run = make(s, a)
    run.dispatch()
    with Session(s.admin) as db, db.begin():
        db.add(MvpEvent(
            id=uuid4(), tenant_id=TENANT_ID, actor_id=ACTOR, actor_role="medical_officer",
            command_id=uuid4(), action="policy_reject", subject_id=str(s.scope.setup.policy_id),
            fingerprint="0" * 64, payload={},
        ))
    denied(run.publish)
    assert rows(s) == ("checkpointed", 0)
