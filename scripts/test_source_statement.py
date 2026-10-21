"""Explicit bounded operator acceptance, not a runtime gateway or source backup.

Combine the already scoped projections into ONE source statement per stage.
Only redacted outcomes, hashes and query provenance are persisted privately.
No raw source output reaches stdout or disk. No automatic retry or activation.
"""

import argparse
import json
import os
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

from scripts import recovery_inputs as recovery

ROOT = recovery.ROOT


def source_sql(stage):
    if stage not in recovery.STAGES:
        raise ValueError("Invalid stage")
    branches = []
    for section, sql in recovery.queries(stage):
        if section in {"context", "warehouse"}:
            continue
        projection = "metadata" if section == "metadata" else section.split(":")[1]
        # Explicit keys/columns, never wildcard object export. NULLs must survive.
        fields = ", ".join(
            f"'{column.upper()}', Q.{column.upper()}"
            for column in sorted(recovery.COLUMNS[projection])
        )
        branches.append(
            f"SELECT '{section}' AS SECTION, OBJECT_CONSTRUCT_KEEP_NULL({fields}) AS ITEM "
            f"FROM ({sql}) Q"
        )
    return "\nUNION ALL\n".join(branches)


def batch(stage):
    return (
        "ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS=30, "
        "STATEMENT_QUEUED_TIMEOUT_IN_SECONDS=15, "
        "QUERY_TAG='cashlessiq:p2:single-statement-acceptance';\n"
        "SELECT CURRENT_ROLE() AS ROLE, CURRENT_SECONDARY_ROLES() AS SECONDARY_ROLES;\n"
        + source_sql(stage)
        + ";\nSELECT LAST_QUERY_ID() AS CAPTURED_QUERY_ID;\n"
        "SHOW WAREHOUSES LIKE 'CIQ_WH';"
    )


def validate(stage, raw):
    if type(raw) is not list or len(raw) != 5:
        raise ValueError("Invalid batch")
    context, records, ids, warehouse = raw[1:]
    if (
        type(context) is not list
        or len(context) != 1
        or type(context[0]) is not dict
        or set(context[0]) != {"ROLE", "SECONDARY_ROLES"}
        or context[0]["ROLE"] != "CIQ_PRODUCT_READER"
        or recovery.decode(context[0]["SECONDARY_ROLES"]) != {"roles": "", "value": ""}
        or type(ids) is not list
        or len(ids) != 1
        or set(ids[0]) != {"CAPTURED_QUERY_ID"}
        or type(ids[0]["CAPTURED_QUERY_ID"]) is not str
        or not 1 <= len(ids[0]["CAPTURED_QUERY_ID"]) <= 128
        or type(warehouse) is not list
        or len(warehouse) != 1
        or warehouse[0].get("name") != "CIQ_WH"
    ):
        raise ValueError("Invalid authority/provenance")
    expected = {name for name, _ in recovery.queries(stage)} - {"context", "warehouse"}
    inputs = {
        "metadata": [],
        **{r: {name: [] for name in recovery.CAPS} for r in recovery.STAGES[stage]},
    }
    # Source subquery caps sum to 129 (A) or 254 (B), including overflow sentinels.
    maximum = 4 + len(recovery.STAGES[stage]) * sum(cap + 1 for cap, _ in recovery.CAPS.values())
    if type(records) is not list or len(records) > maximum:
        raise ValueError("Invalid response size")
    for row in records:
        if (
            type(row) is not dict
            or set(row) != {"SECTION", "ITEM"}
            or row["SECTION"] not in expected
        ):
            raise ValueError("Invalid section")
        item = recovery.decode(row["ITEM"]) if type(row["ITEM"]) is str else row["ITEM"]
        if type(item) is not dict:
            raise ValueError("Invalid item")
        if row["SECTION"] == "metadata":
            inputs["metadata"].append(item)
        else:
            request, name = row["SECTION"].split(":")
            inputs[request][name].append(item)
    observed = recovery.observations(stage, inputs)
    return {
        "stage": stage,
        "query_id": ids[0]["CAPTURED_QUERY_ID"],
        "source_statements": 1,
        "explicit_statements": 5,
        "sql_sha256": recovery.digest(source_sql(stage).encode()),
        "inputs_sha256": recovery.digest(recovery.encoded(inputs)),
        "cases": {
            request: {"status": value["recommendation"]["state"]}
            for request, value in observed.items()
        },
        "warehouse_state": warehouse[0].get("state"),
    }


def prior_success(path):
    if path is None or path.is_symlink() or path.stat().st_mode & 0o777 != 0o700:
        raise ValueError("Prior Stage A required")
    for name in ("report.json", "manifest.json"):
        file = path / name
        if file.is_symlink() or file.stat().st_mode & 0o777 != 0o600 or file.stat().st_size > 8192:
            raise ValueError("Invalid prior report")
    payload = (path / "report.json").read_bytes()
    if recovery.decode((path / "manifest.json").read_bytes()) != {
        "report.json": recovery.digest(payload)
    }:
        raise ValueError("Invalid prior integrity")
    report = recovery.decode(payload)
    if (
        report["stage"] != "A"
        or report["cases"] != {"GOL001": {"status": "SAVED"}}
        or report["sql_sha256"] != recovery.digest(source_sql("A").encode())
    ):
        raise ValueError("Stage A has not passed")
    return recovery.digest(payload)


def capture(destination, stage, prior_stage_a=None):
    if destination.exists() or destination.parent.resolve() != (ROOT / "output").resolve():
        raise ValueError("Use a new private output child")
    prior_hash = prior_success(prior_stage_a) if stage == "B" else None
    # Existing approved export must still replay before any new source test.
    prior = recovery.verify(
        ROOT
        / ("output/replay-inputs-20261021-a" if stage == "A" else "output/replay-inputs-20261021-b")
    )
    if prior["stage"] != stage:
        raise ValueError("Missing offline baseline")
    if subprocess.check_output(
        ["git", "diff", "HEAD", "--", "scripts", "src", "apps/api/src"], cwd=ROOT
    ):
        raise ValueError("Commit capture code first")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    started = time.monotonic()
    raw = recovery.receive(
        [
            "snow",
            "sql",
            "-c",
            "cashlessiq",
            "--role",
            "CIQ_PRODUCT_READER",
            "--secondary-roles",
            "NONE",
            "--warehouse",
            "CIQ_WH",
            "--format",
            "JSON",
            "--enable-templating",
            "NONE",
            "-q",
            batch(stage),
        ],
        timeout=180,
    )
    result = validate(stage, recovery.decode(raw))
    result.update(
        revision=revision,
        captured_at=datetime.now(UTC).isoformat(),
        elapsed_seconds=round(time.monotonic() - started, 3),
        prior_stage_a_sha256=prior_hash,
    )
    destination.mkdir(mode=0o700)
    os.chmod(destination, 0o700)
    payload = recovery.encoded(result)
    for name, content in (
        ("report.json", payload),
        ("manifest.json", recovery.encoded({"report.json": recovery.digest(payload)})),
    ):
        descriptor = os.open(destination / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--capture-stage", choices=("A", "B"), required=True)
    parser.add_argument("--prior-stage-a", type=Path)
    args = parser.parse_args()
    try:
        result = capture(args.destination, args.capture_stage, args.prior_stage_a)
    except Exception:
        parser.exit(1, "Source acceptance unavailable; no retry or fallback.\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
