"""Single-statement operator controls, entirely invented data and no network."""

from copy import deepcopy

import pytest
from test_recovery_inputs import fixture

from scripts import recovery_inputs as recovery
from scripts import test_source_statement as acceptance


def response(stage="A"):
    inputs = fixture(stage)
    records = []
    for section, _ in recovery.queries(stage):
        if section in {"context", "warehouse"}:
            continue
        if section == "metadata":
            rows = inputs["metadata"]
        else:
            request, name = section.split(":")
            rows = inputs[request][name]
        records.extend({"SECTION": section, "ITEM": row} for row in rows)
    return [
        [],
        [{"ROLE": "CIQ_PRODUCT_READER", "SECONDARY_ROLES": '{"roles":"","value":""}'}],
        records,
        [{"CAPTURED_QUERY_ID": "test-query"}],
        [{"name": "CIQ_WH", "state": "STARTED"}],
    ]


@pytest.mark.parametrize("stage", ["A", "B"])
def test_bounded_statement_and_redacted_validation(stage):
    sql = acceptance.batch(stage)
    assert sql.count(";") == 5
    assert sql.count("UNION ALL") == (4 if stage == "A" else 8)
    assert "SELECT *" not in sql and "Q.*" not in sql
    for forbidden in (
        "CLINICAL_NOTE",
        "RAW_EXTRACT",
        "ACCOUNTADMIN",
        "INSERT",
        "GET_DDL",
        "CORTEX",
    ):
        assert forbidden not in sql
    result = acceptance.validate(stage, response(stage))
    assert result["source_statements"] == 1
    assert set(result["cases"]) == set(recovery.STAGES[stage])
    assert {value["status"] for value in result["cases"].values()} == (
        {"SAVED"} if stage == "A" else {"MISSING"}
    )
    assert "Synthetic" not in recovery.encoded(result).decode()


@pytest.mark.parametrize(
    "mutation",
    [
        "role",
        "secondary",
        "section",
        "extra",
        "foreign",
        "missing",
        "duplicate",
        "amount",
        "null",
        "ids",
        "warehouse",
        "oversize",
    ],
)
def test_bad_source_or_provenance_denies(mutation):
    raw = deepcopy(response())
    if mutation == "role":
        raw[1][0]["ROLE"] = "ACCOUNTADMIN"
    elif mutation == "secondary":
        raw[1][0]["SECONDARY_ROLES"] = '{"roles":"ACCOUNTADMIN","value":"ALL"}'
    elif mutation == "section":
        raw[2][0]["SECTION"] = "GOL999:member"
    elif mutation == "extra":
        raw[2][0]["ITEM"]["CLINICAL_NOTE"] = "no"
    elif mutation == "foreign":
        raw[2][0]["ITEM"]["tpa_id"] = "TPA003"
    elif mutation == "missing":
        raw[2] = [row for row in raw[2] if row["SECTION"] != "GOL001:member"]
    elif mutation == "duplicate":
        raw[2].append(raw[2][0])
    elif mutation == "amount":
        next(row for row in raw[2] if row["SECTION"] == "GOL001:decision")["ITEM"][
            "payable_inr"
        ] = 1
    elif mutation == "null":
        raw[2][0]["ITEM"] = None
    elif mutation == "ids":
        raw[3] = []
    elif mutation == "warehouse":
        raw[4][0]["name"] = "OTHER"
    elif mutation == "oversize":
        raw[2] *= 100
    with pytest.raises((ValueError, TypeError, KeyError)):
        acceptance.validate("A", raw)


def test_json_items_preserve_null_and_reject_duplicate_keys():
    raw = response()
    for row in raw[2]:
        row["ITEM"] = recovery.encoded(row["ITEM"]).decode()
    assert acceptance.validate("A", raw)["cases"]["GOL001"]["status"] == "SAVED"
    raw[2][0]["ITEM"] = '{"request_id":"GOL001","request_id":"GOL002"}'
    with pytest.raises(ValueError):
        acceptance.validate("A", raw)


def test_invalid_stage_has_no_sql():
    with pytest.raises(ValueError):
        acceptance.source_sql("C")


def test_stage_b_requires_prior_success_before_network(monkeypatch, tmp_path):
    monkeypatch.setattr(acceptance, "ROOT", tmp_path)

    def forbidden(*args, **kwargs):
        pytest.fail("Network attempted before Stage A gate")

    monkeypatch.setattr(recovery, "receive", forbidden)
    with pytest.raises(ValueError, match="Prior Stage A"):
        acceptance.capture(tmp_path / "output" / "new", "B")


def test_prior_manifest_and_sql_gate(tmp_path):
    import os

    os.chmod(tmp_path, 0o700)
    report = acceptance.validate("A", response())
    payload = recovery.encoded(report)
    for name, data in (
        ("report.json", payload),
        ("manifest.json", recovery.encoded({"report.json": recovery.digest(payload)})),
    ):
        path = tmp_path / name
        path.write_bytes(data)
        os.chmod(path, 0o600)
    assert acceptance.prior_success(tmp_path) == recovery.digest(payload)
    (tmp_path / "report.json").write_bytes(payload + b" ")
    with pytest.raises(ValueError, match="integrity"):
        acceptance.prior_success(tmp_path)
