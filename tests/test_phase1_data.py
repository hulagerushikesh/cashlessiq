"""Contract tests for the fixed-seed Phase 1 data specification."""

from collections import Counter
from pathlib import Path

import yaml

from data_gen.policies import PRODUCT, RULES, VERIFIED_AT, VERIFIED_BY

ROOT = Path(__file__).resolve().parents[1]


def cases() -> list[dict]:
    data = yaml.safe_load((ROOT / "data_gen/golden_cases.yaml").read_text())
    return data["cases"]


def test_golden_matrix_matches_build_plan() -> None:
    assert Counter(case["tag"] for case in cases()) == {
        "clean": 6,
        "room_over_cap": 5,
        "sublimit": 4,
        "waiting_initial": 3,
        "accident_exempt": 2,
        "waiting_specific": 3,
        "waiting_ped": 3,
        "missing_info": 2,
        "si_exhaustion": 1,
        "exclusion": 1,
    }


def test_each_golden_case_has_unique_id_and_expected_result() -> None:
    golden = cases()
    assert len(golden) == 30
    assert len({case["request_id"] for case in golden}) == 30
    assert all(case["expected_outcome"] != "DENY" for case in golden)
    assert all(case["expected_clause_ids"] for case in golden)


def test_hand_calculated_amounts_are_independent_constants() -> None:
    by_tag = {case["tag"]: case for case in cases()}
    assert by_tag["clean"]["expected_payable_inr"] == 95_000
    # Room cap ratio: 5,000 / 8,000. Medicines (24,000) are exempt:
    # (24,000 room + 72,000 professional) * 5/8 + 24,000 = 84,000;
    # mandatory 5% co-pay then gives 79,800.
    assert by_tag["room_over_cap"]["expected_payable_inr"] == 79_800
    assert by_tag["sublimit"]["expected_payable_inr"] == 38_000
    assert by_tag["si_exhaustion"]["expected_payable_inr"] == 42_750


def test_policy_identity_and_rules_have_human_signoff() -> None:
    assert PRODUCT["uin"] == "NIAHLIP25044V022425"
    assert len(RULES) == 10
    assert VERIFIED_BY == "Rushikesh"
    assert VERIFIED_AT == "2026-09-29T23:30:00+05:30"
    assert {rule_type for _, rule_type, _, _ in RULES} >= {
        "ROOM_RENT_CAP",
        "ICU_CAP",
        "PROCEDURE_SUBLIMIT",
        "COPAY",
        "WAITING_INITIAL",
        "WAITING_SPECIFIC",
        "WAITING_PED",
        "EXCLUSION",
        "PROPORTIONATE_DEDUCTION",
    }
