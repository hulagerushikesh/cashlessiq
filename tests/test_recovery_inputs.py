"""Private exporter controls, using invented test rows; no Snowflake calls."""

import json
import sys
from copy import deepcopy

import pytest

from scripts import recovery_inputs as recovery


def fixture(stage="A"):
    inputs = {"metadata": []}
    for request in recovery.STAGES[stage]:
        owner = recovery.OWNERS[request]
        scope = {"request_id": request, "tpa_id": owner}
        inputs["metadata"].append(
            {
                **scope,
                "policy_id": "POL0" + request[3:],
                "product_id": recovery.PRODUCT,
                "product_name": "Synthetic",
                "policy_version": "v1",
                "continuous_cover_since": "2023-01-01",
                "admission_date": "2026-10-02",
                "estimated_total_inr": 100000,
            }
        )
        decision = {
            "request_id": request,
            "outcome": "APPROVE_WITH_DEDUCTIONS",
            "total_claimed_inr": 100000,
            "total_payable_inr": 95000,
            "lines": [
                {
                    "item": "Synthetic",
                    "claimed_inr": 100000,
                    "payable_inr": 95000,
                    "deduction_inr": 5000,
                    "reason": "Co-pay",
                    "calc": "Saved calculation",
                    "citations": [{"type": "clause", "id": "COPAY"}],
                }
            ],
            "queries": [],
            "refer_reasons": [],
            "summary": "Synthetic only",
            "sla": {"elapsed_min": 0, "state": "GREEN"},
        }
        inputs[request] = {
            "member": [
                {
                    **scope,
                    "policy_id": "POL0" + request[3:],
                    "member_id": "MEM0" + request[3:],
                    "sum_insured_inr": 450000,
                    "cumulative_bonus_inr": 0,
                    "status": "ACTIVE",
                    "claim_count": 0,
                    "total_paid_inr": 0,
                    "last_admission_date": None,
                }
            ],
            "conditions": [],
            "decision": [
                {
                    **scope,
                    "decision_id": "SYNTHETIC",
                    "outcome": decision["outcome"],
                    "payable_inr": 95000,
                    "decision_json": decision,
                    "schema_valid": False,
                    "created_at": "2026-10-21",
                }
            ]
            if stage == "A"
            else [],
            "evidence": [
                {
                    **scope,
                    "clause_id": "COPAY",
                    "product_id": recovery.PRODUCT,
                    "heading": "Co-pay",
                    "page": 1,
                    "source_url": "https://example.org/policy.pdf",
                }
            ],
        }
    return inputs


def batch_result(stage="A"):
    inputs = fixture(stage)
    result = [[]]
    for index, (name, _) in enumerate(recovery.queries(stage)):
        if name == "context":
            data = [{"ROLE": "CIQ_PRODUCT_READER", "SECONDARY_ROLES": '{"value":""}'}]
        elif name == "warehouse":
            data = [{"name": "CIQ_WH"}]
        elif name == "metadata":
            data = inputs[name]
        else:
            request, projection = name.split(":")
            data = inputs[request][projection]
        result.extend((data, [{"CAPTURED_QUERY_ID": f"query-{index}"}]))
    return result


@pytest.mark.parametrize("stage,statements,reads", [("A", 15, 5), ("B", 23, 9)])
def test_exact_scope_and_canonical_replay(stage, statements, reads):
    sql = recovery.batch(stage)
    assert sql.count(";") == statements
    assert len(recovery.queries(stage)) - 2 == reads
    assert all(
        word not in sql
        for word in (
            "CLINICAL_NOTE",
            "RAW_EXTRACT",
            "SELECT *",
            "DATA_AGENT_RUN",
            "GRANT ",
            "CREATE ",
        )
    )
    inputs, observed, provenance = recovery.validate(stage, batch_result(stage))
    assert observed == recovery.observations(stage, inputs)
    assert len(provenance) == (statements - 1) // 2
    assert all(item["query_id"] for item in provenance)
    expected = "SAVED" if stage == "A" else "MISSING"
    assert all(row["recommendation"]["state"] == expected for row in observed.values())


