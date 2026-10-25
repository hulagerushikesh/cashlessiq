"""Explicit test image only: synthetic restricted-principal DB acceptance."""

import json
import os
import sys
from pathlib import Path
from uuid import UUID

from ciq_api.worker_authority import WorkerDenied
from ciq_api.worker_membership_store import RestrictedMembershipStore
from ciq_membership_runtime.connection import (
    MembershipConnectionFactory,
    MembershipDatabaseConfig,
)
from sqlalchemy import URL, create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool

TENANT = UUID("10000000-0000-0000-0000-000000000001")
USER = "20000000-0000-0000-0000-000000000001"


def fixed_factory(*, hostname=None):
    """Test-only credential injection into the actual inactive candidate."""
    config = json.loads(Path("/run/ciq/db.json").read_text())
    address = config.pop("query")["hostaddr"]
    return MembershipConnectionFactory(
        MembershipDatabaseConfig(
            **(config | {"host": hostname or config["host"]}),
            hostaddr=address,
            ca_file="/run/ciq/db-ca.pem",
        )
    )


def factory_tls_check(action):
    """Actual factory over disposable TLS; no raw driver errors may escape."""
    factory = fixed_factory(
        hostname="wrong-membership-db.test" if action == "tls-hostname" else None
    )
    try:
        if action == "factory-ambient":
            for name, value in (("PGSSLMODE", "disable"), ("PGSERVICE", "untrusted")):
                os.environ[name] = value
                try:
                    with factory.connect():
                        pass
                except WorkerDenied as error:
                    assert str(error) == "Worker access denied"
                else:
                    raise AssertionError("Ambient libpq setting was accepted")
                finally:
                    del os.environ[name]
            action = "tls-check"  # Same factory succeeds after contamination is removed.
        if action == "tls-check":
            with factory.connect() as connection:
                row = connection.execute(
                    text("SELECT ssl,version FROM pg_stat_ssl WHERE pid=pg_backend_pid()")
                ).one()
                schemas = connection.scalar(text("SELECT current_schemas(false)"))
            # Assert outside the redacting context so a probe assertion is not
            # mistaken for a connection denial. No raw connection data emitted.
            assert row.ssl is True and row.version == "TLSv1.3"
            assert schemas == []
            print("PASS: fixed factory uses verified TLS 1.3 and empty search path")
            return
        try:
            with factory.connect():
                pass
        except WorkerDenied as error:
            assert str(error) == "Worker access denied"
        else:
            raise AssertionError("Bad TLS configuration connected")
        store = RestrictedMembershipStore(factory.connect, schema="ops")
        try:
            store.lookup(USER, TENANT)
        except WorkerDenied:
            pass
        else:
            raise AssertionError("Factory failure became absent membership")
        print(f"PASS: fixed factory {action} denies without fallback")
    finally:
        factory.close()


def test_engine(*, verified_tls=False, hostname=None):
    """Explicit test factory only; fixed verify-full policy in the TLS variant."""
    config = json.loads(Path("/run/ciq/db.json").read_text())
    if hostname is not None:
        assert verified_tls
        config["host"] = hostname  # Explicit hostname-negative test only.
    options = {"connect_timeout": 2, "sslmode": "disable"}
    if verified_tls:
        options.update(
            sslmode="verify-full",
            sslrootcert="/run/ciq/db-ca.pem",
            ssl_min_protocol_version="TLSv1.3",
            gssencmode="disable",
        )
    return create_engine(
        URL.create("postgresql+psycopg", **config),
        poolclass=NullPool,
        connect_args=options,
        hide_parameters=True,
    )


def tls_check(action):
    """Check actual libpq verification errors without emitting connection details."""
    engine = test_engine(
        verified_tls=True,
        hostname="wrong-membership-db.test" if action == "tls-hostname" else None,
    )
    try:
        if action == "tls-check":
            with engine.connect() as connection:
                row = connection.execute(
                    text("SELECT ssl,version FROM pg_stat_ssl WHERE pid=pg_backend_pid()")
                ).one()
                assert row.ssl is True and row.version == "TLSv1.3"
            print("PASS: restricted DB session uses verified TLS 1.3")
            return
        expected = {
            "tls-hostname": "does not match host name",
            "tls-ca": "certificate verify failed",
            "tls-missing-ca": "does not exist",
        }[action]
        try:
            with engine.connect():
                pass
        except DBAPIError as error:
            assert expected in str(error.orig), "Expected precise TLS verification failure"
        else:
            raise AssertionError("Bad TLS configuration connected")
        store = RestrictedMembershipStore(engine.connect, schema="ops")
        try:
            store.lookup(
                "00000000-0000-4000-8000-000000000111", UUID("00000000-0000-4000-8000-000000000101")
            )
        except WorkerDenied:
            pass
        else:
            raise AssertionError("TLS failure became membership absence or fallback")
        print(f"PASS: {action} fails verification and canonical membership denies")
    finally:
        engine.dispose()


def plaintext_denied():
    import psycopg

    config = json.loads(Path("/run/ciq/db.json").read_text())
    config["user"] = config.pop("username")
    config["dbname"] = config.pop("database")
    config.update(config.pop("query"))
    try:
        with psycopg.connect(**config, sslmode="disable", gssencmode="disable", connect_timeout=2):
            pass
    except psycopg.Error as error:
        # libpq may omit SQLSTATE for connection-establishment failures.
        assert error.sqlstate in {None, "28000"}
        assert "pg_hba.conf rejects connection" in str(error) and "no encryption" in str(error)
        print("PASS: database rejects explicit plaintext connection")
    else:
        raise AssertionError("Database allowed plaintext")


def main(action):
    engine = test_engine()
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
    action = sys.argv[1]
    if action == "plaintext-denied":
        plaintext_denied()
    elif action.startswith("tls-"):
        tls_check(action)
        factory_tls_check(action)
    elif action == "factory-ambient":
        factory_tls_check(action)
    else:
        main(action)
