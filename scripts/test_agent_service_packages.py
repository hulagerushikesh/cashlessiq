"""Disposable CI: installed wheel entry points, exact units and dummy private plans.

Never an installer or launcher for an operator host. The loopback password sink
speaks only PostgreSQL startup/authentication and always denies authentication.
It cannot run SQL, issue authority, call a provider or publish a comparison.
"""

import hashlib
import json
import os
import pwd
import secrets
import shutil
import signal
import socket
import struct
import subprocess
import threading
from pathlib import Path
from uuid import uuid4
from zipfile import ZipFile

from scripts import test_agent_services as policy
from scripts.check_domain_package import verify_wheel as verify_domain_wheel

INSTALL = Path("/opt/cashlessiq-agent")
PYTHON = INSTALL / "venv/bin/python"
ACCOUNTS = (("ciq-agent-clinical", 53001), ("ciq-agent-custody", 53002),
            ("ciq-agent-receipt", 53003))
FILES = tuple(path / name for path, name in zip(
    policy.PLANS, ("claim.json", "custody.json", "peer.json"), strict=True,
))
FAULTS = ("missing", "public", "owner", "symlink", "hardlink", "oversize", "duplicate")


def guard():
    if os.environ.get("CIQ_AGENT_PACKAGE_TEST") != "1":
        raise SystemExit("Packaged services require explicit disposable CI")
    policy.guard()
    if INSTALL.exists() or INSTALL.is_symlink():
        raise SystemExit("Refusing existing agent installation")
    for name, _uid in ACCOUNTS:
        for lookup in (pwd.getpwnam, policy.grp.getgrnam):
            try:
                lookup(name)
            except KeyError:
                continue
            raise SystemExit("Refusing existing service account")


def receive(connection, count):
    if not 0 < count <= 8192:
        raise ValueError("Dummy authentication frame bound")
    data = b""
    while len(data) < count:
        block = connection.recv(count - len(data))
        if not block:
            raise ValueError("Dummy authentication frame truncated")
        data += block
    return data


class PasswordSink:
    """Trusted in-memory dummy secret control, not a PostgreSQL implementation."""

    def __init__(self, password):
        self.password = password.encode() + b"\0"
        self.results = []
        self.stopped = threading.Event()
        self.listener = socket.socket()
        try:
            self.listener.bind(("127.0.0.1", 5432))  # Refuse an existing DB listener.
            self.listener.listen(4)
            self.listener.settimeout(0.2)
        except BaseException:
            self.listener.close()
            raise
        self.thread = threading.Thread(target=self.serve, daemon=True)
        self.thread.start()

    def serve(self):
        while not self.stopped.is_set():
            try:
                connection, _ = self.listener.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            try:
                with connection:
                    connection.settimeout(4)
                    size = struct.unpack("!I", receive(connection, 4))[0]
                    startup = receive(connection, size - 4)
                    if startup[:4] != struct.pack("!I", 196608):
                        raise ValueError("Unexpected startup protocol")
                    fields = startup[4:].split(b"\0")
                    if fields[-2:] != [b"", b""] or len(fields) % 2:
                        raise ValueError("Malformed startup fields")
                    values = dict(zip(fields[:-2:2], fields[1:-2:2], strict=True))
                    if (values.get(b"user") != b"ciq_dummy_login"
                        or values.get(b"database") != b"ciq_dummy_database"):
                        raise ValueError("Unexpected startup identity")
                    connection.sendall(b"R" + struct.pack("!II", 8, 3))
                    if receive(connection, 1) != b"p":
                        raise ValueError("Expected password response")
                    size = struct.unpack("!I", receive(connection, 4))[0]
                    if receive(connection, size - 4) != self.password:
                        raise ValueError("Unexpected dummy password")
                    # Fixed error deliberately supplies no password/SQL/details.
                    error = b"SFATAL\0C28P01\0Mdisposable authentication denied\0\0"
                    connection.sendall(b"E" + struct.pack("!I", len(error) + 4) + error)
                self.results.append(True)
            except Exception:
                # Never retain/print exception data, packets or secret values.
                self.results.append(False)

    def close(self):
        self.stopped.set()
        self.listener.close()
        self.thread.join(timeout=5)
        if self.thread.is_alive():
            raise RuntimeError("Dummy authentication listener cleanup unconfirmed")


