"""Independent synthetic history expectations and malformed-row boundary tests."""

import json
import random
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from faker import Faker

from cashlessiq.source_history import SourceHistoryError, observe_member_history
from data_gen import generate

BASELINE = json.loads(
    (Path(__file__).parent / "fixtures/migration/member_history.json").read_text()
)["cases"]
IDENTIFIERS = ("request_id", "tpa_id", "policy_id", "member_id")


def arguments(case):
    member = {key: value for key, value in case.items() if key != "conditions"}
    conditions = [
        {**row, "request_id": case["request_id"], "tpa_id": case["tpa_id"]}
        for row in case["conditions"]
    ]
    return {"member": member, "conditions": conditions, **{key: case[key] for key in IDENTIFIERS}}


@pytest.mark.parametrize("case", BASELINE, ids=lambda row: row["request_id"])
def test_explicit_history_observation(case):
    inputs = arguments(deepcopy(case))
    before = deepcopy(inputs)
    result = observe_member_history(**inputs)
    assert json.loads(json.dumps(asdict(result), default=str)) == case
    assert inputs == before


def test_connector_decimal_and_condition_order():
    inputs = arguments(deepcopy(BASELINE[1]))
    inputs["member"]["sum_insured_inr"] = Decimal("950000")
    inputs["conditions"].reverse()
    assert observe_member_history(**inputs).sum_insured_inr == 950_000
    assert [row.icd10_code for row in observe_member_history(**inputs).conditions] == [
        "E11.6",
        "H25.9",
        "I10",
        "I83.9",
    ]


@pytest.mark.parametrize(
    "field,value",
    [
        ("request_id", "GOL001"),
        ("tpa_id", "TPA001"),
        ("policy_id", "POL0001"),
        ("member_id", "MEM0001"),
        ("claim_count", True),
        ("claim_count", -1),
        ("claim_count", Decimal("0.5")),
        ("sum_insured_inr", 950000.0),
        ("sum_insured_inr", "950000"),
        ("cumulative_bonus_inr", None),
        ("total_paid_inr", Decimal("NaN")),
        ("total_paid_inr", Decimal("Infinity")),
        ("total_paid_inr", 1),
        ("last_admission_date", "2026-99-01"),
        ("last_admission_date", "2026-10-02"),
        ("status", " "),
    ],
)
def test_reject_invalid_member_fields(field, value):
    inputs = arguments(deepcopy(BASELINE[1]))
    inputs["member"][field] = value
    with pytest.raises(SourceHistoryError, match="Source member history unavailable or invalid"):
        observe_member_history(**inputs)


@pytest.mark.parametrize(
    "fault",
    [
        "missing_member",
        "missing_field",
        "missing_claim_date",
        "timestamp",
        "duplicate",
        "overflow",
        "foreign_request",
        "foreign_owner",
        "string_bool",
        "bad_date",
        "empty_name",
    ],
)
def test_reject_incomplete_or_cross_scope_history(fault):
    inputs = arguments(deepcopy(BASELINE[1]))
    if fault == "missing_member":
        inputs["member"] = {}
    elif fault == "missing_field":
        del inputs["conditions"][0]["declared_at_proposal"]
    elif fault == "missing_claim_date":
        inputs["member"]["claim_count"] = 1
    elif fault == "timestamp":
        inputs["conditions"][0]["first_diagnosed_on"] = datetime(2024, 1, 1)
    elif fault == "duplicate":
        inputs["conditions"].append(inputs["conditions"][0])
    elif fault == "overflow":
        inputs["conditions"] *= 6
    elif fault == "foreign_request":
        inputs["conditions"][0]["request_id"] = "GOL001"
    elif fault == "foreign_owner":
        inputs["conditions"][0]["tpa_id"] = "TPA001"
    elif fault == "string_bool":
        inputs["conditions"][0]["declared_at_proposal"] = "True"
    elif fault == "bad_date":
        inputs["conditions"][0]["first_diagnosed_on"] = "2024-02-30"
    elif fault == "empty_name":
        inputs["conditions"][0]["condition_name"] = ""
    with pytest.raises(SourceHistoryError, match="Source member history unavailable or invalid"):
        observe_member_history(**inputs)


def test_history_constants_match_seeded_core_without_writing_files(monkeypatch):
    """Compare explicit constants to generator source, not UI snapshots or live rows.

    Capture core CSV rows in memory. No PDFs, files, database, or rules run.
    Faker's time-relative DOB is irrelevant: no demographic values are inspected.
    """
    tables = {}
    monkeypatch.setattr(
        generate, "write_csv", lambda name, _fields, rows: tables.update({name: rows})
    )
    fake = Faker("en_IN")
    fake.seed_instance(generate.SEED)
    generate.generate_core(fake, random.Random(generate.SEED))
    for case in BASELINE:
        policy = next(row for row in tables["policy.csv"] if row["policy_id"] == case["policy_id"])
        for key in ("member_id", "tpa_id", "sum_insured_inr", "cumulative_bonus_inr", "status"):
            assert policy[key] == case[key]
        claims = [row for row in tables["claim.csv"] if row["policy_id"] == case["policy_id"]]
        assert len(claims) == case["claim_count"]
        assert sum(row["paid_inr"] for row in claims) == case["total_paid_inr"]
        assert (
            max((row["admission_date"] for row in claims), default=None)
            == case["last_admission_date"]
        )
        conditions = sorted(
            (
                {key: value for key, value in row.items() if key != "member_id"}
                for row in tables["member_condition.csv"]
                if row["member_id"] == case["member_id"]
            ),
            key=lambda row: row["icd10_code"],
        )
        assert json.loads(json.dumps(conditions, default=str)) == case["conditions"]
