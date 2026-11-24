"""Disposable systemd payload. Dummy processes only; never an agent entry point."""

import errno
import json
import os
import resource
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path


def main():
    mode, role, output = sys.argv[1:]
    root = Path(output)
    assert os.getuid() > 0 and os.getresuid() == (os.getuid(),) * 3
    assert os.getresgid() == (os.getgid(),) * 3 and set(os.getgroups()) <= {os.getgid()}
    assert set(os.environ) <= {"PATH", "LANG", "LC_CTYPE"}
    assert sys.flags.isolated and sys.dont_write_bytecode
    status = dict(line.split(":", 1) for line in Path("/proc/self/status").read_text().splitlines())
    assert status["NoNewPrivs"].strip() == "1"
    assert all(int(status[k].strip(), 16) == 0 for k in ("CapInh", "CapPrm", "CapEff", "CapAmb"))
    assert resource.getrlimit(resource.RLIMIT_CORE) == (0, 0)
    assert resource.getrlimit(resource.RLIMIT_NOFILE) == (64, 64)
    relative = Path("/proc/self/cgroup").read_text().strip().split("::")[1][1:]
    group = Path("/sys/fs/cgroup") / relative
    expected = (192 if role == "custody" else 128) * 1024**2
    assert (group / "memory.max").read_text().strip() == str(expected)
    assert (group / "memory.swap.max").read_text().strip() == "0"
    assert (group / "pids.max").read_text().strip() == "16"
    quota, period = (group / "cpu.max").read_text().split()
    assert int(quota) / int(period) <= 0.25
    for target in ("192.0.2.1", "127.0.0.1") if role == "receipt" else ("192.0.2.1",):
        with socket.socket() as sock:
            sock.settimeout(0.2)
            assert sock.connect_ex((target, 9)) in (errno.EPERM, errno.EACCES)
    try:
        Path("/etc/ciq-agent-must-not-write").write_text("forbidden")
    except OSError as exc:
        assert exc.errno in (errno.EROFS, errno.EACCES)
    else:
        raise AssertionError("Host filesystem was writable")
    (root / "checked").write_text("checked")
    if mode == "check":
        return
    if mode == "memory":
        # The cgroup must kill the service, rather than returning a Python limit.
        memory = bytearray(256 * 1024**2)
        (root / "escaped").write_text(str(len(memory)))
        return
    if mode == "tasks":
        children = []
        try:
            for _ in range(32):
                children.append(subprocess.Popen(["/usr/bin/sleep", "20"]))
        except OSError as exc:
            assert exc.errno == errno.EAGAIN and len(children) < 16
            (root / "tasks-bounded").write_text("bounded")
        else:
            raise AssertionError("Task bound did not apply")
        finally:
            for child in children:
                child.kill()
            for child in children:
                child.wait(timeout=3)
        return
    assert mode in ("main-kill", "stop", "timeout")
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    child = os.fork()
    if child == 0:
        os.setsid()  # Escaping the process group must not escape the cgroup.
        (root / "child").write_text(json.dumps({"pid": os.getpid(), "sid": os.getsid(0)}))
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
