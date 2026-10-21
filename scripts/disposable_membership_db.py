"""Test-only PostgreSQL fixture for private mTLS composition, never product startup.

The caller owns network/container cleanup, including partial startup failures.
Passwords stay in private temporary files or psql stdin, not argv/environment/logs.
Database TLS is deliberately disabled on this isolated disposable test network.
"""

import json
import secrets
import subprocess
import time


class DisposableMembershipDB:
    def __init__(self, docker, *, name, network, label, directory):
        self.docker = docker
        self.name = name
        self.network = network
        self.label = label
        self.directory = directory

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
            "/tmp:rw,noexec,nosuid,size=8m",
            "--mount",
            f"type=bind,src={admin},dst=/run/admin-password,readonly",
            "-e",
            "POSTGRES_PASSWORD_FILE=/run/admin-password",
            "-e",
            "POSTGRES_DB=synthetic",
            "postgres:17-bookworm",
            "postgres",
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
        self.credential = dict(
            username="membership_test",
            password=password,
            host=self.address,
            port=5432,
            database="synthetic",
        )

    def write_credential(self, path):
        path.write_text(json.dumps(self.credential))
        path.chmod(0o444)
