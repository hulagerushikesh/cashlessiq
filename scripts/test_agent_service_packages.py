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
import stat
import struct
import subprocess
import threading
from pathlib import Path
from uuid import uuid4
from zipfile import ZipFile

from scripts import package_agent_dependencies as dependencies
from scripts import package_agent_python as python_bundle
from scripts import package_agent_release as release
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
PYTHON_KEY = "cpython-3.11.15-linux-x86_64-gnu"
INPUTS = ("python-downloads.json", "build-requirements.txt")


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


def harden_installation(root):
    # Only the fresh invocation-owned installation reaches this function.
    # Never chmod a symlink target or repair a tree owned by another identity.
    for parent, directories, files in os.walk(root):
        for path in (Path(parent), *(Path(parent) / n for n in directories + files)):
            item = path.lstat()
            if item.st_uid != os.geteuid():
                raise ValueError("Foreign installed-artifact owner")
            if stat.S_ISLNK(item.st_mode):
                if not path.resolve(strict=True).is_relative_to(root):
                    raise ValueError("Installed-artifact symlink escapes private root")
                continue
            if not (stat.S_ISREG(item.st_mode) or stat.S_ISDIR(item.st_mode)):
                raise ValueError("Unexpected installed-artifact file kind")
            path.chmod(stat.S_IMODE(item.st_mode) & ~0o7022)


def runtime_inputs(base, revision):
    """Stage reviewed public pins from Git, never dirty local download metadata."""
    files = dependencies.review.committed_files(revision)
    metadata = json.loads(files["deploy/agent-controller/python-downloads.json"])
    if set(metadata) != {PYTHON_KEY}:
        raise ValueError("Expected one pinned private interpreter")
    directory = base / "runtime-inputs"
    directory.mkdir()  # Fresh invocation-owned base only; refuse existing inputs.
    for name in INPUTS:
        with (directory / name).open("xb") as stream:
            stream.write(files["deploy/agent-controller/" + name])
    return directory