def verify_wheel(wheel, package, source):
    """All shipped package files must be byte-identical to this checkout."""
    expected = {package + "/" + str(path.relative_to(source)): path
                for path in source.rglob("*") if path.is_file()
                and "__pycache__" not in path.parts and path.suffix != ".pyc"}
    with ZipFile(wheel) as archive:
        shipped = {name for name in archive.namelist() if ".dist-info/" not in name}
        if shipped != set(expected):
            raise ValueError("Installed package file inventory mismatch")
        for name, path in expected.items():
            if archive.read(name) != path.read_bytes():
                raise ValueError("Installed package source mismatch")


def install(base):
    dist = base / "dist"
    dist.mkdir()
    for project in ("packages/domain", "apps/api"):
        policy.run("uv", "build", "--wheel", str(policy.ROOT / project),
                   "--out-dir", str(dist), timeout=120)
    wheels = sorted(dist.glob("*.whl"))
    if len(wheels) != 2:
        raise ValueError("Expected only API and domain wheels")
    api = next(w for w in wheels if w.name.startswith("cashlessiq_api-"))
    verify_wheel(api, "ciq_api", policy.ROOT / "apps/api/src/ciq_api")
    verify_domain_wheel(next(w for w in wheels if w.name.startswith("cashlessiq_domain-")))
    requirements = base / "requirements.txt"
    policy.run("uv", "export", "--project", str(policy.ROOT / "apps/api"), "--frozen",
               "--no-dev", "--no-emit-local", "--output-file", str(requirements))
    policy.run("uv", "venv", "--python", "3.11", "--no-python-downloads",
               str(INSTALL / "venv"), timeout=30)
    policy.run("uv", "pip", "install", "--python", str(PYTHON), "--require-hashes",
               "--requirements", str(requirements), timeout=120)
    policy.run("uv", "pip", "install", "--python", str(PYTHON), "--no-deps",
               *(str(w) for w in wheels), timeout=30)
    # No editable install or legacy/provider runtime, and all executed modules
    # resolve inside the root-owned venv rather than the checkout/home directory.
    code = """
import importlib.util, os, stat
from pathlib import Path
import ciq_api.agent_claim_runner, ciq_api.agent_custody_runner, ciq_api.agent_receipt_runner
import cashlessiq_domain
for name in ('cashlessiq', 'snowflake', 'pytest'):
    assert importlib.util.find_spec(name) is None
root = Path('/opt/cashlessiq-agent/venv')
for module in (ciq_api.agent_claim_runner, ciq_api.agent_custody_runner,
               ciq_api.agent_receipt_runner, cashlessiq_domain):
    path = Path(module.__file__)
    assert path.is_relative_to(root) and not path.is_symlink()
for parent, dirs, files in os.walk(root):
    for path in (Path(parent), *(Path(parent) / n for n in dirs + files)):
        item = path.stat()
        assert item.st_uid == 0 and not item.st_mode & 0o022
"""
    policy.run(str(PYTHON), "-I", "-B", "-c", code, timeout=20)
    print("PASS: source-matched API/domain wheels, locked dependencies, root-owned installation")


def plan_values(role, password, epoch):
    common = {"database": "ciq_dummy_database", "database_oid": 123,
              "login": "ciq_dummy_login", "login_oid": 456, "password": password,
              "request_id": "REQ-SERVICE-DUMMY"}
    if role == "claim":
        return {**common, "protocol": "ciq-fake-claim-v1", "job_id": str(uuid4()),
                "capture_schema": "ciq_agent_capture"}
    if role == "custody":
        return {**common, "protocol": "ciq-fake-custody-v1", "epoch": epoch,
                "receipt_uid": ACCOUNTS[2][1], "receipts_schema": "ciq_agent_receipts",
                "claim": {"operation_id": str(uuid4()), "fence_id": str(uuid4()),
                          "state": "reserved", "version": 1}}
    return {"protocol": "ciq-fake-receipt-v1", "epoch": epoch,
            "custody_uid": ACCOUNTS[1][1]}


