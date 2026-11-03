"""Inactive fake-only custody coordinator, with no service or transferable permit.

Trusted test construction pins one request/claim and a separate custody engine.
SQL's protected assignment authorizes the clinical principal; no impersonation,
caller-supplied history, tenant, actor, digest or journal path is accepted.
prepare()/issue()/dispatch() return None. Only dispatch() performs one fixed fake
exchange; its candidate stays private until validated comparison publication.
There is no provider execution.
"""

from datetime import UTC, datetime
from threading import Lock
from time import monotonic
from typing import Annotated
from uuid import UUID

from pydantic import AwareDatetime, Field
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from ciq_api.agent_admission import ERROR, FakeReceiptJournal
from ciq_api.agent_contracts import (
    AgentContext,
    AgentContractError,
    AgentInput,
    ImmutableContract,
    canonical_json,
    require_current,
    validate_candidate,
)
from ciq_api.agent_controller_capture import _validated_capture
from ciq_api.agent_executor import (
    MAX_PROCESS_SECONDS,
    PERSISTENCE_MARGIN_SECONDS,
    BoundedFakeProcess,
    FakeProcessRequest,
)
from ciq_api.agent_ledger import ClaimReceipt
from ciq_api.agent_receipt_peer import FakeReceiptPeerClient
from ciq_api.agent_receipt_verifier import FakeReceiptVerifier

_FAILURES = (AgentContractError, DBAPIError, ValueError, TypeError, KeyError, RecursionError)


class _CheckpointReceipt(ImmutableContract):
    operation_id: UUID
    version: Annotated[int, Field(strict=True, ge=1, le=2_147_483_647)]
    fence_id: UUID
    attempt_id: UUID
    submission_id: UUID


class _IssueProjection(ImmutableContract):
    checkpoint: _CheckpointReceipt
    checked_at: AwareDatetime
    deadline: AwareDatetime


class _PublicationProjection(_IssueProjection):
    window_end: AwareDatetime
    clinical: dict = Field(repr=False)


