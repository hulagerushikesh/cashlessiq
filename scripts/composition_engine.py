"""Opt-in bounded Docker CLI transport for disposable composition only.

No discovery, default context, shell, credential inheritance, retry, provisioning
or normal application activation. The trusted owner supplies a closed command
inventory; launcher/journal checks still own resource identity and intentions.
Killing a CLI process NEVER proves its daemon-side mutation did not complete.
"""

import importlib.util
import json
import os
import re
import select
import stat
import subprocess
import sys
import time
from pathlib import Path

if __package__:
    from .bounded_composition_actor import MAX_FRAME, ActorDenied, BoundedActor
else:
    # -I disables repository/sys.path discovery. Load only this fixed sibling.
    _spec = importlib.util.spec_from_file_location(
        "ciq_engine_actor", Path(__file__).with_name("bounded_composition_actor.py")
    )
    _actor = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_actor)
    MAX_FRAME, ActorDenied, BoundedActor = _actor.MAX_FRAME, _actor.ActorDenied, _actor.BoundedActor


def _readonly(args):
    return args[:1] == ("inspect",) or args[:2] in {
        ("image", "inspect"),
        ("network", "inspect"),
        ("network", "ls"),
        ("volume", "inspect"),
        ("volume", "ls"),
        ("container", "ls"),
    }


def _supported(args):
    return (
        _readonly(args)
        or args[:1] in {("create",), ("start",), ("stop",)}
        or args[:2] in {("network", "connect"), ("network", "create"), ("volume", "create")}
    )


class Engine:
    """Explicit finite commands; admission mutations latch shut on any uncertainty.

    Independent bounded inspection/stop remain available for owner containment.
    Caller must reserve cleanup time inside its overall invocation deadline.
    This is trusted test-owner policy, not an arbitrary-command security sandbox.
    """

    def __init__(self, *, binary, socket, config, commands, deadline_ns, budget_ns=2_000_000_000):
        if (
            type(binary) is not str
            or not os.path.isabs(binary)
            or type(socket) is not str
            or not os.path.isabs(socket)
            or not isinstance(config, Path)
            or not config.is_absolute()
            or type(commands) is not tuple
            or not commands
            or len(commands) > 512
            or any(
                type(args) is not tuple
                or len(args) < 2
                or any(type(x) is not str or not x or "\0" in x for x in args)
                or not _supported(args)
                for args in commands
            )
            or type(deadline_ns) is not int
            or not 0 < deadline_ns - time.monotonic_ns() <= 900_000_000_000
            or type(budget_ns) is not int
            or not 100_000_000 <= budget_ns <= 10_000_000_000
        ):
            raise ActorDenied()
        self.binary, self.socket, self.config = binary, socket, config
        self.commands = frozenset(commands)
        self.deadline_ns, self.budget_ns = deadline_ns, budget_ns
        self.fenced = False
        self.incarnations = set()

    def permit_incarnation(self, cid):
        """Allow a returned full ID only in predeclared final-ID command slots.

        This does not attest ownership or authorize a journal observation/stop.
        The launcher must still validate exact owner/attempt metadata. No I/O.
        """
        if type(cid) is not str or re.fullmatch("[a-f0-9]{64}", cid) is None:
            self.fenced = True
            raise ActorDenied()
        if cid not in self.incarnations and len(self.incarnations) >= 8:
            self.fenced = True
            raise ActorDenied()
        self.incarnations.add(cid)

    def __call__(self, *args):
        try:
            exact = args in self.commands and "{incarnation}" not in args
            registered = (
                len(args) >= 2
                and (args[0] in {"inspect", "start", "stop"} or args[:2] == ("network", "connect"))
                and args[-1] in self.incarnations
                and (*args[:-1], "{incarnation}") in self.commands
            )
            if not (exact or registered) or (
                self.fenced and not (_readonly(args) or args[0] == "stop")
            ):
                raise ActorDenied()
            # Explicit empty private Docker configuration: no ambient contexts,
            # credential helpers, TLS config or CLI plugins. Owner paths are
            # trusted; this snapshot is not hostile same-UID exclusion.
            info = self.config.lstat()
            if (
                not stat.S_ISDIR(info.st_mode)
                or stat.S_IMODE(info.st_mode) != 0o700
                or info.st_uid != os.getuid()
                or any(self.config.iterdir())
                or not stat.S_ISSOCK(os.stat(self.socket).st_mode)
            ):
                raise ActorDenied()
            # Reserve the actor's worst-case cleanup/report overhead BEFORE I/O.
            budget = min(self.budget_ns, self.deadline_ns - time.monotonic_ns() - 2_000_000_000)
            task = BoundedActor(
                (
                    sys.executable,
                    "-I",
                    str(Path(__file__).resolve()),
                    "--command",
                    self.binary,
                    "--host",
                    "unix://" + self.socket,
                    "--config",
                    str(self.config),
                    *args,
                ),
                budget_ns=budget,
                grace_ns=300_000_000,
            )
            value = task.execute()
            if set(value) != {"output"} or type(value["output"]) is not str:
                raise ActorDenied()
            return value["output"]
        except Exception:
            self.fenced = True
            raise ActorDenied() from None


def _command(command):
    """Closed child under the actor-owned group, never start a new session.

    BoundedActor bounds time/exit and kills the WHOLE owned group. Bound output
    here as well, so a CLI flood cannot allocate unbounded owner memory.
    """
    child = None
    try:
        child = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env={},
            close_fds=True,
        )
        data = bytearray()
        while True:
            select.select([child.stdout], [], [])
            chunk = os.read(child.stdout.fileno(), 4096)
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > MAX_FRAME // 2:
                raise ActorDenied()
        if child.wait() != 0:
            raise ActorDenied()
        frame = json.dumps({"output": data.decode("utf-8")}, separators=(",", ":")).encode() + b"\n"
        if len(frame) > MAX_FRAME - 1024:
            raise ActorDenied()
        sys.stdout.buffer.write(frame)
        sys.stdout.buffer.flush()
        return 0
    except Exception:
        return 2  # No raw Docker output/error on denial.
    finally:
        if child is not None:
            child.stdout.close()
        # The parent watcher owns group cancellation/reaping even if this helper
        # failed while Docker is still running. Do not claim daemon cleanup.


if __name__ == "__main__":
    raise SystemExit(_command(sys.argv[2:]) if sys.argv[1:2] == ["--command"] else 2)