def stage(path, uid, body, fault, sentinel):
    """Only invocation-owned dummy paths, after the preceding cgroup is empty."""
    raw = json.dumps(body).encode()
    if fault == "missing":
        return
    if fault == "duplicate":
        raw = ('{"protocol":' + json.dumps(sentinel) + ",").encode() + raw[1:]
    if fault == "oversize":
        raw += b" " * 8193
    target = path.with_name("dummy-target") if fault in ("symlink", "hardlink") else path
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.fchown(fd, 0 if fault == "owner" else uid, uid)
        os.fchmod(fd, 0o644 if fault == "public" else 0o600)
        with os.fdopen(fd, "wb", closefd=False) as file:
            file.write(raw)
            file.flush()
            os.fsync(fd)
    finally:
        os.close(fd)
    if fault == "symlink":
        path.symlink_to(target)
    elif fault == "hardlink":
        os.link(target, path)


def logs(invocation):
    if len(invocation) != 32 or any(c not in "0123456789abcdef" for c in invocation):
        raise ValueError("Missing service invocation identity")
    policy.run("journalctl", "--sync")
    output = policy.run("journalctl", "_SYSTEMD_INVOCATION_ID=" + invocation,
                        "_TRANSPORT=stdout", "--output=json", "--no-pager", "--lines=8")
    return [json.loads(line)["MESSAGE"] for line in output.stdout.splitlines()]


def execute(unit, role, ready=False):
    if policy.value(unit, "ActiveState") == "failed":
        policy.run("systemctl", "reset-failed", unit)
    # Do not call policy.start/diagnose: that helper can print raw dummy-probe
    # logs. Actual module logs are private and must match fixed markers in RAM.
    policy.run("systemctl", "start", unit)
    invocation = policy.value(unit, "InvocationID")
    policy.wait_for(lambda: policy.value(unit, "ActiveState") in ("inactive", "failed"), 25)
    if not (policy.empty(unit) and policy.value(unit, "NRestarts") == "0"
            and policy.value(unit, "Result") == "exit-code"
            and policy.value(unit, "ExecMainStatus") == "1"):
        raise RuntimeError("Packaged service result/cgroup mismatch: " + role)
    expected = (["fake_receipt_ready"] if ready else []) + [f"fake_{role}_unavailable"]
    if logs(invocation) != expected:
        raise RuntimeError("Packaged service output was not the fixed private contract: " + role)


