"""Prepared privileged identity transition; no installation or activation.

Only stdlib is imported before permanent privilege loss. A separately reviewed
host must own the interpreter, package, lease, cgroup and fixed private inputs.
This helper neither creates those conditions nor authorizes an attempt.
"""

import ctypes
import errno
import os
import resource
import stat
import sys
from contextlib import suppress
from pathlib import Path

PYTHON = "/opt/cashlessiq-agent/venv/bin/python"
TARGETS = {
    "custody": (53002, "ciq_api.agent_single_call_runner"),
    "receipt": (53003, "ciq_api.agent_single_call_receipt_runner"),
    "provider": (53004, "ciq_api.agent_single_call_provider_runner"),
}
ENV = {"LANG": "C.UTF-8"}
ERROR = b"single_call_identity_unavailable\n"


def require(value):
    if not value:
        raise ValueError("single_call_identity_unavailable")


def status():
    return dict(line.split(":", 1) for line in Path("/proc/self/status").read_text().splitlines())


def prctl(option, value):
    libc = ctypes.CDLL(None, use_errno=True)
    call = libc.prctl
    call.argtypes = [ctypes.c_int, *([ctypes.c_ulong] * 4)]
    call.restype = ctypes.c_int
    require(call(option, value, 0, 0, 0) == 0)


def prepare_identity(role):
    """Irreversibly drop to one fixed UID/GID; never return privileged on success.

    The trusted launcher starts a fresh isolated, single-threaded interpreter
    with null stdin and private output pipes. No credential or application
    module is read/imported here. A partial failure is terminal for the process.
    """
    require(type(role) is str and role in TARGETS)
    require(sys.platform == "linux" and sys.flags.isolated and sys.dont_write_bytecode)
    require(os.getresuid() == (0, 0, 0) and os.getresgid() == (0, 0, 0))
    require(not set(os.environ) - {"LANG", "LC_CTYPE"})
    initial = status()
    require(initial["Threads"].strip() == "1" and all(
        int(initial[key].strip(), 16) == 0 for key in ("CapInh", "CapAmb")
    ))
    null = os.stat("/dev/null")
    stdin = os.fstat(0)
    require(stat.S_ISCHR(stdin.st_mode) and stdin.st_rdev == null.st_rdev)
    require(all(stat.S_ISFIFO(os.fstat(fd).st_mode) for fd in (1, 2)))

    # No inherited credential, database, socket or directory descriptors survive.
    # /proc enumeration briefly opens its own descriptor, already closed by
    # listdir; ignore only EBADF for that vanished descriptor. The fresh process
    # must be single-threaded and must not install descriptor-opening handlers.
    descriptors = os.listdir("/proc/self/fd")
    require(len(descriptors) <= 256 and all(name.isdecimal() for name in descriptors))
    for name in descriptors:
        fd = int(name)
        if fd > 2:
            try:
                os.close(fd)
            except OSError as error:
                if error.errno != errno.EBADF:
                    raise
    for fd in (0, 1, 2):
        os.set_inheritable(fd, True)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    os.umask(0o077)
    os.chdir("/")
    prctl(38, 1)  # PR_SET_NO_NEW_PRIVS, inherited across exec.
    prctl(8, 0)  # PR_SET_KEEPCAPS: reject retaining permitted caps at UID loss.
    prctl(47, 4)  # PR_CAP_AMBIENT / PR_CAP_AMBIENT_CLEAR_ALL.
    uid, _ = TARGETS[role]
    os.setgroups([])  # Clear before losing CAP_SETGID; never initgroups().
    os.setresgid(uid, uid, uid)
    os.setresuid(uid, uid, uid)
    require(os.getresuid() == (uid,) * 3 and os.getresgid() == (uid,) * 3
            and os.getgroups() == [])
    final = status()
    require(final["NoNewPrivs"].strip() == "1" and all(
        int(final[key].strip(), 16) == 0 for key in ("CapInh", "CapPrm", "CapEff", "CapAmb")
    ))


def main():
    try:
        require(len(sys.argv) == 2 and sys.argv[1] in TARGETS)
        role = sys.argv[1]
        prepare_identity(role)
        # The only exec selectors are source constants. No command, UID, path,
        # module, credential, plan or environment selector is accepted from IPC.
        os.execve(PYTHON, (PYTHON, "-I", "-B", "-m", TARGETS[role][1]), ENV)
        raise ValueError("single_call_identity_unavailable")  # exec must not return.
    except Exception:
        with suppress(OSError):
            os.write(2, ERROR)
        return 1


if __name__ == "__main__":
    sys.exit(main())
