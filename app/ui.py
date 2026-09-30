"""Shared Streamlit presentation helpers."""

from __future__ import annotations

from typing import Any

import streamlit as st
from services import identity


def session() -> Any:
    return st.connection("snowflake-callers-rights").session()


def header(title: str) -> tuple[Any, dict[str, str]]:
    active = session()
    who = identity(active)
    st.title(title)
    st.caption(f"Signed in as {st.user.user_name} · role {who['ROLE_NAME']}")
    return active, who


def rupees(value: Any) -> str:
    return "—" if value is None else f"₹{int(value):,}"


def allowed_actions(role: str) -> frozenset[str]:
    """Return reviewer actions allowed by the Phase 4 persona matrix."""

    if role in {"CIQ_MEDICAL_OFFICER", "CIQ_ADMIN"}:
        return frozenset({"ACCEPT", "EDIT", "QUERY", "REFER"})
    if role == "CIQ_PROCESSOR":
        return frozenset({"QUERY"})
    return frozenset()
