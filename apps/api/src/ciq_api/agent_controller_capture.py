"""Inactive, capture-only controller client. No ledger writes or provider permission.

The trusted service supplies a separately authenticated engine and fixed schema;
requests cannot choose a tenant, actor, role, credential or connection. The SQL
capability derives clinical identity from session_user's protected binding.
"""

import re
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from ciq_api.agent_contracts import AgentContractError, capture_selected_input
from ciq_api.assessment import fingerprint


class ControllerCapture:
    def __init__(self, engine, *, schema="ciq_agent_capture"):
        # Trusted installation identifier, never supplied by IPC/browser input.
        if not re.fullmatch(r"ciq_agent_capture(?:_[a-f0-9]{24})?", schema):
            raise AgentContractError("scope_unavailable")
        self.engine = engine
        self._statement = text(f'SELECT "{schema}".capture(:request_id)')

    def capture(self, request_id):
        if type(request_id) is not str or not 1 <= len(request_id) <= 120:
            raise AgentContractError("scope_unavailable")
        try:
            with self.engine.begin() as db:
                # Function locks live scope; all shared validation finishes before
                # commit releases those locks. A capture is never a later permit.
                row = db.scalar(self._statement, {"request_id": request_id})
                if (
                    type(row) is not dict
                    or row["request_id"] != request_id
                    or row["revision_digest"] != fingerprint(row["facts"])
                    or row["revision_digest"] != fingerprint(row["revision_inputs"])
                    or row["record_input_digest"] != row["revision_digest"]
                    or row["record_policy_version"] != row["policy"]["version"]
                    or row["record_rules_digest"] != fingerprint(row["policy"]["rules"])
                ):
                    raise AgentContractError("scope_unavailable")
                return capture_selected_input(
                    tenant_id=row["tenant_id"],
                    request_id=request_id,
                    policy_id=row["policy_id"],
                    input_revision=row["input_revision"],
                    review_version=row["review_version"],
                    correlation_id=uuid4(),
                    facts=row["facts"],
                    policy=row["policy"],
                )
        except (DBAPIError, ValueError, TypeError, KeyError, RecursionError):
            # Never propagate driver SQL/connection details or clinical inputs.
            raise AgentContractError("scope_unavailable") from None
