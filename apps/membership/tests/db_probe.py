"""Explicit test image only: synthetic restricted-principal DB acceptance."""

import json
import sys
from pathlib import Path
from uuid import UUID

from ciq_api.worker_authority import WorkerDenied
from ciq_api.worker_membership_store import RestrictedMembershipStore
from sqlalchemy import URL, create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool

TENANT = UUID("10000000-0000-0000-0000-000000000001")
USER = "20000000-0000-0000-0000-000000000001"


def main(action):
    config = json.loads(Path("/run/ciq/db.json").read_text())
    engine = create_engine(
        URL.create("postgresql+psycopg", **config),
        poolclass=NullPool,
        # Ephemeral isolated test DB only; NOT production TLS acceptance.
        connect_args={"connect_timeout": 2, "sslmode": "disable"},
        hide_parameters=True,
    )
    try:
        store = RestrictedMembershipStore(engine.connect, schema="ops")
        if action == "denied":
            try:
                store.lookup(USER, TENANT)
            except WorkerDenied:
                print("PASS: DB outage/privilege failure denies, not missing")
                return
            raise AssertionError("DB failure did not deny")
        if action == "missing":
            assert store.lookup(USER, TENANT) is None
            print("PASS: fresh deactivation returns absent membership")
            return
        expected = "auditor" if action == "downgraded" else "medical_officer"
        assert store.lookup(USER, TENANT).role == expected
        if action == "downgraded":
            print("PASS: fresh role downgrade observed without cached authority")
            return
        assert action == "check"
        assert store.lookup(USER, UUID("10000000-0000-0000-0000-000000000002")) is None
        assert store.lookup("20000000-0000-0000-0000-000000000002", TENANT) is None
        with engine.connect() as connection:
            flags = connection.execute(
                text(
                    "SELECT rolsuper, rolcreaterole, rolcreatedb, rolreplication, rolbypassrls, "
                    "rolinherit FROM pg_roles WHERE rolname=current_user"
                )
            ).one()
            assert not any(flags)
            assert (
                connection.scalar(
                    text(
                        "SELECT count(*) FROM pg_auth_members m JOIN pg_roles r "
                        "ON r.oid=m.member WHERE r.rolname=current_user"
                    )
                )
                == 0
            )
            assert not connection.scalar(
                text(
                    "SELECT has_column_privilege(current_user, 'ops.app_user', 'id', "
                    "'SELECT WITH GRANT OPTION')"
                )
            )
        forbidden = (
            "SELECT * FROM ops.app_user",
            "SELECT issuer FROM ops.app_user",
            "SELECT subject FROM ops.app_user",
            "SELECT display_name FROM ops.app_user",
            "SELECT name FROM ops.tenant",
            "SELECT * FROM ops.private_record",
            "UPDATE ops.tenant_membership SET role='medical_officer'",
            "DELETE FROM ops.tenant_membership",
            "INSERT INTO ops.tenant(id,active,name) VALUES(gen_random_uuid(),true,'bad')",
            "CREATE TABLE ops.bad(id integer)",
            "CREATE TABLE public.bad(id integer)",
            "CREATE SCHEMA bad",
            "CREATE TEMP TABLE bad(id integer)",
            "ALTER TABLE ops.tenant ADD COLUMN bad integer",
            "TRUNCATE ops.tenant_membership",
            "SET ROLE postgres",
            "SELECT ops.private_function()",
            "SELECT secret FROM ops.future_record",
        )
        for statement in forbidden:
            try:
                # Deliberately NOT READ ONLY: prove grants deny independently.
                with engine.connect() as connection, connection.begin():
                    connection.execute(text(statement))
            except DBAPIError as error:
                assert error.orig.sqlstate == "42501", "Expected insufficient_privilege"
            else:
                raise AssertionError("Forbidden DB operation succeeded")
        print(f"PASS: restricted point lookup; {len(forbidden)} independent DB permission denials")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main(sys.argv[1])
