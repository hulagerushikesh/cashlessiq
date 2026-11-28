"""Disposable Linux CI: actual atomic allocation, fixed exec and permanent IDs."""

import os
import shutil
import signal
import socket
import struct
import subprocess
import sys
from pathlib import Path
from time import monotonic, sleep

from scripts.test_agent_single_call_cgroup import emergency_cleanup, guard, prepare_controllers

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = Path("/opt/cashlessiq-agent")
SOURCE = ROOT / "deploy/agent-controller/native/single-call-launch.c"
ENV = {"LANG": "C.UTF-8"}
ERROR = b"single_call_launch_unavailable\n"


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, timeout=20)


def build(destination, extra=()):
    run("cc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", "-Wconversion",
        "-fstack-protector-strong", "-D_FORTIFY_SOURCE=2", "-fPIE", "-pie",
        "-Wl,-z,relro,-z,now", str(SOURCE), *extra, "-o", str(destination))


def spawn(binary, group, role, *, environment=None, fd=None, arguments=None,
          writers=None, gate_action="start"):
    selected = group._group if fd is None else fd
    host, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    host.settimeout(3)
    process = None
    try:
        process = subprocess.Popen(
            (str(binary), *(arguments if arguments is not None else
                            (role, str(selected), str(child.fileno())))),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE if writers is None else writers[0],
            stderr=subprocess.PIPE if writers is None else writers[1],
            cwd="/", env=ENV if environment is None else environment,
            pass_fds=(selected, child.fileno()), start_new_session=True,
        )
        child.close()
        process._launch_gate = host
        process._waiter_fd = None
        raw, ancillary, flags, _ = host.recvmsg(128, socket.CMSG_SPACE(4),
                                               socket.MSG_CMSG_CLOEXEC)
        if raw:  # Earlier argument/policy refusals exit without a handoff.
            assert raw == b"single_call_waiter_ready\n" and not flags & ~socket.MSG_CMSG_CLOEXEC
            assert (len(ancillary) == 1
                    and ancillary[0][:2] == (socket.SOL_SOCKET, socket.SCM_RIGHTS))
            assert len(ancillary[0][2]) == 4
            process._waiter_fd = struct.unpack("i", ancillary[0][2])[0]
            assert os.waitid(os.P_PIDFD, process._waiter_fd,
                             os.WEXITED | os.WNOHANG | os.WNOWAIT) is None
            if gate_action == "start":
                assert host.send(b"single_call_start\n") == 18
            elif gate_action == "bad":
                host.send(b"unreviewed_start\n")
            elif gate_action == "disconnect":
                host.close()
            else:
                assert gate_action == "hold"
        return process
    except BaseException:
        host.close()
        if process is not None:
            process.wait(timeout=4)
        raise
    finally:
        child.close()



