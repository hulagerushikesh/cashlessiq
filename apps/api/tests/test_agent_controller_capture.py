"""Actual restricted logins, only on the opt-in disposable CI PostgreSQL service.

No local Docker, arbitrary database, real principal or source is contacted.
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

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

from conftest import engine as schema_engine
from psycopg import sql
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from test_agent_ledger import ACTOR
from test_agent_ledger import setup as setup

from ciq_api.agent_contracts import AgentContractError
from ciq_api.agent_controller_capture import ControllerCapture
from ciq_api.models import Membership
from ciq_api.mvp_models import CaseInputRevision, MvpEvent, PolicyVersion, SubmittedCase
from ciq_api.review_models import ReviewCase
from ciq_api.seed import PROFILES, TENANT_ID

EXPECTED = "postgresql+psycopg://postgres:ciq-disposable-agent-ledger@127.0.0.1:5432/postgres"
PACKAGE = Path(__file__).resolve().parents[3] / "deploy/agent-controller/scope-capture.sql"


@pytest.fixture(scope="module")
def controller_database():
    # Verify the exact opted-in dummy service BEFORE any connection or DDL.
    assert os.environ.get("TEST_DATABASE_URL") == EXPECTED
    root = create_engine(EXPECTED, isolation_level="AUTOCOMMIT")
    name = "ciq_controller_" + uuid4().hex[:24]
    with root.connect() as db:
        assert db.scalar(text("SHOW server_version_num"))[:2] == "17"
        db.execute(text(f'CREATE DATABASE "{name}" TEMPLATE template0'))
    url = root.url.set(database=name)
    admin = create_engine(url)
    try:
        with admin.begin() as db:
            # Deliberate NEW disposable DB prerequisites, never a production
            # REVOKE script. Stock PUBLIC TEMP would otherwise permit temp DDL.
            db.execute(text(f'REVOKE ALL ON DATABASE "{name}" FROM PUBLIC'))
            db.execute(text("REVOKE ALL ON SCHEMA public FROM PUBLIC"))
        yield url
    finally:
        admin.dispose()
        with root.connect() as db:
            db.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        root.dispose()


@pytest.fixture
def engine(controller_database, monkeypatch):
    monkeypatch.setenv(
        "TEST_DATABASE_URL", controller_database.render_as_string(hide_password=False)
    )
    yield from schema_engine.__wrapped__()


@pytest.fixture
def scope(setup):
    s = setup
    suffix = uuid4().hex[:24]
    owner, login, capture = (
        "ciq_scope_owner_" + suffix,
        "ciq_scope_login_" + suffix,
        "ciq_agent_capture_" + suffix,
    )
    with s.engine.connect() as db:
        product = db.scalar(text("SELECT current_schema()"))
    package = sql.SQL(PACKAGE.read_text()).format(
        owner=sql.Identifier(owner),
        capture=sql.Identifier(capture),
        product=sql.Identifier(product),
    )
    password = uuid4().hex
    runtime = None
    try:
        with s.engine.begin() as db:
            raw = db.connection.driver_connection
            raw.execute(package)
            raw.execute(
                sql.SQL(
                    "CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE "
                    "NOREPLICATION NOBYPASSRLS PASSWORD {}"
                ).format(sql.Identifier(login), sql.Literal(password))
            )
            raw.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                    sql.Identifier(s.engine.url.database), sql.Identifier(login)
                )
            )
            raw.execute(
                sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
                    sql.Identifier(capture), sql.Identifier(login)
                )
            )
            raw.execute(
                sql.SQL("GRANT EXECUTE ON FUNCTION {}.capture(text) TO {}").format(
                    sql.Identifier(capture), sql.Identifier(login)
                )
            )
            # The migrated product functions are invoker-only trigger functions;
            # record/review all PUBLIC execute grants before future deployment.
            raw.execute(
                sql.SQL("REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA {} FROM PUBLIC").format(
                    sql.Identifier(product)
                )
            )
            now = datetime.now(UTC)
            raw.execute(
                sql.SQL(
                    "INSERT INTO {}.principal SELECT oid, rolname, %s, %s, %s, "
                    "%s, %s, true FROM pg_roles WHERE rolname=%s"
                ).format(sql.Identifier(capture)),
                (TENANT_ID, ACTOR, ["REQ-FAKE-0"], now, now + timedelta(minutes=5), login),
            )
        runtime = create_engine(
            s.engine.url.set(username=login, password=password),
            connect_args={
                "options": "-cstatement_timeout=5000 -cidle_in_transaction_session_timeout=10000"
            },
        )
        yield SimpleNamespace(
            setup=s,
            admin=s.engine,
            runtime=runtime,
            owner=owner,
            login=login,
            capture=capture,
            product=product,
            client=ControllerCapture(runtime, schema=capture),
        )
    finally:
        if runtime:
            runtime.dispose()
        with s.engine.begin() as db:
            raw = db.connection.driver_connection
            raw.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(capture)))
            for role in (login, owner):
                if raw.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,)).fetchone():
                    raw.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(role)))
                    raw.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


def call(scope, request_id="REQ-FAKE-0"):
    with scope.runtime.begin() as db:
        return db.scalar(text(f'SELECT "{scope.capture}".capture(:id)'), {"id": request_id})


def denied(scope, statement):
    with pytest.raises(DBAPIError) as failure, scope.runtime.begin() as db:
        db.execute(text(statement))
    assert failure.value.orig.sqlstate == "42501"


def test_owned_capture_matches_shared_snapshot_and_has_no_regression_examples(scope):
    result = scope.client.capture("REQ-FAKE-0")
    expected = scope.setup.snapshots[0]
    assert result.binding.model_dump(exclude={"correlation_id"}) == expected.binding.model_dump(
        exclude={"correlation_id"}
    )
    assert result.facts_json == expected.facts_json and result.policy_json == expected.policy_json
    projection = call(scope)
    assert "examples" not in projection["policy"]
    assert set(projection["policy"]) == {
        "product_id",
        "version",
        "effective_from",
        "effective_to",
        "wording_document_id",
        "clauses",
        "rules",
    }
    assert "actor_id" not in projection and "record" not in projection
    with Session(scope.admin) as db:
        assert db.get(ReviewCase, (TENANT_ID, "REQ-FAKE-0")).version == 0
        assert db.scalar(text("SELECT count(*) FROM agent_operation")) == 0


@pytest.mark.parametrize(
    "request_id", ["REQ-FAKE-1", "missing", "x' OR true--", "", None, "x" * 121]
)
def test_function_cannot_widen_exact_request_allowlist(scope, request_id):
    with pytest.raises(DBAPIError) as failure:
        call(scope, request_id)
    assert failure.value.orig.sqlstate == "42501"


@pytest.mark.parametrize(
    "mutation",
    [
        "processor",
        "revoked",
        "user",
        "tenant",
        "assigned",
        "final",
        "not_approved",
        "rejected",
        "disabled",
        "future",
        "expired",
        "wrong_tenant",
        "wrong_actor",
        "wrong_oid",
        "wrong_name",
    ],
)
def test_live_scope_denials_before_any_projection(scope, mutation):
    with Session(scope.admin) as db, db.begin():
        from ciq_api.models import AppUser, Tenant

        member = db.get(Membership, (TENANT_ID, ACTOR))
        if mutation == "processor":
            member.role = "processor"
        elif mutation == "revoked":
            member.active = False
        elif mutation == "user":
            db.get(AppUser, ACTOR).active = False
        elif mutation == "tenant":
            db.get(Tenant, TENANT_ID).active = False
        elif mutation == "assigned":
            db.get(ReviewCase, (TENANT_ID, "REQ-FAKE-0")).assignee_id = UUID(
                PROFILES["processor"][0]
            )
        elif mutation == "final":
            db.get(ReviewCase, (TENANT_ID, "REQ-FAKE-0")).state = "APPROVED"
        elif mutation == "not_approved":
            # Immutable audit is not deleted; point at a different subject with no decision.
            policy = db.get(PolicyVersion, scope.setup.policy_id)
            other = uuid4()
            db.add(
                PolicyVersion(
                    id=other,
                    tenant_id=TENANT_ID,
                    product_id=policy.product_id,
                    version="other",
                    author_id=ACTOR,
                    command_id=uuid4(),
                    fingerprint=policy.fingerprint,
                    proposal=policy.proposal,
                )
            )
            db.flush()
            db.get(SubmittedCase, (TENANT_ID, "REQ-FAKE-0")).policy_id = other
        elif mutation == "rejected":
            db.add(
                MvpEvent(
                    id=uuid4(),
                    tenant_id=TENANT_ID,
                    actor_id=ACTOR,
                    actor_role="medical_officer",
                    command_id=uuid4(),
                    action="policy_reject",
                    subject_id=str(scope.setup.policy_id),
                    fingerprint="0" * 64,
                    payload={},
                )
            )
        else:
            column = {
                "disabled": "enabled=false",
                "future": "starts_at=clock_timestamp()+interval '1 hour', "
                "ends_at=clock_timestamp()+interval '2 hours'",
                "expired": "starts_at=clock_timestamp()-interval '2 hours', "
                "ends_at=clock_timestamp()-interval '1 hour'",
                "wrong_oid": "login_oid=0",
                "wrong_name": "login_name='missing'",
                "wrong_actor": f"actor_id='{PROFILES['processor'][0]}'",
                # A valid other tenant/member exists, but it owns no such case.
                "wrong_tenant": "tenant_id=:tenant, actor_id=:actor",
            }[mutation]
            params = {}
            if mutation == "wrong_tenant":
                tenant, actor = uuid4(), uuid4()
                db.add(Tenant(id=tenant, name="Other synthetic"))
                db.add(AppUser(id=actor, issuer="test", subject=str(actor), display_name="Other"))
                db.flush()
                db.add(Membership(tenant_id=tenant, user_id=actor, role="medical_officer"))
                db.flush()
                params = {"tenant": tenant, "actor": actor}
            db.execute(text(f'UPDATE "{scope.capture}".principal SET {column}'), params)
    with pytest.raises(DBAPIError) as failure:
        call(scope)
    assert failure.value.orig.sqlstate == "42501"
    with pytest.raises(AgentContractError, match=r"^scope_unavailable$") as safe:
        scope.client.capture("REQ-FAKE-0")
    assert safe.value.__suppress_context__


@pytest.mark.parametrize(
    "table",
    [
        "tenant",
        "app_user",
        "tenant_membership",
        "submitted_case",
        "policy_version",
        "case_input_revision",
        "review_case",
        "review_comment",
        "review_audit",
        "review_outbox",
        "analytics_event",
        "work_job",
        "document_upload",
        "agent_execution_grant",
        "agent_operation",
        "agent_attempt",
        "agent_comparison",
        "agent_admission_epoch",
    ],
)
def test_no_direct_clinical_or_ledger_reads_writes_or_resets(scope, table):
    for command in (f"SELECT * FROM {table}", f"DELETE FROM {table}", f"TRUNCATE {table}"):
        denied(scope, f'SET LOCAL search_path="{scope.product}"; {command}')


@pytest.mark.parametrize(
    "statement",
    [
        "CREATE TABLE public.unexpected(id int)",
        "CREATE TEMP TABLE unexpected(id int)",
        "CREATE SCHEMA unexpected",
        "CREATE ROLE unexpected",
        "SET ROLE postgres",
        "SET SESSION AUTHORIZATION postgres",
        "SELECT rolpassword FROM pg_authid",
    ],
)
def test_no_ddl_admin_or_identity_switch(scope, statement):
    denied(scope, statement)


def test_no_binding_grant_counter_or_receipt_mutation(scope):
    for statement in (
        f'UPDATE "{scope.capture}".principal SET enabled=true',
        f'SELECT * FROM "{scope.capture}".principal',
        f'SET ROLE "{scope.owner}"',
        f'ALTER FUNCTION "{scope.capture}".capture(text) RENAME TO compromised',
        f"CREATE FUNCTION \"{scope.capture}\".unexpected() RETURNS int LANGUAGE SQL AS 'SELECT 1'",
        f'UPDATE "{scope.product}".agent_execution_grant SET admitted=0, consumed_units=0',
        f'UPDATE "{scope.product}".review_case SET final_payable_inr=1',
        f"INSERT INTO \"{scope.product}\".agent_admission_epoch VALUES (1, 'fake-only', "
        f"'{uuid4()}', '{uuid4()}')",
    ):
        denied(scope, statement)


def test_session_gucs_and_search_path_cannot_select_identity(scope):
    with scope.runtime.begin() as db:
        db.execute(
            text(
                "SET LOCAL search_path=pg_temp, public; "
                "SET LOCAL ciq.tenant_id='attacker'; SET LOCAL ciq.actor_id='attacker'"
            )
        )
        result = db.scalar(text(f"SELECT \"{scope.capture}\".capture('REQ-FAKE-0')"))
        assert result["tenant_id"] == str(TENANT_ID)
        with pytest.raises(DBAPIError):
            db.scalar(text(f"SELECT \"{scope.capture}\".capture('REQ-FAKE-1')"))


def test_public_has_no_execute_and_unbound_real_login_is_denied(scope):
    with scope.admin.begin() as db:
        raw = db.connection.driver_connection
        raw.execute(sql.SQL("DELETE FROM {}.principal").format(sql.Identifier(scope.capture)))
    with pytest.raises(DBAPIError) as failure:
        call(scope)
    assert failure.value.orig.sqlstate == "42501"


def test_null_allowlist_entry_does_not_turn_unknown_request_into_permission(scope):
    with scope.admin.begin() as db:
        db.execute(text(f'UPDATE "{scope.capture}".principal SET request_ids=ARRAY[NULL]::text[]'))
    with pytest.raises(DBAPIError) as failure:
        call(scope)
    assert failure.value.orig.sqlstate == "42501"


def test_role_switch_does_not_borrow_another_bound_session_identity(scope):
    alternate = "ciq_unbound_" + uuid4().hex[:24]
    runtime = None
    password = uuid4().hex
    try:
        with scope.admin.begin() as db:
            raw = db.connection.driver_connection
            raw.execute(
                sql.SQL("CREATE ROLE {} LOGIN NOINHERIT PASSWORD {}").format(
                    sql.Identifier(alternate), sql.Literal(password)
                )
            )
            raw.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                    sql.Identifier(scope.admin.url.database), sql.Identifier(alternate)
                )
            )
            # A deliberately unsafe membership is injected only in this denial
            # test: even SET ROLE to the bound login cannot replace session_user.
            raw.execute(
                sql.SQL("GRANT {} TO {}").format(
                    sql.Identifier(scope.login), sql.Identifier(alternate)
                )
            )
        runtime = create_engine(scope.admin.url.set(username=alternate, password=password))
        with pytest.raises(DBAPIError) as failure, runtime.begin() as db:
            db.execute(text(f'SET ROLE "{scope.login}"'))
            db.scalar(text(f"SELECT \"{scope.capture}\".capture('REQ-FAKE-0')"))
        assert failure.value.orig.sqlstate == "42501"
    finally:
        if runtime:
            runtime.dispose()
        with scope.admin.begin() as db:
            raw = db.connection.driver_connection
            raw.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(alternate)))
            raw.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(alternate)))


def test_catalog_records_effective_runtime_and_definer_privileges(scope):
    with scope.admin.connect() as db:
        raw = db.connection.driver_connection
        role = raw.execute(
            "SELECT rolcanlogin, rolinherit, rolsuper, rolcreatedb, rolcreaterole, "
            "rolreplication, rolbypassrls FROM pg_roles WHERE rolname=%s",
            (scope.login,),
        ).fetchone()
        assert role == (True, False, False, False, False, False, False)
        assert raw.execute(
            "SELECT count(*) FROM pg_auth_members WHERE member="
            "(SELECT oid FROM pg_roles WHERE rolname=%s)",
            (scope.login,),
        ).fetchone() == (0,)
        # Effective ACL checks include PUBLIC, column grants and inherited roles.
        rows = raw.execute(
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname IN (%s,%s) AND c.relkind IN ('r','p','v','m') AND "
            "(has_table_privilege(%s,c.oid,"
            "'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN') "
            "OR has_any_column_privilege(%s,c.oid,'SELECT,INSERT,UPDATE,REFERENCES'))",
            (scope.product, scope.capture, scope.login, scope.login),
        ).fetchall()
        assert rows == []
        assert raw.execute(
            "SELECT count(*) FROM pg_namespace WHERE nspowner="
            "(SELECT oid FROM pg_roles WHERE rolname=%s)",
            (scope.login,),
        ).fetchone() == (0,)
        fn = raw.execute(
            "SELECT p.prosecdef, p.proconfig, r.rolname FROM pg_proc p "
            "JOIN pg_namespace n ON n.oid=p.pronamespace JOIN pg_roles r ON r.oid=p.proowner "
            "WHERE n.nspname=%s",
            (scope.capture,),
        ).fetchall()
        assert fn == [
            (
                True,
                ["search_path=pg_catalog, pg_temp", "row_security=on", "lock_timeout=2s"],
                scope.owner,
            )
        ]
        assert raw.execute(
            "SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace, "
            "LATERAL aclexplode(p.proacl) a WHERE n.nspname=%s AND a.grantee=0",
            (scope.capture,),
        ).fetchone() == (0,)
        # Definer owns only this capability schema and cannot login or administer.
        assert (
            raw.execute(
                "SELECT rolcanlogin, rolsuper, rolcreaterole, rolbypassrls "
                "FROM pg_roles WHERE rolname=%s",
                (scope.owner,),
            ).fetchone()
            == (False,) * 4
        )
        assert raw.execute(
            "SELECT has_table_privilege(%s,%s,'UPDATE')",
            (scope.owner, f"{scope.product}.review_case"),
        ).fetchone() == (False,)


@pytest.mark.parametrize("fault", ["facts", "revision", "record", "rules"])
def test_shared_python_validation_rejects_corrupt_owned_projection(scope, fault):
    with Session(scope.admin) as db, db.begin():
        case = db.get(SubmittedCase, (TENANT_ID, "REQ-FAKE-0"))
        if fault == "facts":
            case.inputs = {**case.inputs, "member_reference": "changed"}
        elif fault == "revision":
            db.add(
                CaseInputRevision(
                    tenant_id=TENANT_ID,
                    request_id="REQ-FAKE-0",
                    revision=1,
                    actor_id=ACTOR,
                    inputs={**case.inputs, "member_reference": "changed"},
                    digest="0" * 64,
                )
            )
        elif fault == "record":
            case.record = {**case.record, "input_digest": "0" * 64}
        else:
            case.record = {**case.record, "rules_digest": "0" * 64}
    with pytest.raises(AgentContractError, match=r"^scope_unavailable$") as failure:
        scope.client.capture("REQ-FAKE-0")
    assert failure.value.__suppress_context__


def test_capture_locks_scope_until_validation_transaction_finishes(scope):
    with scope.runtime.begin() as db, ThreadPoolExecutor(max_workers=1) as pool:
        db.scalar(text(f"SELECT \"{scope.capture}\".capture('REQ-FAKE-0')"))

        def revoke():
            with scope.admin.begin() as admin:
                admin.execute(text("SET LOCAL lock_timeout='250ms'"))
                admin.execute(
                    text(
                        "UPDATE tenant_membership SET active=false WHERE tenant_id=:t "
                        "AND user_id=:a"
                    ),
                    {"t": TENANT_ID, "a": ACTOR},
                )

        with pytest.raises(DBAPIError) as failure:
            pool.submit(revoke).result(timeout=3)
        assert failure.value.orig.sqlstate == "55P03"
    with scope.admin.begin() as db:
        db.execute(
            text("UPDATE tenant_membership SET active=false WHERE tenant_id=:t AND user_id=:a"),
            {"t": TENANT_ID, "a": ACTOR},
        )
    with pytest.raises(AgentContractError):
        scope.client.capture("REQ-FAKE-0")


def test_window_is_rechecked_after_waiting_for_clinical_lock(scope):
    with scope.admin.begin() as admin:
        admin.execute(
            text(
                f'UPDATE "{scope.capture}".principal SET '
                "starts_at=clock_timestamp()-interval '1 second', "
                "ends_at=clock_timestamp()+interval '400 milliseconds'"
            )
        )
    with scope.admin.begin() as admin, ThreadPoolExecutor(max_workers=1) as pool:
        admin.execute(text("SELECT id FROM tenant WHERE id=:t FOR UPDATE"), {"t": TENANT_ID})
        future = pool.submit(call, scope)
        time.sleep(0.65)
        admin.commit()
        with pytest.raises(DBAPIError) as failure:
            future.result(timeout=4)
        assert failure.value.orig.sqlstate == "42501"
