"""Inactive protected product adapter for ONE manually reviewed captured call.

No route, service or generic worker selects this program. The trusted supervisor
supplies a dedicated custody engine and matching independent peers; neither a
browser nor an agent chooses authority, snapshots, configuration or responses.
The inactive SQL package must be separately reviewed/staged by the owner. Its
disabled registry is not itself consent or a production recovery mechanism.
"""

import hashlib
import re
from datetime import UTC, datetime
from threading import Lock
from time import monotonic
from typing import Annotated
from uuid import UUID

from pydantic import AwareDatetime, Field
from sqlalchemy import text

from ciq_api.agent_contracts import (
    AgentContext,
    AgentContractError,
    AgentInput,
    Digest,
    ImmutableContract,
    canonical_json,
)
from ciq_api.agent_controller_capture import _validated_capture
from ciq_api.agent_one_shot import CapturedOneShotConfig
from ciq_api.agent_provider_peer import ReviewedProviderPeerClient
from ciq_api.agent_single_call_custody import ATTEMPT_SECONDS, PreparedSingleCallCustody
from ciq_api.agent_single_call_journal import ReviewedCallPin
from ciq_api.agent_single_call_peer import SingleCallReceiptClient
from ciq_api.agent_snapshot_tools import select_captured_snapshot

ERROR = "single_call_product_unavailable"


class _Projection(ImmutableContract):
    operation_id: UUID
    pin: Annotated[str, Field(max_length=4096, repr=False)]
    pin_sha256: Digest
    snapshot: AgentInput = Field(repr=False)
    config: CapturedOneShotConfig = Field(repr=False)
    clinical: dict = Field(repr=False)
    checked_at: AwareDatetime
    deadline: AwareDatetime


def _require(value):
    if not value:
        raise ValueError(ERROR)


def _material(row, operation_id):
    """Validate only a protected projection while its SQL scope locks are held."""
    projection = _Projection.model_validate(row)
    pin = ReviewedCallPin.model_validate_json(projection.pin)
    _require(projection.operation_id == pin.operation_id == operation_id
             and projection.pin == pin.canonical()
             and hashlib.sha256(projection.pin.encode()).hexdigest() == projection.pin_sha256
             and pin.starts_at <= projection.checked_at < projection.deadline <= pin.ends_at)
    snapshot = projection.snapshot
    fresh = _validated_capture(
        projection.clinical, snapshot.binding.request_id, snapshot.binding.correlation_id,
    )
    current = AgentContext(
        binding=fresh.binding, tenant_active=True, policy_approved=True,
        clinical_authorized=True, review_open=True,
    )
    select_captured_snapshot(snapshot, current)
    return projection, pin, current


class ProductSingleCall:
    """Original checkpoint -> committed issue -> private reply -> locked advisory.

    SQL derives custody from session_user and an owner-staged assignment; it
    delegates only the fixed clinical principal. Validation occurs under those
    locks. Local checkpoint COMMIT must succeed before receipt/provider I/O.
    No database transaction or connection stays open during either peer call.
    Receipt history remains independent of this database. All failures consume
    this original attempt, including ambiguous commits; no retry/rehydration.

    The exact custody program and credential are trusted, as in the existing
    fake coordinator. Direct SQL execution by a compromised custody can forge
    an advisory row; SQL is not Python validation or provider provenance. The
    credential must never belong to the API, controller or provider processes.
    """

    def __init__(self, engine, *, operation_id: UUID, receipt: SingleCallReceiptClient,
                 provider: ReviewedProviderPeerClient, schema="ciq_agent_single_call"):
        try:
            _require(type(operation_id) is UUID and type(schema) is str
                     and re.fullmatch(r"ciq_agent_single_call(?:_[a-f0-9]{24})?", schema)
                     and type(receipt) is SingleCallReceiptClient
                     and type(provider) is ReviewedProviderPeerClient
                     and receipt.pin_sha256 == provider.pin_sha256)
            self._engine, self._operation = engine, operation_id
            self._receipt, self._provider = receipt, provider
            self._checkpoint = text(f'SELECT "{schema}".checkpoint(:operation)')
            self._context = text(f'SELECT "{schema}".publication_context(:operation)')
            self._publish = text(
                f'SELECT "{schema}".publish(:operation, '
                'CAST(:candidate AS jsonb), CAST(:observation AS jsonb))'
            )
            self._lock, self._started, self._pending = Lock(), False, None
            self._publication_started = False
        except Exception:
            raise AgentContractError(ERROR) from None

    def run(self):
        """One dispatch and advisory publication; no transferable result/permit."""
        self.dispatch()
        self.publish()

    def _budget(self, end, deadline):
        _require(monotonic() < end and datetime.now(UTC) < deadline)

    def dispatch(self):
        with self._lock:
            if self._started or self._publication_started:
                raise AgentContractError(ERROR) from None
            self._started = True
        try:
            # Conservative DB clock translation: start BEFORE connect/lock. The
            # whole elapsed time is deducted even though SQL samples later.
            started = monotonic()
            params = {"operation": self._operation}
            with self._engine.begin() as db:
                projection, pin, current = _material(db.scalar(self._checkpoint, params),
                                                     self._operation)
                assembly = PreparedSingleCallCustody(
                    projection.snapshot, current, projection.config, pin,
                    self._receipt, self._provider,
                )
                end = started + min(ATTEMPT_SECONDS,
                    (projection.deadline - projection.checked_at).total_seconds())
                self._budget(end, projection.deadline)
            # An exception/uncertain COMMIT never reaches issue or provider.
            self._budget(end, projection.deadline)
            assembly.dispatch(current, monotonic_deadline=end)
            self._budget(end, projection.deadline)
            with self._lock:
                _require(not self._publication_started)
                self._pending = assembly, projection, end
        except Exception:
            raise AgentContractError(ERROR) from None

    def publish(self):
        """Consume only this original reply under fresh locked product authority.

        Saves a private ADVISORY comparison only. It never finalizes a review,
        writes human audit/outbox, refunds uncertainty or resumes a provider.
        Revocation committed after dispatch admission prevents publication;
        it cannot cancel a call already admitted/in flight.
        """
        with self._lock:
            if self._publication_started:
                raise AgentContractError(ERROR) from None
            self._publication_started = True
            pending, self._pending = self._pending, None
        try:
            _require(pending is not None)
            assembly, original, end = pending
            self._budget(end, original.deadline)
            params = {"operation": self._operation}
            with self._engine.begin() as db:
                projection, _, current = _material(
                    db.scalar(self._context, params), self._operation,
                )
                _require(projection.pin == original.pin
                         and projection.pin_sha256 == original.pin_sha256
                         and projection.snapshot == original.snapshot
                         and projection.config == original.config
                         and projection.deadline <= original.deadline
                         and projection.checked_at >= original.checked_at)
                self._budget(end, projection.deadline)
                final = assembly.take_candidate(current)
                self._budget(end, projection.deadline)
                db.scalar(self._publish, {
                    **params, "candidate": canonical_json(final.candidate.model_dump(mode="json")),
                    "observation": canonical_json(final.observation.model_dump(mode="json")),
                })
                self._budget(end, projection.deadline)
            self._budget(end, projection.deadline)
        except Exception:
            raise AgentContractError(ERROR) from None
