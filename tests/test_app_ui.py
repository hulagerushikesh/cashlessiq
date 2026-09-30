"""Unit tests for role-sensitive reviewer controls."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "app"))

from ui import allowed_actions


def test_medical_officer_can_take_all_review_actions() -> None:
    assert allowed_actions("CIQ_MEDICAL_OFFICER") == {
        "ACCEPT",
        "EDIT",
        "QUERY",
        "REFER",
    }


def test_processor_can_only_raise_query() -> None:
    assert allowed_actions("CIQ_PROCESSOR") == {"QUERY"}


def test_auditor_is_read_only() -> None:
    assert not allowed_actions("CIQ_AUDITOR")
