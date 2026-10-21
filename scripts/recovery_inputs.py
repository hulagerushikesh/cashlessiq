"""Explicit, private synthetic replay capture; offline verification by default.

Operator tool only. Never import a connector, start an app, or substitute fixtures.
"""

import argparse
import ast
import hashlib
import json
import os
import selectors
import subprocess
import time
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path

from cashlessiq.source_history import observe_member_history
from cashlessiq.source_recommendation import observe_source_recommendation

ROOT = Path(__file__).resolve().parents[1]
LIMIT = 2 * 1024 * 1024
PRODUCT = "AS_NIA_V02_2425"
OWNERS = {"GOL001": "TPA001", "GOL024": "TPA003", "GOL027": "TPA003"}
STAGES = {"A": ("GOL001",), "B": ("GOL024", "GOL027")}
COLUMNS = {
    "metadata": set(
        [
            "request_id",
            "policy_id",
            "tpa_id",
            "product_id",
            "product_name",
            "policy_version",
            "continuous_cover_since",
            "admission_date",
            "estimated_total_inr",
        ]
    ),
    "member": set(
        [
            "request_id",
            "tpa_id",
            "policy_id",
            "member_id",
            "sum_insured_inr",
            "cumulative_bonus_inr",
            "status",
            "claim_count",
            "total_paid_inr",
            "last_admission_date",
        ]
    ),
    "conditions": set(
        [
            "request_id",
            "tpa_id",
            "icd10_code",
            "condition_name",
            "first_diagnosed_on",
            "declared_at_proposal",
        ]
    ),
    "decision": set(
        [
            "request_id",
            "tpa_id",
            "decision_id",
            "outcome",
            "payable_inr",
            "decision_json",
            "schema_valid",
            "created_at",
        ]
    ),
    "evidence": set(
        ["request_id", "tpa_id", "clause_id", "product_id", "heading", "page", "source_url"]
    ),
}
CAPS = {
    "member": (1, "policy_id"),
    "conditions": (20, "icd10_code"),
    "decision": (1, "decision_id"),
    "evidence": (100, "clause_id"),
}


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def decode(raw):
    return json.loads(
        raw,
        object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite")),
    )


