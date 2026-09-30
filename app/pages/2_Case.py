"""Case facts, agent recommendation, evidence, and human action page."""

import json

import streamlit as st
from services import (
    case,
    clause,
    latest_decision,
    member_summary,
    review,
    run_agent,
    source_pdf_url,
)
from ui import allowed_actions, header, rupees

active, who = header("Case review")
request_id = st.text_input("Request ID", value=st.session_state.get("request_id", "GOL001"))
st.session_state["request_id"] = request_id

try:
    details = case(active, request_id)
except ValueError as exc:
    st.error(str(exc))
    st.stop()

top = st.columns(4)
top[0].metric("Estimate", rupees(details["ESTIMATED_TOTAL_INR"]))
top[1].metric("Sum insured", rupees(details["SUM_INSURED_INR"]))
top[2].metric("Member", details["FULL_NAME"])
top[3].metric("Policy", details["POLICY_ID"])

summary = member_summary(active, details["MEMBER_ID"], details["POLICY_ID"])
with st.expander("Member 360 summary"):
    claims = summary["claims"]
    st.write(
        f"**Prior claims:** {claims['CLAIM_COUNT']} · "
        f"**Previously paid:** {rupees(claims['TOTAL_PAID_INR'])} · "
        f"**Last admission:** {claims['LAST_ADMISSION_DATE'] or 'None'}"
    )
    if summary["conditions"]:
        st.dataframe(summary["conditions"], use_container_width=True, hide_index=True)
    else:
        st.caption("No recorded pre-existing conditions.")

with st.expander("Extracted case facts", expanded=True):
    st.write(f"**Hospital:** {details['HOSPITAL_NAME']}, {details['HOSPITAL_CITY']}")
    st.write(f"**Diagnosis:** {details['DIAGNOSIS']} · **ICD-10:** {details['ICD10_CODE']}")
    st.write(f"**Procedure:** {details['PROCEDURE']}")
    st.write(
        f"**Admission:** {details['ADMISSION_DATE']} · **Room:** {details['ROOM_CATEGORY']} · "
        f"**Stay:** {details['PLANNED_LOS_DAYS']} days"
    )
    st.write(f"**Clinical note:** {details['CLINICAL_NOTE']}")
    costs = details["COST_BREAKUP"]
    st.json(json.loads(costs) if isinstance(costs, str) else costs)
    try:
        pdf_url = source_pdf_url(active, details["FILE_PATH"])
        st.link_button("Open source PDF", pdf_url)
    except Exception:
        st.caption(f"Source PDF: {details['FILE_PATH']}")

if st.button("Run CashlessIQ", type="primary"):
    with st.spinner("Applying policy tools and retrieving cited wording…"):
        try:
            run_agent(active, request_id)
            st.success("Validated draft saved")
            st.rerun()
        except Exception as exc:
            st.error("The draft could not be validated. No recommendation was saved.")
            st.exception(exc)

saved = latest_decision(active, request_id)
if saved:
    decision = saved["DECISION_JSON"]
    st.divider()
    st.subheader(decision["outcome"])
    st.write(decision["summary"])
    cols = st.columns(3)
    cols[0].metric("Claimed", rupees(decision["total_claimed_inr"]))
    cols[1].metric("Payable", rupees(decision["total_payable_inr"]))
    cols[2].metric("SLA", decision["sla"]["state"], f"{decision['sla']['elapsed_min']} min")
    for line in decision["lines"]:
        with st.container(border=True):
            st.write(f"**{line['item']}** — {rupees(line['payable_inr'])} payable")
            st.caption(line["calc"])
            st.write(line["reason"])
            for citation in line["citations"]:
                with st.expander(f"{citation['type']}: {citation['id']}"):
                    evidence = (
                        clause(active, citation["id"])
                        if citation["type"] == "clause"
                        else None
                    )
                    st.write(evidence["TEXT"] if evidence else citation["id"])

    allowed = allowed_actions(who["ROLE_NAME"])
    amount = st.number_input(
        "Final payable (₹)",
        min_value=0,
        value=int(decision["total_payable_inr"]),
        disabled="EDIT" not in allowed,
    )
    comment = st.text_area("Reviewer comment")
    action_cols = st.columns(4)
    actions = (
        ("Accept", "ACCEPT"),
        ("Edit amount", "EDIT"),
        ("Raise query", "QUERY"),
        ("Refer", "REFER"),
    )
    for target, (label, action) in zip(action_cols, actions, strict=True):
        disabled = action not in allowed
        if target.button(label, disabled=disabled, key=f"review-{action}"):
            review(active, saved["DECISION_ID"], action, int(amount), comment)
            st.success(f"{action} recorded")
