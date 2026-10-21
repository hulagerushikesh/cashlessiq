"""Disposable membership image/DB permission smoke; never ordinary product DB.

Creates one ephemeral PostgreSQL cluster, test principal/schema and three private
pair networks. Passwords travel only through test files/stdin, never argv/output.
All invocation-owned containers/networks/image tags are removed in finally.
"""

import json
import secrets
import subprocess
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
LABEL = "cashlessiq.membership-db-test"


def docker(*arguments, input=None, timeout=60):
    return subprocess.run(
        ["docker", *arguments],
        cwd=ROOT,
        input=input,
        text=True,
        check=True,
        capture_output=True,
        timeout=timeout,
    ).stdout.strip()


def main():
    prefix = "ciq-membership-" + uuid4().hex[:12]
    images = [f"{prefix}:{target}" for target in ("candidate", "db-test", "worker")]
    names, networks = [], []
    try:
        for image, target, file in (
            (images[0], "candidate", "apps/membership/Dockerfile"),
            (images[1], "db-test", "apps/membership/Dockerfile"),
            (images[2], "candidate", "apps/worker/Dockerfile"),
        ):
            docker("build", "-f", file, "--target", target, "-t", image, ".", timeout=240)
        excluded = (
            "import importlib.util; "
            "from ciq_api.worker_membership_store import RestrictedMembershipStore; "
            "assert all(importlib.util.find_spec(x) is None for x in "
            "('ciq_api.main','ciq_api.auth','ciq_api.models','ciq_api.worker_broker',"
            "'ciq_membership_runtime.db_probe','fastapi','snowflake'))"
        )
        docker(
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--entrypoint",
            "python",
            images[0],
            "-I",
            "-c",
            excluded,
        )
        refusal = subprocess.run(
            ["docker", "run", "--rm", "--network", "none", "--read-only", images[0]],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert refusal.returncode != 0 and "Membership activation unavailable" in refusal.stderr
        for edge in ("db", "reader", "validator"):
            name = f"{prefix}-{edge}"
            networks.append(name)
            docker("network", "create", "--internal", "--label", f"{LABEL}={prefix}", name)
        with TemporaryDirectory(prefix=prefix) as temporary:
            directory = Path(temporary)
            admin = directory / "admin-password"
            admin.write_text(secrets.token_hex(32))
            admin.chmod(0o444)
            db = f"{prefix}-postgres"
            names.append(db)
            docker(
                "run",
                "-d",
                "--name",
                db,
                "--label",
                f"{LABEL}={prefix}",
                "--network",
                networks[0],
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
            for _ in range(50):
                ready = subprocess.run(
                    ["docker", "exec", db, "pg_isready", "-U", "postgres", "-d", "synthetic"],
                    capture_output=True,
                    timeout=5,
                )
                if ready.returncode == 0:
                    break
                time.sleep(0.2)
            else:
                raise RuntimeError("Disposable PostgreSQL startup failed")

            def sql(statement):
                return docker(
                    "exec",
                    "-i",
                    db,
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

            password = secrets.token_hex(32)
            sql(f"""
CREATE ROLE membership_test LOGIN PASSWORD '{password}' NOSUPERUSER NOCREATEDB
 NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
REVOKE ALL ON DATABASE synthetic FROM PUBLIC;
GRANT CONNECT ON DATABASE synthetic TO membership_test;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
CREATE SCHEMA ops;
CREATE TABLE ops.tenant(id uuid PRIMARY KEY,active boolean NOT NULL,name text);
CREATE TABLE ops.app_user(id uuid PRIMARY KEY,active boolean NOT NULL,issuer text,
 subject text,display_name text);
CREATE TABLE ops.tenant_membership(user_id uuid,tenant_id uuid,role text,active boolean,
 PRIMARY KEY(user_id,tenant_id));
CREATE TABLE ops.private_record(secret text);
CREATE FUNCTION ops.private_function() RETURNS text LANGUAGE SQL AS $$SELECT 'secret'$$;
REVOKE ALL ON FUNCTION ops.private_function() FROM PUBLIC;
INSERT INTO ops.tenant VALUES('10000000-0000-0000-0000-000000000001',true,'Synthetic');
INSERT INTO ops.app_user VALUES('20000000-0000-0000-0000-000000000001',true,
 'synthetic','test','Synthetic');
INSERT INTO ops.tenant_membership VALUES('20000000-0000-0000-0000-000000000001',
 '10000000-0000-0000-0000-000000000001','medical_officer',true);
GRANT USAGE ON SCHEMA ops TO membership_test;
GRANT SELECT(id,active) ON ops.tenant,ops.app_user TO membership_test;
GRANT SELECT(user_id,tenant_id,role,active) ON ops.tenant_membership TO membership_test;
CREATE TABLE ops.future_record(secret text);
""")
            info = json.loads(docker("inspect", db))[0]
            address = info["NetworkSettings"]["Networks"][networks[0]]["IPAddress"]
            credential = directory / "db.json"
            credential.write_text(
                json.dumps(
                    dict(
                        username="membership_test",
                        password=password,
                        host=address,
                        port=5432,
                        database="synthetic",
                    )
                )
            )
            credential.chmod(0o444)
            for role, image, network in (
                ("membership", images[1], networks[0]),
                ("reader", images[2], networks[1]),
                ("validator", images[2], networks[2]),
            ):
                name = f"{prefix}-{role}"
                names.append(name)
                mounts = (
                    ["--mount", f"type=bind,src={credential},dst=/run/ciq/db.json,readonly"]
                    if role == "membership"
                    else []
                )
                docker(
                    "run",
                    "-d",
                    "--name",
                    name,
                    "--label",
                    f"{LABEL}={prefix}",
                    "--network",
                    network,
                    "--read-only",
                    "--cap-drop",
                    "ALL",
                    "--security-opt",
                    "no-new-privileges",
                    "--memory",
                    "128m",
                    "--cpus",
                    "0.5",
                    "--pids-limit",
                    "32",
                    "--tmpfs",
                    "/tmp:rw,noexec,nosuid,size=8m",
                    *mounts,
                    "--entrypoint",
                    "python",
                    image,
                    "-c",
                    "import time; time.sleep(300)",
                )
                if role == "membership":
                    for worker_network in networks[1:]:
                        docker("network", "connect", worker_network, name)
                actual = json.loads(docker("inspect", name))[0]
                assert actual["Config"]["User"] == "10001:10001"
                assert actual["HostConfig"]["ReadonlyRootfs"]
                assert actual["HostConfig"]["CapDrop"] == ["ALL"]
                assert "no-new-privileges" in actual["HostConfig"]["SecurityOpt"]
                assert not actual["HostConfig"]["PortBindings"]
                assert set(actual["NetworkSettings"]["Networks"]) == (
                    set(networks) if role == "membership" else {network}
                )
                assert actual["HostConfig"]["Memory"] == 128 * 1024 * 1024
                assert actual["HostConfig"]["NanoCpus"] == 500_000_000
                assert actual["HostConfig"]["PidsLimit"] == 32
                assert len(actual["Mounts"]) == (1 if role == "membership" else 0)
                if role == "membership":
                    mount = actual["Mounts"][0]
                    assert mount["Source"] == str(credential)
                    assert mount["Destination"] == "/run/ciq/db.json" and not mount["RW"]
                else:
                    probe = (
                        "import importlib.util,socket; from pathlib import Path; "
                        "assert not Path('/run/ciq/db.json').exists(); "
                        "assert all(importlib.util.find_spec(x) is None for x in "
                        "('sqlalchemy','psycopg','ciq_api.worker_membership_store')); "
                        "s=socket.socket(); s.settimeout(1); "
                        f"assert s.connect_ex(({address!r},5432)) != 0; s.close()"
                    )
                    docker("exec", name, "python", "-c", probe)
            print(
                "PASS: per-service read-only DB mount; "
                "workers have no DB driver/credential/reachability"
            )
            for network in networks:
                assert json.loads(docker("network", "inspect", network))[0]["Internal"]

            def check(action):
                print(
                    docker(
                        "exec",
                        f"{prefix}-membership",
                        "python",
                        "-m",
                        "ciq_membership_runtime.db_probe",
                        action,
                    )
                )

            check("check")
            sql("UPDATE ops.tenant_membership SET role='auditor';")
            check("downgraded")
            for table in ("app_user", "tenant", "tenant_membership"):
                sql(f"UPDATE ops.{table} SET active=false;")
                check("missing")
                sql(f"UPDATE ops.{table} SET active=true;")
            sql("REVOKE SELECT(role) ON ops.tenant_membership FROM membership_test;")
            check("denied")
            sql("GRANT SELECT(role) ON ops.tenant_membership TO membership_test;")
            check("downgraded")
            docker("stop", "--time", "1", db)
            check("denied")
    finally:
        failures = []
        for command in (
            *[("rm", "-f", name) for name in reversed(names)],
            *[("network", "rm", name) for name in reversed(networks)],
            *[("image", "rm", image) for image in reversed(images)],
        ):
            result = subprocess.run(
                ["docker", *command], capture_output=True, text=True, timeout=30
            )
            if result.returncode and "No such" not in result.stderr:
                failures.append(command[0])
        if failures:
            raise RuntimeError(f"Test cleanup incomplete for {prefix}: {failures}")
    print("PASS: disposable membership/DB boundary; test resources removed")


if __name__ == "__main__":
    main()
