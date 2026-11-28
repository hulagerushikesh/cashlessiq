"""Explicit disposable root Linux CI only; dummy process trees, no activation."""

import grp
import os
import pwd
import selectors
import signal
import subprocess
import sys
from pathlib import Path
from time import monotonic, sleep


def guard():
    if not (
        sys.platform == "linux" and os.getresuid() == (0, 0, 0)
        and os.environ.get("GITHUB_ACTIONS") == "true"
        and os.environ.get("GITHUB_REPOSITORY") == "hulagerushikesh/cashlessiq"
        and os.environ.get("CIQ_SINGLE_CALL_CGROUP_TEST") == "1"
        and Path("/proc/1/comm").read_text().strip() == "systemd"
    ):
        raise SystemExit("Cgroup cleanup acceptance requires explicit disposable Linux CI")
    for lookup in (pwd.getpwuid, grp.getgrgid):
        try:
            lookup(53002)
        except KeyError:
            continue
        raise SystemExit("Cgroup acceptance refuses an occupied dummy identity")


def spawn(path):
    # Fixture only: enter the owned cgroup BEFORE forking and dropping root.
    # Production launch must provide its own atomic, externally bounded entry.
    child = r"""
import os,signal,time
from pathlib import Path
root=Path(PATH)
(root/'cgroup.procs').write_text('0\n')
pid=os.fork()
if pid==0:
    os.setsid()
    assert os.getsid(0)==os.getpid()
    (root/'nested'/'cgroup.procs').write_text('0\n')
    os.setgroups([])
    os.setresgid(53002,53002,53002)
    os.setresuid(53002,53002,53002)
    os.fork()
    os.write(1,b'CHILD\n')
else:
    os.setgroups([])
    os.setresgid(53002,53002,53002)
    os.setresuid(53002,53002,53002)
    os.write(1,b'MAIN\n')
signal.signal(signal.SIGTERM,signal.SIG_IGN)
end=time.monotonic()+12
while time.monotonic()<end:
    time.sleep(0.02)
os._exit(0)
""".replace("PATH", repr(str(path)))
    process = subprocess.Popen(
        (sys.executable, "-I", "-B", "-c", child), cwd="/",
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env={"LANG": "C.UTF-8"}, start_new_session=True,
    )
    return process


def prepare_controllers():
    # Disposable runner setup only, after the explicit guard. Production never
    # changes a shared ancestor's controller policy as a launch fallback.
    guard()
    for path in (Path("/sys/fs/cgroup"), Path("/sys/fs/cgroup/system.slice")):
        required = {"cpu", "memory", "pids"}
        assert required <= set((path / "cgroup.controllers").read_text().split())
        missing = required - set((path / "cgroup.subtree_control").read_text().split())
        if missing:
            (path / "cgroup.subtree_control").write_text(
                " ".join("+" + name for name in sorted(missing)) + "\n")
        assert required <= set((path / "cgroup.subtree_control").read_text().split())


def ready(process):
    received = b""
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ)
        end = monotonic() + 3
        while received.count(b"\n") < 3:
            remaining = end - monotonic()
            if remaining <= 0 or not selector.select(remaining):
                raise RuntimeError("Dummy descendant readiness unconfirmed")
            raw = os.read(process.stdout.fileno(), 64)
            if not raw:
                raise RuntimeError("Dummy descendant exited before readiness")
            received += raw
    assert sorted(received.splitlines()) == [b"CHILD", b"CHILD", b"MAIN"]


def emergency_cleanup(path, process):
    # Fixture cleanup only, independently attempted after every test outcome.
    # Never use this path to adopt/remove production state after uncertainty.
    if path.exists():
        (path / "cgroup.kill").write_text("1\n")
    if process is not None:
        process.wait(timeout=3)
        for stream in (process.stdout, process.stderr):
            if stream is not None:
                stream.close()
    if path.exists():
        end = monotonic() + 3
        while b"populated 0\n" not in (path / "cgroup.events").read_bytes():
            if monotonic() >= end:
                raise RuntimeError("Owned dummy process tree remains populated")
            sleep(0.02)
        if (path / "nested").exists():
            (path / "nested").rmdir()
        path.rmdir()
    assert not path.exists()


def scenario(module, role, mode):
    group = module.OwnedSingleCallCgroup(role)
    path = Path(module.PARENT) / group.name
    process = None
    original_write = module.os.write
    try:
        group.prepare()
        assert group.quiescent()
        if mode == "empty":
            assert group.stop() and group.stop() and path.exists()
            return
        if mode == "replacement":
            path.rmdir()  # Original remains pinned, replacement has a new inode.
            path.mkdir()
        (path / "nested").mkdir()
        process = spawn(path)
        ready(process)
        if mode == "replacement":
            assert not group.stop() and not group.quiescent()
            assert b"populated 1\n" in (path / "cgroup.events").read_bytes()
            return
        assert not group.quiescent()
        if mode == "lost-ack":
            writes = []
            def uncertain(fd, raw):
                result = original_write(fd, raw)
                writes.append(result)
                raise OSError("dummy lost kernel write acknowledgment")
            module.os.write = uncertain
            assert not group.stop() and not group.stop() and writes == [2]
            module.os.write = original_write
        else:
            assert group.stop() and group.stop() and group.quiescent()
        assert process.wait(timeout=3) == -signal.SIGKILL
        assert not process.stderr.read()
        assert path.exists()  # Product cleanup preserves the namespace/evidence.
    finally:
        module.os.write = original_write
        # Only this invocation's fresh dummy namespace is retired by CI.
        # Failures propagate; never report cleanup success from a finally alone.
        try:
            if group._created:
                emergency_cleanup(path, process)
        finally:
            group.close()


def main():
    guard()
    prepare_controllers()
    from ciq_api import agent_single_call_cgroup as module
    signal.signal(signal.SIGTERM, lambda *_: sys.exit("Interrupted cgroup acceptance"))
    for role in ("receipt", "provider", "custody"):
        scenario(module, role, "tree")
        print("PASS: " + role + " recursive cleanup includes separate-session nested descendants")
    for mode in ("empty", "replacement", "lost-ack"):
        scenario(module, "custody", mode)
        print("PASS: owned cgroup " + mode + " control")
    print("PASS: all invocation-owned dummy processes, handles and cgroup names retired")


if __name__ == "__main__":
    main()
