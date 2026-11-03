"""Inactive fake-only custody observer; a successful check is NEVER an I/O permit.

Trusted configuration supplies a separate restricted DB login and retained fake
journal. No caller provides an inventory, epoch, tenant, file or connection. This
does not expose prepare/issue, a ticket or a bypassable admission attestation.
"""

import json
import re
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from ciq_api.agent_admission import (
    ERROR,
    MAX_RECEIPTS,
    FakeEpochPin,
    FakeReceiptJournal,
    checkpoint_from_material,
)
from ciq_api.agent_contracts import AgentContractError, Digest, ImmutableContract, Label

MAX_INVENTORY_BYTES = 4 * 1024 * 1024
Limit = Annotated[int, Field(strict=True, ge=1, le=30)]
Units = Annotated[int, Field(strict=True, ge=1, le=30_000_000)]


class _Operation(ImmutableContract):
    tenant_id: UUID
    id: UUID
    actor_id: UUID
    request_id: Label
    grant_id: UUID
    operation_key: Digest
    snapshot: dict = Field(repr=False)
    config_digest: Digest
    source_digest: Digest
    created_at: AwareDatetime
    deadline: AwareDatetime


class _Grant(ImmutableContract):
    tenant_id: UUID
    id: UUID
    mode: Literal["fake-only"]
    approval_ref: Label = Field(repr=False)
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    case_limit: Limit
    concurrency_limit: Limit
    unit_limit: Units
    units_per_attempt: Annotated[int, Field(strict=True, ge=1, le=1_000_000)]


class _Attempt(ImmutableContract):
    tenant_id: UUID
    id: UUID
    operation_id: UUID
    attempt_number: Annotated[int, Field(strict=True, ge=1, le=1)]
    submission_id: UUID
    fence_id: UUID
    submitted_at: AwareDatetime


class _Material(ImmutableContract):
    operation: _Operation = Field(repr=False)
    grant: _Grant = Field(repr=False)
    attempt: _Attempt = Field(repr=False)

    @model_validator(mode="after")
    def exact_joins(self):
        op, grant, attempt = self.operation, self.grant, self.attempt
        if (
            op.tenant_id != grant.tenant_id or op.tenant_id != attempt.tenant_id
            or op.grant_id != grant.id or attempt.operation_id != op.id
            or not op.created_at < op.deadline
            or not grant.starts_at < grant.ends_at
            or grant.concurrency_limit > grant.case_limit
            or grant.units_per_attempt > grant.unit_limit
        ):
            raise ValueError("invalid_receipt_material")
        return self


class _Inventory(ImmutableContract):
    epoch: FakeEpochPin
    entries: Annotated[tuple[_Material, ...], Field(max_length=MAX_RECEIPTS)] = Field(repr=False)


class FakeReceiptVerifier:
    """Observes independently through one no-argument definer function.

    Holds the local epoch lock until the full retained journal comparison ends.
    Returns no transferable result, receipt or submission permission. There is
    deliberately no network/IPC/service installer or automatic integration.
    """

    def __init__(self, engine, journal: FakeReceiptJournal, *, schema="ciq_agent_receipts"):
        if (
            type(schema) is not str
            or not re.fullmatch(r"ciq_agent_receipts(?:_[a-f0-9]{24})?", schema)
            or type(journal) is not FakeReceiptJournal
        ):
            raise AgentContractError(ERROR) from None
        self.engine = engine
        self.journal = journal
        self._statement = text(f'SELECT "{schema}".inventory_fake()')

    def check(self):
        try:
            with self.engine.begin() as db:
                raw = db.scalar(self._statement)
                if len(json.dumps(raw, allow_nan=False).encode()) > MAX_INVENTORY_BYTES:
                    raise ValueError("inventory_bound")
                # JSON validation revalidates nested models and rejects extras.
                inventory = _Inventory.model_validate_json(json.dumps(raw, allow_nan=False))
                if inventory.epoch != self.journal.pin:
                    raise ValueError("epoch_mismatch")
                expected = tuple(
                    checkpoint_from_material(e.operation, e.grant, e.attempt)
                    for e in inventory.entries
                )
                if any(len({getattr(c, key) for c in expected}) != len(expected) for key in (
                    "operation_id", "submission_id",
                )) or len({(c.tenant_id, c.request_id) for c in expected}) != len(expected):
                    raise ValueError("duplicate_receipt")
                self.journal.check(expected)
        except (AgentContractError, DBAPIError, ValueError, TypeError, KeyError, RecursionError):
            raise AgentContractError(ERROR) from None
