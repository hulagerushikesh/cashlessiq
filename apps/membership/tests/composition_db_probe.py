"""Explicit test target only: fresh composition DB, canonical client and store.

Fictional credentials arrive through bounded stdin, never argv/environment.
Only CA certificates are written, inside the container's private /tmp tmpfs.
Every failure emits one fixed message, without driver errors or private frames.
"""

import json
import os
import sys
import time
from dataclasses import replace
from pathlib import Path
from uuid import UUID

import psycopg
from ciq_api.worker_authority import WorkerDenied
from ciq_api.worker_membership_store import RestrictedMembershipStore
from ciq_membership_runtime.connection import (
    MembershipConnectionFactory,
    MembershipDatabaseConfig,
)
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

CA = "/tmp/db-ca.pem"
WRONG_CA = "/tmp/wrong-ca.pem"
MISSING_CA = "/tmp/missing-ca.pem"


def denied(factory, profiles):
    # The assertion must be OUTSIDE connect(): it redacts all exceptions,
    # including assertions, so raising inside could falsely pass a negative.
    try:
        with factory.connect():
            pass
    except WorkerDenied as error:
        assert str(error) == "Worker access denied"
    else:
        raise AssertionError("Unexpected connection acceptance")
    tenant, user, _ = profiles[0]
    store = RestrictedMembershipStore(factory.connect, schema="ops")
    try:
        store.lookup(user, UUID(tenant))
    except WorkerDenied as error:
        assert str(error) == "Worker access denied"
    else:
        raise AssertionError("Connection failure became membership absence")


def raw_denied(config, expected, *, plaintext=False):
    """Precise libpq reason rules out an unrelated server/network outage."""
    try:
        with psycopg.connect(
            host=config.host,
            hostaddr=config.hostaddr,
            port=config.port,
            dbname=config.database,
            user=config.username,
            password=config.password,
            sslmode="disable" if plaintext else "verify-full",
            sslrootcert=config.ca_file,
            ssl_min_protocol_version="TLSv1.3",
            sslcertmode="disable",
            passfile="/dev/null",
            gssencmode="disable",
            connect_timeout=2,
        ):
            pass
    except psycopg.Error as error:
        assert expected in str(error), "Expected specific connection denial"
    else:
        raise AssertionError("Unexpected driver connection acceptance")


def accepted(factory, profiles):
    with factory.connect() as connection:
        tls = connection.execute(
            text("SELECT ssl,version FROM pg_stat_ssl WHERE pid=pg_backend_pid()")
        ).one()
        schemas = connection.scalar(text("SELECT current_schemas(false)"))
        identity = connection.execute(text("SELECT current_user,current_database()")).one()
        rows = connection.execute(
            text(
                "SELECT m.tenant_id::text,m.user_id::text,m.role "
                "FROM ops.tenant_membership m "
                "JOIN ops.tenant t ON t.id=m.tenant_id "
                "JOIN ops.app_user u ON u.id=m.user_id "
                "WHERE m.active AND t.active AND u.active"
            )
        ).all()
    assert tls.ssl is True and tls.version == "TLSv1.3"
    assert schemas == [] and tuple(identity) == ("membership_test", "synthetic")
    assert sorted(tuple(row) for row in rows) == sorted(tuple(row) for row in profiles)
    store = RestrictedMembershipStore(factory.connect, schema="ops")
    for tenant, user, role in profiles:
        member = store.lookup(user, UUID(tenant))
        assert member is not None and member.tenant_id == UUID(tenant) and member.role == role
        other = next(t for t, _, _ in profiles if t != tenant)
        assert store.lookup(user, UUID(other)) is None


def privileges(factory):
    statements = (
        "INSERT INTO ops.tenant VALUES ('00000000-0000-4000-8000-000000000999', true)",
        "UPDATE ops.tenant SET active=false",
        "DELETE FROM ops.tenant_membership",
        "TRUNCATE ops.app_user",
        "CREATE TABLE ops.unexpected(id int)",
        "CREATE TABLE public.unexpected(id int)",
        "CREATE TEMP TABLE unexpected(id int)",
        "CREATE SCHEMA unexpected",
        "SELECT rolpassword FROM pg_authid",
    )
    for statement in statements:
        # Capture the driver code inside the redacting boundary, assert outside.
        code = None
        with factory.connect() as connection:
            try:
                connection.execute(text(statement))
            except DBAPIError as error:
                code = error.orig.sqlstate
        assert code == "42501", "Expected actual insufficient-privilege denial"
    return len(statements)


def probe(body, *, source_denied=False):
    profiles = body["profiles"]
    assert len(profiles) == 6 and len({p[0] for p in profiles}) == 2
    for path, value in ((CA, body["ca"]), (WRONG_CA, body["wrong_ca"])):
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
        with os.fdopen(fd, "w") as stream:
            stream.write(value)
    assert not Path(MISSING_CA).exists()
    supplied = body["config"].copy()
    address = supplied.pop("query")["hostaddr"]
    config = MembershipDatabaseConfig(**supplied, hostaddr=address, ca_file=CA)
    factory = MembershipConnectionFactory(config)
    try:
        if source_denied:
            raw_denied(config, "pg_hba.conf rejects connection")
            denied(factory, profiles)
            return dict(state="VERIFIED", source_denials=1)
        # Only the initial, read-only connection probe retries, bounded to 5s.
        deadline = time.monotonic() + 5
        while True:
            try:
                with factory.connect() as connection:
                    one = connection.scalar(text("SELECT 1"))
            except WorkerDenied:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.05)
            else:
                assert one == 1
                break
        accepted(factory, profiles)
        count = privileges(factory)
        variants = (
            (replace(config, host="wrong-membership-db.test"), "does not match host name"),
            (replace(config, ca_file=WRONG_CA), "certificate verify failed"),
            (replace(config, ca_file=MISSING_CA), "does not exist"),
            (replace(config, password=config.password + "wrong"), "password authentication failed"),
        )
        for bad, expected in variants:
            raw_denied(bad, expected)
            negative = MembershipConnectionFactory(bad)
            try:
                denied(negative, profiles)
            finally:
                negative.close()
        raw_denied(config, "no encryption", plaintext=True)
        # Ambient libpq configuration cannot override canonical TLS policy.
        for name, value in (("PGSSLMODE", "disable"), ("PGSERVICE", "untrusted")):
            os.environ[name] = value
            try:
                denied(factory, profiles)
            finally:
                del os.environ[name]
        # Same factory and DB remain usable after all negative checks.
        accepted(factory, profiles)
        return dict(
            state="VERIFIED",
            profiles=6,
            cross_tenant_absences=6,
            privilege_denials=count,
            connection_denials=7,
        )
    finally:
        factory.close()


def main():
    try:
        assert len(sys.argv) == 2 and sys.argv[1] in {"membership", "source-denied"}
        body = sys.stdin.buffer.read(65537)
        assert len(body) <= 65536
        result = probe(json.loads(body), source_denied=sys.argv[1] == "source-denied")
        print(json.dumps(result))
        return 0
    except Exception:
        print("Disposable membership database acceptance denied", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
