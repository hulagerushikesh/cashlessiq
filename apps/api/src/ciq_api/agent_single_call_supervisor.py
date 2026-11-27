"""One original launch sequence for an independently prepared, exclusive host.

No entry point, process launcher, approval issuer, credential/history writer or
deployment wiring. The trusted host adapter must enforce bounded calls, exclusive
ownership, current consent, exact installed identities and whole-cgroup cleanup.
This coordinator cannot establish those properties from readiness messages.
"""

import math
import re
from dataclasses import dataclass, field
from threading import Lock
from time import monotonic, sleep, time
from typing import Literal, Protocol

Role = Literal["receipt", "provider", "custody"]
ROLES: tuple[Role, ...] = ("receipt", "provider", "custody")
READY = {
    "receipt": b"single_call_receipt_ready\n",
    "provider": b"single_call_provider_ready\n",
    "custody": b"single_call_advisory_published\n",
}
STARTUP_SECONDS = 3.0
TOTAL_SECONDS = 30.0
MAX_GAP_SECONDS = 2.0
CLOCK_DRIFT_SECONDS = 1.0
ERROR = "single_call_supervision_unavailable"


def require(value):
    if not value:
        raise ValueError(ERROR)


@dataclass(frozen=True)
class Observation:
    incarnation: str
    running: bool
    exit_code: int | None
    stdout: bytes = field(repr=False)
    stderr: bytes = field(repr=False)


class PreparedHost(Protocol):
    """Trusted adapter, not an interface exposed to HTTP/IPC or untrusted code.

    check() freshly verifies the exclusive lease and previously staged consent,
    matching private plans, retained history and effective installed containment.
    Every method must be externally bounded. observe() returns cumulative output
    from only the original invocation, bounded to 128 bytes per stream. start()
    must transfer cleanup ownership BEFORE allocation, even if it raises. stop()
    kills/reaps the whole owned cgroup and verifies it empty, including after a
    partially acknowledged start. No method may restart/reset/remove authority.
    """

    def check(self) -> bool: ...
    def quiescent(self, role: Role) -> bool: ...
    def start(self, role: Role) -> str: ...
    def observe(self, role: Role) -> Observation: ...
    def stop(self, role: Role) -> bool: ...


@dataclass(frozen=True)
class SupervisionResult:
    outcome: Literal["published", "unavailable", "quarantined"]
    cleanup_confirmed: bool


class SingleCallSupervisor:
    """Consume once, require both original peers ready, finish all three, stop all.

    A second call never invokes the host, even after a preflight failure. A new
    object is not replay authority: independent SQL/history/host gates remain
    mandatory. Unavailable includes uncertain publication; it never grants retry.
    Clock checks fence delivery but cannot retract an already submitted request.
    """

    def __init__(self, host: PreparedHost):
        self._host = host
        self._lock, self._used = Lock(), False
        self._owned: list[Role] = []
        self._incarnations: dict[Role, str] = {}
        self._outputs: dict[Role, bytes] = {}
        self._last = self._origin = None

    def _sample(self):
        sample = (monotonic(), time())
        require(all(type(v) in (float, int) and math.isfinite(v) for v in sample))
        if self._last is not None:
            require(0 <= sample[0] - self._last[0] <= MAX_GAP_SECONDS
                    and sample[1] >= self._last[1])
            require(abs((sample[0] - self._origin[0])
                        - (sample[1] - self._origin[1])) <= CLOCK_DRIFT_SECONDS)
        else:
            self._origin = sample
        self._last = sample
        require(sample[0] - self._origin[0] < TOTAL_SECONDS)
        return sample[0]

    def _check(self):
        self._sample()
        require(self._host.check() is True)
        return self._sample()

    def _start(self, role):
        self._check()
        # Register the role BEFORE start: a lost start ACK can hide a live cgroup.
        self._owned.append(role)
        incarnation = self._host.start(role)
        require(type(incarnation) is str and re.fullmatch(r"[a-f0-9]{32}", incarnation)
                and incarnation not in self._incarnations.values())
        self._incarnations[role] = incarnation
        self._check()

    def _observe(self, role, *, before_custody=False):
        self._check()
        observation = self._host.observe(role)
        self._check()
        require(type(observation) is Observation
                and observation.incarnation == self._incarnations[role]
                and type(observation.running) is bool
                and type(observation.stdout) is bytes and len(observation.stdout) <= 128
                and type(observation.stderr) is bytes and observation.stderr == b"")
        require(observation.stdout in (b"", READY[role]))
        require(observation.stdout.startswith(self._outputs.get(role, b"")))
        self._outputs[role] = observation.stdout
        if observation.running:
            require(observation.exit_code is None)
        else:
            require(not before_custody and type(observation.exit_code) is int
                    and observation.exit_code == 0 and observation.stdout == READY[role])
        return observation

    def _ready(self, role):
        deadline = self._sample() + STARTUP_SECONDS
        while True:
            # Earlier peers must remain ready and alive while the next starts.
            for previous in self._owned[:-1]:
                require(self._observe(previous, before_custody=True).stdout == READY[previous])
            observation = self._observe(role, before_custody=True)
            require(self._sample() < deadline)
            if observation.stdout == READY[role]:
                return
            sleep(0.02)

    def _cleanup(self):
        clean = True
        # Cleanup must run even when clocks, authorization or the lease failed.
        # It must not delete files, clear failures, rotate credentials or rebind.
        for role in reversed(self._owned):
            try:
                stopped = self._host.stop(role) is True
                quiet = self._host.quiescent(role) is True
                clean = stopped and quiet and clean
            except BaseException:
                clean = False
        return clean

    def run(self):
        with self._lock:
            require(not self._used)
            self._used = True
        published = False
        interrupted = None
        try:
            self._check()
            for role in ROLES:
                require(self._host.quiescent(role) is True)
                self._check()
            for role in ("receipt", "provider"):
                self._start(role)
                self._ready(role)
            for role in ("receipt", "provider"):
                require(self._observe(role, before_custody=True).stdout == READY[role])
            self._start("custody")
            while True:
                states = [self._observe(role) for role in ROLES]
                if all(not state.running for state in states):
                    self._check()
                    published = True
                    break
                sleep(0.02)
        except BaseException as error:
            if not isinstance(error, Exception):
                interrupted = error
        finally:
            clean = self._cleanup()
        if interrupted is not None:
            # Preserve cancellation after attempting every owned cleanup.
            raise interrupted
        return SupervisionResult(
            "quarantined" if not clean else "published" if published else "unavailable", clean,
        )