def prepare_runtime():
    # Exact fixed path, no test selector/backdoor in production C. Only public
    # identity source and dummy runners are copied; no plans, network or secrets.
    run("/usr/bin/python3", "-m", "venv", "--without-pip", str(RUNTIME / "venv"))
    library = next((RUNTIME / "venv/lib").glob("python*/site-packages"))
    package = library / "ciq_api"
    package.mkdir(mode=0o755)
    (package / "__init__.py").touch(mode=0o644)
    shutil.copyfile(ROOT / "apps/api/src/ciq_api/agent_single_call_identity.py",
                    package / "agent_single_call_identity.py")
    # Verify membership during interpreter initialization, before role entry.
    # The real identity launcher then permanently drops UID/GID and fixed-execs
    # each dummy role. Any failed assertion is fatal, including sitecustomize.
    (library / "sitecustomize.py").write_text('''
import os
try:
    from pathlib import Path
    expected = Path("/opt/cashlessiq-agent/expected").read_text().splitlines()[0]
    assert Path("/proc/self/cgroup").read_text() == "0::/system.slice/" + expected + "\\n"
    assert os.geteuid() in (0, 53002, 53003, 53004)
    assert all(int(fd) < 3 or not Path("/proc/self/fd/" + fd).exists()
               for fd in os.listdir("/proc/self/fd"))
except BaseException:
    os._exit(118)
''')
    for uid, module in (
        (53002, "agent_single_call_runner"),
        (53003, "agent_single_call_receipt_runner"),
        (53004, "agent_single_call_provider_runner"),
    ):
        from ciq_api.agent_single_call_supervisor import READY
        role = {53002: "custody", 53003: "receipt", 53004: "provider"}[uid]
        (package / (module + ".py")).write_text(f'''
import errno, os, resource, signal, time
from pathlib import Path
assert os.getresuid() == ({uid},)*3 and os.getresgid() == ({uid},)*3
assert os.getgroups() == []
assert os.sched_getscheduler(0) == os.SCHED_OTHER
assert resource.getrlimit(resource.RLIMIT_RTPRIO) == (0, 0)
assert resource.getrlimit(resource.RLIMIT_MEMLOCK) == (0, 0)
assert not set(os.environ) - {{"LANG", "LC_CTYPE"}}
assert Path("/proc/self/status").read_text().split("NoNewPrivs:")[1].splitlines()[0].strip()=="1"
mode = Path("/opt/cashlessiq-agent/expected").read_text().splitlines()[1]
marker = {READY[role]!r}
if mode == "memory":
    retained = []
    for _ in range(96):  # At most 384 MiB even if the reviewed cap is broken.
        block = bytearray(4 * 1024 * 1024)
        for offset in range(0, len(block), 4096):
            block[offset] = 1  # Actually fault writable pages, not lazy mappings.
        retained.append(block)
    os._exit(119)  # A missing OOM limit must fail, never become a passing control.
if mode == "tasks":
    for _ in range(40):  # Bounded even if pids.max enforcement is broken.
        try:
            pid = os.fork()
        except OSError as error:
            assert error.errno == errno.EAGAIN
            os.write(1, b"TASK_LIMIT\\n")
            time.sleep(12)
            os._exit(0)
        if pid == 0:
            os.setsid()
            time.sleep(12)
            os._exit(0)
    os._exit(119)
if mode == "cpu":
    end = time.monotonic() + 2
    while time.monotonic() < end:
        pass
    os.write(1, b"CPU_LIMIT\\n")
    os._exit(0)
if mode == "marker":
    for byte in marker:
        os.write(1, bytes([byte]))
        time.sleep(0.002)
    os._exit(0)
if mode == "flood":
    os.write(1, b"X" * 1048576)
    os._exit(0)
if mode == "diagnostic":
    os.write(1, marker)
    os.write(2, b"PRIVATE dummy diagnostic")
    os._exit(0)
if mode == "inherited":
    if os.fork() == 0:
        os.setsid()
        time.sleep(12)
        os._exit(0)
    os.write(1, marker)
    os._exit(0)
if mode == "exit":
    os._exit(0)
if mode == "signal":
    os.kill(os.getpid(), signal.SIGTERM)
pid = os.fork()
if pid == 0:
    os.setsid()
    os.write(1, b"CHILD\\n")
else:
    os.write(1, b"MAIN\\n")
time.sleep(12)
os._exit(0)
''')
    # Root-owned, public and immutable to the fixed dummy identities.
    for path in RUNTIME.rglob("*"):
        if not path.is_symlink():
            path.chmod(0o755 if path.is_dir() or path.name == "python" else 0o644)


def ready(process):
    import selectors
    raw = b""
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ)
        deadline = monotonic() + 3
        while raw.count(b"\n") < 2:
            left = deadline - monotonic()
            if left <= 0 or not selector.select(left):
                raise RuntimeError("Atomic launch dummy readiness unconfirmed")
            data = os.read(process.stdout.fileno(), 64)
            if not data:
                raise RuntimeError("Atomic launch dummy exited before readiness")
            raw += data
    assert sorted(raw.splitlines()) == [b"CHILD", b"MAIN"]