def install(base):
    revision = policy.run("git", "-c", f"safe.directory={policy.ROOT}",
                          "-C", str(policy.ROOT), "rev-parse", "HEAD").stdout.strip()
    inputs = runtime_inputs(base, revision)
    source = base / "source"
    dependencies.review.stage(revision, source)
    version = policy.run("uv", "--version").stdout.split()
    if version[:2] != ["uv", "0.11.25"]:
        raise ValueError("Expected reviewed uv version")
    # setup-python's hosted toolcache is runner-owned. Do not follow its mutable
    # interpreter from a purportedly root-owned installed service environment.
    # Download preparation is separate from installation. Verify against Git,
    # then install from the retained archive with network resolution disabled.
    archive = base / "python-bundle"
    python_bundle.create(archive, revision)
    metadata = python_bundle.local_metadata(archive, revision, base / "local-python.json")
    policy.run("uv", "python", "install", PYTHON_KEY, "--no-bin", "--no-cache", "--no-config",
               "--offline", "--python-downloads-json-url", metadata.as_uri(),
               "--install-dir", str(INSTALL / "python"), timeout=120)
    print("PASS: Git-pinned interpreter archive installed offline without cache")
    # uv may add a version-family directory symlink alongside the exact build.
    interpreters = sorted({path.resolve(strict=True)
                           for path in (INSTALL / "python").glob("*/bin/python3.11")})
    if len(interpreters) != 1 or not interpreters[0].is_relative_to(INSTALL / "python"):
        raise RuntimeError("Expected one private root-owned Python interpreter")
    # Build tools never enter the service venv. Both first-party wheels use this
    # separate hash-locked environment with network/index resolution disabled.
    builder = base / "builder"
    build_python = builder / "bin/python"
    policy.run("uv", "venv", "--no-config", "--python", str(interpreters[0]),
               "--no-python-downloads", str(builder), timeout=30)
    policy.run("uv", "pip", "install", "--no-config", "--python", str(build_python),
               "--require-hashes", "--no-build", "--no-cache", "--link-mode", "copy",
               "--requirements", str(inputs / "build-requirements.txt"), timeout=120)
    policy.run("uv", "pip", "check", "--no-config", "--python", str(build_python), timeout=20)
    dist = base / "dist"
    dist.mkdir()
    for project in ("packages/domain", "apps/api"):
        policy.run("uv", "build", "--wheel", str(source / project),
                   "--python", str(build_python), "--no-python-downloads",
                   "--no-build-isolation", "--offline", "--no-index", "--no-cache", "--no-config",
                   "--no-create-gitignore",
                   "--out-dir", str(dist), timeout=120)
    wheels = sorted(dist.glob("*.whl"))
    if len(wheels) != 2:
        raise ValueError("Expected only API and domain wheels")
    api = next(w for w in wheels if w.name.startswith("cashlessiq_api-"))
    verify_wheel(api, "ciq_api", source / "apps/api/src/ciq_api")
    verify_domain_wheel(next(w for w in wheels if w.name.startswith("cashlessiq_domain-")),
                        source_root=source)
    print("PASS: first-party wheels built and verified against pinned Git source")
    print("PASS: pinned interpreter and isolated hash-locked first-party wheel build")
    wheelhouse = base / "runtime-wheels"
    count = dependencies.create(wheelhouse, revision)
    release_directory = base / "release"
    digest, release_count = release.create(release_directory, revision, dist, wheelhouse)
    if release_count != count + 2:
        raise ValueError("Expected complete offline wheel release")
    print(f"PASS: offline wheel release SHA-256 {digest}; revision {revision}")
    policy.run("uv", "venv", "--no-config", "--offline", "--python", str(interpreters[0]),
               "--no-python-downloads",
               str(INSTALL / "venv"), timeout=30)
    policy.run("uv", "pip", "install", "--no-config", "--offline",
               "--python", str(PYTHON), "--require-hashes", "--no-deps",
               "--no-index", "--no-cache", "--no-build", "--find-links", str(release_directory),
               "--requirements", str(release_directory / "requirements.txt"),
               "--link-mode", "copy", timeout=120)
    policy.run("uv", "pip", "check", "--no-config", "--python", str(PYTHON), timeout=20)
    print(f"PASS: {count} commit-locked Linux dependency wheels installed offline without cache")
    harden_installation(INSTALL)
    digests = {}
    for wheel in wheels:
        with ZipFile(wheel) as archive:
            digests.update({name: hashlib.sha256(archive.read(name)).hexdigest()
                            for name in archive.namelist() if ".dist-info/" not in name})
    # No editable install or legacy/provider runtime, and all executed modules
    # resolve inside the root-owned venv rather than the checkout/home directory.
    code = """
import hashlib, importlib.util, json, os, sys, sysconfig
from pathlib import Path
import ciq_api.agent_claim_runner, ciq_api.agent_custody_runner, ciq_api.agent_receipt_runner
import cashlessiq_domain
if sys.version_info[:3] != (3, 11, 15): sys.exit(16)
for name in ('cashlessiq', 'snowflake', 'pytest', 'hatchling', 'pathspec', 'trove_classifiers'):
    if importlib.util.find_spec(name) is not None: sys.exit(14)
root = Path('/opt/cashlessiq-agent')
for module in (ciq_api.agent_claim_runner, ciq_api.agent_custody_runner,
               ciq_api.agent_receipt_runner, cashlessiq_domain):
    path = Path(module.__file__)
    if not path.is_relative_to(root / 'venv') or path.is_symlink(): sys.exit(13)
for parent, dirs, files in os.walk(root):
    for path in (Path(parent), *(Path(parent) / n for n in dirs + files)):
        item = path.stat()
        if item.st_uid != 0: sys.exit(11)
        if item.st_mode & 0o022: sys.exit(12)
site = Path(sysconfig.get_path('purelib'))
for name, digest in json.load(sys.stdin).items():
    if hashlib.sha256((site / name).read_bytes()).hexdigest() != digest: sys.exit(15)
"""
    result = subprocess.run([str(PYTHON), "-I", "-B", "-c", code], capture_output=True,
                            text=True, input=json.dumps(digests), timeout=20)
    if result.returncode or result.stdout or result.stderr:
        raise RuntimeError("Private installed-artifact verification failed: "
                           + str(result.returncode))
    print("PASS: source-matched API/domain wheels, locked dependencies, root-owned installation")
    return release_directory, revision, digest


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
        policy.STORAGE.mkdir(mode=0o755)
        paths.append(policy.STORAGE)
        journal_parent = policy.STORAGE / "receipts"
        ipc.mkdir(mode=0o755)
        journal_parent.mkdir(mode=0o700)
        for path in (ipc, journal_parent):
            os.chown(path, ACCOUNTS[2][1], ACCOUNTS[2][1])
        epoch = {"database_id": str(uuid4()), "epoch_id": str(uuid4())}
        # Trusted fixture provisioning, independent of runtime entry points.
        provision = """
import json, sys
from pathlib import Path
from uuid import uuid4
from ciq_api.agent_admission import FakeCheckpoint, FakeEpochPin, FakeReceiptJournal
journal = FakeReceiptJournal.provision(Path('/var/lib/cashlessiq-agent/receipts/retained'),
                                      FakeEpochPin.model_validate(json.loads(sys.argv[1])))
receipt = FakeCheckpoint(tenant_id=uuid4(), request_id='SYN-RETAINED',
                        operation_id=uuid4(), submission_id=uuid4(), digest='a' * 64)
journal.prepare(receipt)
journal.issue(receipt)
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
            if role == "receipt":
                # All custody consumers are stopped. Remove only the supervisor's
                # bound dummy endpoint BEFORE receipt file faults: an existing
                # socket must not mask accidental acceptance of an unsafe plan.
                endpoint.close()
                endpoint = None
                socket_path.unlink()
            body = plan_values(role, password, epoch)
            for fault in FAULTS:
                stage(path, uid, body, fault, password)
                before = len(sink.results)
                execute(unit, role)
                if len(sink.results) != before:
                    raise RuntimeError("Unsafe private plan reached authentication")
                if role == "receipt" and (socket_path.exists() or socket_path.is_symlink()):
                    raise RuntimeError("Unsafe private plan created a receipt endpoint")
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
        stage(FILES[2], ACCOUNTS[2][1], plan_values("receipt", password, epoch), None, password)
        execute(units[2][0], "receipt", ready=True)
        if not socket_path.is_socket() or hashlib.sha256(journal.read_bytes()).digest() != original:
            raise RuntimeError("Receipt idle exit did not preserve retained state")
        print("PASS: installed receipt readiness/idle exit preserve history and stale socket")
        execute(units[2][0], "receipt")
        if not socket_path.is_socket() or hashlib.sha256(journal.read_bytes()).digest() != original:
            raise RuntimeError("Receipt stale restart mutated retained state")
        print("PASS: installed receipt refuses stale endpoint without reset or adoption")
        # Recreate only the quiescent temporary receipt runtime, as after /run
        # loss. The original persistent journal must reopen without provisioning.
        shutil.rmtree(policy.PLANS[2])
        policy.PLANS[2].mkdir(mode=0o755)
        ipc.mkdir(mode=0o755)
        os.chown(ipc, ACCOUNTS[2][1], ACCOUNTS[2][1])
        stage(FILES[2], ACCOUNTS[2][1], plan_values("receipt", password, epoch), None, password)
        execute(units[2][0], "receipt", ready=True)
        if not socket_path.is_socket() or hashlib.sha256(journal.read_bytes()).digest() != original:
            raise RuntimeError("Receipt runtime recreation changed persistent history")
        print("PASS: installed receipt reopens original journal after temporary runtime loss")
        if sink.results != [True, True]:
            raise RuntimeError("Unexpected authentication activity during private plan acceptance")
    finally:
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
        if endpoint is not None:
            endpoint.close()
        if sink is not None:
            try:
                sink.close()
            except Exception:
                failures.append("dummy-authentication-listener")
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
