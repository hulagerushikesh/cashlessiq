"""TEST IMAGE ONLY: dummy mount and TCP topology probe, not an application server."""

import importlib.util
import json
import os
import socket
import socketserver
import sys
from contextlib import suppress
from pathlib import Path

ROLES = (
    "broker",
    "read1nonclinical",
    "read1medical",
    "read3nonclinical",
    "read3medical",
    "validator1",
    "validator3",
    "membership",
)


def package_check():
    from ciq_api import (
        validation_worker,
        worker_authority,
        worker_delegation,
        worker_membership,
        worker_replay,
        worker_transport,
    )

    assert all(
        (
            validation_worker,
            worker_authority,
            worker_delegation,
            worker_membership,
            worker_replay,
            worker_transport,
        )
    )
    for module in (
        "fastapi",
        "sqlalchemy",
        "psycopg",
        "snowflake",
        "uvicorn",
        "ciq_api.main",
        "ciq_api.seed",
        "ciq_api.worker_broker",
        "ciq_api.models",
        "ciq_api.snowflake_reads",
        "ciq_api.source_cases",
    ):
        assert importlib.util.find_spec(module) is None, module


def mounts(role):
    assert os.getuid() == 10001 and os.getgid() == 10001
    own = Path("/run/ciq/identity")
    assert own.read_text() == f"dummy-only:{role}"
    for path in (own, Path("/opt/venv/forbidden-write")):
        try:
            with path.open("w"):
                pass
        except OSError:
            pass
        else:
            raise AssertionError("Protected file is writable")
    signing = Path("/run/ciq/broker-signing-key")
    database = Path("/run/ciq/membership-db")
    assert signing.exists() == (role == "broker")
    assert database.exists() == (role == "membership")
    for path in ("/var/run/docker.sock", "/repo", "/root/.snowflake", "/run/ciq/other-identity"):
        # An inaccessible root home is expected for the non-root UID.
        with suppress(PermissionError):
            assert not Path(path).exists()
    assert not any(name.startswith(("CIQ_", "SNOWFLAKE_", "AWS_", "AZURE_")) for name in os.environ)


def network(role, allowed, addresses):
    for target in ROLES:
        if target == role:
            continue
        try:
            with socket.create_connection((target, 8443), timeout=0.5) as connection:
                observed = connection.recv(100).decode()
        except OSError:
            observed = None
        if target in allowed:
            assert observed == target, f"Required edge failed: {role}->{target}"
        else:
            assert observed is None, f"Forbidden edge reachable: {role}->{target}"
            # DNS denial alone is not isolation: also try every forbidden peer IP.
            for address in addresses[target]:
                try:
                    with socket.create_connection((address, 8443), timeout=0.2):
                        pass
                except OSError:
                    continue
                raise AssertionError(f"Forbidden direct-IP edge: {role}->{target}")
    for host, port in (("db", 5432), ("api", 8000), ("198.51.100.1", 443)):
        try:
            with socket.create_connection((host, port), timeout=0.5):
                pass
        except OSError:
            continue
        raise AssertionError("Unexpected non-test network access")


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.sendall(self.server.role.encode())


if __name__ == "__main__":
    action, role, *allowed = sys.argv[1:]
    assert role in ROLES
    if action == "serve":
        with socketserver.ThreadingTCPServer(("0.0.0.0", 8443), Handler) as server:
            server.daemon_threads = True
            server.role = role
            server.serve_forever()
    elif action == "check":
        addresses = json.loads(allowed.pop(0))
        package_check()
        mounts(role)
        network(role, set(allowed), addresses)
        print(f"PASS {role}: package, non-root/read-only mounts, allowed/denied network edges")
    else:
        raise SystemExit("Invalid test operation")
