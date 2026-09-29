"""Minimal Phase 0 container-runtime Cortex Agent connectivity spike."""

from __future__ import annotations

import json

import _snowflake
import streamlit as st

AGENT_ENDPOINT = "/api/v2/databases/CASHLESSIQ/schemas/AI/agents/CIQ_SPIKE_AGENT:run"


def run_spike() -> object:
    """Call the temporary Cortex Agent through the active Snowflake session."""

    payload = {
        "messages": [
            {
                "role": "user",
                "content": [{"type": "text", "text": "Reply with: CashlessIQ spike connected."}],
            }
        ]
    }
    # VERIFY WITH COCO: Confirm send_snow_api_request is available in the
    # selected 2026 container runtime and confirm the Agent response envelope.
    response = _snowflake.send_snow_api_request(
        "POST",
        AGENT_ENDPOINT,
        {"Content-Type": "application/json"},
        {},
        json.dumps(payload),
        None,
        30_000,
    )
    return response


st.set_page_config(page_title="CashlessIQ spike", page_icon="❄️")
st.title("CashlessIQ Agent connectivity spike")
st.caption("Phase 0 only — this is not the reviewer console.")

if st.button("Call CIQ_SPIKE_AGENT", type="primary"):
    try:
        st.success("Agent replied")
        st.write(run_spike())
    except Exception as exc:
        st.error("Agent call failed. Copy this error into the CoCo session.")
        st.exception(exc)
