"""Run the Cortex Agent, validate its JSON, retry once, and persist it."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Mapping
from typing import Any

from cashlessiq.decision_schema import DecisionValidationError, validate_decision

AGENT_NAME = "CASHLESSIQ.AI.CASHLESSIQ_AGENT"


def _json_object(value: Any) -> dict[str, Any]:
    """Find the decision object in an aggregated DATA_AGENT_RUN response."""

    if isinstance(value, str):
        text = value.strip()
        if text.startswith("```"):
            text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError:
            start, end = text.find("{"), text.rfind("}")
            if start < 0 or end <= start:
                raise ValueError("Agent response contains no JSON object") from None
            decoded = json.loads(text[start : end + 1])
        return _json_object(decoded)
    if isinstance(value, Mapping):
        if {"request_id", "outcome", "lines"}.issubset(value):
            return dict(value)
        for key in ("response", "message", "content", "text", "data"):
            if key in value:
                try:
                    return _json_object(value[key])
                except (TypeError, ValueError, json.JSONDecodeError):
                    pass
        for child in value.values():
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
    raise ValueError("Agent response contains no CashlessIQ decision JSON")


def _run(session: Any, prompt: str) -> tuple[dict[str, Any], str | None]:
    body = json.dumps(
        {"messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}]}
    )
    row = session.sql(
        "SELECT TRY_PARSE_JSON(SNOWFLAKE.CORTEX.DATA_AGENT_RUN"
        f"('{AGENT_NAME}', ?, TRUE)) AS RESPONSE",
        params=[body],
    ).collect()[0]
    response = row["RESPONSE"]
    if isinstance(response, str):
        response = json.loads(response)
    run_id = response.get("run_id") if isinstance(response, Mapping) else None
    return _json_object(response), run_id


def decide(
    session: Any, request_id: str, *, model: str = "auto", persist: bool = True
) -> dict[str, Any]:
    """Return a validated decision, retrying once with exact validation feedback."""

    started = time.perf_counter()
    prompt = f"Produce the CashlessIQ decision for request_id {request_id}."
    run_id: str | None = None
    error: Exception | None = None
    for attempt in range(2):
        try:
            decision, run_id = _run(session, prompt)
            validate_decision(decision)
            break
        except (DecisionValidationError, ValueError, json.JSONDecodeError) as exc:
            error = exc
            if attempt:
                raise
            prompt += (
                f"\nYour previous response was invalid: {exc}. Return a corrected JSON object only."
            )
    else:  # pragma: no cover - loop either breaks or raises
        raise error or RuntimeError("Agent did not return a decision")

    latency_ms = int((time.perf_counter() - started) * 1000)
    if persist:
        decision_id = f"DEC-{uuid.uuid4().hex[:20].upper()}"
        session.sql(
            """INSERT INTO CASHLESSIQ.APP.DECISION
               (DECISION_ID, REQUEST_ID, AGENT_RUN_ID, MODEL, OUTCOME, PAYABLE_INR,
                DECISION_JSON, SCHEMA_VALID, LATENCY_MS)
               SELECT ?, ?, ?, ?, ?, ?, PARSE_JSON(?), TRUE, ?""",
            params=[
                decision_id,
                request_id,
                run_id,
                model,
                decision["outcome"],
                decision["total_payable_inr"],
                json.dumps(decision),
                latency_ms,
            ],
        ).collect()
    return decision
