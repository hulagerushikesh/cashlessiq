"""Disposable systemd/real-database acceptance, never an operator launcher."""

import io
import json
import os
import re
import shutil
import signal
import socket
import subprocess
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from pathlib import Path
from uuid import uuid4

from scripts import test_agent_service_packages as packages

policy = packages.policy
EXPECTED = "postgresql+psycopg://postgres:ciq-disposable-agent-ledger@127.0.0.1:5432/postgres"


def guard():
    if (os.environ.get("CIQ_AGENT_SERVICE_JOURNEY_TEST") != "1"
        or os.environ.get("CIQ_AGENT_CONTROLLER_TEST") != "1"
        or os.environ.get("TEST_DATABASE_URL") != EXPECTED):
        raise SystemExit("Service journeys require the exact opted-in disposable database")
    packages.guard()  # All host/path/identity checks precede mutation or connection.


class Services:
    def __init__(self, units):
        self.units = dict(units)
        self.invocations = {}

    def start(self, role):
        unit = self.units[role]
        if (policy.value(unit, "ActiveState") not in ("inactive", "failed")
            or not policy.empty(unit)):
            raise RuntimeError("Previous service invocation is not quiescent")
        if policy.value(unit, "ActiveState") == "failed":
            policy.run("systemctl", "reset-failed", unit)
        policy.run("systemctl", "start", unit)
        invocation = policy.value(unit, "InvocationID")
        if not re.fullmatch("[0-9a-f]{32}", invocation):
            raise RuntimeError("Missing service invocation identity")
        if invocation in self.invocations.values():
            raise RuntimeError("Service invocation identity was reused")
        self.invocations[role] = invocation

    def finish(self, role, code):
        unit = self.units[role]
        policy.wait_for(lambda: policy.value(unit, "ActiveState") in ("inactive", "failed"), 45)
        if (not policy.empty(unit) or policy.value(unit, "NRestarts") != "0"
            or policy.value(unit, "Result") != ("success" if code == 0 else "exit-code")
            or policy.value(unit, "ExecMainStatus") != str(code)):
            raise RuntimeError("Service journey result/cgroup mismatch: " + role)
        return packages.logs(self.invocations[role])  # Private memory only.

    def receipt_ready(self):
        def ready():
            if policy.value(self.units["receipt"], "ActiveState") != "active":
                raise RuntimeError("Receipt service exited before readiness")
            records = packages.logs(self.invocations["receipt"])
            if records and records != ["fake_receipt_ready"]:
                raise RuntimeError("Unexpected private receipt readiness output")
            return records == ["fake_receipt_ready"]

        # Type=exec alone, socket metadata and earlier invocation logs are not readiness.
        policy.wait_for(ready, 6)

    def stop(self):
        failures = []
        for role, unit in reversed(tuple(self.units.items())):
            try:
                policy.run("systemctl", "stop", unit)
                if (policy.value(unit, "ActiveState") not in ("inactive", "failed")
                    or not policy.empty(unit)):
                    raise RuntimeError("Owned service is not quiescent")
            except Exception:
                failures.append(role)
        if failures:
            raise RuntimeError("Service journey quiescence unconfirmed; fixtures retained")


@contextmanager
def installed_services():
    guard()
    base = Path("/run") / ("ciq-service-journey-" + uuid4().hex[:16])
    paths, accounts, units = [], [], []
    services = None
    try:
        base.mkdir(mode=0o755)
        paths.append(base)
        packages.INSTALL.mkdir(mode=0o755)
        paths.append(packages.INSTALL)
        packages.install(base)
        for name, uid in packages.ACCOUNTS:
            policy.run("groupadd", "--gid", str(uid), name)
            accounts.append((name, uid))
            policy.run("useradd", "--system", "--uid", str(uid), "--gid", str(uid),
                       "--no-create-home", "--no-log-init", "--shell", "/usr/sbin/nologin", name)
        for path in policy.PLANS:
            path.mkdir(mode=0o755)
            paths.append(path)
        for leaf, mode in (("ipc", 0o755), ("journal-parent", 0o700)):
            path = policy.PLANS[2] / leaf
            path.mkdir(mode=mode)
            os.chown(path, packages.ACCOUNTS[2][1], packages.ACCOUNTS[2][1])
        for role in policy.ROLES:
            unit = base.name + "-" + role + ".service"
            target = Path("/run/systemd/system") / unit
            # Exact source bytes, including all identities, paths, limits and commands.
            target.write_bytes((policy.SOURCES / ("ciq-agent-" + role + ".service.example"))
                               .read_bytes())
            units.append((role, unit, target))
        policy.run("systemd-analyze", "verify", "--man=no", *(str(t) for _, _, t in units))
        policy.run("systemctl", "daemon-reload")
        services = Services((role, unit) for role, unit, _ in units)
        yield services
    finally:
        # Even partial installation must quiesce every owned unit before teardown.
        (services or Services((role, unit) for role, unit, _ in units)).stop()
        for _role, unit, target in reversed(units):
            target.unlink()
            policy.run("systemctl", "reset-failed", unit, check=False)
        policy.run("systemctl", "daemon-reload")
        for path in reversed(paths):
            shutil.rmtree(path)
        policy.retire_accounts(accounts)
        if any(p.exists() or p.is_symlink() for p in paths):
            raise RuntimeError("Owned service journey cleanup unconfirmed")
        print("PASS: owned journey services, plans, retained fixtures, accounts "
              "and install removed")