class FakeCustodySubmission:
    """One original in-process fake coordinator, never a browser/IPC endpoint.

    Each stage keeps the independent inventory/check and protected write/read on
    ONE custody connection and epoch transaction. External prepare precedes local
    checkpoint commit. External issue is consumed once, after that commit.
    A new instance cannot rehydrate pending issue from rows or receipts.
    Database/registry owners and custody-process memory remain trusted.
    """

    def __init__(self, engine, journal: FakeReceiptJournal | FakeReceiptPeerClient,
                 *, request_id, claim: ClaimReceipt,
                 schema="ciq_agent_receipts", transport: BoundedFakeProcess | None = None):
        self._verifier = FakeReceiptVerifier(engine, journal, schema=schema)
        if (
            type(request_id) is not str or not 1 <= len(request_id) <= 120
            or type(claim) is not ClaimReceipt or claim.state != "reserved"
            or type(claim.version) is not int or not 1 <= claim.version < 2_147_483_647
            or type(claim.operation_id) is not UUID or type(claim.fence_id) is not UUID
            or (transport is not None and type(transport) is not BoundedFakeProcess)
        ):
            raise AgentContractError(ERROR) from None
        self._engine, self._journal = engine, journal
        self._params = {
            "request": request_id, "operation": claim.operation_id,
            "version": claim.version, "fence": claim.fence_id,
        }
        self._checkpoint = text(
            f'SELECT "{schema}".checkpoint_fake(:request, :operation, :version, :fence)'
        )
        self._issue = text(
            f'SELECT "{schema}".issue_fake(:request, :operation, :version, :fence, :submission)'
        )
        self._publication_context = text(
            f'SELECT "{schema}".publication_context_fake('
            ':request, :operation, :version, :fence, :submission)'
        )
        self._heartbeat = text(
            f'SELECT "{schema}".heartbeat_submitted_fake('
            ':request, :operation, :version, :fence, :submission)'
        )
        self._publish = text(
            f'SELECT "{schema}".publish_comparison_fake('
            ':request, :operation, :version, :fence, :submission, CAST(:candidate AS jsonb))'
        )
        self._started = False
        self._pending = None
        self._stage_lock = Lock()
        # Fixed trusted construction only. No service, caller-selected command,
        # factory, callback or later injection of an already-issued receipt.
        self._transport = transport
        self._candidate = None

    def prepare(self):
        with self._stage_lock:
            if self._started:
                raise AgentContractError(ERROR) from None
            # No automatic retry even after a failure with an uncertain commit.
            self._started = True
        try:
            with self._engine.begin() as db:
                _, previous = self._verifier._observe(db)
                self._journal.check(previous)
                receipt = _CheckpointReceipt.model_validate(
                    db.scalar(self._checkpoint, self._params)
                )
                if (
                    receipt.operation_id != self._params["operation"]
                    or receipt.fence_id != self._params["fence"]
                    or receipt.version != self._params["version"] + 1
                ):
                    raise ValueError("checkpoint_mismatch")
                material, current = self._verifier._observe(db)
                selected = self._selected(material, current, receipt)
                if set(current) != {*previous, selected} or len(current) != len(previous) + 1:
                    raise ValueError("history_mismatch")
                # Durable independently retained prepare FIRST; local rollback or
                # uncertain commit leaves a gap that closes subsequent admission.
                self._journal.prepare(selected)
                self._journal.check(current)
            # Assigned only after the engine context confirms local commit.
            with self._stage_lock:
                self._pending = (receipt, selected)
        except _FAILURES:
            raise AgentContractError(ERROR) from None

    def issue(self):
        """Consume without dispatch; deliberately sacrifices this exchange."""
        self._finish(dispatch=False)

    def dispatch(self):
        """Consume issue then exchange once, entirely within the original custody.

        No return value, clinical publication, retry, refund or peer endpoint.
        The response remains unvalidated private memory for a later narrow
        publication command. Same-process trusted construction is not OS/IPC
        peer authentication or proof of production process/secret isolation.
        """
        self._finish(dispatch=True)

    def _finish(self, *, dispatch):
        with self._stage_lock:
            pending, self._pending = self._pending, None
        if pending is None or (dispatch and self._transport is None):
            raise AgentContractError(ERROR) from None
        receipt, retained = pending
        try:
            # Start BEFORE connecting/locking: subtracting the entire elapsed
            # time from DB's later sample is conservative. A slow local wall
            # clock cannot enlarge DB's remaining budget; a fast one may deny.
            start = monotonic()
            with self._engine.begin() as db:
                material, current = self._verifier._observe(db)
                self._journal.check(current)
                projection = _IssueProjection.model_validate(db.scalar(self._issue, {
                    **self._params, "version": receipt.version,
                    "submission": receipt.submission_id,
                }))
                observed = projection.checkpoint
                if observed != receipt or self._selected(material, current, observed) != retained:
                    raise ValueError("checkpoint_mismatch")
                selected = next(
                    m for m in material.entries if m.operation.id == receipt.operation_id
                )
                op = selected.operation
                if not (
                    op.created_at <= projection.checked_at < projection.deadline
                    <= min(op.deadline, selected.grant.ends_at)
                ):
                    raise ValueError("invalid_issue_budget")
                end = start + (projection.deadline - projection.checked_at).total_seconds()
                if dispatch:
                    snapshot = AgentInput.model_validate_json(canonical_json(op.snapshot))
                    if (
                        snapshot.binding.tenant_id != op.tenant_id
                        or snapshot.binding.request_id != self._params["request"]
                    ):
                        raise ValueError("snapshot_mismatch")
                    request = FakeProcessRequest(
                        operation_id=op.id, attempt_id=observed.attempt_id,
                        submission_id=observed.submission_id, tenant_id=op.tenant_id,
                        config_digest=op.config_digest, source_digest=op.source_digest,
                        deadline=projection.deadline, snapshot=snapshot,
                    ).wire()
                    self._budget(end, projection.deadline)
                # Single-use external issue commits before this method returns.
                # Exit/rollback afterwards sacrifices permission; never refund or
                # recreate it. This method returns NO transport/I/O capability.
                self._journal.issue(retained)
            if dispatch:
                # Do not hold database/clinical locks or an open connection over
                # child I/O. Commit failure or expired margin means NO child;
                # issued cost stays held, never permission to replay/refund.
                raw = self._transport.exchange(
                    request, timeout=self._budget(end, projection.deadline),
                )
                self._budget(end, projection.deadline)
                with self._stage_lock:
                    self._candidate = (receipt, raw, projection.deadline, end, retained)
        except _FAILURES:
            raise AgentContractError(ERROR) from None

    def heartbeat(self):
        """Maintain the current submitted lease, without widening the I/O budget."""
        self._complete(publish=False)

    def publish(self):
        """Consume the private reply and save only a fresh, validated comparison.

        Returns None. No caller response/identity/validation flag is accepted.
        No human decision or audit/outbox is written. Any failure sacrifices the
        candidate; neither transport issue nor publication is automatically retried.
        """
        self._complete(publish=True)

    def _complete(self, *, publish):
        with self._stage_lock:
            pending, self._candidate = self._candidate, None
        if pending is None:
            raise AgentContractError(ERROR) from None
        receipt, raw, deadline, end, retained = pending
        try:
            self._budget(end, deadline)
            with self._engine.begin() as db:
                material, current = self._verifier._observe(db)
                self._journal.check_issued(current, retained)
                params = {
                    **self._params, "version": receipt.version,
                    "submission": receipt.submission_id,
                }
                projection = _PublicationProjection.model_validate(
                    db.scalar(self._publication_context, params)
                )
                if (
                    projection.checkpoint != receipt
                    or self._selected(material, current, receipt) != retained
                    or not projection.checked_at < projection.deadline <= projection.window_end
                ):
                    raise ValueError("checkpoint_mismatch")
                selected = next(
                    m for m in material.entries if m.operation.id == receipt.operation_id
                )
                op = selected.operation
                if not (
                    op.created_at <= projection.checked_at < projection.deadline
                    <= projection.window_end <= min(op.deadline, selected.grant.ends_at)
                ):
                    raise ValueError("invalid_publication_budget")
                snapshot = AgentInput.model_validate_json(canonical_json(op.snapshot))
                # Fresh protected clinical capture is validated independently of
                # the immutable submitted snapshot. SQL retains these row locks
                # through Python validation and the final narrow command/commit.
                fresh = _validated_capture(
                    projection.clinical, self._params["request"], snapshot.binding.correlation_id,
                )
                context = AgentContext(
                    binding=fresh.binding, tenant_active=True, policy_approved=True,
                    clinical_authorized=True, review_open=True,
                )
                require_current(snapshot, context)
                self._budget(end, min(deadline, projection.deadline))
                if publish:
                    candidate = validate_candidate(snapshot, context, receipt.operation_id, raw)
                    params["candidate"] = canonical_json(candidate.model_dump(mode="json"))
                self._budget(end, min(deadline, projection.deadline))
                result = _CheckpointReceipt.model_validate(
                    db.scalar(self._publish if publish else self._heartbeat, params)
                )
                if result != receipt.model_copy(update={"version": receipt.version + 1}):
                    raise ValueError("checkpoint_mismatch")
                self._budget(end, min(deadline, projection.deadline))
            if not publish:
                # Only confirmed heartbeat commit retains the original response;
                # neither original issue deadline nor monotonic budget expands.
                with self._stage_lock:
                    self._candidate = (result, raw, deadline, end, retained)
        except _FAILURES:
            raise AgentContractError(ERROR) from None

    @staticmethod
    def _budget(end, deadline):
        budget = min(
            MAX_PROCESS_SECONDS,
            end - monotonic() - PERSISTENCE_MARGIN_SECONDS,
            (deadline - datetime.now(UTC)).total_seconds() - PERSISTENCE_MARGIN_SECONDS,
        )
        if budget <= 0:
            raise ValueError("expired_issue_budget")
        return budget

    def _selected(self, inventory, checkpoints, receipt):
        pairs = [(m, c) for m, c in zip(inventory.entries, checkpoints, strict=True)
                 if m.operation.id == receipt.operation_id]
        if len(pairs) != 1:
            raise ValueError("checkpoint_missing")
        material, selected = pairs[0]
        if (
            material.operation.request_id != self._params["request"]
            or material.attempt.id != receipt.attempt_id
            or material.attempt.submission_id != receipt.submission_id
            or material.attempt.fence_id != receipt.fence_id
        ):
            raise ValueError("checkpoint_mismatch")
        return selected
