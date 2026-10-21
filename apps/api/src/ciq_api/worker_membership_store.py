"""Trusted membership-only DB adapter; never supplied to readers or validators."""

import re
from collections.abc import Callable
from uuid import UUID

from sqlalchemy import Boolean, Column, MetaData, String, Table, Uuid, select, text
from sqlalchemy.engine import Connection

from ciq_api.worker_authority import Membership, WorkerDenied


class RestrictedMembershipStore:
    """Fresh bounded read transaction against three explicitly qualified tables.

    The injected factory must open a NEW connection as the separately provisioned
    membership-only principal. This adapter cannot establish least privilege by
    itself: column grants, role inheritance and network/secret custody need review.
    No ORM, user profile/OIDC fields, session cache, retry or write endpoint.
    """

    def __init__(self, connect: Callable[[], Connection], *, schema: str):
        if not isinstance(schema, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", schema):
            raise ValueError("Invalid membership schema")
        metadata = MetaData(schema=schema)
        user = Table("app_user", metadata, Column("id", Uuid), Column("active", Boolean))
        tenant = Table("tenant", metadata, Column("id", Uuid), Column("active", Boolean))
        member = Table(
            "tenant_membership",
            metadata,
            Column("user_id", Uuid),
            Column("tenant_id", Uuid),
            Column("role", String),
            Column("active", Boolean),
        )
        self._connect = connect
        self._user = user
        self._tenant = tenant
        self._member = member

    def lookup(self, subject: str, tenant_id: UUID) -> Membership | None:
        try:
            user_id = UUID(subject)
            if str(user_id) != subject or type(tenant_id) is not UUID:
                raise ValueError("Invalid membership identity")
            # New connection/transaction for every check; never reuse a prior
            # authorization snapshot. Database errors are DENIAL, not absence.
            with self._connect() as connection, connection.begin():
                connection.execute(text("SET TRANSACTION READ ONLY"))
                connection.execute(text("SET LOCAL statement_timeout = '1000ms'"))
                connection.execute(text("SET LOCAL lock_timeout = '250ms'"))
                rows = connection.execute(
                    select(self._member.c.role)
                    .select_from(
                        self._member.join(
                            self._user, self._user.c.id == self._member.c.user_id
                        ).join(self._tenant, self._tenant.c.id == self._member.c.tenant_id)
                    )
                    .where(
                        self._member.c.user_id == user_id,
                        self._member.c.tenant_id == tenant_id,
                        self._user.c.active.is_(True),
                        self._tenant.c.active.is_(True),
                        self._member.c.active.is_(True),
                    )
                    .limit(2)
                ).all()
            if not rows:
                return None
            if len(rows) != 1 or rows[0].role not in {"processor", "auditor", "medical_officer"}:
                raise ValueError("Invalid membership result")
            return Membership(tenant_id, rows[0].role)
        except Exception:
            raise WorkerDenied("Worker access denied") from None
