"""CashlessIQ reviewer console landing page."""

import streamlit as st
from ui import header

st.set_page_config(page_title="CashlessIQ", page_icon="₹", layout="wide")
_, who = header("CashlessIQ")
st.subheader("Cited cashless pre-authorisation, ready for human review")
st.write(
    "The copilot extracts case facts, applies deterministic policy rules, retrieves the exact "
    "wording, and drafts a recommendation. It never issues a denial."
)
st.info(
    "Start in **Queue**, open a request in **Case**, then review the decision and its evidence. "
    f"Your current permissions are derived from `{who['ROLE_NAME']}`."
)