def scenario(module, binary, role, mode):
    group = module.OwnedSingleCallCgroup(role)
    path = Path(module.PARENT) / group.name
    process = None
    try:
        group.prepare()
        (RUNTIME / "expected").write_text(group.name + "\n" + mode + "\n")
        process = spawn(binary, group, role)
        if mode == "tree":
            ready(process)
            assert not group.quiescent() and group.stop()
            assert process.wait(timeout=3) == 128 + signal.SIGKILL
            assert not process.stderr.read()
        else:
            output, errors = process.communicate(timeout=3)
            assert process.returncode == (0 if mode == "exit" else 128 + signal.SIGTERM)
            assert output == errors == b"" and group.quiescent() and group.stop()
        assert group.quiescent() and path.exists()
    finally:
        try:
            if group._created:
                emergency_cleanup(path, process)
        finally:
            group.close()


def denied(module, binary, *, arguments=None, environment=None, ordinary=False, removed=False,
           clone_failure=False, changed_limit=None):
    group = module.OwnedSingleCallCgroup("custody")
    path = Path(module.PARENT) / group.name
    process = None
    fd = None
    try:
        group.prepare()
        if changed_limit is not None:
            name, raw = changed_limit
            (path / name).write_bytes(raw)
            assert not group.resource_limited()
        if removed:
            path.rmdir()
        if ordinary:
            fd = os.open(RUNTIME, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        process = spawn(binary, group, "custody", arguments=arguments,
                        environment=environment, fd=fd)
        output, errors = process.communicate(timeout=3)
        assert process.returncode == 125 and errors == ERROR
        assert output == (b"ONE_CLONE\n" if clone_failure else b"")
        if not removed:
            assert group.quiescent()
    finally:
        if fd is not None:
            os.close(fd)
        try:
            if group._created:
                emergency_cleanup(path, process)
        finally:
            group.close()


def capture_scenario(module, binary, role, mode):
    from ciq_api.agent_single_call_output import ERROR, OwnedSingleCallOutput
    from ciq_api.agent_single_call_supervisor import READY
    group = module.OwnedSingleCallCgroup(role)
    output = OwnedSingleCallOutput(role)
    path = Path(module.PARENT) / group.name
    process = None
    try:
        group.prepare()
        output.prepare()
        (RUNTIME / "expected").write_text(group.name + "\n" + mode + "\n")
        writers = output.take_writers()
        try:
            # Fixture only. Popen is not proof of production ownership before a
            # lost start ACK; this scenario verifies the actual output boundary.
            process = spawn(binary, group, role, writers=writers)
        finally:
            output.release_writers()
        deadline = monotonic() + 3
        while True:
            assert monotonic() < deadline
            try:
                snapshot = output.observe()
            except ValueError as error:
                assert mode in ("flood", "diagnostic") and str(error) == ERROR
                assert group.stop()
                process.wait(timeout=3)
                try:
                    output.observe()
                except ValueError as repeated:
                    assert str(repeated) == ERROR
                    break
                raise AssertionError("Failed capture was reusable") from None
            assert snapshot.stdout in (b"", READY[role]) and snapshot.stderr == b""
            if mode == "inherited" and (snapshot.drained or process.poll() is not None):
                assert process.wait(timeout=3) == 0 and group.quiescent()
                mode = "retired"  # Native waiter kills descendants before reporting exit.
            if snapshot.drained:
                assert mode in ("marker", "retired") and snapshot.stdout == READY[role]
                assert process.wait(timeout=3) == 0 and group.quiescent() and group.stop()
                break
            sleep(0.005)
        assert group.quiescent()
    finally:
        try:
            if group._created:
                emergency_cleanup(path, process)
        finally:
            output.close()
            group.close()


def resource_scenario(module, binary, role, mode):
    group = module.OwnedSingleCallCgroup(role)
    path = Path(module.PARENT) / group.name
    process = None
    def counters(name):
        return {key: int(value) for key, value in
                (line.split() for line in (path / name).read_text().splitlines())}
    try:
        group.prepare()
        assert group.resource_limited()
        (RUNTIME / "expected").write_text(group.name + "\n" + mode + "\n")
        before = counters("cpu.stat" if mode == "cpu" else "memory.events")
        process = spawn(binary, group, role)
        if mode == "tasks":
            import selectors
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                assert selector.select(3)
                assert os.read(process.stdout.fileno(), 64) == b"TASK_LIMIT\n"
            assert int((path / "pids.current").read_text()) == 32
            assert counters("pids.events")["max"] >= 1
            assert group.stop() and process.wait(timeout=3) == 128 + signal.SIGKILL
            assert not process.stderr.read()
        else:
            output, errors = process.communicate(timeout=6)
            assert not errors
            if mode == "memory":
                assert process.returncode == 128 + signal.SIGKILL and output == b""
                assert counters("memory.events")["oom_kill"] > before["oom_kill"]
            else:
                assert process.returncode == 0 and output == b"CPU_LIMIT\n"
                assert counters("cpu.stat")["nr_throttled"] > before["nr_throttled"]
            assert group.quiescent() and group.stop()
        assert group.resource_limited() and group.quiescent()
    finally:
        try:
            if group._created:
                emergency_cleanup(path, process)
        finally:
            group.close()


def owned_launch_scenario(module, binary, mode):
    from ciq_api.agent_single_call_launch import OwnedSingleCallLaunch, WaiterStatus
    from ciq_api.agent_single_call_output import OwnedSingleCallOutput
    from ciq_api.agent_single_call_supervisor import READY
    # All original owners exist before creation can become uncertain.
    group = module.OwnedSingleCallCgroup("custody")
    output = OwnedSingleCallOutput("custody")
    launch = OwnedSingleCallLaunch()
    path = Path(module.PARENT) / group.name
    fixture_process = None
    try:
        group.prepare()
        output.prepare()
        launch.prepare()
        fd = launch.take_descriptor()
        writers = output.take_writers()
        (RUNTIME / "expected").write_text(group.name + "\n" + (
            "marker" if mode == "complete" else "tree") + "\n")
        try:
            # Popen return is fixture bookkeeping ONLY. The product gate retains
            # its own original pidfd and uses only it for observe/signal/reap.
            fixture_process = subprocess.Popen(
                (str(binary), "custody", str(group._group), str(fd)),
                stdin=subprocess.DEVNULL, stdout=writers[0], stderr=writers[1],
                cwd="/", env=ENV, pass_fds=(group._group, fd), start_new_session=True,
            )
        finally:
            launch.release_descriptor()
            output.release_writers()
        deadline = monotonic() + 3
        while not launch.receive():
            assert monotonic() < deadline
            sleep(0.005)
        if mode == "creation-ack-lost":
            # Ownership recovered with NO START, no process-return evidence.
            launch.disconnect()
        else:
            launch.authorize()
            if mode == "start-ack-lost":
                # Ignore all start-return evidence after the packet was sent.
                # The private pidfd was already retained before authorization.
                sleep(0.05)
                launch.disconnect()
            elif mode == "waiter-killed":
                sleep(0.05)
                # Fixture-only pause ensures the native waiter cannot race to
                # exit normally when independent application cleanup happens.
                signal.pidfd_send_signal(launch._pidfd, signal.SIGSTOP)
                assert group.stop()  # Independently retire roles before waiter kill.
                launch.terminate()
        snapshot = None
        while True:
            assert monotonic() < deadline
            state = launch.observe()
            if mode == "complete":
                snapshot = output.observe()
            if not state.running and (mode != "complete" or snapshot.drained):
                break
            sleep(0.005)
        expected = 0 if mode == "complete" else 137 if mode == "waiter-killed" else 125
        assert state == WaiterStatus(False, expected)
        assert group.quiescent() and group.resource_limited()
        if mode == "complete":
            assert snapshot.stdout == READY["custody"] and snapshot.stderr == b""
        assert launch.reap() == state
        # Prevent Popen's destructor from attempting another wait after product
        # ownership already reaped the ORIGINAL direct child via P_PIDFD.
        fixture_process.returncode = expected
        assert group.stop() and group.quiescent()
    finally:
        try:
            try:
                launch.disconnect()
            finally:
                if group._created:
                    emergency_cleanup(path, fixture_process)
        finally:
            launch.close()
            output.close()
            group.close()


def gate_scenario(module, binary, mode):
    group = module.OwnedSingleCallCgroup("custody")
    path = Path(module.PARENT) / group.name
    process = None
    try:
        group.prepare()
        (RUNTIME / "expected").write_text(group.name + "\ntree\n")
        process = spawn(binary, group, "custody", gate_action=(
            mode if mode in ("bad", "disconnect", "hold") else "start"))
        if mode == "lost-ack":
            ready(process)
            # No start-return acknowledgment is consulted: the original handle
            # and endpoint were retained before START. EOF retires the tree.
            process._launch_gate.close()
        output, errors = process.communicate(timeout=5)
        assert process.returncode == 125 and errors == ERROR
        if mode in ("bad", "disconnect", "hold"):
            assert output == b""  # No role process before exact start authority.
        assert group.quiescent()
    finally:
        try:
            if group._created:
                emergency_cleanup(path, process)
        finally:
            group.close()


def main():
    guard()  # Same explicit disposable-root opt-in; no Mac/local path.
    prepare_controllers()
    from ciq_api import agent_single_call_cgroup as module
    for uid in (53003, 53004):
        import grp
        import pwd
        for lookup in (pwd.getpwuid, grp.getgrgid):
            try:
                lookup(uid)
            except KeyError:
                continue
            raise RuntimeError("Atomic launch refuses an occupied dummy identity")
    if RUNTIME.exists() or RUNTIME.is_symlink():
        raise RuntimeError("Atomic launch refuses an existing runtime")
    RUNTIME.mkdir(mode=0o755)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit("Interrupted atomic launch acceptance"))
    try:
        prepare_runtime()
        binary = RUNTIME / "launch"
        build(binary)
        for mode in ("complete", "creation-ack-lost", "start-ack-lost", "waiter-killed"):
            owned_launch_scenario(module, binary, mode)
            print("PASS: original gate/pidfd/pipe composition " + mode + " and complete cleanup")
        for mode in ("bad", "disconnect", "hold", "lost-ack"):
            gate_scenario(module, binary, mode)
            print("PASS: native pre-allocation gate " + mode + " and original cleanup")
        timer_wrapper = RUNTIME / "timer-wrapper.c"
        timer_wrapper.write_text('''
#define _GNU_SOURCE
#include <sys/timerfd.h>
#include <time.h>
int __real_timerfd_settime(int, int, const struct itimerspec *, struct itimerspec *);
int __wrap_timerfd_settime(int fd, int flags, const struct itimerspec *value,
                          struct itimerspec *old) {
    static int calls = 0;
    struct itimerspec shortened = *value;
    if (++calls == 2) {
        if (clock_gettime(CLOCK_MONOTONIC, &shortened.it_value)) return -1;
        shortened.it_value.tv_nsec += 150000000;
        if (shortened.it_value.tv_nsec >= 1000000000) {
            shortened.it_value.tv_nsec -= 1000000000;
            shortened.it_value.tv_sec++;
        }
    }
    return __real_timerfd_settime(fd, flags, &shortened, old);
}
''')
        timed = RUNTIME / "launch-timed"
        build(timed, (str(timer_wrapper), "-Wl,--wrap=timerfd_settime"))
        gate_scenario(module, timed, "deadline")
        print("PASS: native kernel deadline retires original descendants and root waiter")
        for role in ("receipt", "provider", "custody"):
            scenario(module, binary, role, "tree")
            print("PASS: atomic " + role + " placement, permanent identity and descendant cleanup")
        for mode in ("exit", "signal"):
            scenario(module, binary, "custody", mode)
            print("PASS: original pidfd " + mode + " status and reaping")
        for role in ("receipt", "provider", "custody"):
            capture_scenario(module, binary, role, "marker")
            print("PASS: bounded split-marker capture and EOF for " + role)
        for mode in ("flood", "diagnostic", "inherited"):
            capture_scenario(module, binary, "custody", mode)
            print("PASS: bounded capture " + mode + " control and whole-group retirement")
        for role in ("receipt", "provider", "custody"):
            resource_scenario(module, binary, role, "memory")
            print("PASS: native " + role + " kernel memory OOM boundary and cleanup")
        for mode in ("tasks", "cpu"):
            resource_scenario(module, binary, "custody", mode)
            print("PASS: native kernel " + mode + " enforcement and cleanup")
        for args in ((), ("root", "3"), ("custody", "../3"), ("custody", "2"),
                     ("custody", "99999"), ("custody", "3", "extra")):
            denied(module, binary, arguments=args)
        denied(module, binary, environment={**ENV, "UNREVIEWED": "1"})
        denied(module, binary, ordinary=True)
        denied(module, binary, removed=True)
        print("PASS: invalid selectors, environment, ordinary and removed cgroups denied")
        for changed in (("memory.max", b"max\n"), ("memory.swap.max", b"4096\n"),
                        ("memory.oom.group", b"0\n"), ("pids.max", b"max\n"),
                        ("cpu.max", b"max 100000\n"), ("memory.max", b"134217728\n")):
            denied(module, binary, changed_limit=changed)
            print("PASS: native allocation denied changed " + changed[0])
        # Force each clone3 failure in a separately linked test-only wrapper.
        # Production source has no test switch, alternate launcher or fallback.
        for code in ("ENOSYS", "EPERM", "EINVAL", "EBUSY"):
            wrapper = RUNTIME / "wrapper.c"
            wrapper.write_text('''
#define _GNU_SOURCE
#include <errno.h>
#include <stdarg.h>
#include <sys/syscall.h>
#include <unistd.h>
long __real_syscall(long number, ...);
long __wrap_syscall(long number, ...) {
    if (number == SYS_clone3) {
        if (write(1, "ONE_CLONE\\n", 10) != 10) _exit(119);
        errno = FAILURE;
        return -1;
    }
    va_list args;
    va_start(args, number);
    if (number == SYS_pidfd_open) {
        pid_t pid = va_arg(args, pid_t);
        unsigned int options = va_arg(args, unsigned int);
        va_end(args);
        return __real_syscall(number, pid, options);
    }
    if (number != SYS_close_range) _exit(119);
    unsigned int first = va_arg(args, unsigned int);
    unsigned int last = va_arg(args, unsigned int);
    unsigned int flags = va_arg(args, unsigned int);
    va_end(args);
    return __real_syscall(number, first, last, flags);
}
'''.replace("FAILURE", code))
            failure = RUNTIME / ("launch-" + code)
            build(failure, (str(wrapper), "-Wl,--wrap=syscall"))
            denied(module, failure, clone_failure=True)
            print("PASS: " + code + " clone3 denial without fallback or retry")
        print("PASS: atomic launch fixtures completed; no provider or private inputs")
    finally:
        shutil.rmtree(RUNTIME)
    assert not RUNTIME.exists()
    print("PASS: all invocation-owned launch processes, cgroups and runtime retired")


if __name__ == "__main__":
    main()
