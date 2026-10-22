"""Inactive, single-threaded lifecycle model. Injected fake adapters only.

No entry point, process launcher, credential access, durable fence or application
wiring. Callback budgets are modeled inputs, not enforced execution deadlines.
Adapters must not reenter the controller; real containment needs separate review.
"""

from __future__ import annotations

import re
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from typing import Protocol

ROLES = frozenset(
    {"broker", "membership"}
    | {f"reader-{tenant}-{kind}" for tenant in (0, 1) for kind in ("clinical", "nonclinical")}
    | {f"validator-{tenant}" for tenant in (0, 1)}
)
MAX_NS = 2**63 - 1


class SupervisorDenied(ValueError):
    def __init__(self):
        super().__init__("Offline supervisor denied")


class State(StrEnum):
    STOPPED = "STOPPED"
    VERIFYING = "VERIFYING"
    STARTING = "STARTING"
    READY = "READY"
    DRAINING = "DRAINING"
    FENCED = "FENCED"


def _name(value: object) -> bool:
    return type(value) is str and re.fullmatch(r"[a-z0-9-]{1,64}", value) is not None


def _integer(value: object, minimum: int = 0) -> bool:
    return type(value) is int and minimum <= value <= MAX_NS


@dataclass(frozen=True)
class Service:
    role: str
    generation: str
    artifact: str
    configuration: str
    authority_state: str | None


def inventory(services: tuple[Service, ...]) -> str:
    """Validate identifiers only; never open or initialize an authority state."""
    if (
        type(services) is not tuple
        or len(services) != 8
        or any(type(s) is not Service for s in services)
    ):
        raise SupervisorDenied()
    if {s.role for s in services if type(s.role) is str} != ROLES:
        raise SupervisorDenied()
    generations = set()
    states = []
    rows = []
    for s in sorted(services, key=lambda s: s.role):
        if not _name(s.generation) or any(
            type(v) is not str or re.fullmatch(r"[a-f0-9]{64}", v) is None
            for v in (s.artifact, s.configuration)
        ):
            raise SupervisorDenied()
        if s.role == "membership":
            if s.authority_state is not None:
                raise SupervisorDenied()
        elif not _name(s.authority_state):
            raise SupervisorDenied()
        else:
            states.append(s.authority_state)
        generations.add(s.generation)
        rows.append(
            "|".join((s.role, s.generation, s.artifact, s.configuration, s.authority_state or ""))
        )
    if len(generations) != 1 or len(set(states)) != 7:
        raise SupervisorDenied()
    return sha256("\n".join(rows).encode()).hexdigest()


@dataclass(frozen=True)
class Limits:
    startup_ns: int
    operation_ns: int
    stop_grace_ns: int
    max_gap_ns: int
    capacity: int
    audit_capacity: int

    def __post_init__(self):
        if any(not _integer(v, 1) for v in vars(self).values()):
            raise SupervisorDenied()
        if self.operation_ns > 30_000_000_000 or self.audit_capacity > 4096:
            raise SupervisorDenied()


@dataclass(frozen=True)
class Sample:
    domain: str
    elapsed_ns: int


@dataclass(frozen=True)
class Binding:
    attempt: str
    generation: str
    fingerprint: str


@dataclass(frozen=True)
class Ready:
    binding: Binding
    service: Service
    incarnation: str


@dataclass(frozen=True)
class Operation:
    binding: Binding
    identifier: str
    deadline_ns: int


class Process(Protocol):
    @property
    def incarnation(self) -> str: ...
    def stop(self, grace_ns: int) -> bool: ...


class Approval(Protocol):
    """Fake external authority; take consumes a fresh approval, current rechecks it."""

    def take(self, binding: Binding) -> bool: ...
    def current(self, binding: Binding) -> bool: ...
    def recovery(self, old: Binding, new_generation: str, fingerprint: str) -> bool: ...


