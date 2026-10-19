"""Export three existing golden cases for a read-only, offline product alpha."""

import json
from pathlib import Path

import yaml

from data_gen.policies import CLAUSES, PRODUCT

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "apps/api/src/ciq_api/fixtures/cases.json"


def main() -> None:
    baseline = json.loads((ROOT / "tests/fixtures/migration/v1.json").read_text())
    cases = yaml.safe_load((ROOT / "data_gen/golden_cases.yaml").read_text())["cases"]
    records = []
    for case in cases:
        request_id = case["request_id"]
        if request_id not in {"GOL001", "GOL024", "GOL027"}:
            continue
        result = baseline["rule_results"][request_id]
        payable = result["payable"]
        records.append(
            {
                "request_id": request_id,
                "member_reference": f"SYN-{request_id}",
                "outcome": result["outcome"],
                "admission_date": str(case["admission_date"]),
                # Copy the supplied estimate when no calculation exists; never infer payable.
                "claimed_inr": (
                    payable["total_claimed_inr"] if payable else case["estimated_total_inr"]
                ),
                "payable_inr": payable["total_payable_inr"] if payable else None,
                "baseline_commit": baseline["baseline_commit"],
                "policy_id": case["policy_id"],
                "product_name": PRODUCT["product_name"],
                "policy_version": PRODUCT["version"],
                "continuous_cover_since": str(case["continuous_cover_since"]),
                "diagnosis": case["diagnosis"],
                "procedure": case["procedure"],
                "clinical_note": case["clinical_note"],
                "clinical_visible": True,
                "lines": payable["lines"] if payable else [],
                "checks": result["checks"],
                "queries": result["queries"],
                "refer_reasons": result["refer_reasons"],
                "evidence": [
                    {
                        "clause_id": clause_id,
                        "title": title,
                        "page": page,
                        "source_url": PRODUCT["source_url"],
                    }
                    for clause_id, _section, title, page in CLAUSES
                    if clause_id
                    in {
                        *result["clause_ids"],
                        *(check["clause_id"] for check in result["checks"]),
                    }
                ],
            }
        )
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    DESTINATION.write_text(json.dumps(records, indent=2) + "\n")
    print("Exported three synthetic snapshots; no rule execution or external calls.")


if __name__ == "__main__":
    main()
