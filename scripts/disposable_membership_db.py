"""Test-only PostgreSQL fixture for private mTLS composition, never product startup.

The caller owns network/container cleanup, including partial startup failures.
Passwords stay in private temporary files or psql stdin, not argv/environment/logs.
Optional disposable server PKI enables verify-full acceptance, not production custody.
"""

import json
import secrets
import subprocess
import time
from datetime import UTC, datetime, timedelta

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

DB_HOSTNAME = "ciq-membership-db.test"


def test_ca(name):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    now = datetime.now(UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(hours=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.KeyUsage(False, False, False, False, False, True, True, False, False), True
        )
        .sign(key, hashes.SHA256())
    )
    return key, certificate


class DisposableMembershipDB:
    def __init__(self, docker, *, name, network, label, directory, verified_tls=False):
        self.docker = docker
        self.name = name
        self.network = network
        self.label = label
        self.directory = directory
        self.verified_tls = verified_tls

    def tls_files(self):
        """Test-only CA stays in host memory; server alone receives its leaf key."""
        key, ca = test_ca("Disposable membership DB CA")
        _, wrong = test_ca("Untrusted disposable DB CA")
        self.ca_pem = ca.public_bytes(serialization.Encoding.PEM)
        self.wrong_ca_pem = wrong.public_bytes(serialization.Encoding.PEM)
        server_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        now = datetime.now(UTC)
        certificate = (
            x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, DB_HOSTNAME)]))
            .issuer_name(ca.subject)
            .public_key(server_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(hours=1))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), True)
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(DB_HOSTNAME)]), False)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), True)
            .sign(key, hashes.SHA256())
        )
        directory = self.directory / "db-server"
        directory.mkdir(mode=0o755)
        for name, data in (
            ("server.pem", certificate.public_bytes(serialization.Encoding.PEM)),
            (
                "server.key",
                server_key.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.PKCS8,
                    serialization.NoEncryption(),
                ),
            ),
            (
                "pg_hba.conf",
                b"local all all trust\n"
                b"hostnossl all all 0.0.0.0/0 reject\n"
                b"hostssl synthetic membership_test 0.0.0.0/0 scram-sha-256\n"
                b"host all all ::/0 reject\n",
            ),
        ):
            path = directory / name
            path.write_bytes(data)
            path.chmod(0o444)
        return [
            "--mount",
            f"type=bind,src={directory},dst=/run/db-server,readonly",
            "--entrypoint",
            "sh",
        ], [
            "-c",
            "set -eu; umask 077; cp /run/db-server/server.key /tmp/server.key; "
            "chmod 600 /tmp/server.key; "
            'exec docker-entrypoint.sh "$@"',
            "--",
            "postgres",
            "-c",
            "ssl=on",
            "-c",
            "ssl_cert_file=/run/db-server/server.pem",
            "-c",
            "ssl_key_file=/tmp/server.key",
            "-c",
            "ssl_min_protocol_version=TLSv1.3",
            "-c",
            "hba_file=/run/db-server/pg_hba.conf",
        ]

    def sql(self, statement):
        return self.docker(
            "exec",
            "-i",
            self.name,
            "psql",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "postgres",
            "-d",
            "synthetic",
            input=statement,
        )

    def start(self):
        tls_mounts, command = self.tls_files() if self.verified_tls else ([], ["postgres"])
        admin = self.directory / "admin-password"
        admin.write_text(secrets.token_hex(32))
        admin.chmod(0o444)
        self.docker(
            "run",
            "-d",
            "--name",
            self.name,
            "--label",
            self.label,
            "--network",
            self.network,
            "--user",
            "999:999",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--memory",
            "256m",
            "--cpus",
            "1",
            "--pids-limit",
            "64",
            "--tmpfs",
            "/var/lib/postgresql/data:rw,noexec,nosuid,size=128m,uid=999,gid=999,mode=0700",
            "--tmpfs",
            "/var/run/postgresql:rw,noexec,nosuid,uid=999,gid=999",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=8m,mode=1777",
            "--mount",
            f"type=bind,src={admin},dst=/run/admin-password,readonly",
            "-e",
            "POSTGRES_PASSWORD_FILE=/run/admin-password",
            "-e",
            "POSTGRES_DB=synthetic",
            *tls_mounts,
            "postgres:17-bookworm",
            *command,
            "-c",
            "shared_buffers=16MB",
            "-c",
            "max_connections=12",
            "-c",
            "log_min_error_statement=panic",
        )
        # Wait for the final TCP listener, not initdb's temporary socket-only server.
        for _ in range(50):
            ready = subprocess.run(
                [
                    "docker",
                    "exec",
                    self.name,
                    "pg_isready",
                    "-h",
                    "127.0.0.1",
                    "-U",
                    "postgres",
                    "-d",
                    "synthetic",
                ],
                capture_output=True,
                timeout=5,
            )
            if ready.returncode == 0:
                break
            time.sleep(0.2)
        else:
            raise RuntimeError("Disposable membership DB startup failed")

        password = secrets.token_hex(32)
        self.sql(f"""
CREATE ROLE membership_test LOGIN PASSWORD '{password}' NOSUPERUSER NOCREATEDB
 NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
REVOKE ALL ON DATABASE synthetic FROM PUBLIC;
GRANT CONNECT ON DATABASE synthetic TO membership_test;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
CREATE SCHEMA ops;
CREATE TABLE ops.tenant(id uuid PRIMARY KEY, active boolean NOT NULL);
CREATE TABLE ops.app_user(id uuid PRIMARY KEY, active boolean NOT NULL);
CREATE TABLE ops.tenant_membership(user_id uuid, tenant_id uuid, role text,
 active boolean, PRIMARY KEY(user_id,tenant_id));
INSERT INTO ops.tenant VALUES('00000000-0000-4000-8000-000000000101',true);
INSERT INTO ops.app_user VALUES('00000000-0000-4000-8000-000000000111',true);
INSERT INTO ops.tenant_membership VALUES('00000000-0000-4000-8000-000000000111',
 '00000000-0000-4000-8000-000000000101','processor',true);
GRANT USAGE ON SCHEMA ops TO membership_test;
GRANT SELECT(id,active) ON ops.tenant,ops.app_user TO membership_test;
GRANT SELECT(user_id,tenant_id,role,active) ON ops.tenant_membership TO membership_test;
""")
        config = json.loads(self.docker("inspect", self.name))[0]
        attached = list(config["NetworkSettings"]["Networks"].values())
        assert len(attached) == 1 and attached[0]["NetworkID"] == self.network
        self.address = attached[0]["IPAddress"]
        assert not config["HostConfig"]["PortBindings"]
        if self.verified_tls:
            assert (
                self.docker("exec", self.name, "stat", "-c", "%u:%g:%a", "/tmp/server.key")
                == "999:999:600"
            )
            mounts = {mount["Destination"]: mount for mount in config["Mounts"]}
            assert set(mounts) == {"/run/admin-password", "/run/db-server"}
            assert all(not mount["RW"] for mount in mounts.values())
            assert mounts["/run/db-server"]["Source"] == str(self.directory / "db-server")
        self.credential = dict(
            username="membership_test",
            password=password,
            host=self.address,
            port=5432,
            database="synthetic",
        )

    def write_credential(self, path):
        credential = dict(self.credential)
        if self.verified_tls:
            credential["host"] = DB_HOSTNAME
            credential["query"] = {"hostaddr": self.address}
            ca = path.parent / "db-ca.pem"
            ca.write_bytes(self.ca_pem)
            ca.chmod(0o444)
        path.write_text(json.dumps(credential))
        path.chmod(0o444)