def main():
    guard()  # Before every build, NSS mutation, file creation or network bind.
    signal.signal(signal.SIGTERM, lambda *_: policy.sys.exit("Interrupted package acceptance"))
    base = Path("/run") / ("ciq-packaged-service-" + uuid4().hex[:16])
    paths, accounts, units = [], [], []
    sink = endpoint = None
    try:
        base.mkdir(mode=0o755)
        paths.append(base)
        INSTALL.mkdir(mode=0o755)
        paths.append(INSTALL)
        install(base)
        for account, uid in ACCOUNTS:
            policy.run("groupadd", "--gid", str(uid), account)
            accounts.append((account, uid))
            policy.run("useradd", "--system", "--uid", str(uid), "--gid", str(uid),
                       "--no-create-home", "--no-log-init", "--shell", "/usr/sbin/nologin", account)
        for path in policy.PLANS:
            path.mkdir(mode=0o755)
            paths.append(path)
        ipc = policy.PLANS[2] / "ipc"
        journal_parent = policy.PLANS[2] / "journal-parent"
        ipc.mkdir(mode=0o755)
        journal_parent.mkdir(mode=0o700)
        for path in (ipc, journal_parent):
            os.chown(path, ACCOUNTS[2][1], ACCOUNTS[2][1])
        epoch = {"database_id": str(uuid4()), "epoch_id": str(uuid4())}
        # Trusted fixture provisioning, independent of runtime entry points.
        provision = """
import json, sys
from pathlib import Path
from ciq_api.agent_admission import FakeEpochPin, FakeReceiptJournal
FakeReceiptJournal.provision(Path('/run/ciq-agent-receipts/journal-parent/retained'),
                             FakeEpochPin.model_validate(json.loads(sys.argv[1])))
"""
        result = subprocess.run([str(PYTHON), "-I", "-B", "-c", provision, json.dumps(epoch)],
                                user=ACCOUNTS[2][1], group=ACCOUNTS[2][1], extra_groups=[],
                                capture_output=True, timeout=10)
        if result.returncode or result.stdout or result.stderr:
            raise RuntimeError("Private dummy journal provisioning failed")
        journal = journal_parent / "retained/fake-receipts.sqlite3"
        original = hashlib.sha256(journal.read_bytes()).digest()
        password = secrets.token_urlsafe(32)
        sink = PasswordSink(password)
        # Socket metadata is needed before custody constructs its SQL engine.
        # This fixture never accepts or answers a receipt command.
        endpoint = socket.socket(socket.AF_UNIX)
        socket_path = ipc / "peer.sock"
        endpoint.bind(str(socket_path))
        os.chown(socket_path, ACCOUNTS[2][1], ACCOUNTS[2][1])
        for role in policy.ROLES:
            unit = base.name + "-" + role + ".service"
            target = Path("/run/systemd/system") / unit
            source = policy.SOURCES / ("ciq-agent-" + role + ".service.example")
            # Identical bytes: no ExecStart, User, path, output or limit override.
            target.write_bytes(source.read_bytes())
            units.append((unit, target))
        policy.run("systemd-analyze", "verify", "--man=no", *(str(t) for _, t in units))
        policy.run("systemctl", "daemon-reload")
        for index, ((unit, _target), path, (_account, uid)) in enumerate(
            zip(units, FILES, ACCOUNTS, strict=True)
        ):
            role = policy.ROLES[index]
            body = plan_values(role, password, epoch)
            for fault in FAULTS:
                stage(path, uid, body, fault, password)
                before = len(sink.results)
                execute(unit, role)
                if len(sink.results) != before:
                    raise RuntimeError("Unsafe private plan reached authentication")
                if hashlib.sha256(journal.read_bytes()).digest() != original:
                    raise RuntimeError("Private plan denial mutated retained journal")
                # No actual module is alive; these are only our dummy plan names.
                path.unlink(missing_ok=True)
                path.with_name("dummy-target").unlink(missing_ok=True)
                print("PASS: installed " + role + " private plan denial " + fault, flush=True)
            if role != "receipt":
                stage(path, uid, body, None, password)
                before = len(sink.results)
                execute(unit, role)
                policy.wait_for(lambda before=before: len(sink.results) > before, 5)
                if sink.results[before:] != [True]:
                    raise RuntimeError("Private plan did not reach fixed dummy authentication")
                path.unlink()
                print("PASS: installed " + role + " password delivered only to loopback control",
                      flush=True)
        # Retire only the supervisor's bound dummy socket after all consumers are
        # stopped. This is not stale real-endpoint cleanup or a production recipe.
        endpoint.close()
        endpoint = None
        socket_path.unlink()
        stage(FILES[2], ACCOUNTS[2][1], plan_values("receipt", password, epoch), None, password)
        execute(units[2][0], "receipt", ready=True)
        if not socket_path.is_socket() or hashlib.sha256(journal.read_bytes()).digest() != original:
            raise RuntimeError("Receipt idle exit did not preserve retained state")
        print("PASS: installed receipt readiness/idle exit preserve history and stale socket")
        execute(units[2][0], "receipt")
        if not socket_path.is_socket() or hashlib.sha256(journal.read_bytes()).digest() != original:
            raise RuntimeError("Receipt stale restart mutated retained state")
        print("PASS: installed receipt refuses stale endpoint without reset or adoption")
        if sink.results != [True, True]:
            raise RuntimeError("Unexpected authentication activity during private plan acceptance")
    finally:
        if endpoint is not None:
            endpoint.close()
        if sink is not None:
            sink.close()
        failures = []
        for unit, target in reversed(units):
            try:
                policy.run("systemctl", "stop", unit)
                if (policy.value(unit, "ActiveState") not in ("inactive", "failed")
                    or not policy.empty(unit)):
                    raise RuntimeError("Owned service still active")
                target.unlink()
                policy.run("systemctl", "reset-failed", unit, check=False)
            except Exception:
                failures.append(unit)
        policy.run("systemctl", "daemon-reload")
        if failures:
            raise RuntimeError("Packaged service quiescence unconfirmed; private fixtures retained")
        for path in reversed(paths):
            shutil.rmtree(path)
        policy.retire_accounts(accounts)
        if any(path.exists() or path.is_symlink() for path in paths):
            raise RuntimeError("Packaged fixture cleanup unconfirmed")
        print("PASS: owned services, credentials, retained fixture, accounts and install removed")


if __name__ == "__main__":
    main()
