"""Explicit disposable GHA systemd/cgroup-v2 acceptance, never a local installer."""

import grp
import os
import pwd
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "deploy/agent-controller/systemd"
ROLES = ("claim", "custody", "receipt")
PLANS = (Path("/run/ciq-agent-claim"), Path("/run/ciq-agent-custody"),
         Path("/run/ciq-agent-receipts"))


def guard():
    if (sys.platform != "linux" or os.geteuid() != 0
        or os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("GITHUB_REPOSITORY") != "hulagerushikesh/cashlessiq"
        or os.environ.get("CIQ_AGENT_SERVICE_TEST") != "1"):
        raise SystemExit("Agent service probes require explicit disposable Linux CI")
    if Path("/proc/1/comm").read_text().strip() != "systemd":
        raise SystemExit("Disposable systemd host required")
    if not Path("/sys/fs/cgroup/cgroup.controllers").is_file():
        raise SystemExit("Unified cgroup resource control required")
    if any(path.exists() or path.is_symlink() for path in PLANS):
        raise SystemExit("Refusing existing agent runtime paths")
    for uid in range(53001, 53004):
        for lookup in (pwd.getpwuid, grp.getgrgid):
            try:
                lookup(uid)
            except KeyError:
                continue
            raise SystemExit("Refusing existing dummy service identity")


def run(*args, check=True, timeout=10):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if check and result.returncode:
        # No raw service journal or arbitrary subprocess diagnostics.
        raise RuntimeError("Disposable agent service command failed")
    return result


def value(unit, name):
    return run("systemctl", "show", unit, "--property=" + name, "--value").stdout.strip()


def wait_for(predicate, seconds=12):
    end = time.monotonic() + seconds
    while not predicate():
        if time.monotonic() >= end:
            raise RuntimeError("Disposable agent service evidence timed out")
        time.sleep(0.05)


def empty(unit):
    group = value(unit, "ControlGroup")
    if not group:
        return True
    path = Path("/sys/fs/cgroup") / group.lstrip("/") / "cgroup.events"
    return not path.exists() or "populated 0" in path.read_text().splitlines()


def diagnose(unit):
    print("FAIL: dummy service " + unit, flush=True)
    for name in ("Result", "ExecMainCode", "ExecMainStatus", "StatusErrno"):
        print(name + "=" + value(unit, name), flush=True)
    # Only this disposable stdlib probe, never real inputs or an API module.
    print(run("journalctl", "--unit=" + unit, "--no-pager", "--lines=12",
              "--output=cat").stdout, flush=True)


def start(unit):
    if run("systemctl", "start", unit, check=False).returncode:
        diagnose(unit)
        raise RuntimeError("Disposable agent service startup failed")


def network_evidence(listeners, role):
    for index, listener in enumerate(listeners):
        try:
            client, _ = listener.accept()
        except TimeoutError:
            assert index == 1 or role == "receipt"
        else:
            client.close()
            assert index == 0 and role != "receipt"
            try:
                extra, _ = listener.accept()
            except TimeoutError:
                pass
            else:
                extra.close()
                raise AssertionError("Unexpected extra probe connection")


def retire_accounts(accounts):
    failures = []
    for account, uid in reversed(accounts):
        try:
            try:
                user = pwd.getpwnam(account)
            except KeyError:
                pass
            else:
                assert user.pw_uid == user.pw_gid == uid
                run("userdel", account)
            # userdel may automatically retire the matching private group.
            try:
                group = grp.getgrnam(account)
            except KeyError:
                pass
            else:
                assert group.gr_gid == uid
                run("groupdel", account)
            for lookup in (pwd.getpwnam, grp.getgrnam):
                try:
                    lookup(account)
                except KeyError:
                    continue
                raise AssertionError("Owned identity remains")
        except Exception:
            failures.append(account)
    if failures:
        raise RuntimeError("Owned dummy identity cleanup unconfirmed")


