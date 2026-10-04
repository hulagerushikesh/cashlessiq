"""Run the 30-case golden evaluation and persist an auditable scorecard."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

import yaml
from snowflake.snowpark import Session

from cashlessiq.agent_client import decide

GOLDEN_PATH = Path(__file__).parents[1] / "data_gen" / "golden_cases.yaml"


def score(decision: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    """Score one schema-valid decision against its fixed golden expectation."""

    expected_citations = set(case["expected_clause_ids"])
    actual_citations = {
        citation["id"]
        for line in decision["lines"]
        for citation in line["citations"]
        if citation["type"] == "clause"
    }
    recall = (
        len(expected_citations & actual_citations) / len(expected_citations)
        if expected_citations
        else 1.0
    )
    expected_payable = case.get("expected_payable_inr")
    tolerance = int(case.get("tolerance_inr", 0))
    amount_match = expected_payable is None or (
        abs(int(decision["total_payable_inr"]) - int(expected_payable)) <= tolerance
    )
    return {
        "actual_outcome": decision["outcome"],
        "actual_payable_inr": decision["total_payable_inr"],
        "outcome_match": decision["outcome"] == case["expected_outcome"],
        "amount_match": amount_match,
        "citation_recall": recall,
    }


def _git_sha() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()


def _insert_result(
    session: Session,
    run_id: str,
    request_id: str,
    result: dict[str, Any],
    latency_ms: int,
    error: str | None,
) -> None:
    session.sql(
        """INSERT INTO CASHLESSIQ.EVAL.EVAL_RESULT
           (EVAL_RUN_ID, REQUEST_ID, ACTUAL_OUTCOME, ACTUAL_PAYABLE_INR,
            OUTCOME_MATCH, AMOUNT_MATCH, CITATION_RECALL, SCHEMA_VALID,
            LATENCY_MS, ERROR)
           SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?, ?""",
        params=[
            run_id,
            request_id,
            result.get("actual_outcome"),
            result.get("actual_payable_inr"),
            result.get("outcome_match", False),
            result.get("amount_match", False),
            result.get("citation_recall", 0.0),
            error is None,
            latency_ms,
            error,
        ],
    ).collect()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--connection", default="cashlessiq")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--model", default="auto")
    args = parser.parse_args()
    cases = yaml.safe_load(GOLDEN_PATH.read_text(encoding="utf-8"))["cases"][: args.limit]
    run_id = f"EVAL-{uuid.uuid4().hex[:20].upper()}"
    session = Session.builder.config("connection_name", args.connection).create()
    try:
        session.sql(
            """INSERT INTO CASHLESSIQ.EVAL.EVAL_RUN
               (EVAL_RUN_ID, MODEL, GIT_SHA, STARTED_AT)
               SELECT ?, ?, ?, CURRENT_TIMESTAMP()""",
            params=[run_id, args.model, _git_sha()],
        ).collect()
        for index, case in enumerate(cases, start=1):
            request_id = case["request_id"]
            started = time.perf_counter()
            try:
                decision = decide(session, request_id, model=args.model, persist=False)
                result = score(decision, case)
                error = None
            except Exception as exc:  # keep failures visible instead of losing the run
                result = {}
                error = f"{type(exc).__name__}: {exc}"[:4000]
            latency_ms = int((time.perf_counter() - started) * 1000)
            _insert_result(session, run_id, request_id, result, latency_ms, error)
            print(
                json.dumps(
                    {
                        "n": index,
                        "request_id": request_id,
                        "expected": case["expected_outcome"],
                        "actual": result.get("actual_outcome"),
                        "schema_valid": error is None,
                        "outcome_match": result.get("outcome_match", False),
                        "amount_match": result.get("amount_match", False),
                        "citation_recall": result.get("citation_recall", 0.0),
                        "latency_ms": latency_ms,
                        "error": error,
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
        session.sql(
            "UPDATE CASHLESSIQ.EVAL.EVAL_RUN SET COMPLETED_AT=CURRENT_TIMESTAMP() "
            "WHERE EVAL_RUN_ID=?",
            params=[run_id],
        ).collect()
        summary = session.sql(
            """SELECT COUNT(*) AS TOTAL, COUNT_IF(SCHEMA_VALID) AS SCHEMA_VALID,
                      COUNT_IF(OUTCOME_MATCH) AS OUTCOME_MATCH,
                      COUNT_IF(AMOUNT_MATCH) AS AMOUNT_MATCH,
                      ROUND(AVG(CITATION_RECALL), 3) AS CITATION_RECALL,
                      ROUND(AVG(LATENCY_MS), 0) AS AVG_LATENCY_MS
               FROM CASHLESSIQ.EVAL.EVAL_RESULT WHERE EVAL_RUN_ID=?""",
            params=[run_id],
        ).collect()[0].as_dict()
        print(json.dumps({"eval_run_id": run_id, **summary}, sort_keys=True))
        target = len(cases)
        return int(summary["SCHEMA_VALID"] != target or summary["OUTCOME_MATCH"] < 24)
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
