"""Generated disposable bytes/contracts only; not PostgreSQL TLS/grant acceptance."""

import json
from dataclasses import replace

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.x509.oid import ExtendedKeyUsageOID

from scripts.composition_database import prepare
from scripts.composition_inventory import EDGES, ROLES, Inventory, Network
from scripts.disposable_membership_db import DB_HOSTNAME, SOURCE_PROFILES


def plan():
    return Inventory(
        "ciq-comp-abcdef123456",
        tuple(
            (kind, "sha256:" + f"{i:064x}")
            for i, kind in enumerate(("worker", "broker", "membership"), 1)
        ),
        tuple((role, f"{i:064x}") for i, role in enumerate((*ROLES, "controller"), 10)),
        tuple(Network(edge, f"{i:064x}", f"10.80.{i}.0/29") for i, edge in enumerate(EDGES, 1)),
    )


def test_credentials_and_hba_use_exact_membership_database_edge():
    p = plan()
    bundle = prepare(p)
    config = json.loads(bundle.membership["db.json"])
    assert config["query"] == {"hostaddr": p.address("member-db", "db")}
    assert (config["host"], config["database"], config["username"], config["port"]) == (
        DB_HOSTNAME,
        "synthetic",
        "membership_test",
        5432,
    )
    assert len(config["password"]) == 64
    hba = bundle.server["pg_hba.conf"].decode().splitlines()
    assert hba == [
        "local all postgres trust",
        "local all all reject",
        "hostnossl all all 0.0.0.0/0 reject",
        f"hostssl synthetic membership_test {p.address('member-db', 'membership')}/32 "
        "scram-sha-256",
        "host all all 0.0.0.0/0 reject",
        "host all all ::/0 reject",
    ]
    assert config["password"].encode() != bundle.server["admin-password"]
    assert config["password"] not in repr(bundle)
    assert set(bundle.membership) == {"db.json", "db-ca.pem"}
    assert set(bundle.server) == {
        "server.pem",
        "server.key",
        "admin-password",
        "bootstrap.sql",
        "pg_hba.conf",
    }


def test_leaf_is_signed_by_delivered_ca_with_fixed_dns_identity():
    b = prepare(plan())
    ca = x509.load_pem_x509_certificate(b.membership["db-ca.pem"])
    leaf = x509.load_pem_x509_certificate(b.server["server.pem"])
    key = serialization.load_pem_private_key(b.server["server.key"], password=None)
    ca.public_key().verify(
        leaf.signature,
        leaf.tbs_certificate_bytes,
        padding.PKCS1v15(),
        leaf.signature_hash_algorithm,
    )
    assert leaf.public_key().public_numbers() == key.public_key().public_numbers()
    assert leaf.extensions.get_extension_for_class(x509.SubjectAlternativeName).value == (
        x509.SubjectAlternativeName([x509.DNSName(DB_HOSTNAME)])
    )
    assert list(leaf.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value) == [
        ExtendedKeyUsageOID.SERVER_AUTH,
    ]
    assert not leaf.extensions.get_extension_for_class(x509.BasicConstraints).value.ca
    assert ca.extensions.get_extension_for_class(x509.BasicConstraints).value.ca
    assert b"PRIVATE KEY" not in b.membership["db-ca.pem"]


def test_bootstrap_is_one_transaction_with_six_profiles_and_only_narrow_grants():
    b = prepare(plan())
    sql = b.server["bootstrap.sql"].decode()
    password = json.loads(b.membership["db.json"])["password"]
    assert sql.count("BEGIN;") == sql.count("COMMIT;") == 1
    assert f"LOGIN PASSWORD '{password}' NOSUPERUSER NOCREATEDB" in sql
    assert "NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS" in sql
    assert [line for line in sql.splitlines() if line.startswith("GRANT")] == [
        "GRANT CONNECT ON DATABASE synthetic TO membership_test;",
        "GRANT USAGE ON SCHEMA ops TO membership_test;",
        "GRANT SELECT(id,active) ON ops.tenant,ops.app_user TO membership_test;",
        "GRANT SELECT(user_id,tenant_id,role,active) ON ops.tenant_membership TO membership_test;",
    ]
    for tenant, user, role in SOURCE_PROFILES:
        assert f"('{user}','{tenant}','{role}',true)" in sql
    assert "IF NOT EXISTS" not in sql
    assert sql.index("CREATE SCHEMA") < sql.index("INSERT INTO") < sql.index("COMMIT;")


def test_preparations_are_independent_and_changed_topology_changes_only_endpoint_contract():
    p = plan()
    one = prepare(p)
    changed = replace(
        p,
        networks=tuple(
            replace(n, subnet="10.99.1.0/29") if n.edge == "member-db" else n for n in p.networks
        ),
    )
    two = prepare(changed)
    assert one.server["server.key"] != two.server["server.key"]
    assert one.server["admin-password"] != two.server["admin-password"]
    assert one.membership["db-ca.pem"] != two.membership["db-ca.pem"]
    assert json.loads(two.membership["db.json"])["query"] == {"hostaddr": "10.99.1.3"}
    assert b"10.99.1.2/32" in two.server["pg_hba.conf"]


@pytest.mark.parametrize("bad", [None, {}, "product-db"])
def test_no_ambient_or_caller_selected_database(bad):
    with pytest.raises(ValueError, match="preparation denied"):
        prepare(bad)
