"""Golden and boundary tests for the deterministic Phase 3a rules core."""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
import yaml

from cashlessiq.rules import compute_payable, evaluate_case, sla_status
from cashlessiq.rules.models import (
    CostItem,
    MemberCondition,
    Outcome,
    Policy,
    PreAuthFacts,
    Rule,
    SlaState,
)
from data_gen.policies import PRODUCT, RULES

ROOT = Path(__file__).resolve().parents[1]


def _cases() -> list[dict]:
    return yaml.safe_load(
        (ROOT / "data_gen" / "golden_cases.yaml").read_text(encoding="utf-8")
    )["cases"]


def _rules() -> tuple[Rule, ...]:
    return tuple(
        Rule(
            rule_id=rule_id,
            product_id=PRODUCT["product_id"],
            rule_type=rule_type,
            params=json.loads(params),
            clause_id=clause_id,
        )
        for rule_id, rule_type, params, clause_id in RULES
    )


def _inputs(case: dict) -> tuple[Policy, PreAuthFacts, tuple[MemberCondition, ...]]:
    policy = Policy(
        policy_id=case["policy_id"],
        member_id=f"MEM{int(case['policy_id'][-4:]):04d}",
        product_id=PRODUCT["product_id"],
        tpa_id="TPA001",
        sum_insured_inr=500_000,
        inception_date=case["inception_date"],
        continuous_cover_since=case["continuous_cover_since"],
    )
    missing = tuple(
        field
        for field in (
            "diagnosis",
            "procedure",
            "admission_date",
            "room_category",
            "room_rent_per_day_inr",
            "estimated_total_inr",
            "cost_breakup",
        )
        if case.get(field) is None or (field == "cost_breakup" and not case.get(field))
    )
    facts = PreAuthFacts(
        request_id=case["request_id"],
        diagnosis=case.get("diagnosis"),
        icd10_code=case.get("icd10_code"),
        procedure=case.get("procedure"),
        is_emergency=case.get("is_emergency"),
        admission_date=case.get("admission_date"),
        planned_los_days=case.get("planned_los_days"),
        room_category=case.get("room_category"),
        room_rent_per_day_inr=case.get("room_rent_per_day_inr"),
        icu_days=case.get("icu_days", 0),
        cost_breakup=tuple(CostItem(**item) for item in case.get("cost_breakup", ())),
        estimated_total_inr=case.get("estimated_total_inr"),
        clinical_note=case.get("clinical_note"),
        missing_fields=missing,
    )
    conditions = tuple(
        MemberCondition(**condition) for condition in case.get("declared_conditions", ())
    )
    return policy, facts, conditions


@pytest.mark.parametrize("case", _cases(), ids=lambda case: case["request_id"])
def test_all_golden_outcomes_and_amounts(case: dict) -> None:
    policy, facts, conditions = _inputs(case)
    result = evaluate_case(
        policy,
        facts,
        _rules(),
        si_remaining_inr=case.get(
            "si_remaining_inr", policy.sum_insured_inr + policy.cumulative_bonus_inr
        ),
        declared_conditions=conditions,
    )

    assert result.outcome == Outcome(case["expected_outcome"])
    if case["expected_payable_inr"] is None:
        assert result.payable is None
    else:
        assert result.payable is not None
        assert result.payable.total_payable_inr == case["expected_payable_inr"]
        assert result.payable.total_claimed_inr == sum(
            item["claimed_inr"] for item in case["cost_breakup"]
        )
        assert sum(line.payable_inr for line in result.payable.lines) == (
            result.payable.total_payable_inr
        )
        assert all(line.citations for line in result.payable.lines)


def test_golden_suite_exercises_every_required_tag() -> None:
    assert set(Counter(case["tag"] for case in _cases())) == {
        "clean",
        "room_over_cap",
        "sublimit",
        "waiting_initial",
        "accident_exempt",
        "waiting_specific",
        "waiting_ped",
        "missing_info",
        "si_exhaustion",
        "exclusion",
    }


def test_room_proportion_is_driven_by_rule_data() -> None:
    case = next(case for case in _cases() if case["tag"] == "room_over_cap")
    policy, facts, conditions = _inputs(case)
    result = evaluate_case(
        policy,
        facts,
        _rules(),
        si_remaining_inr=policy.sum_insured_inr,
        declared_conditions=conditions,
    )
    assert result.payable is not None
    professional = next(
        line for line in result.payable.lines if line.item == "Procedure and professional fees"
    )
    assert "5000/8000 x 72000 = 45000" in professional.calc
    assert {citation.id for citation in professional.citations} == {
        "NIA-4.1-NOTE-B",
        "NIA-9.5",
    }


def test_icu_cap_precedes_copay() -> None:
    policy = Policy(
        policy_id="POL-ICU",
        member_id="MEM-ICU",
        product_id=PRODUCT["product_id"],
        tpa_id="TPA001",
        sum_insured_inr=300_000,
        inception_date=date(2023, 1, 1),
        continuous_cover_since=date(2023, 1, 1),
    )
    facts = PreAuthFacts(
        request_id="ICU001",
        diagnosis="Critical illness",
        icd10_code="J96.0",
        procedure="ICU management",
        is_emergency=True,
        admission_date=date(2026, 10, 2),
        planned_los_days=2,
        room_category="ICU",
        room_rent_per_day_inr=0,
        icu_days=2,
        cost_breakup=(CostItem("ICU charges", 30_000),),
        estimated_total_inr=30_000,
        clinical_note="Two ICU days.",
    )
    result = compute_payable(policy, facts, _rules(), si_remaining_inr=300_000)
    assert result.total_payable_inr == 19_000
    assert result.lines[0].calc == "min(30000, 10000 x 2) = 20000; 20000 x 95% = 19000"


@pytest.mark.parametrize(
    ("elapsed", "expected"),
    ((0, SlaState.GREEN), (29, SlaState.GREEN), (30, SlaState.AMBER),
     (44, SlaState.AMBER), (45, SlaState.RED), (75, SlaState.RED)),
)
def test_sla_boundaries(elapsed: int, expected: SlaState) -> None:
    received = datetime(2026, 9, 30, 9, 0, tzinfo=UTC)
    status = sla_status(received, received + timedelta(minutes=elapsed))
    assert status.state == expected
    assert status.elapsed_min == elapsed
    assert status.remaining_min == max(60 - elapsed, 0)


def test_sla_rejects_naive_timestamps() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        sla_status(datetime(2026, 9, 30, 9), datetime(2026, 9, 30, 10))


def test_whole_month_calculation_handles_month_end() -> None:
    from cashlessiq.rules.waiting_periods import completed_months

    assert completed_months(date(2026, 1, 31), date(2026, 2, 28)) == 0
    assert completed_months(date(2026, 1, 31), date(2026, 3, 31)) == 2
