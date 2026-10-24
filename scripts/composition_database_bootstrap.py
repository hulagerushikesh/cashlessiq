"""One-shot private-socket bootstrap, not a network service/readiness claim.

Requires exclusive disposable mounts and an outer watchdog/container owner.
Partial startup, SQL, shutdown or marker outcomes are retained, never adopted.
"""

import json
import os
import signal
import stat
import subprocess
import sys
import time
from contextlib import suppress
from pathlib import Path

from scripts import composition_database_cluster as cluster
from scripts import composition_database_data as data
from scripts import composition_volume as volume
from scripts.composition_database_catalog import CATALOG_SQL
from scripts.composition_database_runtime import BIN, ENV
from scripts.composition_database_runtime import check as check_runtime
from scripts.composition_database_volume import DatabaseVolume

MARKER = "ciq-bootstrap.json"
SOCKET = Path("/database-data/pgdata/ciq-bootstrap-socket")


def server_command(root, material, socket):
    return (
        str(BIN / "postgres"),
        "-D",
        str(root / "pgdata"),
        "-c",
        "listen_addresses=",
        "-c",
        "port=5432",
        "-c",
        "unix_socket_directories=" + str(socket),
        "-c",
        "unix_socket_permissions=0700",
        "-c",
        "hba_file=" + str(material / "pg_hba.conf"),
        "-c",
        "ssl=off",
        "-c",
        "password_encryption=scram-sha-256",
        "-c",
        "logging_collector=off",
        "-c",
        "log_statement=none",
        "-c",
        "log_min_error_statement=panic",
        "-c",
        "shared_buffers=16MB",
        "-c",
        "max_connections=10",
        "-c",
        "fsync=on",
        "-c",
        "synchronous_commit=on",
    )


def client_command(socket, database):
    data.require(database in {"postgres", "synthetic"})
    return (
        str(BIN / "psql"),
        "--no-psqlrc",
        "--no-password",
        "--host=" + str(socket),
        "--port=5432",
        "--username=postgres",
        "--dbname=" + database,
        "--set=ON_ERROR_STOP=1",
        "--file=-",
    )


def sql(socket, database, body):
    # Secrets are stdin only. A failed or timed-out client never gets retried.
    result = subprocess.run(
        client_command(socket, database),
        input=body,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env={**ENV, "PGCONNECT_TIMEOUT": "3"},
        close_fds=True,
        timeout=10,
        check=False,
    )
    data.require(result.returncode == 0)


def wait_ready(child, socket, deadline):
    """Retry only a read-only connection probe; never retry bootstrap SQL."""
    while True:
        remaining = deadline - time.monotonic()
        data.require(child.poll() is None and remaining > 0)
        result = subprocess.run(
            client_command(socket, "postgres"),
            input=b"SELECT 1;\n",
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env={**ENV, "PGCONNECT_TIMEOUT": "1"},
            close_fds=True,
            timeout=min(1, remaining),
            check=False,
        )
        if result.returncode == 0:
            return
        # psql code 2 is a failed connection; SQL/other errors fail closed.
        data.require(result.returncode == 2)
        time.sleep(0.05)


def stop(child):
    # Signal the owned supervisor, not a PID read from mutable database files.
    data.require(child.poll() is None)
    child.send_signal(signal.SIGINT)
    data.require(child.wait(timeout=5) == 0)


def execute(root, material, body, *, socket=SOCKET):
    socket.mkdir(mode=0o700)  # Exclusive; no reuse of an existing socket directory.
    socket.chmod(0o700)
    child = subprocess.Popen(
        server_command(root, material, socket),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=ENV,
        close_fds=True,
        start_new_session=True,
    )
    stopped = False
    try:
        deadline = time.monotonic() + 5
        endpoint = socket / ".s.PGSQL.5432"
        while not endpoint.exists():
            data.require(child.poll() is None and time.monotonic() < deadline)
            time.sleep(0.05)
        data.require(stat.S_ISSOCK(endpoint.lstat().st_mode))
        data.require(child.poll() is None)
        # Socket appearance alone is not acceptance. Probe only the private
        # admin connection; this is not the membership TLS/grant readiness gate.
        wait_ready(child, socket, deadline)
        sql(socket, "postgres", b"CREATE DATABASE synthetic TEMPLATE template0;\n")
        sql(socket, "synthetic", body)
        sql(socket, "synthetic", CATALOG_SQL)
        stop(child)
        stopped = True
    finally:
        if not stopped:
            # Try a clean stop on SQL failure too. Any forced outcome stays failed.
            try:
                stop(child)
            except BaseException:
                if child.returncode is None:
                    with suppress(ProcessLookupError):
                        os.killpg(child.pid, signal.SIGKILL)
                    with suppress(subprocess.TimeoutExpired):
                        child.wait(timeout=2)
        # Retain socket directory and all data/markers on every outcome.


def bootstrap(root, material, spec, *, owner=data.OWNER, runner=execute):
    cluster.verify(root, material, spec, owner=owner)
    body = cluster.read_file(material, "bootstrap.sql", volume.MAX_FRAME, owner, 0o400)
    marker_root = root / "pgdata"
    fd = os.open(marker_root / MARKER, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(fd, 0o600)
        attempted = cluster.record(spec, "ATTEMPTED")
        data.require(os.write(fd, attempted) == len(attempted))
        os.fsync(fd)
        directory = os.open(marker_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        runner(root, material, body)
        cluster.verify(root, material, spec, owner=owner)
        completed = cluster.record(spec, "BOOTSTRAPPED")
        os.lseek(fd, 0, os.SEEK_SET)
        data.require(os.write(fd, completed) == len(completed))
        os.ftruncate(fd, len(completed))
        os.fsync(fd)
    finally:
        os.close(fd)


def verify(root, material, spec, *, owner=data.OWNER):
    # Structural completion evidence only, not SQL catalog or grant acceptance.
    cluster.verify(root, material, spec, owner=owner)
    data.require(
        cluster.read_file(root / "pgdata", MARKER, 4096, owner, 0o600)
        == cluster.record(spec, "BOOTSTRAPPED")
    )


def main():
    try:
        data.require(len(sys.argv) == 2 and sys.argv[1] in {"bootstrap", "verify"})
        check_runtime()
        spec, _ = volume.parse(
            sys.stdin.buffer.read(volume.MAX_FRAME + 1), install=False, material_type=DatabaseVolume
        )
        (bootstrap if sys.argv[1] == "bootstrap" else verify)(cluster.DATA, cluster.MATERIAL, spec)
        print(
            json.dumps(
                dict(
                    state="BOOTSTRAPPED" if sys.argv[1] == "bootstrap" else "VERIFIED",
                    role="database",
                    fingerprint=spec.fingerprint,
                )
            )
        )
        return 0
    except Exception:
        print("Disposable bootstrap denied; outcome unknown", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
