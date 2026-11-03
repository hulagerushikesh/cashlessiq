"""Inactive fake reservation/lease commands, never submission permission.

Only a trusted disposable operator stages exact validated approvals. Runtime
commands accept no tenant/actor/grant/hash/snapshot/epoch/clock selectors and
cannot create grants, submit attempts, publish, release cost or reset history.
Independent admission/custody integration is deliberately not supplied here.
"""

import re
from typing import Annotated
from uuid import UUID

from pydantic import Field
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from ciq_api.agent_admission import FakeEpochPin
from ciq_api.agent_contracts import AgentContractError, AgentInput, Digest, ImmutableContract
from ciq_api.agent_ledger import ClaimReceipt, OperationReceipt, operation_key

ERROR = "reservation_unavailable"


class FakeReservationApproval(ImmutableContract):
    """Trusted test preparation only; not a browser/IPC contract or live approval."""

    epoch: FakeEpochPin
    grant_id: UUID
    snapshot: AgentInput = Field(repr=False)
    config_digest: Digest
    source_digest: Digest
    timeout_seconds: Annotated[int, Field(strict=True, ge=1, le=120)] = 120

    def staging_values(self):
        # Revalidate even nested model instances before staging operator authority.
        snapshot = AgentInput.model_validate_json(self.snapshot.model_dump_json())
        return {
            "request_id": snapshot.binding.request_id,
            "grant_id": self.grant_id,
            "database_id": self.epoch.database_id,
            "epoch_id": self.epoch.epoch_id,
            "operation_key": operation_key(snapshot, self.config_digest, self.source_digest),
            "config_digest": self.config_digest,
            "source_digest": self.source_digest,
            "snapshot": snapshot.model_dump(mode="json"),
            "timeout_seconds": self.timeout_seconds,
            # An explicit separate trusted operator step must enable the row.
            "enabled": False,
        }


class ControllerReservation:
    def __init__(self, engine, *, schema="ciq_agent_capture"):
        if type(schema) is not str or not re.fullmatch(
            r"ciq_agent_capture(?:_[a-f0-9]{24})?", schema
        ):
            raise AgentContractError(ERROR)
        self.engine = engine
        self._reserve = text(f'SELECT "{schema}".reserve_fake(:request_id, :timeout)')
        self._lease = text(
            f'SELECT "{schema}".lease_fake(:request_id, :operation_id, :version, :fence_id)'
        )

    def _call(self, statement, params, model):
        if type(params["request_id"]) is not str or not 1 <= len(params["request_id"]) <= 120:
            raise AgentContractError(ERROR)
        try:
            with self.engine.begin() as db:
                return model.model_validate(db.scalar(statement, params))
        except (DBAPIError, ValueError, TypeError, KeyError, RecursionError):
            raise AgentContractError(ERROR) from None

    def reserve(self, request_id, *, timeout_seconds=120):
        if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 120:
            raise AgentContractError(ERROR)
        return self._call(
            self._reserve, {"request_id": request_id, "timeout": timeout_seconds}, OperationReceipt
        )

    def claim(self, request_id, receipt: OperationReceipt):
        return self._transition(request_id, receipt, None)

    def heartbeat(self, request_id, claim: ClaimReceipt):
        if type(claim) is not ClaimReceipt:
            raise AgentContractError(ERROR)
        return self._transition(request_id, claim, claim.fence_id)

    def _transition(self, request_id, receipt, fence_id):
        if type(receipt) not in {OperationReceipt, ClaimReceipt}:
            raise AgentContractError(ERROR)
        return self._call(
            self._lease,
            {
                "request_id": request_id,
                "operation_id": receipt.operation_id,
                "version": receipt.version,
                "fence_id": fence_id,
            },
            ClaimReceipt,
        )
