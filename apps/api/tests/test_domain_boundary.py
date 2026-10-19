"""Installed pure-domain boundary, independent of PostgreSQL and Snowflake."""

from dataclasses import asdict

import pytest
from cashlessiq_domain.source_decision import SourceDecisionError
from cashlessiq_domain.source_history import observe_member_history
from cashlessiq_domain.source_recommendation import observe_source_recommendation


def test_api_imports_installed_domain_missing_state():
    result = observe_source_recommendation(
        [],
        request_id="GOL024",
        tpa_id="TPA003",
        product_id="AS_NIA_V02_2425",
        estimated_total_inr=80_000,
        evidence=[],
        verified_record_ids=frozenset(),
    )
    assert asdict(result) == {
        "state": "MISSING",
        "request_id": "GOL024",
        "tpa_id": "TPA003",
        "product_id": "AS_NIA_V02_2425",
        "supplied_estimate_inr": 80_000,
    }


def test_api_imports_installed_domain_history():
    context = dict(request_id="GOL027", tpa_id="TPA003", policy_id="POL0027", member_id="MEM0027")
    result = observe_member_history(
        {
            **context,
            "sum_insured_inr": 600_000,
            "cumulative_bonus_inr": 0,
            "status": "ACTIVE",
            "claim_count": 0,
            "total_paid_inr": 0,
            "last_admission_date": None,
        },
        [],
        **context,
    )
    assert result.claim_count == 0
    assert result.conditions == ()


def test_api_domain_rejects_invalid_saved_data_not_missing():
    with pytest.raises(SourceDecisionError):
        observe_source_recommendation(
            [{}],
            request_id="GOL024",
            tpa_id="TPA003",
            product_id="AS_NIA_V02_2425",
            estimated_total_inr=80_000,
            evidence=[],
            verified_record_ids=frozenset(),
        )