def encoded(value):
    return json.dumps(value, default=str, sort_keys=True, allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def projection(path, name):
    """Read literal SQL, without importing API startup or connector dependencies."""
    tree = ast.parse((ROOT / path).read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise ValueError("Missing reviewed projection")


def bind(sql, values):
    # Values come exclusively from immutable constants above, never user input.
    for value in values:
        sql = sql.replace("%s", "NULL" if value is None else "'" + value + "'", 1)
    if "%s" in sql:
        raise ValueError("Incomplete fixed binding")
    return sql.strip()


def queries(stage):
    requests = STAGES[stage]
    slots = (*requests, *(None,) * (3 - len(requests)))
    result = [
        ("context", "SELECT CURRENT_ROLE() AS ROLE, CURRENT_SECONDARY_ROLES() AS SECONDARY_ROLES")
    ]
    result.append(
        (
            "metadata",
            bind(
                projection("apps/api/src/ciq_api/snowflake_reads.py", "READ_SQL"),
                (OWNERS[requests[0]], *slots),
            ),
        )
    )
    for request in requests:
        for name in CAPS:
            sql = projection("apps/api/src/ciq_api/source_inspection.py", name.upper() + "_SQL")
            result.append((request + ":" + name, bind(sql, (request, OWNERS[request]))))
    result.append(("warehouse", "SHOW WAREHOUSES LIKE 'CIQ_WH'"))
    return result


def batch(stage):
    parts = [
        "ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS=30, "
        "STATEMENT_QUEUED_TIMEOUT_IN_SECONDS=15, "
        "QUERY_TAG='cashlessiq:p2:private-replay-inputs'"
    ]
    for _, sql in queries(stage):
        parts.extend((sql, "SELECT LAST_QUERY_ID() AS CAPTURED_QUERY_ID"))
    return ";\n".join(parts) + ";"


def receive(command, timeout=300, limit=LIMIT):
    """Bound both pipes while receiving; kill/reap on timeout, error or overflow."""
    start = time.monotonic()
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output = bytearray()
    total = 0
    try:
        with selectors.DefaultSelector() as selector:
            for pipe in (process.stdout, process.stderr):
                selector.register(pipe, selectors.EVENT_READ)
            while selector.get_map():
                if time.monotonic() - start >= timeout:
                    raise ValueError("Capture deadline exceeded")
                for key, _ in selector.select(timeout=min(0.1, timeout)):
                    chunk = os.read(key.fileobj.fileno(), 16384)
                    total += len(chunk)
                    if total > limit:
                        raise ValueError("Capture size exceeded")
                    if not chunk:
                        selector.unregister(key.fileobj)
                    elif key.fileobj is process.stdout:
                        output.extend(chunk)
            remaining = timeout - (time.monotonic() - start)
            if remaining <= 0 or process.wait(timeout=remaining) != 0:
                raise ValueError("Capture unavailable")
        return bytes(output)
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        process.stdout.close()
        process.stderr.close()


def rows(value, name):
    if not isinstance(value, list):
        raise ValueError("Invalid rows")
    result = []
    for row in value:
        if not isinstance(row, dict):
            raise ValueError("Invalid row")
        normalized = {key.lower(): item for key, item in row.items()}
        if len(normalized) != len(row) or set(normalized) != COLUMNS[name]:
            raise ValueError("Unexpected projection")
        result.append(normalized)
    return result


def observations(stage, inputs):
    """Pure canonical replay. This function has no network/connector dependency."""
    if set(inputs) != {"metadata", *STAGES[stage]}:
        raise ValueError("Unexpected input set")
    metadata = rows(inputs["metadata"], "metadata")
    if len(metadata) != len(STAGES[stage]) or {r["request_id"] for r in metadata} != set(
        STAGES[stage]
    ):
        raise ValueError("Invalid metadata coverage")
    result = {}
    for meta in metadata:
        request = meta["request_id"]
        owner = OWNERS[request]
        suffix = request[3:]
        policy, member = "POL0" + suffix, "MEM0" + suffix
        if (meta["tpa_id"], meta["policy_id"], meta["product_id"]) != (owner, policy, PRODUCT):
            raise ValueError("Invalid metadata identity")
        for field in ("continuous_cover_since", "admission_date"):
            if not isinstance(meta[field], str) or len(meta[field]) != 10:
                raise ValueError("Invalid date")
            date.fromisoformat(meta[field])
        if any(
            not isinstance(meta[f], str) or not meta[f].strip()
            for f in ("product_name", "policy_version")
        ):
            raise ValueError("Invalid product context")
        if type(meta["estimated_total_inr"]) is not int or meta["estimated_total_inr"] < 0:
            raise ValueError("Invalid estimate")
        source = inputs[request]
        if set(source) != set(CAPS):
            raise ValueError("Incomplete inspection")
        checked = {}
        for name, (maximum, key) in CAPS.items():
            checked[name] = rows(source[name], name)
            values = checked[name]
            if len(values) > maximum or len({r[key] for r in values}) != len(values):
                raise ValueError("Ambiguous or excessive rows")
            if any(r["request_id"] != request or r["tpa_id"] != owner for r in values):
                raise ValueError("Foreign source row")
        if len(checked["member"]) != 1 or not checked["evidence"]:
            raise ValueError("Incomplete coverage")
        if stage == "B" and checked["decision"]:
            raise ValueError("Unexpected new saved decision; review required")
        if stage == "A" and not checked["decision"]:
            raise ValueError("Expected saved decision absent")
        for row in checked["decision"]:
            if len(encoded(row["decision_json"])) > 256 * 1024:
                raise ValueError("Decision payload cap exceeded")
        for row in checked["evidence"]:
            if (
                row["product_id"] != PRODUCT
                or type(row["page"]) is not int
                or row["page"] < 1
                or not isinstance(row["heading"], str)
                or not isinstance(row["source_url"], str)
                or not row["source_url"].startswith("https://")
            ):
                raise ValueError("Invalid clause reference")
        history = observe_member_history(
            checked["member"][0],
            checked["conditions"],
            request_id=request,
            tpa_id=owner,
            policy_id=policy,
            member_id=member,
        )
        recommendation = observe_source_recommendation(
            checked["decision"],
            request_id=request,
            tpa_id=owner,
            product_id=PRODUCT,
            estimated_total_inr=meta["estimated_total_inr"],
            evidence=checked["evidence"],
            verified_record_ids=frozenset(),
        )
        result[request] = {"history": asdict(history), "recommendation": asdict(recommendation)}
    return decode(encoded(result))


def validate(stage, raw):
    expected = queries(stage)
    if not isinstance(raw, list) or len(raw) != 1 + 2 * len(expected):
        raise ValueError("Unexpected batch shape")
    inputs, provenance = {}, []
    for index, (name, sql) in enumerate(expected):
        data, ids = raw[1 + 2 * index : 3 + 2 * index]
        if (
            not isinstance(ids, list)
            or len(ids) != 1
            or set(ids[0]) != {"CAPTURED_QUERY_ID"}
            or not isinstance(ids[0]["CAPTURED_QUERY_ID"], str)
            or not 1 <= len(ids[0]["CAPTURED_QUERY_ID"]) <= 128
        ):
            raise ValueError("Invalid query provenance")
        provenance.append(
            {
                "name": name,
                "sql": sql,
                "sha256": digest(sql.encode()),
                "query_id": ids[0]["CAPTURED_QUERY_ID"],
            }
        )
        if name == "context":
            if (
                not isinstance(data, list)
                or len(data) != 1
                or set(data[0]) != {"ROLE", "SECONDARY_ROLES"}
                or data[0]["ROLE"] != "CIQ_PRODUCT_READER"
                or decode(data[0]["SECONDARY_ROLES"]).get("value") != ""
            ):
                raise ValueError("Unexpected authority")
        elif name == "warehouse":
            if not isinstance(data, list) or len(data) != 1 or data[0].get("name") != "CIQ_WH":
                raise ValueError("Unexpected warehouse")
        elif name == "metadata":
            inputs[name] = data
        else:
            request, projection_name = name.split(":")
            inputs.setdefault(request, {})[projection_name] = data
    return inputs, observations(stage, inputs), provenance


def capture_stage(destination, stage, prior=None):
    if destination.exists() or destination.parent.resolve() != (ROOT / "output").resolve():
        raise ValueError("Use a new private output child")
    if stage == "B" and (prior is None or verify(prior)["stage"] != "A"):
        raise ValueError("Stage A must pass first")
    if subprocess.check_output(
        ["git", "diff", "HEAD", "--", "scripts", "src", "apps/api/src"], cwd=ROOT
    ):
        raise ValueError("Commit capture code first")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    start = time.monotonic()
    raw = receive(
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
        ]
    )
    inputs, observed, provenance = validate(stage, decode(raw))
    evidence = {
        "version": 1,
        "stage": stage,
        "revision": revision,
        "captured_at": datetime.now(UTC).isoformat(),
        "elapsed_seconds": round(time.monotonic() - start, 3),
        "explicit_statements": 15 if stage == "A" else 23,
        "source_selects": 5 if stage == "A" else 9,
        "prior_stage_a": digest((prior / "inputs.json").read_bytes()) if prior else None,
        "inputs": inputs,
        "observations": observed,
        "queries": provenance,
        "batch_sha256": digest(batch(stage).encode()),
        "limits": "Synthetic, restricted, separate reads; not coherent/full backup",
    }
    payload = encoded(evidence)
    if len(payload) > LIMIT:
        raise ValueError("Private artifact cap exceeded")
    destination.mkdir(mode=0o700)
    os.chmod(destination, 0o700)
    for name, content in (
        ("inputs.json", payload),
        ("manifest.json", encoded({"inputs.json": digest(payload)})),
    ):
        descriptor = os.open(destination / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
    verify(destination)
    return evidence


def verify(destination):
    """Offline-only replay; a connector is neither accepted nor imported."""
    if destination.is_symlink() or destination.stat().st_mode & 0o777 != 0o700:
        raise ValueError("Invalid private directory")
    for name in ("inputs.json", "manifest.json"):
        path = destination / name
        if path.is_symlink() or path.stat().st_mode & 0o777 != 0o600 or path.stat().st_size > LIMIT:
            raise ValueError("Invalid private file")
    payload = (destination / "inputs.json").read_bytes()
    if decode((destination / "manifest.json").read_bytes()) != {"inputs.json": digest(payload)}:
        raise ValueError("Integrity mismatch")
    evidence = decode(payload)
    stage = evidence["stage"]
    if evidence["batch_sha256"] != digest(batch(stage).encode()):
        raise ValueError("Projection changed; use archived revision")
    if observations(stage, evidence["inputs"]) != evidence["observations"]:
        raise ValueError("Canonical replay mismatch")
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--capture-stage", choices=("A", "B"))
    parser.add_argument("--prior-stage-a", type=Path)
    args = parser.parse_args()
    try:
        result = (
            capture_stage(args.destination, args.capture_stage, args.prior_stage_a)
            if args.capture_stage
            else verify(args.destination)
        )
    except Exception:
        parser.exit(
            1,
            "Private replay input check failed; no raw output saved or printed. "
            "Stop and review before retry.\n",
        )
    print(f"Stage {result['stage']}: private canonical replay verified; no payload printed.")


if __name__ == "__main__":
    main()
