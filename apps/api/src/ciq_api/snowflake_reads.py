"""Bounded, tenant-scoped source reads. No rules, agent calls, or writes.

Not yet wired into the HTTP repository: source parity and a dedicated read-only
role must pass before replacing the offline snapshots.
"""

from collections.abc import Callable, Mapping
from datetime import date
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ALPHA_REQUESTS = ("GOL001", "GOL024", "GOL027")
READ_SQL = """
SELECT R.REQUEST_ID, P.POLICY_ID, P.TPA_ID, P.PRODUCT_ID,
       PP.PRODUCT_NAME, PP.VERSION AS POLICY_VERSION,
       P.CONTINUOUS_COVER_SINCE, F.ADMISSION_DATE, F.ESTIMATED_TOTAL_INR
FROM CASHLESSIQ.DOCS.PREAUTH_REQUEST R
JOIN CASHLESSIQ.CORE.POLICY P ON P.POLICY_ID = R.POLICY_ID
JOIN CASHLESSIQ.CORE.POLICY_PRODUCT PP ON PP.PRODUCT_ID = P.PRODUCT_ID
JOIN CASHLESSIQ.DOCS.PREAUTH_FACTS F ON F.REQUEST_ID = R.REQUEST_ID
WHERE P.TPA_ID = %s AND R.REQUEST_ID IN (%s, %s, %s)
ORDER BY R.REQUEST_ID
LIMIT 4
"""


class SourceReadUnavailable(RuntimeError):
    """Safe boundary error; never expose connector details or credentials."""


class SourceCase(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    request_id: str
    policy_id: str
    tpa_id: str
    product_id: str
    product_name: str
    policy_version: str
    continuous_cover_since: date
    admission_date: date
    estimated_total_inr: int = Field(ge=0)


class SnowflakeCaseSource:
    """The server supplies the mapping; HTTP headers/filters never select a TPA.

    Alpha allowlisting is deliberate, not general multi-tenant RLS. Mapping
    ownership must be verified before use; unknown tenants perform no I/O.
    """

    def __init__(self, connect: Callable[[], Any], tenant_tpas: Mapping[UUID, str]):
        self._connect = connect
        self._tenant_tpas = dict(tenant_tpas)

    def read_cases(self, tenant_id: UUID) -> list[SourceCase]:
        tpa = self._tenant_tpas.get(tenant_id)
        if tpa is None:
            return []
        try:
            with self._connect() as connection, connection.cursor() as cursor:
                cursor.execute(READ_SQL, (tpa, *ALPHA_REQUESTS), timeout=30)
                columns = [column[0].lower() for column in cursor.description]
                rows = cursor.fetchmany(4)
                records = [
                    SourceCase.model_validate(dict(zip(columns, row, strict=True))) for row in rows
                ]
                if len(records) > 3 or len({r.request_id for r in records}) != len(records):
                    raise ValueError("Duplicate or excessive source records")
                if any(r.tpa_id != tpa or r.request_id not in ALPHA_REQUESTS for r in records):
                    raise ValueError("Source scope mismatch")
                return records
        except Exception as exc:
            raise SourceReadUnavailable("Snowflake source read unavailable") from exc


def local_connection(connection_name: str = "cashlessiq") -> Any:
    """Explicit operator-only connection; no secrets in env files or API config.

    The optional connector is imported only here. No connection is opened by
    API startup, tests, or ordinary UI reads. Never fall back to ACCOUNTADMIN.
    """
    import snowflake.connector

    return snowflake.connector.connect(
        connection_name=connection_name,
        role="CIQ_PRODUCT_READER",
        warehouse="CIQ_WH",
        database="CASHLESSIQ",
        schema="DOCS",
        paramstyle="pyformat",
        login_timeout=30,
        network_timeout=30,
        session_parameters={
            "QUERY_TAG": "cashlessiq:product:p2:source-read",
            "STATEMENT_TIMEOUT_IN_SECONDS": 30,
            "STATEMENT_QUEUED_TIMEOUT_IN_SECONDS": 15,
        },
    )


def main() -> None:
    """Explicit bounded operator check; never called by API or CI."""
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Read approved synthetic source metadata only")
    parser.add_argument("--tenant-id", type=UUID, required=True)
    parser.add_argument("--verified-tpa-id", required=True)
    args = parser.parse_args()
    gateway = SnowflakeCaseSource(local_connection, {args.tenant_id: args.verified_tpa_id})
    try:
        records = gateway.read_cases(args.tenant_id)
    except SourceReadUnavailable:
        parser.exit(1, "Source read unavailable; check local authentication and reader grants.\n")
    print(json.dumps({"request_ids": [r.request_id for r in records], "count": len(records)}))


if __name__ == "__main__":
    main()
