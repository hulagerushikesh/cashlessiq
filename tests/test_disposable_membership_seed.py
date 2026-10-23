"""Synthetic registry and portable INSERT behavior; no PostgreSQL/Docker acceptance."""

import sqlite3
from unittest.mock import Mock

from apps.api.src.ciq_api.source_alpha import SOURCE_TENANTS
from scripts.disposable_membership_db import SOURCE_PROFILES, DisposableMembershipDB


def test_disposable_profile_registry_matches_canonical_source_identities():
    expected = tuple(
        (str(tenant.tenant_id), str(profile.user_id), profile.role)
        for tenant in SOURCE_TENANTS
        for profile in tenant.profiles
    )
    assert expected == SOURCE_PROFILES
    assert len(SOURCE_PROFILES) == 6


def test_opt_in_seed_is_transactional_additive_and_never_restores_revocation(tmp_path):
    docker = Mock(return_value="")
    fixture = DisposableMembershipDB(
        docker,
        name="disposable-seed-test",
        network="fictional-network",
        label="fictional-label",
        directory=tmp_path,
        verified_tls=True,
    )
    docker.assert_not_called()  # Construction and ordinary startup do not call the new seed.
    fixture.seed_source_profiles()
    docker.assert_called_once()
    args, kwargs = docker.call_args
    assert args[:4] == ("exec", "-i", "disposable-seed-test", "psql")
    sql = kwargs["input"]
    assert sql.strip().startswith("BEGIN;") and sql.strip().endswith("COMMIT;")
    assert all(word not in sql.upper() for word in ("GRANT", "UPDATE", "DELETE", "CREATE"))
    # SQLite checks shared INSERT/ON CONFLICT semantics only, not PostgreSQL TLS,
    # privilege enforcement, connection policy or transaction-failure behavior.
    with sqlite3.connect(":memory:") as db:
        db.execute("ATTACH DATABASE ':memory:' AS ops")
        db.executescript("""
CREATE TABLE ops.tenant(id TEXT PRIMARY KEY,active BOOL);
CREATE TABLE ops.app_user(id TEXT PRIMARY KEY,active BOOL);
CREATE TABLE ops.tenant_membership(user_id TEXT,tenant_id TEXT,role TEXT,active BOOL,
 PRIMARY KEY(user_id,tenant_id));
""")
        db.executescript(sql)
        assert db.execute("SELECT COUNT(*) FROM ops.tenant").fetchone() == (2,)
        assert db.execute("SELECT COUNT(*) FROM ops.app_user").fetchone() == (6,)
        assert db.execute("SELECT COUNT(*) FROM ops.tenant_membership").fetchone() == (6,)
        tenant, user, _ = SOURCE_PROFILES[1]
        db.execute("UPDATE ops.app_user SET active=false WHERE id=?", (user,))
        db.execute("UPDATE ops.tenant SET active=false WHERE id=?", (tenant,))
        db.execute(
            "UPDATE ops.tenant_membership SET active=false,role='auditor' WHERE user_id=?", (user,)
        )
        db.commit()
        db.executescript(sql)
        assert db.execute("SELECT active FROM ops.app_user WHERE id=?", (user,)).fetchone() == (0,)
        assert db.execute("SELECT active FROM ops.tenant WHERE id=?", (tenant,)).fetchone() == (0,)
        assert db.execute(
            "SELECT role,active FROM ops.tenant_membership WHERE user_id=?", (user,)
        ).fetchone() == ("auditor", 0)
