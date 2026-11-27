"""Inactive original single-call assembly; no route, DB adapter or service.

Trusted construction supplies a reviewed pin, captured product scope and two
exact authenticated peers. Contexts supplied here are assertions from a future
protected caller, NOT live authorization. No owner-consent, revocation or locked
publication gate is implemented by accepting these objects. Do not activate this
assembly until that adapter, provisioning and the outer supervisor are reviewed.
"""

import hashlib
import math
from datetime import UTC, datetime
from threading import Lock
from time import monotonic

from ciq_api.agent_contracts import AgentContext, AgentContractError, AgentInput
from ciq_api.agent_https_process import MAX_PROCESS_SECONDS
from ciq_api.agent_one_shot import CapturedOneShotConfig, prepare_captured_one_shot
from ciq_api.agent_provider_peer import ReviewedProviderPeerClient
from ciq_api.agent_single_call_journal import ReviewedCallPin
from ciq_api.agent_single_call_peer import IPC_SECONDS, SingleCallReceiptClient
from ciq_api.agent_single_call_response import (
    decode_single_call_final,
    inspect_single_call_response,
)
from ciq_api.agent_snapshot_tools import select_captured_snapshot
from ciq_api.assessment import fingerprint

ERROR = "single_call_custody_unavailable"
# Two receipt exchanges, provider envelope, process cleanup, validation margin.
ATTEMPT_SECONDS = 2 * IPC_SECONDS + MAX_PROCESS_SECONDS + 2
_AFTER_PROVIDER_SECONDS = IPC_SECONDS + 2


def _require(value):
    if not value:
        raise ValueError(ERROR)


def captured_call_source_sha256(snapshot: AgentInput) -> str:
    """Pin this captured-product profile, not independent Snowflake source parity."""
    try:
        _require(type(snapshot) is AgentInput)
        snapshot = AgentInput.model_validate(snapshot.model_dump(mode="python", warnings=False))
        return fingerprint(snapshot.model_dump(mode="json"))
    except Exception:
        raise AgentContractError(ERROR) from None


class PreparedSingleCallCustody:
    """One original in-memory dispatch and one private candidate handoff.

    Receipt commit/ACK precedes all provider access. No status lookup can create
    permission. Every dispatch/handoff, including denial or ambiguity, consumes
    its original pending state. A reconstructed object must issue again and is
    denied by retained history after issue. Methods cannot accept a response or a transport
    callback. No SQL connection/transaction is owned across provider I/O.
    """

    def __init__(
        self, snapshot: AgentInput, current: AgentContext, config: CapturedOneShotConfig,
        pin: ReviewedCallPin, receipt: SingleCallReceiptClient,
        provider: ReviewedProviderPeerClient,
    ):
        try:
            _require(type(pin) is ReviewedCallPin)
            pin = ReviewedCallPin.model_validate(pin.model_dump(mode="python", warnings=False))
            snapshot = select_captured_snapshot(snapshot, current)
            request = prepare_captured_one_shot(snapshot, current, pin.operation_id, config)
            _require(config.seconds == pin.provider_seconds and config.tokens == pin.max_tokens)
            _require(request.binding == snapshot.binding
                     and fingerprint(snapshot.binding.model_dump(mode="json")) == pin.binding_sha256
                     and captured_call_source_sha256(snapshot) == pin.source_sha256
                     and request.config_digest == pin.config_sha256
                     and request.request_digest == pin.request_sha256)
            body = request.body_json.encode("utf-8")
            _require(hashlib.sha256(body).hexdigest() == pin.request_sha256)
            digest = hashlib.sha256(pin.canonical().encode()).hexdigest()
            _require(type(receipt) is SingleCallReceiptClient
                     and type(provider) is ReviewedProviderPeerClient
                     and receipt.pin_sha256 == provider.pin_sha256 == digest)
            self._snapshot, self._pin = snapshot, pin
            self._receipt, self._provider = receipt, provider
            self._pending, self._reply = body, None
            self._lock = Lock()
            self._end, self._last_wall = None, None
        except Exception:
            raise AgentContractError(ERROR) from None

    def _remaining(self):
        now = datetime.now(UTC)
        _require(self._last_wall <= now < self._pin.ends_at)
        self._last_wall = now
        remaining = min(self._end - monotonic(), (self._pin.ends_at - now).total_seconds())
        _require(remaining > 0)
        return remaining

    def dispatch(self, current: AgentContext, *, monotonic_deadline=None):
        """Issue, exchange, retain observation; return no response or I/O ticket.

        The optional absolute monotonic ceiling only SHORTENS this attempt. It
        lets the protected adapter include connection/lock/validation/commit time
        in the same original budget. It is not an authorization or clock proof.
        Fresh locked authority belongs to that caller. Failures never retry,
        reset history or release uncertainty.
        """
        with self._lock:
            body, self._pending = self._pending, None
        try:
            _require(body is not None)
            started = monotonic()  # Includes scope validation and receipt IPC.
            now = datetime.now(UTC)
            _require(self._pin.starts_at <= now
                     and (self._pin.ends_at - now).total_seconds() >= ATTEMPT_SECONDS)
            self._end, self._last_wall = started + ATTEMPT_SECONDS, now
            if monotonic_deadline is not None:
                _require(type(monotonic_deadline) in (int, float)
                         and math.isfinite(monotonic_deadline))
                self._end = min(self._end, monotonic_deadline)
            select_captured_snapshot(self._snapshot, current)
            _require(self._remaining() > self._pin.provider_seconds + 2
                     + _AFTER_PROVIDER_SECONDS)
            # Never dispatch on a status read, an unacknowledged issue, or a
            # reconstruction. This exact original call must confirm its issue.
            self._receipt.issue()
            budget = min(MAX_PROCESS_SECONDS, self._remaining() - _AFTER_PROVIDER_SECONDS)
            _require(budget > self._pin.provider_seconds + 2)
            raw = self._provider.exchange(body, timeout=budget)
            self._remaining()
            observation = inspect_single_call_response(raw)
            self._remaining()
            self._receipt.observe(
                observation.response_sha256, provider_run_id=observation.provider_run_id,
                usage=observation.reported_usage,
            )
            self._remaining()
            with self._lock:
                self._reply = raw, observation
        except Exception:
            raise AgentContractError(ERROR) from None

    def take_candidate(self, current: AgentContext):
        """Consume this original private reply under freshly supplied context.

        Returns an advisory validated comparison, not a published decision. A
        future protected adapter must call and persist it within its fresh locked
        publication transaction. Receipt observation survives a rejected answer,
        revoked context, expired deadline or a lost publication acknowledgment.
        """
        with self._lock:
            pending, self._reply = self._reply, None
        try:
            _require(pending is not None)
            self._remaining()
            raw, observation = pending
            final = decode_single_call_final(
                self._snapshot, current, self._pin.operation_id, raw,
            )
            _require(final.observation == observation)
            self._remaining()
            return final
        except Exception:
            raise AgentContractError(ERROR) from None
