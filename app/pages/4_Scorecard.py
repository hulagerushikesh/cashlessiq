"""Measured golden-set quality for the latest completed evaluation run."""

import streamlit as st
from services import rows
from ui import header

active, _ = header("Evaluation scorecard")
runs = rows(
    active,
    """SELECT EVAL_RUN_ID, MODEL, GIT_SHA, STARTED_AT, COMPLETED_AT
       FROM CASHLESSIQ.EVAL.EVAL_RUN
       WHERE COMPLETED_AT IS NOT NULL ORDER BY COMPLETED_AT DESC LIMIT 1""",
)
if not runs:
    st.info("No completed evaluation run yet. Run `make eval` as CIQ_ADMIN.")
    st.stop()

run = runs[0]
summary = rows(
    active,
    """SELECT COUNT(*) AS TOTAL, COUNT_IF(SCHEMA_VALID) AS SCHEMA_VALID,
              COUNT_IF(OUTCOME_MATCH) AS OUTCOME_MATCH,
              COUNT_IF(AMOUNT_MATCH) AS AMOUNT_MATCH,
              AVG(CITATION_RECALL) AS CITATION_RECALL,
              AVG(LATENCY_MS) AS AVG_LATENCY_MS
       FROM CASHLESSIQ.EVAL.EVAL_RESULT WHERE EVAL_RUN_ID = ?""",
    [run["EVAL_RUN_ID"]],
)[0]

st.caption(
    f"Run {run['EVAL_RUN_ID']} · model {run['MODEL']} · commit {run['GIT_SHA'][:8]} · "
    f"completed {run['COMPLETED_AT']}"
)
total = int(summary["TOTAL"] or 0)
columns = st.columns(5)
columns[0].metric("Schema valid", f"{int(summary['SCHEMA_VALID'])}/{total}")
columns[1].metric("Outcome correct", f"{int(summary['OUTCOME_MATCH'])}/{total}")
columns[2].metric("Amount correct", f"{int(summary['AMOUNT_MATCH'])}/{total}")
columns[3].metric("Citation recall", f"{float(summary['CITATION_RECALL'] or 0):.0%}")
columns[4].metric("Average latency", f"{int(summary['AVG_LATENCY_MS'] or 0) / 1000:.1f}s")

details = rows(
    active,
    """SELECT REQUEST_ID, ACTUAL_OUTCOME, ACTUAL_PAYABLE_INR, OUTCOME_MATCH,
              AMOUNT_MATCH, CITATION_RECALL, SCHEMA_VALID, LATENCY_MS, ERROR
       FROM CASHLESSIQ.EVAL.EVAL_RESULT WHERE EVAL_RUN_ID = ? ORDER BY REQUEST_ID""",
    [run["EVAL_RUN_ID"]],
)
st.dataframe(details, use_container_width=True, hide_index=True)
