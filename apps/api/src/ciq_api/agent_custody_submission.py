"""Inactive fake-only custody checkpoints, with no transport/service or I/O permit.

Trusted test construction pins one request/claim and a separate custody engine.
SQL's protected assignment authorizes the clinical principal; no impersonation,
caller-supplied history, tenant, actor, digest or journal path is accepted.
prepare()/issue() return None. They do NOT dispatch or enable provider execution.
"""

from typing import Annotated
from uuid import UUID

from pydantic import Field
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from ciq_api.agent_admission import ERROR, FakeReceiptJournal
from ciq_api.agent_contracts import AgentContractError, ImmutableContract
from ciq_api.agent_ledger import ClaimReceipt
from ciq_api.agent_receipt_verifier import FakeReceiptVerifier

_FAILURES = (AgentContractError, DBAPIError, ValueError, TypeError, KeyError, RecursionError)


class _CheckpointReceipt(ImmutableContract):
    operation_id: UUID
    version: Annotated[int, Field(strict=True, ge=1, le=2_147_483_647)]
    fence_id: UUID
    attempt_id: UUID
    submission_id: UUID


class FakeCustodySubmission:
    """One original in-process fake coordinator, never a browser/IPC endpoint.

    Each stage keeps the independent inventory/check and protected write/read on
    ONE custody connection and epoch transaction. External prepare precedes local
    checkpoint commit. External issue is consumed once, after that commit.
    A new instance cannot rehydrate pending issue from rows or receipts.
    Database/registry owners and custody-process memory remain trusted.
    """

    def __init__(self, engine, journal: FakeReceiptJournal, *, request_id, claim: ClaimReceipt,
                 schema="ciq_agent_receipts"):
        self._verifier = FakeReceiptVerifier(engine, journal, schema=schema)
        if (
            type(request_id) is not str or not 1 <= len(request_id) <= 120
            or type(claim) is not ClaimReceipt or claim.state != "reserved"
            or type(claim.version) is not int or not 1 <= claim.version < 2_147_483_647
            or type(claim.operation_id) is not UUID or type(claim.fence_id) is not UUID
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
        self._started = False
        self._pending = None

    def prepare(self):
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
            self._pending = (receipt, selected)
        except _FAILURES:
            raise AgentContractError(ERROR) from None

    def issue(self):
        pending, self._pending = self._pending, None
        if pending is None:
            raise AgentContractError(ERROR) from None
        receipt, retained = pending
        try:
            with self._engine.begin() as db:
                material, current = self._verifier._observe(db)
                self._journal.check(current)
                observed = _CheckpointReceipt.model_validate(db.scalar(self._issue, {
                    **self._params, "version": receipt.version,
                    "submission": receipt.submission_id,
                }))
                if observed != receipt or self._selected(material, current, observed) != retained:
                    raise ValueError("checkpoint_mismatch")
                # Single-use external issue commits before this method returns.
                # Exit/rollback afterwards sacrifices permission; never refund or
                # recreate it. This method returns NO transport/I/O capability.
                self._journal.issue(retained)
        except _FAILURES:
            raise AgentContractError(ERROR) from None

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
