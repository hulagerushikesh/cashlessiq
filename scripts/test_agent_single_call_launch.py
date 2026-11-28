"""Disposable Linux CI: actual atomic allocation, fixed exec and permanent IDs."""

import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path
from time import monotonic

from scripts.test_agent_single_call_cgroup import emergency_cleanup, guard

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


def spawn(binary, group, role, *, environment=None, fd=None, arguments=None):
    selected = group._group if fd is None else fd
    return subprocess.Popen(
        (str(binary), *(arguments if arguments is not None else (role, str(selected)))),
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd="/", env=ENV if environment is None else environment,
        pass_fds=(selected,), start_new_session=True,
    )


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
        (package / (module + ".py")).write_text(f'''
import os, signal, time
from pathlib import Path
assert os.getresuid() == ({uid},)*3 and os.getresgid() == ({uid},)*3
assert os.getgroups() == []
assert not set(os.environ) - {{"LANG", "LC_CTYPE"}}
assert Path("/proc/self/status").read_text().split("NoNewPrivs:")[1].splitlines()[0].strip()=="1"
mode = Path("/opt/cashlessiq-agent/expected").read_text().splitlines()[1]
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
           clone_failure=False):
    group = module.OwnedSingleCallCgroup("custody")
    path = Path(module.PARENT) / group.name
    process = None
    fd = None
    try:
        group.prepare()
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


def main():
    guard()  # Same explicit disposable-root opt-in; no Mac/local path.
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
        for role in ("receipt", "provider", "custody"):
            scenario(module, binary, role, "tree")
            print("PASS: atomic " + role + " placement, permanent identity and descendant cleanup")
        for mode in ("exit", "signal"):
            scenario(module, binary, "custody", mode)
            print("PASS: original pidfd " + mode + " status and reaping")
        for args in ((), ("root", "3"), ("custody", "../3"), ("custody", "2"),
                     ("custody", "99999"), ("custody", "3", "extra")):
            denied(module, binary, arguments=args)
        denied(module, binary, environment={**ENV, "UNREVIEWED": "1"})
        denied(module, binary, ordinary=True)
        denied(module, binary, removed=True)
        print("PASS: invalid selectors, environment, ordinary and removed cgroups denied")
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
    if (number != SYS_close_range) _exit(119);
    va_list args;
    va_start(args, number);
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
