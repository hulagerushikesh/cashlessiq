"""Explicit disposable process boundary; no Docker backend or normal activation.

One trusted test command per instance. A separate watcher owns/reaps the actor;
the caller also bounds the watcher and kills its unreaped owned process group.
Closed test actors must not escape that group. Same-host suspension pauses this
mechanism: no external hard-deadline SLA or Docker-resource termination proof.
"""

import json
import os
import select
import signal
import subprocess
import sys
import time
from contextlib import suppress
from pathlib import Path

MAX_FRAME = 32768


class ActorDenied(ValueError):
    def __init__(self):
        super().__init__("Disposable actor denied; outcome unknown")


def _json(data):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ActorDenied()
            value[key] = item
        return value

    def invalid_constant(_):
        raise ActorDenied()

    value = json.loads(data, object_pairs_hook=unique, parse_constant=invalid_constant)
    if type(value) is not dict:
        raise ActorDenied()
    return value


def _line(fd, deadline):
    result = bytearray()
    os.set_blocking(fd, False)
    while time.monotonic_ns() < deadline:
        remaining = (deadline - time.monotonic_ns()) / 1e9
        if remaining <= 0 or not select.select([fd], [], [], remaining)[0]:
            break
        data = os.read(fd, min(4096, MAX_FRAME + 1 - len(result)))
        if not data:
            raise ActorDenied()
        result.extend(data)
        if len(result) > MAX_FRAME:
            raise ActorDenied()
        if b"\n" in result:
            if not result.endswith(b"\n") or result.count(b"\n") != 1:
                raise ActorDenied()
            return _json(result[:-1])
    raise ActorDenied()


def _write(fd, data, deadline):
    os.set_blocking(fd, False)
    offset = 0
    while offset < len(data) and time.monotonic_ns() < deadline:
        remaining = (deadline - time.monotonic_ns()) / 1e9
        if remaining <= 0 or not select.select([], [fd], [], remaining)[1]:
            break
        offset += os.write(fd, data[offset:])
    if offset != len(data):
        raise ActorDenied()


def _terminate(child, grace):
    # Only the original parent reaps this direct child. Group cleanup happens
    # outside, before reaping the watcher/session leader, avoiding PID reuse.
    with suppress(ProcessLookupError):
        child.terminate()
    try:
        child.wait(timeout=grace / 2)
    except subprocess.TimeoutExpired:
        child.kill()
        try:
            child.wait(timeout=grace / 2)
        except subprocess.TimeoutExpired:
            return False
    return child.returncode is not None


def _watch():
    child = None
    report = {"state": "denied", "actor_reaped": False}
    # Initial framing has its own small bound before accepting the caller lease.
    try:
        request = _line(0, time.monotonic_ns() + 2_000_000_000)
        if set(request) != {"command", "deadline", "grace_ns"}:
            raise ActorDenied()
        command, deadline, grace = request["command"], request["deadline"], request["grace_ns"]
        if (
            type(command) is not list
            or not command
            or not os.path.isabs(command[0])
            or any(type(x) is not str or not x or "\0" in x for x in command)
            or type(deadline) is not int
            or not 0 < deadline - time.monotonic_ns() <= 10_000_000_000
            or type(grace) is not int
            or not 50_000_000 <= grace <= 2_000_000_000
        ):
            raise ActorDenied()
        child = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env={},
            close_fds=True,
        )
        value = _line(child.stdout.fileno(), deadline)
        remaining = (deadline - time.monotonic_ns()) / 1e9
        if remaining <= 0:
            raise ActorDenied()
        child.wait(timeout=remaining)  # Printing a result then blocking cannot escape.
        if os.read(child.stdout.fileno(), 1):
            raise ActorDenied()  # Any bytes after the single frame are forbidden.
        if child.returncode != 0 or time.monotonic_ns() >= deadline:
            raise ActorDenied()
        report = dict(state="completed", actor_reaped=True, value=value)
    except Exception:
        if child is not None:
            report["actor_reaped"] = _terminate(child, request["grace_ns"] / 1e9)
    finally:
        if child is not None:
            child.stdout.close()
    # No actor stdout/error detail is reported on denial.
    payload = json.dumps(report, separators=(",", ":")).encode() + b"\n"
    _write(1, payload, time.monotonic_ns() + 500_000_000)
    # Keep the owned group leader alive until the caller kills/reaps it. macOS
    # may return EPERM for a group containing only an already-exited leader.
    while True:
        signal.pause()


class BoundedActor:
    """Inactive until execute; one use even on success, no implicit retry/queue."""

    def __init__(self, command, *, budget_ns, grace_ns):
        if (
            type(command) is not tuple
            or not command
            or not os.path.isabs(command[0])
            or any(type(x) is not str or not x or "\0" in x for x in command)
            or type(budget_ns) is not int
            or not 100_000_000 <= budget_ns <= 10_000_000_000
            or type(grace_ns) is not int
            or not 50_000_000 <= grace_ns <= 2_000_000_000
        ):
            raise ActorDenied()
        if len(json.dumps(command).encode()) > 8192:
            raise ActorDenied()
        self.command, self.budget_ns, self.grace_ns = command, budget_ns, grace_ns
        self.used, self.fenced, self.actor_reaped, self.watcher_reaped = False, False, False, False

    def execute(self):
        if self.used or os.name != "posix" or signal.getsignal(signal.SIGCHLD) != signal.SIG_DFL:
            raise ActorDenied()
        self.used = True
        child = None
        result = None
        deadline = time.monotonic_ns() + self.budget_ns
        outer = deadline + self.grace_ns + 1_000_000_000
        try:
            child = subprocess.Popen(
                [sys.executable, "-I", str(Path(__file__).resolve()), "--watch"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env={},
                start_new_session=True,
                close_fds=True,
            )
            request = dict(command=self.command, deadline=deadline, grace_ns=self.grace_ns)
            _write(child.stdin.fileno(), json.dumps(request).encode() + b"\n", deadline)
            child.stdin.close()
            report = _line(child.stdout.fileno(), outer)
            self.actor_reaped = report.get("actor_reaped") is True
            if (
                set(report) != {"state", "actor_reaped", "value"}
                or report["state"] != "completed"
                or not self.actor_reaped
                or time.monotonic_ns() >= deadline
                or type(report["value"]) is not dict
            ):
                raise ActorDenied()
            result = report["value"]
        except Exception:
            self.fenced = True
        finally:
            if child is not None:
                # The watcher is an unreaped owned session leader: its PID cannot
                # have been recycled into an unrelated process group here.
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except OSError:
                    self.fenced = True  # No raw syscall error or false cleanup claim.
                    with suppress(OSError):
                        child.kill()  # Direct owned watcher only; group outcome stays unknown.
                try:
                    child.wait(timeout=self.grace_ns / 1e9)
                    self.watcher_reaped = True
                except subprocess.TimeoutExpired:
                    self.fenced = True
                if not child.stdin.closed:
                    child.stdin.close()
                child.stdout.close()
            if result is None:
                self.fenced = True
        if self.fenced or not self.watcher_reaped or result is None:
            raise ActorDenied()
        return result


if __name__ == "__main__":
    if sys.argv[1:] != ["--watch"]:
        raise ActorDenied()
    _watch()
