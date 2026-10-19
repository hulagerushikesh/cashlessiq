"""Operator-only P2 parity inputs; never wired to HTTP or automatic startup.

Requires separately reviewed grants. Reading a saved decision does not validate
it or establish parity. No fallback, money calculation, AI or writes occur here.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from ciq_api.snowflake_reads import SourceReadUnavailable
from ciq_api.source_scopes import SyntheticSourceScopes

# Each statement binds one inspected request AND its owner. No names, phone,
# DOB, document URLs, free-text clinical notes or clause text are selected.
MEMBER_SQL = """
SELECT R.REQUEST_ID, P.TPA_ID, P.POLICY_ID, P.MEMBER_ID,
       P.SUM_INSURED_INR, P.CUMULATIVE_BONUS_INR, P.STATUS,
       COUNT(C.CLAIM_ID) AS CLAIM_COUNT,
       COALESCE(SUM(C.PAID_INR), 0) AS TOTAL_PAID_INR,
       MAX(C.ADMISSION_DATE) AS LAST_ADMISSION_DATE
FROM CASHLESSIQ.DOCS.PREAUTH_REQUEST R
JOIN CASHLESSIQ.CORE.POLICY P ON P.POLICY_ID = R.POLICY_ID
LEFT JOIN CASHLESSIQ.CORE.CLAIM C ON C.POLICY_ID = P.POLICY_ID
WHERE R.REQUEST_ID = %s AND P.TPA_ID = %s
GROUP BY R.REQUEST_ID, P.TPA_ID, P.POLICY_ID, P.MEMBER_ID,
         P.SUM_INSURED_INR, P.CUMULATIVE_BONUS_INR, P.STATUS
LIMIT 2
"""

CONDITIONS_SQL = """
SELECT R.REQUEST_ID, P.TPA_ID, MC.ICD10_CODE, MC.CONDITION_NAME,
       MC.FIRST_DIAGNOSED_ON, MC.DECLARED_AT_PROPOSAL
FROM CASHLESSIQ.DOCS.PREAUTH_REQUEST R
JOIN CASHLESSIQ.CORE.POLICY P ON P.POLICY_ID = R.POLICY_ID
JOIN CASHLESSIQ.CORE.MEMBER_CONDITION MC ON MC.MEMBER_ID = P.MEMBER_ID
WHERE R.REQUEST_ID = %s AND P.TPA_ID = %s
ORDER BY MC.FIRST_DIAGNOSED_ON, MC.ICD10_CODE
LIMIT 21
"""

DECISION_SQL = """
SELECT R.REQUEST_ID, P.TPA_ID, D.DECISION_ID, D.OUTCOME, D.PAYABLE_INR,
       D.DECISION_JSON, D.SCHEMA_VALID, D.CREATED_AT
FROM CASHLESSIQ.DOCS.PREAUTH_REQUEST R
JOIN CASHLESSIQ.CORE.POLICY P ON P.POLICY_ID = R.POLICY_ID
JOIN CASHLESSIQ.APP.DECISION D ON D.REQUEST_ID = R.REQUEST_ID
WHERE R.REQUEST_ID = %s AND P.TPA_ID = %s
ORDER BY D.CREATED_AT DESC, D.DECISION_ID DESC
LIMIT 1
"""

EVIDENCE_SQL = """
SELECT R.REQUEST_ID, P.TPA_ID, PC.CLAUSE_ID, PC.PRODUCT_ID,
       PC.HEADING, PC.PAGE, PP.SOURCE_URL
FROM CASHLESSIQ.DOCS.PREAUTH_REQUEST R
JOIN CASHLESSIQ.CORE.POLICY P ON P.POLICY_ID = R.POLICY_ID
JOIN CASHLESSIQ.CORE.POLICY_PRODUCT PP ON PP.PRODUCT_ID = P.PRODUCT_ID
JOIN CASHLESSIQ.DOCS.POLICY_CLAUSE PC ON PC.PRODUCT_ID = P.PRODUCT_ID
WHERE R.REQUEST_ID = %s AND P.TPA_ID = %s
ORDER BY PC.CLAUSE_ID
LIMIT 101
"""


@dataclass(frozen=True)
class InspectionQuery:
    name: str
    sql: str
    maximum: int
    key: str


QUERIES = (
    InspectionQuery("member", MEMBER_SQL, 1, "policy_id"),
    InspectionQuery("conditions", CONDITIONS_SQL, 20, "icd10_code"),
    InspectionQuery("decision", DECISION_SQL, 1, "decision_id"),
    InspectionQuery("evidence", EVIDENCE_SQL, 100, "clause_id"),
)


class SnowflakeSourceInspection:
    """Return bounded diagnostic rows, not validated product read models.

    The caller must treat condition/decision data as restricted clinical data.
    Do not log the returned rows. This class intentionally has no CLI/export or
    API registration: grants and the parity validator must be reviewed first.
    """

    def __init__(self, connect: Callable[[], Any], tenant_tpas: Mapping[UUID, str]):
        self._connect = connect
        self._scopes = SyntheticSourceScopes(tenant_tpas)

    def inspect(self, tenant_id: UUID, request_id: str) -> dict[str, list[dict[str, Any]]]:
        scope = self._scopes.get(tenant_id)
        if scope is None or request_id not in scope.request_ids:
            return {}  # No network I/O for unknown or cross-owner cases.
        try:
            result = {}
            with self._connect() as connection, connection.cursor() as cursor:
                cursor.execute("USE SECONDARY ROLES NONE", timeout=30)
                for query in QUERIES:
                    cursor.execute(query.sql, (request_id, scope.tpa_id), timeout=30)
                    columns = [column[0].lower() for column in cursor.description]
                    if len(columns) != len(set(columns)):
                        raise ValueError("Ambiguous source columns")
                    rows = [
                        dict(zip(columns, row, strict=True))
                        for row in cursor.fetchmany(query.maximum + 1)
                    ]
                    if len(rows) > query.maximum:
                        raise ValueError("Source diagnostic row cap exceeded")
                    if any(
                        row["request_id"] != request_id or row["tpa_id"] != scope.tpa_id
                        for row in rows
                    ):
                        raise ValueError("Source diagnostic scope mismatch")
                    if len({row[query.key] for row in rows}) != len(rows):
                        raise ValueError("Duplicate source diagnostic key")
                    result[query.name] = rows
                # Missing source data is not a successful parity observation.
                if not result["member"]:
                    raise ValueError("Missing source policy context")
            return result
        except Exception as exc:
            raise SourceReadUnavailable("Snowflake source inspection unavailable") from exc
