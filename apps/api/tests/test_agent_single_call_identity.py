"""Offline identity transition failures and fixed exec wiring; no privilege use."""

import errno
import stat
from types import SimpleNamespace

import pytest

from ciq_api import agent_single_call_identity as identity


@pytest.fixture
def process(monkeypatch):
    calls = []
    state = SimpleNamespace(uid=0, gid=0, groups=[0, 777], final_fault=None, threads="1")

    def record(name, *values):
        calls.append((name, *values))

    def setuid(*values):
        record("uid", *values)
        state.uid = values[0]

    def setgid(*values):
        record("gid", *values)
        state.gid = values[0]

    def groups(values):
        record("groups", values)
        state.groups = values

    def status():
        result = dict.fromkeys(("CapInh", "CapPrm", "CapEff", "CapAmb"), "0")
        result.update(Threads=state.threads, NoNewPrivs="1")
        if state.uid and state.final_fault:
            result[state.final_fault] = "1" if state.final_fault != "NoNewPrivs" else "0"
        return result

    process_os = SimpleNamespace(
        environ={"LANG": "C.UTF-8"}, getresuid=lambda: (state.uid,) * 3,
        getresgid=lambda: (state.gid,) * 3, getgroups=lambda: state.groups,
        stat=lambda _: SimpleNamespace(st_rdev=259),
        fstat=lambda fd: SimpleNamespace(st_mode=stat.S_IFCHR if fd == 0 else stat.S_IFIFO,
                                       st_rdev=259),
        listdir=lambda _: ["0", "1", "2", "9"], close=lambda fd: record("close", fd),
        set_inheritable=lambda *args: record("inherit", *args),
        umask=lambda value: record("umask", value), chdir=lambda value: record("cwd", value),
        setgroups=groups, setresgid=setgid, setresuid=setuid,
        execve=lambda *args: record("exec", *args), write=lambda *args: record("write", *args),
    )
    monkeypatch.setattr(identity, "os", process_os)
    monkeypatch.setattr(identity, "sys", SimpleNamespace(
        platform="linux", flags=SimpleNamespace(isolated=1), dont_write_bytecode=True,
        argv=["fixed-entry", "custody"],
    ))
    monkeypatch.setattr(identity, "status", status)
    monkeypatch.setattr(identity, "prctl", lambda *args: record("prctl", *args))
    monkeypatch.setattr(identity, "resource", SimpleNamespace(
        RLIMIT_CORE=4, RLIMIT_NOFILE=7, setrlimit=lambda *args: record("limit", *args),
    ))
    return SimpleNamespace(calls=calls, state=state, os=process_os)


@pytest.mark.parametrize("role,uid", [("custody", 53002), ("receipt", 53003), ("provider", 53004)])
def test_closes_inherited_authority_before_permanent_group_and_uid_loss(process, role, uid):
    identity.prepare_identity(role)
    assert process.calls == [
        ("close", 9), ("inherit", 0, True), ("inherit", 1, True), ("inherit", 2, True),
        ("limit", 4, (0, 0)), ("limit", 7, (64, 64)), ("umask", 0o077), ("cwd", "/"),
        ("prctl", 38, 1), ("prctl", 8, 0), ("prctl", 47, 4),
        ("groups", []), ("gid", uid, uid, uid), ("uid", uid, uid, uid),
    ]


@pytest.mark.parametrize("role", [None, True, 53002, "root", "claim", "custody --retry", "../x"])
def test_role_selectors_denied_before_process_changes(process, role):
    with pytest.raises(ValueError):
        identity.prepare_identity(role)
    assert process.calls == []


@pytest.mark.parametrize("fault", ["platform", "isolated", "bytecode", "uid", "gid", "env",
                                   "threads", "stdin", "stdout", "fd-count"])