class OfflineSupervisor:
    """Deterministic test controller, not a runtime or a cryptographic authority.

    Public methods require serialized, non-reentrant use. Result delivery carries
    only an opaque operation receipt, never raw source data or a capability.
    """

    def __init__(
        self,
        services: tuple[Service, ...],
        limits: Limits,
        domain: str,
        *,
        approval: Approval,
        verify: Callable[[tuple[Service, ...]], bool],
        launch: Callable[[Service, Binding], Process],
        clock: Callable[[], Sample],
        cancel: Callable[[Operation, int], bool],
        deliver: Callable[[Operation], None],
    ):
        if type(limits) is not Limits or not _name(domain):
            raise SupervisorDenied()
        self._services = services
        self._limits, self._domain = limits, domain
        self._approval, self._verify, self._launch = approval, verify, launch
        self._clock, self._cancel, self._deliver = clock, cancel, deliver
        self._state = State.STOPPED
        self._binding: Binding | None = None
        self._handles: dict[str, Process] = {}
        self._incarnations: dict[str, str] = {}
        self._ready: set[str] = set()
        self._operations: dict[str, Operation] = {}
        self._last: int | None = None
        self._startup_deadline = 0
        self._counter = 0
        self._attempts: set[str] = set()
        self._audit: deque[tuple[str, str, str, str, str]] = deque(maxlen=limits.audit_capacity)

    @property
    def state(self) -> State:
        return self._state

    @property
    def binding(self) -> Binding | None:
        return self._binding

    @property
    def active_count(self) -> int:
        return len(self._operations)

    @property
    def audit(self) -> tuple[tuple[str, str, str, str, str], ...]:
        return tuple(self._audit)

    def _event(self, reason: str, *, role: str = "", operation: str = "") -> None:
        b = self._binding
        self._audit.append(
            (b.attempt if b else "", b.generation if b else "", role, operation, reason)
        )

    def _sample(self) -> int:
        s = self._clock()
        if type(s) is not Sample or s.domain != self._domain or not _integer(s.elapsed_ns):
            raise SupervisorDenied()
        if self._last is not None and not 0 <= s.elapsed_ns - self._last <= self._limits.max_gap_ns:
            raise SupervisorDenied()
        self._last = s.elapsed_ns
        return s.elapsed_ns

    def _deadline(self, now: int, delta: int) -> int:
        if now > MAX_NS - delta:
            raise SupervisorDenied()
        return now + delta

    def _cleanup(self) -> bool:
        """Close delivery before callbacks; retain every unconfirmed ownership handle."""
        if not self._operations and not self._handles:
            self._ready.clear()
            return True
        clean = True
        deadline = None
        try:
            deadline = self._deadline(self._sample(), self._limits.stop_grace_ns)
        except Exception:
            clean = False
        for op in tuple(self._operations.values()):
            try:
                stopped = self._cancel(op, self._limits.stop_grace_ns) is True
            except Exception:
                stopped = False
            if stopped:
                self._operations.pop(op.identifier, None)
            else:
                clean = False
        for role, handle in tuple(self._handles.items()):
            try:
                stopped = handle.stop(self._limits.stop_grace_ns) is True
            except Exception:
                stopped = False
            if stopped:
                del self._handles[role]
            else:
                clean = False
        self._ready.clear()
        try:
            if deadline is None or self._sample() >= deadline:
                clean = False
        except Exception:
            clean = False
        return clean

    def _fence(self) -> None:
        self._state = State.FENCED
        self._event("fenced")
        self._cleanup()

    def start(self, attempt: str) -> Binding:
        if self._state is not State.STOPPED or not _name(attempt) or attempt in self._attempts:
            raise SupervisorDenied()
        # Bounded lifetime for this model instance; never forget an old attempt.
        if len(self._attempts) >= 4096:
            raise SupervisorDenied()
        self._attempts.add(attempt)
        self._state = State.VERIFYING
        try:
            fingerprint = inventory(self._services)
            self._binding = Binding(attempt, self._services[0].generation, fingerprint)
            if self._approval.take(self._binding) is not True:
                raise SupervisorDenied()
            if self._verify(self._services) is not True:
                raise SupervisorDenied()
            now = self._sample()
            self._startup_deadline = self._deadline(now, self._limits.startup_ns)
            self._state = State.STARTING
            self._incarnations.clear()
            for service in self._services:
                handle = self._launch(service, self._binding)
                # Own the handle BEFORE inspecting any fallible property.
                self._handles[service.role] = handle
                incarnation = handle.incarnation
                if not _name(incarnation) or incarnation in self._incarnations.values():
                    raise SupervisorDenied()
                self._incarnations[service.role] = incarnation
                self._check()
            self._event("started")
            return self._binding
        except Exception:
            # A raising launcher may hide a partially allocated resource; even
            # successful cleanup of known handles must not silently enable retry.
            self._fence()
            raise SupervisorDenied() from None

    def _check(self) -> int:
        try:
            if self._state not in (State.STARTING, State.READY):
                raise SupervisorDenied()
            now = self._sample()
            if self._approval.current(self._binding) is not True:
                raise SupervisorDenied()
            now = self._sample()
            if self._state is State.STARTING and now >= self._startup_deadline:
                raise SupervisorDenied()
            return now
        except Exception:
            if self._state in (State.STARTING, State.READY):
                self._fence()
            raise SupervisorDenied() from None

    def acknowledge(self, ready: Ready) -> None:
        self._check()
        if (
            self._state is not State.STARTING
            or type(ready) is not Ready
            or ready.binding != self._binding
            or ready.service not in self._services
            or ready.service.role in self._ready
            or ready.incarnation != self._incarnations.get(ready.service.role)
        ):
            raise SupervisorDenied()
        self._ready.add(ready.service.role)
        self._event("ready-ack", role=ready.service.role)
        if self._ready == ROLES:
            self._state = State.READY
            self._event("ready")

    def admit(self) -> Operation:
        now = self.poll()
        if self._state is not State.READY or len(self._operations) >= self._limits.capacity:
            raise SupervisorDenied()
        try:
            deadline = self._deadline(now, self._limits.operation_ns)
        except SupervisorDenied:
            self._fence()
            raise
        self._counter += 1
        op = Operation(self._binding, f"operation-{self._counter}", deadline)
        self._operations[op.identifier] = op
        self._event("admitted", operation=op.identifier)
        return op

    def poll(self) -> int:
        now = self._check()
        for op in tuple(self._operations.values()):
            if now >= op.deadline_ns:
                # Remove delivery eligibility before requesting cancellation.
                # Unknown termination retains the execution slot and fences all.
                self._state = State.DRAINING
                try:
                    cancel_deadline = self._deadline(now, self._limits.stop_grace_ns)
                    stopped = self._cancel(op, self._limits.stop_grace_ns) is True
                    if self._sample() >= cancel_deadline:
                        stopped = False
                except Exception:
                    stopped = False
                if not stopped:
                    self._fence()
                    raise SupervisorDenied()
                del self._operations[op.identifier]
                self._event("expired", operation=op.identifier)
                self._state = State.READY
                now = self._check()
        return now

    def complete(self, operation: Operation) -> None:
        self.poll()
        if (
            self._state is not State.READY
            or type(operation) is not Operation
            or self._operations.get(operation.identifier) is not operation
            or operation.binding != self._binding
        ):
            raise SupervisorDenied()
        # Retire once before callback; delivery failure never causes a retry.
        del self._operations[operation.identifier]
        try:
            self._deliver(operation)
        except Exception:
            self._fence()
            raise SupervisorDenied() from None
        self._event("delivered", operation=operation.identifier)

    def readiness_lost(self) -> None:
        if self._state not in (State.STARTING, State.READY):
            raise SupervisorDenied()
        self._fence()

    def stop(self) -> None:
        if self._state is State.STOPPED:
            return
        fenced = self._state is State.FENCED
        self._state = State.FENCED if fenced else State.DRAINING
        clean = self._cleanup()
        self._state = State.FENCED if fenced or not clean else State.STOPPED
        self._event("fenced" if self._state is State.FENCED else "stopped")

    def recover(self, services: tuple[Service, ...]) -> None:
        """Operator-model transition only; no keys/files are rotated or created."""
        if self._state is not State.FENCED or self._handles or self._operations:
            raise SupervisorDenied()
        try:
            fingerprint = inventory(services)
            old = self._binding
            old_states = {s.authority_state for s in self._services if s.authority_state}
            new_states = {s.authority_state for s in services if s.authority_state}
            if (
                old is None
                or services[0].generation == old.generation
                or old_states & new_states
                or self._approval.recovery(old, services[0].generation, fingerprint) is not True
            ):
                raise SupervisorDenied()
        except Exception:
            raise SupervisorDenied() from None
        self._services = services
        self._binding = None
        self._last = None
        self._state = State.STOPPED
        self._event("recovered")
