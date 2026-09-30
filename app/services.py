"""Snowflake data and Cortex Agent services used by the Streamlit pages."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Mapping
from typing import Any

from cashlessiq.decision_schema import DecisionValidationError, validate_decision

AGENT_NAME = "CASHLESSIQ.AI.CASHLESSIQ_AGENT"


def rows(session: Any, query: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
    """Execute a parameterized read and return uppercase-key dictionaries."""

    return [row.as_dict() for row in session.sql(query, params=params or []).collect()]


def identity(session: Any) -> dict[str, str]:
    return rows(
        session,
        "SELECT CURRENT_USER() AS USER_NAME, CURRENT_ROLE() AS ROLE_NAME",
    )[0]


def queue(session: Any) -> list[dict[str, Any]]:
    return rows(
        session,
        """SELECT R.REQUEST_ID, R.RECEIVED_AT, R.STATUS, H.NAME AS HOSPITAL_NAME,
                  M.FULL_NAME AS MEMBER_NAME, F.ESTIMATED_TOTAL_INR,
                  DATEDIFF('minute', R.RECEIVED_AT, CURRENT_TIMESTAMP()) AS ELAPSED_MIN,
                  IFF(DATEDIFF('minute', R.RECEIVED_AT, CURRENT_TIMESTAMP()) >= 45, 'RED',
                    IFF(DATEDIFF('minute', R.RECEIVED_AT, CURRENT_TIMESTAMP()) >= 30,
                        'AMBER', 'GREEN')) AS SLA_STATE
           FROM CASHLESSIQ.DOCS.PREAUTH_REQUEST R
           JOIN CASHLESSIQ.CORE.HOSPITAL H ON H.HOSPITAL_ID = R.HOSPITAL_ID
           JOIN CASHLESSIQ.CORE.POLICY P ON P.POLICY_ID = R.POLICY_ID
           JOIN CASHLESSIQ.CORE.MEMBER M ON M.MEMBER_ID = P.MEMBER_ID
           LEFT JOIN CASHLESSIQ.DOCS.PREAUTH_FACTS F ON F.REQUEST_ID = R.REQUEST_ID
           ORDER BY R.RECEIVED_AT DESC""",
    )


def case(session: Any, request_id: str) -> dict[str, Any]:
    found = rows(
        session,
        """SELECT R.REQUEST_ID, R.FILE_PATH, R.RECEIVED_AT, R.STATUS,
                  H.NAME AS HOSPITAL_NAME, H.CITY AS HOSPITAL_CITY,
                  P.POLICY_ID, P.PRODUCT_ID, P.SUM_INSURED_INR,
                  M.MEMBER_ID, M.FULL_NAME, M.PHONE,
                  F.DIAGNOSIS, F.ICD10_CODE, F.PROCEDURE, F.IS_EMERGENCY,
                  F.ADMISSION_DATE, F.PLANNED_LOS_DAYS, F.ROOM_CATEGORY,
                  F.ROOM_RENT_PER_DAY_INR, F.ICU_DAYS, F.COST_BREAKUP,
                  F.ESTIMATED_TOTAL_INR, F.CLINICAL_NOTE, F.MISSING_FIELDS
           FROM CASHLESSIQ.DOCS.PREAUTH_REQUEST R
           JOIN CASHLESSIQ.CORE.HOSPITAL H ON H.HOSPITAL_ID = R.HOSPITAL_ID
           JOIN CASHLESSIQ.CORE.POLICY P ON P.POLICY_ID = R.POLICY_ID
           JOIN CASHLESSIQ.CORE.MEMBER M ON M.MEMBER_ID = P.MEMBER_ID
           LEFT JOIN CASHLESSIQ.DOCS.PREAUTH_FACTS F ON F.REQUEST_ID = R.REQUEST_ID
           WHERE R.REQUEST_ID = ?""",
        [request_id],
    )
    if not found:
        raise ValueError(f"Unknown request: {request_id}")
    return found[0]


def member_summary(session: Any, member_id: str, policy_id: str) -> dict[str, Any]:
    """Return the compact member-360 facts used by the reviewer console."""

    condition_rows = rows(
        session,
        """SELECT CONDITION_NAME, ICD10_CODE, FIRST_DIAGNOSED_ON,
                  DECLARED_AT_PROPOSAL
           FROM CASHLESSIQ.CORE.MEMBER_CONDITION
           WHERE MEMBER_ID = ? ORDER BY FIRST_DIAGNOSED_ON""",
        [member_id],
    )
    claim_rows = rows(
        session,
        """SELECT COUNT(*) AS CLAIM_COUNT,
                  COALESCE(SUM(PAID_INR), 0) AS TOTAL_PAID_INR,
                  MAX(ADMISSION_DATE) AS LAST_ADMISSION_DATE
           FROM CASHLESSIQ.CORE.CLAIM WHERE POLICY_ID = ?""",
        [policy_id],
    )
    return {"conditions": condition_rows, "claims": claim_rows[0]}


def source_pdf_url(session: Any, file_path: str) -> str:
    """Create a short-lived URL for a synthetic pre-authorisation PDF."""

    result = rows(
        session,
        """SELECT GET_PRESIGNED_URL(
                 @CASHLESSIQ.DOCS.PREAUTH_STAGE, ?, 900) AS PDF_URL""",
        [file_path],
    )
    return result[0]["PDF_URL"]


def latest_decision(session: Any, request_id: str) -> dict[str, Any] | None:
    found = rows(
        session,
        """SELECT DECISION_ID, DECISION_JSON, CREATED_AT, LATENCY_MS
           FROM CASHLESSIQ.APP.DECISION WHERE REQUEST_ID = ?
           ORDER BY CREATED_AT DESC LIMIT 1""",
        [request_id],
    )
    if not found:
        return None
    decision = found[0]
    if isinstance(decision["DECISION_JSON"], str):
        decision["DECISION_JSON"] = json.loads(decision["DECISION_JSON"])
    return decision


def decision_log(session: Any) -> list[dict[str, Any]]:
    return rows(
        session,
        """SELECT D.DECISION_ID, D.REQUEST_ID, D.OUTCOME, D.PAYABLE_INR,
                  D.SCHEMA_VALID, D.LATENCY_MS, D.CREATED_AT,
                  A.REVIEWER, A.ROLE, A.ACTION, A.FINAL_PAYABLE_INR, A.ACTED_AT,
                  D.DECISION_JSON:sla.state::VARCHAR AS SLA_STATE
           FROM CASHLESSIQ.APP.DECISION D
           LEFT JOIN CASHLESSIQ.APP.REVIEW_ACTION A ON A.DECISION_ID = D.DECISION_ID
           ORDER BY D.CREATED_AT DESC""",
    )


def clause(session: Any, clause_id: str) -> dict[str, Any] | None:
    found = rows(
        session,
        "SELECT CLAUSE_ID, HEADING, TEXT, PAGE FROM CASHLESSIQ.DOCS.POLICY_CLAUSE "
        "WHERE CLAUSE_ID = ?",
        [clause_id],
    )
    return found[0] if found else None


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("```"):
            text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            return _json_object(json.loads(text))
        except json.JSONDecodeError:
            start, end = text.find("{"), text.rfind("}")
            if start >= 0 and end > start:
                return _json_object(json.loads(text[start : end + 1]))
    if isinstance(value, Mapping):
        if {"request_id", "outcome", "lines"}.issubset(value):
            return dict(value)
        for child in reversed(list(value.values())):
            try:
                return _json_object(child)
            except (TypeError, ValueError, json.JSONDecodeError):
                pass
    if isinstance(value, list):
        for child in reversed(value):
            try:
                return _json_object(child)
            except (TypeError, ValueError, json.JSONDecodeError):
                pass
    raise ValueError("Agent response contains no decision JSON")


def _agent_request(session: Any, prompt: str) -> tuple[dict[str, Any], str | None]:
    body = json.dumps(
        {"messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}]}
    )
    row = session.sql(
        "SELECT TRY_PARSE_JSON(SNOWFLAKE.CORTEX.DATA_AGENT_RUN"
        f"('{AGENT_NAME}', ?, TRUE)) AS RESPONSE",
        params=[body],
    ).collect()[0]
    payload = row["RESPONSE"]
    if isinstance(payload, str):
        payload = json.loads(payload)
    run_id = payload.get("metadata", {}).get("run_id")
    return _json_object(payload), run_id


def run_agent(session: Any, request_id: str) -> dict[str, Any]:
    """Run, validate, retry once, and persist a reviewer draft."""

    started = time.perf_counter()
    prompt = f"Produce the CashlessIQ decision for request_id {request_id}. JSON only."
    for attempt in range(2):
        try:
            decision, run_id = _agent_request(session, prompt)
            validate_decision(decision)
            break
        except (DecisionValidationError, ValueError, json.JSONDecodeError) as exc:
            if attempt:
                raise
            prompt += f"\nValidation failed: {exc}. Correct it and return raw JSON only."
    latency_ms = int((time.perf_counter() - started) * 1000)
    decision_id = f"DEC-{uuid.uuid4().hex[:20].upper()}"
    session.sql(
        """INSERT INTO CASHLESSIQ.APP.DECISION
           (DECISION_ID, REQUEST_ID, AGENT_RUN_ID, MODEL, OUTCOME, PAYABLE_INR,
            DECISION_JSON, SCHEMA_VALID, LATENCY_MS)
           SELECT ?, ?, ?, 'auto', ?, ?, PARSE_JSON(?), TRUE, ?""",
        params=[decision_id, request_id, run_id, decision["outcome"],
                decision["total_payable_inr"], json.dumps(decision), latency_ms],
    ).collect()
    return decision


def review(
    session: Any,
    decision_id: str,
    action: str,
    final_payable_inr: int | None,
    comment: str,
) -> None:
    who = identity(session)
    session.sql(
        """INSERT INTO CASHLESSIQ.APP.REVIEW_ACTION
           (ACTION_ID, DECISION_ID, REVIEWER, ROLE, ACTION, FINAL_PAYABLE_INR, COMMENT)
           SELECT ?, ?, ?, ?, ?, ?, ?""",
        params=[f"ACT-{uuid.uuid4().hex[:20].upper()}", decision_id, who["USER_NAME"],
                who["ROLE_NAME"], action, final_payable_inr, comment or None],
    ).collect()