def main():
    guard()  # Every mutation is after the explicit CI/root/empty-path guard.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit("Interrupted service acceptance"))
    prefix = "ciq-service-test-" + uuid4().hex[:16]
    base = Path("/run") / prefix
    units, paths, outputs, accounts, listeners = [], [], [], [], []
    success = False
    try:
        base.mkdir(mode=0o755)
        paths.append(base)
        port = 0
        for address in ("127.0.0.1", "127.0.0.2"):
            listener = socket.socket()
            listeners.append(listener)
            listener.bind((address, port))
            port = listener.getsockname()[1]
            listener.listen(16)
            listener.settimeout(0.2)
        shutil.copyfile(ROOT / "scripts/agent_service_probe.py", base / "probe.py")
        for path in PLANS:
            path.mkdir(mode=0o755)
            paths.append(path)
        for leaf in ("ipc", "journal-parent/retained"):
            (PLANS[2] / leaf).mkdir(parents=True)
        for index, role in enumerate(ROLES):
            # Current systemd also requires NSS records for fixed numeric UIDs.
            # Create no home/password; retire only these invocation-owned names.
            uid = 53001 + index
            account = "ciqprobe-" + prefix[-16:] + "-" + str(index)
            run("groupadd", "--gid", str(uid), account)
            accounts.append((account, uid))
            run("useradd", "--system", "--uid", str(uid), "--gid", str(uid),
                "--no-create-home", "--no-log-init", "--shell", "/usr/sbin/nologin", account)
            output = base / role
            output.mkdir(mode=0o700)
            os.chown(output, uid, uid)
            outputs.append(output)
            unit = prefix + "-" + role + ".service"
            target = Path("/run/systemd/system") / unit
            source = (SOURCES / ("ciq-agent-" + role + ".service.example")).read_text()
            # Root-owned CI overrides replace ONLY the payload/identity/output;
            # all source sandbox/resource/shutdown properties remain effective.
            override = (
                f"\nUser={uid}\nGroup={uid}\nExecStart=\n"
                f"ExecStart=/usr/bin/env -i PATH=/usr/bin:/bin LANG=C.UTF-8 "
                f"/usr/bin/python3 -I -B {base}/probe.py check {role} {output} {port}\n"
                f"ReadWritePaths={output}\nStandardOutput=null\nStandardError=journal\n"
            )
            target.write_text(source + override)
            units.append((unit, target, source, override))
        run("systemd-analyze", "verify", "--man=no", *(str(item[1]) for item in units))
        run("systemctl", "daemon-reload")
        for (unit, _target, _source, _override), output in zip(units, outputs, strict=True):
            start(unit)
            wait_for(lambda unit=unit: value(unit, "ActiveState") in ("inactive", "failed"))
            if value(unit, "Result") != "success":
                diagnose(unit)
            assert value(unit, "Result") == "success" and (output / "checked").is_file()
            assert value(unit, "NRestarts") == "0" and empty(unit)
            network_evidence(listeners, output.name)
            print("PASS: " + unit.rsplit("-", 1)[1].removesuffix(".service") + " resource sandbox")
        unit, target, source, override = units[1]
        output = outputs[1]
        for mode in ("main-kill", "stop", "timeout", "memory", "tasks"):
            for item in output.iterdir():
                item.unlink()
            run("systemctl", "reset-failed", unit)
            changed = override.replace("probe.py check ", "probe.py " + mode + " ")
            # Shortened only for the deadline probe; the source 40s ceiling is
            # checked separately. The same systemd expiration path is exercised.
            if mode == "timeout":
                changed += "RuntimeMaxSec=2s\n"
            target.write_text(source + changed)
            run("systemctl", "daemon-reload")
            start(unit)
            if mode in ("main-kill", "stop", "timeout"):
                wait_for(lambda: (output / "child").is_file())
                if mode == "main-kill":
                    run("systemctl", "kill", "--kill-whom=main", "--signal=SIGKILL", unit)
                elif mode == "stop":
                    run("systemctl", "stop", unit)
            wait_for(lambda: value(unit, "ActiveState") in ("inactive", "failed"))
            wait_for(lambda: empty(unit))
            expected = {"main-kill": "signal", "stop": "timeout", "timeout": "timeout",
                        "memory": "oom-kill", "tasks": "success"}[mode]
            assert value(unit, "Result") == expected
            assert (output / "checked").is_file() and not (output / "escaped").exists()
            if mode == "tasks":
                assert (output / "tasks-bounded").is_file()
            assert value(unit, "NRestarts") == "0"
            network_evidence(listeners, "custody")
            print("PASS: custody " + mode + " and empty owned cgroup")
        success = True
    finally:
        for listener in listeners:
            listener.close()
        failures = []
        for unit, target, _source, _override in reversed(units):
            try:
                run("systemctl", "stop", unit)
                assert value(unit, "ActiveState") in ("inactive", "failed") and empty(unit)
                target.unlink()
                run("systemctl", "reset-failed", unit, check=False)
            except Exception:
                failures.append(unit)
        run("systemctl", "daemon-reload")
        if failures:
            raise RuntimeError("Owned service cleanup unconfirmed; fixture evidence retained")
        for path in reversed(paths):
            shutil.rmtree(path)
        retire_accounts(accounts)
        assert not any(path.exists() for path in paths)
        print("PASS: all invocation-owned services, dummy identities and runtime paths removed")
    if not success:
        raise RuntimeError("Disposable service acceptance incomplete")


if __name__ == "__main__":
    main()