def provision(epoch):
    """Trusted dummy provisioning, separate from the installed receipt command."""
    code = """
import json, sys
from pathlib import Path
from ciq_api.agent_admission import FakeEpochPin, FakeReceiptJournal
FakeReceiptJournal.provision(Path('/run/ciq-agent-receipts/journal-parent/retained'),
                             FakeEpochPin.model_validate(json.load(sys.stdin)))
"""
    uid = packages.ACCOUNTS[2][1]
    result = subprocess.run([str(packages.PYTHON), "-I", "-B", "-c", code],
                            input=json.dumps(epoch), text=True, capture_output=True,
                            user=uid, group=uid, extra_groups=[], timeout=10)
    if result.returncode or result.stdout or result.stderr:
        raise RuntimeError("Private journey journal provisioning failed")


@contextmanager
def database():
    guard()
    # Exact loopback topology without Docker's port-forwarding/DNAT path. The
    # server itself listens only on 127.0.0.1 in this disposable host namespace.
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 5432))  # Refuse an existing database/listener.
    name = "ciq-service-pg-" + uuid4().hex[:16]
    identifier = None
    try:
        policy.run("docker", "pull", "postgres:17-bookworm", timeout=120)
        result = policy.run(
            "docker", "create", "--name", name, "--network", "host", "--read-only",
            "--cap-drop", "ALL", "--cap-add", "SETUID", "--cap-add", "SETGID",
            "--cap-add", "CHOWN", "--cap-add", "DAC_OVERRIDE", "--cap-add", "FOWNER",
            "--security-opt", "no-new-privileges", "--memory", "512m", "--memory-swap", "512m",
            "--cpus", "1", "--pids-limit", "64",
            "--tmpfs", "/var/lib/postgresql/data:rw,nosuid,nodev,noexec,size=192m,mode=755",
            "--tmpfs", "/var/run/postgresql:rw,nosuid,nodev,noexec,size=4m,mode=777",
            "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=16m,mode=1777",
            "--env", "POSTGRES_PASSWORD=ciq-disposable-agent-ledger",
            "--env", "PGDATA=/var/lib/postgresql/data", "postgres:17-bookworm",
            "-c", "listen_addresses=127.0.0.1", timeout=30,
        )
        identifier = result.stdout.strip()
        if not re.fullmatch("[0-9a-f]{64}", identifier):
            raise RuntimeError("Missing owned disposable database container identity")
        config = json.loads(policy.run("docker", "inspect", identifier).stdout)[0]
        host = config["HostConfig"]
        if (host["NetworkMode"] != "host" or host["PortBindings"] or host["Binds"]
            or not host["ReadonlyRootfs"] or host["Privileged"]
            or host["PidMode"] == "host" or host["IpcMode"] == "host"
            or any(m["Type"] != "tmpfs" for m in config["Mounts"])
            or host["Memory"] != 512 * 1024 * 1024 or host["MemorySwap"] != host["Memory"]
            or host["NanoCpus"] != 1_000_000_000 or host["PidsLimit"] != 64):
            raise RuntimeError("Disposable database isolation mismatch")
        policy.run("docker", "start", identifier)
        policy.wait_for(lambda: policy.run(
            "docker", "exec", identifier, "pg_isready", "-h", "127.0.0.1", "-U", "postgres",
            check=False,
        ).returncode == 0, 35)
        yield
    finally:
        if identifier:
            policy.run("docker", "rm", "-f", identifier)
            if policy.run("docker", "ps", "-aq", "--no-trunc", "--filter",
                          "id=" + identifier).stdout.strip():
                raise RuntimeError("Owned disposable database cleanup unconfirmed")
            print("PASS: owned loopback-only database container and tmpfs data removed")


def acceptance(result, passed):
    # Count actual passing call reports; pytest's inherited quiet settings may
    # suppress its textual summary. Zero collected/skipped cases cannot pass.
    if result != 0 or passed != 3:
        raise RuntimeError("Disposable exact-service journey failed; private diagnostics withheld")


def main():
    guard()
    signal.signal(signal.SIGTERM, lambda *_: policy.sys.exit("Interrupted service journey"))
    # The trusted test supervisor uses dev fixtures; service Python remains a
    # separate verified, non-editable installation without pytest/httpx/provider.
    import pytest

    class Diagnostics:
        def __init__(self):
            self.passed = 0

        @pytest.hookimpl(hookwrapper=True)
        def pytest_runtest_makereport(self, item, call):
            outcome = yield
            report = outcome.get_result()
            if report.when == "call" and report.passed:
                self.passed += 1
            if report.failed and call.excinfo:
                frame = call.excinfo.traceback[-1]
                # Fixed phase + code location, never the exception or assertion values.
                name = Path(str(frame.path)).name
                if re.fullmatch(r"[a-z_]+\.py", name):
                    print(f"FAIL: journey {report.when} at {name}:{frame.lineno + 1}")

    output = io.StringIO()
    diagnostics = Diagnostics()
    with redirect_stdout(output), redirect_stderr(output), database():
        result = pytest.main([
            "apps/api/tests/test_agent_service_journey.py", "--tb=no", "--no-header", "-q", "-s",
        ], plugins=[diagnostics])
    # No assertion values, private invocation logs, SQL or arbitrary errors escape.
    for line in output.getvalue().splitlines():
        line = line.lstrip(".")  # pytest progress dots may precede trusted markers.
        if line.startswith(("PASS: ", "FAIL: journey ")) and re.fullmatch(
            r"[A-Za-z0-9 ,:/.-]+", line,
        ):
            print(line, flush=True)
    acceptance(result, diagnostics.passed)
    print("PASS: three actual HTTP-to-service journeys and confirmed cleanup")


if __name__ == "__main__":
    main()