def test_untrusted_initial_state_is_denied_before_privilege_transition(process, fault):
    if fault == "platform":
        identity.sys.platform = "darwin"
    elif fault == "isolated":
        identity.sys.flags.isolated = 0
    elif fault == "bytecode":
        identity.sys.dont_write_bytecode = False
    elif fault in ("uid", "gid"):
        setattr(process.state, fault, 53002)
    elif fault == "env":
        process.os.environ["PGPASSWORD"] = "PRIVATE"
    elif fault == "threads":
        process.state.threads = "2"
    elif fault in ("stdin", "stdout"):
        fd = 0 if fault == "stdin" else 1
        original = process.os.fstat
        process.os.fstat = lambda n: (
            SimpleNamespace(st_mode=stat.S_IFREG) if n == fd else original(n)
        )
    else:
        process.os.listdir = lambda _: [str(n) for n in range(257)]
    with pytest.raises(ValueError):
        identity.prepare_identity("custody")
    assert process.calls == []


@pytest.mark.parametrize("capability", ["CapInh", "CapPrm", "CapEff", "CapAmb", "NoNewPrivs"])
def test_residual_privilege_cannot_reach_exec(process, capability):
    process.state.final_fault = capability
    assert identity.main() == 1
    assert not any(call[0] == "exec" for call in process.calls)
    assert process.calls[-1] == ("write", 2, identity.ERROR)


@pytest.mark.parametrize("err", [errno.EBADF, errno.EIO])
def test_only_vanished_proc_descriptor_is_ignored(process, err):
    process.os.close = lambda _: (_ for _ in ()).throw(OSError(err, "PRIVATE diagnostic"))
    if err == errno.EBADF:
        identity.prepare_identity("custody")
        assert process.state.uid == 53002
    else:
        assert identity.main() == 1
        assert process.calls == [("write", 2, identity.ERROR)]


@pytest.mark.parametrize("operation", ["setgroups", "setresgid", "setresuid"])
def test_partial_transition_failure_is_terminal_with_fixed_output(process, operation):
    setattr(process.os, operation,
            lambda *args: (_ for _ in ()).throw(PermissionError("PRIVATE diagnostic")))
    assert identity.main() == 1
    assert not any(call[0] == "exec" for call in process.calls)
    assert process.calls[-1] == ("write", 2, identity.ERROR)


@pytest.mark.parametrize("role", ["custody", "receipt", "provider"])
def test_exec_has_only_fixed_interpreter_module_and_clean_environment(process, role):
    identity.sys.argv[1] = role

    class Replaced(BaseException):
        pass

    def execve(path, args, env):
        assert process.state.uid == identity.TARGETS[role][0]
        assert path == identity.PYTHON
        assert args == (path, "-I", "-B", "-m", identity.TARGETS[role][1])
        assert env == {"LANG": "C.UTF-8"}
        raise Replaced

    process.os.execve = execve
    with pytest.raises(Replaced):
        identity.main()


@pytest.mark.parametrize("args", [[], ["entry"], ["entry", "root"],
                                  ["entry", "custody", "--retry"]])
def test_main_rejects_additional_or_unknown_selectors(process, args):
    identity.sys.argv = args
    assert identity.main() == 1
    assert process.calls == [("write", 2, identity.ERROR)]


def test_exec_return_never_reports_success(process):
    assert identity.main() == 1
    assert process.calls[-1] == ("write", 2, identity.ERROR)


@pytest.mark.parametrize("result", [-1, 0])
def test_prctl_uses_complete_fixed_abi_and_checks_syscall_result(monkeypatch, result):
    calls = []

    class Call:
        def __call__(self, *args):
            calls.append(args)
            return result

    call = Call()
    monkeypatch.setattr(identity.ctypes, "CDLL", lambda *args, **kwargs:
                        SimpleNamespace(prctl=call))
    if result == 0:
        identity.prctl(38, 1)
    else:
        with pytest.raises(ValueError):
            identity.prctl(38, 1)
    assert calls == [(38, 1, 0, 0, 0)] and len(call.argtypes) == 5
