"""Generate the complete deterministic Phase 1 dataset (seed 42)."""

from __future__ import annotations

import csv
import json
import random
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import yaml
from faker import Faker

from data_gen.policies import CLAUSES, PRODUCT, RULES, VERIFIED_AT, VERIFIED_BY
from data_gen.preauth_pdfs import render_case

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data_gen" / "output"
SEED = 42
REFERENCE_DATE = date(2026, 9, 29)
CITIES = ("Pune", "Mumbai", "Bengaluru", "Hyderabad", "Delhi")
TPAS = (
    ("TPA001", "Sahyadri Benefit Services"),
    ("TPA002", "Nirmaan Health Desk"),
    ("TPA003", "Blue Banyan Assist"),
)
CONDITIONS = (
    ("E11.9", "Type 2 diabetes mellitus"),
    ("I10", "Essential hypertension"),
    ("H25.9", "Age-related cataract"),
    ("K40.9", "Inguinal hernia"),
    ("M17.9", "Knee osteoarthritis"),
    ("K80.2", "Gallstones"),
    ("J45.9", "Asthma"),
    ("E03.9", "Hypothyroidism"),
    ("N20.0", "Kidney stone"),
    ("K21.9", "Gastro-oesophageal reflux"),
    ("M10.9", "Gout"),
    ("J32.9", "Chronic sinusitis"),
    ("N40", "Benign prostate hyperplasia"),
    ("I83.9", "Varicose veins"),
    ("K60.2", "Anal fissure"),
    ("K64.9", "Haemorrhoids"),
    ("M51.9", "Intervertebral disc disorder"),
    ("D25.9", "Uterine fibroid"),
    ("N43.3", "Hydrocele"),
    ("H66.9", "Otitis media"),
    ("K27.9", "Peptic ulcer"),
    ("M06.9", "Rheumatoid arthritis"),
    ("D17.9", "Benign lipoma"),
    ("C50.9", "Breast malignancy"),
    ("S72.0", "Fracture of neck of femur"),
)


def write_csv(name: str, fieldnames: list[str], rows: list[dict]) -> None:
    with (OUT / name).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def generate_core(fake: Faker, rng: random.Random) -> tuple[list[dict], list[dict]]:
    hospitals = []
    for index in range(25):
        city = CITIES[index % len(CITIES)]
        hospitals.append(
            {
                "hospital_id": f"HOS{index + 1:03d}",
                "name": f"{fake.last_name()} Care Hospital",
                "city": city,
                "is_network": index < 20,
            }
        )
    members, policies = [], []
    for index in range(500):
        member_id = f"MEM{index + 1:04d}"
        inception = REFERENCE_DATE - timedelta(days=rng.randint(0, 6 * 365))
        members.append(
            {
                "member_id": member_id,
                "synthea_id": "",
                "full_name": fake.name(),
                "dob": fake.date_of_birth(minimum_age=18, maximum_age=78).isoformat(),
                "gender": rng.choice(("Female", "Male", "Other")),
                "city": rng.choice(CITIES),
                "phone": fake.msisdn()[:10],
            }
        )
        policies.append(
            {
                "policy_id": f"POL{index + 1:04d}",
                "member_id": member_id,
                "product_id": PRODUCT["product_id"],
                "tpa_id": TPAS[index % 3][0],
                "sum_insured_inr": rng.randrange(300_000, 1_000_001, 50_000),
                "inception_date": inception.isoformat(),
                "continuous_cover_since": inception.isoformat(),
                "cumulative_bonus_inr": 0,
                "status": "ACTIVE",
            }
        )
    spec = yaml.safe_load((ROOT / "data_gen" / "golden_cases.yaml").read_text(encoding="utf-8"))
    golden_cases = spec["cases"]
    for case in golden_cases:
        policy = policies[int(case["policy_id"][-4:]) - 1]
        policy["inception_date"] = case["inception_date"].isoformat()
        policy["continuous_cover_since"] = case["continuous_cover_since"].isoformat()
    conditions = []
    pairs: set[tuple[int, int]] = set()
    while len(pairs) < 800:
        pairs.add((rng.randrange(500), rng.randrange(len(CONDITIONS))))
    for member_index, condition_index in sorted(pairs):
        code, name = CONDITIONS[condition_index]
        diagnosed = REFERENCE_DATE - timedelta(days=rng.randint(60, 10 * 365))
        conditions.append(
            {
                "member_id": f"MEM{member_index + 1:04d}",
                "icd10_code": code,
                "condition_name": name,
                "first_diagnosed_on": diagnosed.isoformat(),
                "declared_at_proposal": rng.random() < 0.35,
            }
        )
    protected_members = {
        f"MEM{int(case['policy_id'][-4:]):04d}"
        for case in golden_cases
        if case.get("declared_conditions")
    }
    forced_condition_count = sum(
        len(case.get("declared_conditions", ())) for case in golden_cases
    )
    removable = [
        index
        for index, condition in enumerate(conditions)
        if condition["member_id"] not in protected_members
    ][-forced_condition_count:]
    for index in reversed(removable):
        conditions.pop(index)
    for case in golden_cases:
        member_id = f"MEM{int(case['policy_id'][-4:]):04d}"
        for condition in case.get("declared_conditions", ()):
            conditions.append({"member_id": member_id, **condition})
    claims = []
    for index in range(300):
        policy_index = rng.randrange(500)
        admission = REFERENCE_DATE - timedelta(days=rng.randint(40, 3 * 365))
        claimed = rng.randrange(20_000, 250_001, 1_000)
        paid = int(claimed * rng.choice((0, 0.65, 0.8, 0.95)))
        claims.append(
            {
                "claim_id": f"CLM{index + 1:04d}",
                "policy_id": f"POL{policy_index + 1:04d}",
                "admission_date": admission.isoformat(),
                "discharge_date": (admission + timedelta(days=rng.randint(1, 7))).isoformat(),
                "icd10_code": rng.choice(CONDITIONS)[0],
                "claimed_inr": claimed,
                "paid_inr": paid,
                "status": "REJECTED" if paid == 0 else "PAID",
            }
        )
    write_csv("tpa.csv", ["tpa_id", "name"], [{"tpa_id": a, "name": b} for a, b in TPAS])
    write_csv("hospital.csv", list(hospitals[0]), hospitals)
    write_csv("member.csv", list(members[0]), members)
    write_csv("policy.csv", list(policies[0]), policies)
    write_csv("member_condition.csv", list(conditions[0]), conditions)
    write_csv("claim.csv", list(claims[0]), claims)
    write_csv("policy_product.csv", list(PRODUCT), [PRODUCT])
    clause_rows = [
        {
            "clause_id": cid,
            "product_id": PRODUCT["product_id"],
            "section": section,
            "heading": heading,
            "text": heading,
            "page": page,
        }
        for cid, section, heading, page in CLAUSES
    ]
    write_csv("policy_clause.csv", list(clause_rows[0]), clause_rows)
    rule_rows = [
        {
            "rule_id": rid,
            "product_id": PRODUCT["product_id"],
            "rule_type": kind,
            "params": params,
            "clause_id": cid,
            "verified_by": VERIFIED_BY,
            "verified_at": VERIFIED_AT,
        }
        for rid, kind, params, cid in RULES
    ]
    write_csv("policy_rule.csv", list(rule_rows[0]), rule_rows)
    return members, hospitals


