"""Test-only Linux process containment. Never imported by application startup."""

from __future__ import annotations

import ctypes
import json
import os
import select
import signal
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

from offline_supervisor import (
    ROLES,
    Limits,
    OfflineSupervisor,
    Ready,
    Sample,
    Service,
    State,
    SupervisorDenied,
)


def elapsed():
    return time.clock_gettime_ns(time.CLOCK_BOOTTIME)


def command(*arguments):
    return [
        sys.executable,
        "-I",
        "-c",
        "import sys,runpy; sys.path.insert(0,'/probe'); "
        "runpy.run_path('/probe/supervisor_probe.py',run_name='__main__')",
        *arguments,
    ]


def denied(callback):
    try:
        callback()
    except SupervisorDenied:
        return
    raise AssertionError("Expected supervisor denial")


def line(process, timeout=3):
    if not select.select([process.stdout], [], [], timeout)[0]:
        raise AssertionError("Test child readiness timed out")
    value = process.stdout.readline(256)
    if not value or len(value) >= 256:
        raise AssertionError("Invalid test child readiness")
    return value.strip()


class OwnedProcess:
    def __init__(self, stubborn=False):
        self.incarnation = uuid4().hex
        self.escalated = False
        self.process = subprocess.Popen(
            command("child", "stubborn" if stubborn else "normal"),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            env={},
            text=True,
        )

    def stop(self, grace_ns):
        p = self.process
        if p.poll() is None:
            os.killpg(p.pid, signal.SIGTERM)
            try:
                p.wait(timeout=min(grace_ns / 2e9, 0.1))
            except subprocess.TimeoutExpired:
                self.escalated = True
                os.killpg(p.pid, signal.SIGKILL)
                p.wait(timeout=max(grace_ns / 2e9, 0.001))
        p.stdout.close()
        return p.returncode is not None


class TestApproval:
    """Disposable approval only; not durable activation authority."""

    def __init__(self):
        self.active = None

    def take(self, binding):
        if self.active is not None:
            return False
        self.active = binding
        return True

    def current(self, binding):
        return binding == self.active

    def recovery(self, *_):
        return False


class Harness:
    def __init__(self, fail_at=None):
        self.owned = []
        self.jobs = {}
        self.delivered = []
        self.fail_at = fail_at
        self.cancel_confirmed = True
        self.services = tuple(
            Service(r, "test-generation", "a" * 64, "b" * 64, None if r == "membership" else r)
            for r in sorted(ROLES)
        )
        self.controller = OfflineSupervisor(
            self.services,
            Limits(10_000_000_000, 50_000_000, 3_000_000_000, 30_000_000_000, 2, 64),
            "test-boot",
            approval=TestApproval(),
            verify=lambda services: services == self.services,
            launch=self.launch,
            clock=lambda: Sample("test-boot", elapsed()),
            cancel=self.cancel,
            deliver=self.delivered.append,
        )

    def launch(self, _service, _binding):
        if len(self.owned) == self.fail_at:
            raise ValueError("Injected partial startup failure")
        p = OwnedProcess()
        self.owned.append(p)  # Own before any readiness I/O can fail.
        assert line(p.process) == "ready"
        return p

    def cancel(self, operation, grace_ns):
        assert self.controller.state in (State.DRAINING, State.FENCED)
        if not self.cancel_confirmed:
            return False
        return self.jobs[operation.identifier].stop(grace_ns)

    def start(self):
        c = self.controller
        binding = c.start("test-attempt")
        for service, process in zip(self.services, self.owned, strict=True):
            denied(c.admit)
            assert process.process.poll() is None
            c.acknowledge(Ready(binding, service, process.incarnation))
        assert c.state is State.READY

    def job(self):
        operation = self.controller.admit()
        p = OwnedProcess(stubborn=True)
        self.jobs[operation.identifier] = p
        assert line(p.process) == "ready"
        return operation, p

    def cleanup(self):
        self.controller.stop()
        for p in [*self.owned, *self.jobs.values()]:
            assert p.stop(3_000_000_000)
            assert not Path(f"/proc/{p.process.pid}").exists()


def lifecycle():
    h = Harness()
    try:
        h.start()
        first = h.controller.admit()
        h.controller.complete(first)
        denied(lambda: h.controller.complete(first))
        late, p = h.job()
        # Actual elapsed time, not a fabricated clock jump.
        time.sleep(0.07)
        denied(lambda: h.controller.complete(late))
        assert p.escalated and p.process.returncode == -signal.SIGKILL
        assert h.controller.active_count == 0
        assert h.delivered == [first]
        stopped, _ = h.job()
        h.controller.stop()
        assert h.controller.state is State.STOPPED
        denied(lambda: h.controller.complete(stopped))
        denied(h.controller.admit)
        assert h.delivered == [first]
    finally:
        h.cleanup()


