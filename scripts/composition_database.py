"""Explicit in-memory disposable DB preparation, not a launcher or credential store.

Only fresh fictional credentials/PKI and the closed two-tenant registry. Nothing
is written, connected, initialized or activated. The future physical owner must
install DB-only material privately and prove PostgreSQL TLS/grants/readiness.
"""

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from .composition_inventory import Inventory, canonical
from .disposable_membership_db import DB_HOSTNAME, source_profiles_sql, test_ca


@dataclass(frozen=True, repr=False)
class DatabaseMaterial:
    server: dict[str, bytes]
    membership: dict[str, bytes]

    def __repr__(self):
        return "DatabaseMaterial(<disposable-private-material>)"


def prepare(plan):
    """Build one fresh DB bundle for the exact inventory's member-db edge.

    The CA signing key stays in local memory. The DB leaf key, admin password
    and bootstrap SQL never enter membership's bundle. No user-supplied SQL,
    password, host or registry and no reuse of existing product credentials.
    """
    if type(plan) is not Inventory:
        raise ValueError("Disposable database preparation denied")
    address = plan.address("member-db", "db")
    member_address = plan.address("member-db", "membership")
    ca_key, ca = test_ca("Disposable composition DB CA")
    leaf_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, DB_HOSTNAME)]))
        .issuer_name(ca.subject)
        .public_key(leaf_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(hours=1))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), True)
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(DB_HOSTNAME)]), False)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), True)
        .sign(ca_key, hashes.SHA256())
    )
    password, admin = secrets.token_hex(32), secrets.token_hex(32)
    # Every interpolated SQL value is generated hex or a frozen registry value.
    # Provision only an empty disposable cluster. No IF EXISTS/adoption/repair.
    bootstrap = f"""BEGIN;
CREATE ROLE membership_test LOGIN PASSWORD '{password}' NOSUPERUSER NOCREATEDB
 NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
REVOKE ALL ON DATABASE synthetic FROM PUBLIC;
GRANT CONNECT ON DATABASE synthetic TO membership_test;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
CREATE SCHEMA ops;
CREATE TABLE ops.tenant(id uuid PRIMARY KEY, active boolean NOT NULL);
CREATE TABLE ops.app_user(id uuid PRIMARY KEY, active boolean NOT NULL);
CREATE TABLE ops.tenant_membership(user_id uuid, tenant_id uuid, role text,
 active boolean NOT NULL, PRIMARY KEY(user_id,tenant_id));
GRANT USAGE ON SCHEMA ops TO membership_test;
GRANT SELECT(id,active) ON ops.tenant,ops.app_user TO membership_test;
GRANT SELECT(user_id,tenant_id,role,active) ON ops.tenant_membership TO membership_test;
"""
    # One transaction for schema/grants AND all six seed identities.
    seed = source_profiles_sql().strip().removeprefix("BEGIN;").removesuffix("COMMIT;")
    bootstrap += seed + "\nCOMMIT;\n"
    return DatabaseMaterial(
        server={
            "server.pem": certificate.public_bytes(serialization.Encoding.PEM),
            "server.key": leaf_key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ),
            "admin-password": admin.encode(),
            "bootstrap.sql": bootstrap.encode(),
            "pg_hba.conf": (
                "local all postgres trust\n"
                "local all all reject\n"
                "hostnossl all all 0.0.0.0/0 reject\n"
                f"hostssl synthetic membership_test {member_address}/32 scram-sha-256\n"
                "host all all 0.0.0.0/0 reject\n"
                "host all all ::/0 reject\n"
            ).encode(),
        },
        membership={
            "db-ca.pem": ca.public_bytes(serialization.Encoding.PEM),
            "db.json": canonical(
                dict(
                    username="membership_test",
                    password=password,
                    host=DB_HOSTNAME,
                    port=5432,
                    database="synthetic",
                    query={"hostaddr": address},
                )
            ),
        },
    )
