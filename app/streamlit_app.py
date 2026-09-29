"""Minimal Phase 0 container-runtime Cortex Agent connectivity spike."""

from __future__ import annotations

import json
import os
from pathlib import Path

import requests
import streamlit as st

AGENT_ENDPOINT = "/api/v2/databases/CASHLESSIQ/schemas/AI/agents/CIQ_SPIKE_AGENT:run"


def run_spike() -> object:
    """Call the temporary Agent with the container's scoped OAuth token."""

    payload = {
        "messages": [
            {
                "role": "user",
                "content": [{"type": "text", "text": "Reply with: CashlessIQ spike connected."}],
            }
        ],
        "stream": False,
    }
    host = os.environ["SNOWFLAKE_HOST"]
    token = Path("/snowflake/session/token").read_text(encoding="utf-8")
    response = requests.post(
        f"https://{host}{AGENT_ENDPOINT}",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Snowflake-Authorization-Token-Type": "OAUTH",
        },
        data=json.dumps(payload),
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


st.set_page_config(page_title="CashlessIQ spike", page_icon="❄️")
st.title("CashlessIQ Agent connectivity spike")
st.caption("Phase 0 only — this is not the reviewer console.")

if st.button("Call CIQ_SPIKE_AGENT", type="primary"):
    try:
        with st.spinner("Waiting for the Agent..."):
            reply = run_spike()
        st.success("Agent replied")
        st.json(reply)
    except Exception as exc:
        st.error("Agent call failed. Copy this error into the CoCo session.")
        st.exception(exc)
