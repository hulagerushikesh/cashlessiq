"""Product display snapshots preserve frozen domain outputs, not new calculations."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_product_snapshots_match_frozen_golden_results():
    baseline = json.loads((ROOT / "tests/fixtures/migration/v1.json").read_text())
    records = json.loads((ROOT / "apps/api/src/ciq_api/fixtures/cases.json").read_text())
    assert {item["request_id"] for item in records} == {"GOL001", "GOL024", "GOL027"}
    for item in records:
        frozen = baseline["rule_results"][item["request_id"]]
        assert item["baseline_commit"] == baseline["baseline_commit"]
        for field in ("outcome", "checks", "queries", "refer_reasons"):
            assert item[field] == frozen[field]
        assert {e["clause_id"] for e in item["evidence"]} == {
            *frozen["clause_ids"],
            *(check["clause_id"] for check in frozen["checks"]),
        }
        if frozen["payable"] is None:
            assert item["payable_inr"] is None
            assert item["lines"] == []
        else:
            assert item["payable_inr"] == frozen["payable"]["total_payable_inr"]
            assert item["claimed_inr"] == frozen["payable"]["total_claimed_inr"]
            assert item["lines"] == frozen["payable"]["lines"]
