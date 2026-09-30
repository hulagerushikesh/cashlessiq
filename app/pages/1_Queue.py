"""Reviewer work queue with deterministic SLA states."""

import streamlit as st
from services import queue
from ui import header, rupees

active, _ = header("Pre-authorisation queue")
requests = queue(active)
state = st.segmented_control("SLA state", ["ALL", "GREEN", "AMBER", "RED"], default="ALL")
if state != "ALL":
    requests = [row for row in requests if row["SLA_STATE"] == state]

st.metric("Requests", len(requests))
for row in requests:
    with st.container(border=True):
        left, middle, right = st.columns([3, 2, 1])
        left.subheader(row["REQUEST_ID"])
        left.write(f"{row['HOSPITAL_NAME']} · {row['MEMBER_NAME']}")
        middle.metric("Estimate", rupees(row["ESTIMATED_TOTAL_INR"]))
        middle.write(f"Status: {row['STATUS']}")
        right.metric("SLA", row["SLA_STATE"])
        right.caption(f"{row['ELAPSED_MIN']} minutes elapsed")
        if right.button("Open case", key=f"open-{row['REQUEST_ID']}", type="primary"):
            st.session_state["request_id"] = row["REQUEST_ID"]
            st.switch_page("pages/2_Case.py")