def partial_start():
    h = Harness(fail_at=3)
    try:
        denied(h.start)
        assert h.controller.state is State.FENCED
        assert len(h.owned) == 3
        assert all(p.process.returncode is not None for p in h.owned)
        denied(h.controller.admit)
    finally:
        h.cleanup()


def readiness_loss():
    h = Harness()
    try:
        h.start()
        operation, _ = h.job()
        h.controller.readiness_lost()
        assert h.controller.state is State.FENCED
        denied(lambda: h.controller.complete(operation))
        assert h.delivered == []
    finally:
        h.cleanup()


def unknown_termination():
    h = Harness()
    try:
        h.start()
        operation, p = h.job()
        h.cancel_confirmed = False
        time.sleep(0.07)
        denied(lambda: h.controller.complete(operation))
        assert h.controller.state is State.FENCED
        assert h.controller.active_count == 1
        assert p.process.poll() is None
        denied(h.controller.admit)
        assert h.delivered == []
        h.cancel_confirmed = True
        h.controller.stop()
        assert p.process.returncode == -signal.SIGKILL
        assert h.controller.state is State.FENCED
        denied(h.controller.admit)
    finally:
        h.cleanup()


def watchdog(pgid, fd):
    # Separate OS process: a blocked controller cannot prevent this timeout.
    # Same-host suspension pauses this watchdog too; no external hard-bound claim.
    try:
        select.select([fd], [], [], 0.5)
        os.killpg(pgid, signal.SIGTERM)
        time.sleep(0.1)
        os.killpg(pgid, signal.SIGKILL)
        print("escalated", flush=True)
    finally:
        os.close(fd)


def blocked_controller():
    # Adopt/reap the actor's descendant after killing the whole owned group.
    assert ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) == 0
    actor = subprocess.Popen(
        command("actor"),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        env={},
        text=True,
    )
    watcher = None
    read_fd, write_fd = os.pipe()
    child_pid = None
    try:
        child_pid = int(line(actor))
        watcher = subprocess.Popen(
            command("watchdog", str(actor.pid), str(read_fd)),
            pass_fds=(read_fd,),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env={},
            text=True,
        )
        os.close(read_fd)
        read_fd = None
        assert watcher.communicate(timeout=3)[0].strip() == "escalated"
        assert watcher.returncode == 0
        assert actor.wait(timeout=3) == -signal.SIGKILL
        end = elapsed() + 3_000_000_000
        while elapsed() < end:
            pid, status = os.waitpid(child_pid, os.WNOHANG)
            if pid:
                assert os.waitstatus_to_exitcode(status) == -signal.SIGKILL
                break
            time.sleep(0.01)
        else:
            raise AssertionError("Descendant termination not confirmed")
        assert not Path(f"/proc/{child_pid}").exists()
        assert not Path(f"/proc/{actor.pid}").exists()
    finally:
        if read_fd is not None:
            os.close(read_fd)
        os.close(write_fd)
        if actor.poll() is None:
            os.killpg(actor.pid, signal.SIGKILL)
            actor.wait(timeout=3)
        actor.stdout.close()
        if watcher is not None:
            if watcher.poll() is None:
                watcher.kill()
                watcher.wait(timeout=3)
            watcher.stdout.close()


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "probe"
    if mode == "child":
        if sys.argv[2] == "stubborn":
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
        print("ready", flush=True)
        while True:
            signal.pause()
    elif mode == "actor":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)

        class BlockedLaunch(Harness):
            def launch(self, _service, _binding):
                # This child deliberately shares the owned actor's process group.
                # Block INSIDE a real supervisor callback before returning a handle.
                p = subprocess.Popen(
                    command("child", "stubborn"),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    env={},
                    text=True,
                )
                assert line(p) == "ready"
                print(p.pid, flush=True)
                while True:
                    signal.pause()

        BlockedLaunch().controller.start("blocked-attempt")
    elif mode == "watchdog":
        watchdog(int(sys.argv[2]), int(sys.argv[3]))
    elif mode == "probe":
        for case in (
            lifecycle,
            partial_start,
            readiness_loss,
            unknown_termination,
            blocked_controller,
        ):
            case()
            print(json.dumps({"case": case.__name__, "status": "PASS"}), flush=True)
    else:
        raise ValueError("Unknown test mode")


if __name__ == "__main__":
    main()