def generate_requests(members: list[dict], hospitals: list[dict]) -> None:
    spec = yaml.safe_load((ROOT / "data_gen" / "golden_cases.yaml").read_text(encoding="utf-8"))
    requests, golden = [], []
    pdf_dir = OUT / "preauth"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    all_cases = list(spec["cases"])
    for index in range(20):
        total = 80_000 + index * 2_500
        all_cases.append(
            {
                "request_id": f"UNL{index + 1:03d}",
                "tag": "unlabelled",
                "policy_id": f"POL{101 + index:04d}",
                "admission_date": "2026-10-02",
                "diagnosis": "Acute appendicitis",
                "icd10_code": "K35.8",
                "procedure": "Laparoscopic appendicectomy",
                "is_emergency": index % 3 == 0,
                "room_category": "Twin sharing",
                "room_rent_per_day_inr": 4000,
                "planned_los_days": 3,
                "cost_breakup": [
                    {"item": "Room and nursing", "claimed_inr": 12000},
                    {"item": "Procedure and professional fees", "claimed_inr": total - 22000},
                    {"item": "Medicines and diagnostics", "claimed_inr": 10000},
                ],
                "estimated_total_inr": total,
                "clinical_note": "Acute abdominal pain with imaging consistent with appendicitis.",
            }
        )
    received = datetime(2026, 9, 29, 9, 0, tzinfo=UTC)
    for index, raw in enumerate(all_cases):
        case = dict(raw)
        member = members[(int(case["policy_id"][-4:]) - 1) % len(members)]
        hospital = hospitals[index % len(hospitals)]
        case["patient_name"] = member["full_name"]
        case["hospital_name"] = hospital["name"]
        target = pdf_dir / f"{case['request_id']}.pdf"
        render_case(case, target)
        requests.append(
            {
                "request_id": case["request_id"],
                "file_path": f"preauth/{target.name}",
                "policy_id": case["policy_id"],
                "hospital_id": hospital["hospital_id"],
                "received_at": (received + timedelta(minutes=index * 3)).isoformat(),
                "status": "NEW",
            }
        )
        if case["request_id"].startswith("GOL"):
            golden.append(
                {
                    "request_id": case["request_id"],
                    "expected_outcome": case["expected_outcome"],
                    "expected_payable_inr": case.get("expected_payable_inr", ""),
                    "tolerance_inr": 0,
                    "expected_clause_ids": json.dumps(
                        case["expected_clause_ids"], separators=(",", ":")
                    ),
                    "tags": json.dumps([case["tag"]], separators=(",", ":")),
                }
            )
    write_csv("preauth_request.csv", list(requests[0]), requests)
    write_csv("golden_case.csv", list(golden[0]), golden)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fake = Faker("en_IN")
    Faker.seed(SEED)
    rng = random.Random(SEED)
    members, hospitals = generate_core(fake, rng)
    generate_requests(members, hospitals)
    print(
        "Generated 3 TPAs, 25 hospitals, 500 members/policies, "
        "800 conditions, 300 claims, and 50 PDFs."
    )


if __name__ == "__main__":
    main()