@pytest.mark.parametrize(
    "fault",
    [
        "owner",
        "identity",
        "extra",
        "duplicate",
        "total",
        "record",
        "clause",
        "float",
        "oversize",
        "empty",
    ],
)
def test_bad_inputs_fail_without_substitution(fault):
    inputs = fixture()
    source = inputs["GOL001"]
    if fault == "owner":
        source["member"][0]["tpa_id"] = "TPA003"
    elif fault == "identity":
        inputs["metadata"][0]["policy_id"] = "POL9999"
    elif fault == "extra":
        source["member"][0]["clinical_note"] = "Unexpected"
    elif fault == "duplicate":
        source["evidence"] *= 2
    elif fault == "total":
        source["decision"][0]["payable_inr"] = 1
    elif fault in ("record", "clause"):
        source["decision"][0]["decision_json"]["lines"][0]["citations"] = [
            {"type": fault, "id": "UNVERIFIED"}
        ]
    elif fault == "float":
        source["member"][0]["total_paid_inr"] = 0.0
    elif fault == "oversize":
        source["decision"][0]["decision_json"]["summary"] = "X" * (256 * 1024)
    else:
        source["decision"] = []
    with pytest.raises(ValueError):
        recovery.observations("A", inputs)


def test_new_stage_b_decision_needs_review():
    inputs = fixture("B")
    inputs["GOL024"]["decision"] = deepcopy(fixture()["GOL001"]["decision"])
    inputs["GOL024"]["decision"][0].update(request_id="GOL024", tpa_id="TPA003")
    with pytest.raises(ValueError, match="Unexpected new saved"):
        recovery.observations("B", inputs)


def test_duplicate_keys_and_nonfinite_rejected():
    for value in ('{"x":1,"x":2}', '{"x":NaN}'):
        with pytest.raises(ValueError):
            recovery.decode(value)


@pytest.mark.parametrize(
    "script,limit,timeout",
    [
        ("print('x' * 100000)", 100, 2),
        ("import time; time.sleep(2)", 100, 0.05),
        ("import sys; sys.stderr.write('x'*100000)", 100, 2),
        ("raise SystemExit(1)", 100, 2),
    ],
)
def test_stream_caps_timeout_and_error(script, limit, timeout):
    with pytest.raises(ValueError):
        recovery.receive([sys.executable, "-c", script], limit=limit, timeout=timeout)


def test_capture_private_offline_replay_and_tamper(tmp_path, monkeypatch):
    monkeypatch.setattr(recovery, "ROOT", tmp_path)
    (tmp_path / "output").mkdir()
    monkeypatch.setattr(recovery, "batch", lambda _: "fixed")
    monkeypatch.setattr(recovery, "queries", lambda _: [])
    expected = recovery.observations("A", fixture())
    monkeypatch.setattr(recovery, "receive", lambda _: b"[]")
    monkeypatch.setattr(recovery, "validate", lambda *_: (fixture(), expected, []))
    monkeypatch.setattr(
        recovery.subprocess,
        "check_output",
        lambda command, **_: b"" if "diff" in command else "revision",
    )
    destination = tmp_path / "output" / "private"
    recovery.capture_stage(destination, "A")
    monkeypatch.setattr(recovery, "receive", lambda *_: pytest.fail("Replay must not connect"))
    monkeypatch.setattr(recovery.subprocess, "Popen", lambda *_: pytest.fail("No process"))
    assert recovery.verify(destination)["observations"] == expected
    with pytest.raises(ValueError):
        recovery.capture_stage(destination, "A")
    assert destination.stat().st_mode & 0o777 == 0o700
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in destination.iterdir())
    (destination / "inputs.json").write_text(json.dumps({"tampered": True}))
    with pytest.raises(ValueError, match="Integrity"):
        recovery.verify(destination)


def test_stage_b_requires_prior_before_network(tmp_path, monkeypatch):
    monkeypatch.setattr(recovery, "ROOT", tmp_path)
    (tmp_path / "output").mkdir()
    monkeypatch.setattr(recovery, "receive", lambda *_: pytest.fail("Must not connect"))
    with pytest.raises(ValueError, match="Stage A"):
        recovery.capture_stage(tmp_path / "output" / "private", "B")
