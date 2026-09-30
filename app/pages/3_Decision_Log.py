"""Auditable decision and reviewer-action log."""

import streamlit as st
from services import decision_log
from ui import header

active, _ = header("Decision log")
records = decision_log(active)
outcomes = sorted({row["OUTCOME"] for row in records})
reviewers = sorted({row["REVIEWER"] for row in records if row["REVIEWER"]})
sla_states = sorted({row["SLA_STATE"] for row in records if row["SLA_STATE"]})
left, middle, right = st.columns(3)
selected_outcome = left.multiselect("Outcome", outcomes)
selected_reviewer = middle.multiselect("Reviewer", reviewers)
selected_sla = right.multiselect("SLA state", sla_states)
if selected_outcome:
    records = [row for row in records if row["OUTCOME"] in selected_outcome]
if selected_reviewer:
    records = [row for row in records if row["REVIEWER"] in selected_reviewer]
if selected_sla:
    records = [row for row in records if row["SLA_STATE"] in selected_sla]
st.dataframe(records, use_container_width=True, hide_index=True)
