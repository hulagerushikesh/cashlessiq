"""Opt-in, destructive tests against a dedicated GitHub service database only.

Never accepts a caller DSN. Local collection skips before importing psycopg.
This verifies real SQL semantics, not the Mac image/container or TLS boundary.
"""

import os

import pytest

if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("CIQ_CATALOG_TEST") != "1":
    pytest.skip("Dedicated CI PostgreSQL service required", allow_module_level=True)

import psycopg

from scripts.composition_database import prepare
from scripts.composition_database_catalog import CATALOG_SQL
from tests.test_composition_database import plan

DSN = "host=127.0.0.1 port=5432 user=postgres password=ciq-disposable-catalog connect_timeout=3"


@pytest.fixture
def database():
    with psycopg.connect(DSN, autocommit=True) as admin:
        admin.execute("CREATE DATABASE synthetic TEMPLATE template0")
        try:
            with psycopg.connect(DSN + " dbname=synthetic", autocommit=True) as conn:
                conn.execute("SET password_encryption = 'scram-sha-256'")
                conn.execute(prepare(plan()).server["bootstrap.sql"].decode())
                yield conn
        finally:
            admin.execute("DROP DATABASE synthetic WITH (FORCE)")
            admin.execute("DROP ROLE IF EXISTS membership_test")


def test_exact_bootstrap_catalog_passes(database):
    database.execute(CATALOG_SQL.decode())


@pytest.mark.parametrize(
    "mutation",
    [
        "ALTER ROLE membership_test SUPERUSER",
        "ALTER ROLE membership_test CREATEDB",
        "ALTER ROLE membership_test CREATEROLE",
        "ALTER ROLE membership_test INHERIT",
        "ALTER ROLE membership_test REPLICATION",
        "ALTER ROLE membership_test BYPASSRLS",
        "ALTER ROLE membership_test NOLOGIN",
        "ALTER ROLE membership_test PASSWORD NULL",
        "GRANT pg_read_all_data TO membership_test",
        "GRANT CREATE ON DATABASE synthetic TO membership_test",
        "GRANT TEMPORARY ON DATABASE synthetic TO PUBLIC",
        "REVOKE CONNECT ON DATABASE synthetic FROM membership_test",
        "GRANT CREATE ON SCHEMA ops TO membership_test",
        "REVOKE USAGE ON SCHEMA ops FROM membership_test",
        "GRANT USAGE ON SCHEMA public TO PUBLIC",
        "GRANT SELECT ON ops.tenant TO membership_test",
        "GRANT DELETE ON ops.app_user TO PUBLIC",
        "GRANT UPDATE(active) ON ops.tenant TO membership_test",
        "GRANT SELECT(id) ON ops.tenant TO membership_test WITH GRANT OPTION",
        "REVOKE SELECT(id) ON ops.tenant FROM membership_test",
        "ALTER TABLE ops.tenant ADD COLUMN unexpected text",
        "ALTER TABLE ops.tenant ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE ops.tenant OWNER TO membership_test",
        "CREATE TABLE ops.unexpected(id int)",
    ],
)
def test_privilege_or_schema_drift_denied(database, mutation):
    database.execute(mutation)
    with pytest.raises(psycopg.Error):
        database.execute(CATALOG_SQL.decode())
    database.execute("ROLLBACK")
