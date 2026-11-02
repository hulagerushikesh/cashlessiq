"""Inactive, fake-only checkpoint-to-process seam. No route, worker or provider.

The controller still uses the existing owner-level test DB connection. Process
separation is not database least privilege. A configured argv is trusted harness
configuration, never a browser field; this module is not a sandbox launcher.
"""

import base64
import hashlib
import json
import math
import os
import selectors
import signal
import subprocess
import time
from contextlib import suppress
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, ValidationError

from ciq_api.agent_contracts import (
    AgentContractError,
    AgentInput,
    Digest,
    ImmutableContract,
    canonical_json,
)

MAX_REQUEST = 1_200_000
MAX_REPLY = 180_000
MAX_CANDIDATE = 128_000
MAX_PROCESS_SECONDS = 10
PERSISTENCE_MARGIN_SECONDS = 2


class FakeProcessRequest(ImmutableContract):
    protocol: Literal["ciq-fake-process-v1"] = "ciq-fake-process-v1"
    operation_id: UUID
    attempt_id: UUID
    submission_id: UUID
    tenant_id: UUID
    config_digest: Digest
    source_digest: Digest
    deadline: AwareDatetime
    snapshot: AgentInput = Field(repr=False)

    def wire(self) -> bytes:
        raw = canonical_json(self.model_dump(mode="json")).encode()
        if len(raw) > MAX_REQUEST:
            raise AgentContractError("fake_request_too_large")
        return raw


class FakeProcessReply(ImmutableContract):
    protocol: Literal["ciq-fake-process-v1"]
    request_sha256: Digest
    candidate_base64: Annotated[str, Field(max_length=170_668, repr=False)]


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_key")
        result[key] = value
    return result


def decode_reply(raw: bytes, request: bytes) -> bytes:
    """Framing only. The ledger separately validates clinical content and scope."""
    try:
        if type(raw) is not bytes or not 0 < len(raw) <= MAX_REPLY:
            raise ValueError
        reply = FakeProcessReply.model_validate(json.loads(raw, object_pairs_hook=_unique))
        if reply.request_sha256 != hashlib.sha256(request).hexdigest():
            raise ValueError
        candidate = base64.b64decode(reply.candidate_base64, validate=True)
        if not 0 < len(candidate) <= MAX_CANDIDATE:
            raise ValueError
        return candidate
    except (ValueError, TypeError, RecursionError, ValidationError):
        raise AgentContractError("invalid_fake_process_reply") from None


class BoundedFakeProcess:
    """One child, one exchange, no retry. Explicit harness use only (POSIX).

    Environment and FDs are not inherited. OS/file/network isolation must be
    supplied separately. Both pipes are bounded; stderr contents never escape.
    argv is fixed trusted configuration and must contain no secret/clinical data.
    """

    def __init__(self, argv: tuple[str, ...]):
        if not argv or not os.path.isabs(argv[0]) or any(type(a) is not str for a in argv):
            raise ValueError("invalid_fake_process_command")
        self._argv = argv
        self._used = False

    def exchange(self, request: bytes, *, timeout: float) -> bytes:
        if (
            self._used
            or type(request) is not bytes
            or not 0 < len(request) <= MAX_REQUEST
            or isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout)
            or not 0 < timeout <= MAX_PROCESS_SECONDS
        ):
            raise AgentContractError("fake_transport_unavailable")
        # Even spawn failure consumes this local instance. Durable admission is
        # enforced by begin_submission, not this in-memory latch.
        self._used = True
        child = None
        end = time.monotonic() + timeout
        try:
            child = subprocess.Popen(
                self._argv,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd="/",
                env={"LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1"},
                close_fds=True,
                start_new_session=True,
            )
            output = bytearray()
            sent = 0
            with selectors.DefaultSelector() as selector:
                for pipe, event, label in (
                    (child.stdin, selectors.EVENT_WRITE, "input"),
                    (child.stdout, selectors.EVENT_READ, "output"),
                    (child.stderr, selectors.EVENT_READ, "error"),
                ):
                    os.set_blocking(pipe.fileno(), False)
                    selector.register(pipe, event, label)
                while selector.get_map():
                    remaining = end - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError
                    for key, _ in selector.select(remaining):
                        pipe = key.fileobj
                        if key.data == "input":
                            sent += os.write(pipe.fileno(), request[sent : sent + 16_384])
                            if sent == len(request):
                                selector.unregister(pipe)
                                pipe.close()
                        else:
                            chunk = os.read(pipe.fileno(), 16_384)
                            if not chunk:
                                selector.unregister(pipe)
                                pipe.close()
                            elif key.data == "error":
                                raise ValueError("child_stderr")
                            else:
                                if len(output) + len(chunk) > MAX_REPLY:
                                    raise ValueError("child_output_bound")
                                output.extend(chunk)
            if child.wait(timeout=max(0.001, end - time.monotonic())) != 0:
                raise ValueError("child_exit")
            return decode_reply(bytes(output), request)
        except (OSError, ValueError, subprocess.SubprocessError):
            raise AgentContractError("fake_transport_unavailable") from None
        finally:
            if child is not None:
                # Kill the owned process group, including descendants retaining
                # pipes. Do not kill unrelated processes or leave child zombies.
                with suppress(ProcessLookupError):
                    os.killpg(child.pid, signal.SIGKILL)
                child.wait()
                for pipe in (child.stdin, child.stdout, child.stderr):
                    if not pipe.closed:
                        pipe.close()


def _utc_now():
    return datetime.now(UTC)


def execute_fake_process(ledger, tenant_id, actor_id, claim, transport: BoundedFakeProcess):
    """Commit the sole checkpoint before any child; publish under fresh DB locks.

    Failure leaves submitting/unknown cost reserved. Existing status-only recovery
    handles lease expiry. Never replay, reclaim or refund based on a child exit.
    No externally retained receipt/restore epoch is implemented by this seam.
    """
    permit = ledger.begin_submission(tenant_id, actor_id, claim)
    request = FakeProcessRequest(
        operation_id=permit.operation_id,
        attempt_id=permit.attempt_id,
        submission_id=permit.submission_id,
        tenant_id=permit.tenant_id,
        config_digest=permit.config_digest,
        source_digest=permit.source_digest,
        deadline=permit.deadline,
        snapshot=AgentInput.model_validate(permit.snapshot.model_dump()),
    ).wire()
    budget = min(
        MAX_PROCESS_SECONDS,
        (permit.deadline - _utc_now()).total_seconds() - PERSISTENCE_MARGIN_SECONDS,
    )
    # A late local clock may waste this fake checkpoint; it never expands its
    # lease/deadline or grants a second call. DB time remains publication authority.
    if budget <= 0:
        raise AgentContractError("fake_transport_unavailable")
    raw = transport.exchange(request, timeout=budget)
    return ledger.publish_fake_result(permit, raw)
