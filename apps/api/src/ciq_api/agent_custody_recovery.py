"""Inactive fake-only status recovery; never reconstructs submission permission."""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from ciq_api.agent_admission import ERROR, FakeReceiptJournal
from ciq_api.agent_contracts import AgentContractError
from ciq_api.agent_receipt_verifier import FakeReceiptVerifier

_FAILURES = (AgentContractError, DBAPIError, ValueError, TypeError, KeyError, RecursionError)


class FakeCustodyRecovery:
    """Trusted exact assignment, separate custody login, no clinical capability.

    A replacement process may recover STATUS, never a permit/response. Available
    independently retained full history is required to refund unused allowance.
    Missing/closed/contradictory history permits only conservative submitted
    unknown settlement, retaining uncertain units AND the concurrency slot.
    """

    def __init__(
        self,
        engine,
        journal: FakeReceiptJournal,
        *,
        request_id,
        operation_id,
        schema="ciq_agent_receipts",
    ):
        self._verifier = FakeReceiptVerifier(engine, journal, schema=schema)
        if (
            type(request_id) is not str
            or not 1 <= len(request_id) <= 120
            or type(operation_id) is not UUID
        ):
            raise AgentContractError(ERROR) from None
        self._engine, self._journal = engine, journal
        self._params = {"request": request_id, "operation": operation_id}
        self._status = text(f'SELECT "{schema}".recover_submitted_fake(:request, :operation)')
        self._verified = text(f'SELECT "{schema}".recover_verified_fake(:request, :operation)')

    def recover(self):
        """No arguments/result, I/O, retries, journal writes or reconciliation.

        An explicit later status check is safe/idempotent; it does not recreate
        the original coordinator's private pending issue or candidate. Keep the
        verified history's epoch lock through settlement on ONE transaction.
        """
        try:
            with self._engine.begin() as db:
                verified = False
                try:
                    # A denied SQL observer aborts only this savepoint, so the
                    # same outer connection can still do conservative recovery.
                    with db.begin_nested():
                        _, expected = self._verifier._observe(db)
                        self._journal.check(expected)
                    verified = True
                except _FAILURES:
                    pass
                db.scalar(self._verified if verified else self._status, self._params)
        except _FAILURES:
            raise AgentContractError(ERROR) from None
