"""Private, metadata-only operator checkpoint. Never a full source backup.

Default operation is offline. --capture explicitly permits a single bounded
Snow CLI batch using the existing human profile, never API/service startup.
"""

import argparse
import hashlib
import io
import json
import os
import subprocess
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATHS = (
    "src",
    "data_gen",
    "sql",
    "tests",
    "packages",
    "apps/api/src",
    "apps/api/pyproject.toml",
    "apps/api/uv.lock",
    "apps/worker",
    "apps/membership",
    "docs/architecture",
    "docs/product",
    "docs/build-plan.md",
    "docs/strategy.md",
    "scripts",
    "pyproject.toml",
    "uv.lock",
    "Makefile",
    "README.md",
    "LICENSE",
)
SCOPE = """(P.TPA_ID = 'TPA001' AND R.REQUEST_ID = 'GOL001')
 OR (P.TPA_ID = 'TPA003' AND R.REQUEST_ID IN ('GOL024', 'GOL027'))"""
JOINS = """FROM CASHLESSIQ.DOCS.PREAUTH_REQUEST R
JOIN CASHLESSIQ.CORE.POLICY P ON P.POLICY_ID = R.POLICY_ID"""
QUERIES = (
    "SELECT CURRENT_ROLE() AS ROLE, CURRENT_SECONDARY_ROLES() AS SECONDARY_ROLES",
    f"""SELECT R.REQUEST_ID, P.TPA_ID, P.POLICY_ID, P.PRODUCT_ID,
 PP.PRODUCT_NAME, PP.VERSION AS POLICY_VERSION, P.CONTINUOUS_COVER_SINCE,
 F.ADMISSION_DATE, F.ESTIMATED_TOTAL_INR {JOINS}
 JOIN CASHLESSIQ.CORE.POLICY_PRODUCT PP ON PP.PRODUCT_ID = P.PRODUCT_ID
 JOIN CASHLESSIQ.DOCS.PREAUTH_FACTS F ON F.REQUEST_ID = R.REQUEST_ID
 WHERE {SCOPE} ORDER BY R.REQUEST_ID LIMIT 4""",
    f"""SELECT R.REQUEST_ID, P.TPA_ID, COUNT(D.DECISION_ID) AS SAVED_ROWS {JOINS}
 LEFT JOIN CASHLESSIQ.APP.DECISION D ON D.REQUEST_ID = R.REQUEST_ID
 WHERE {SCOPE} GROUP BY R.REQUEST_ID, P.TPA_ID ORDER BY R.REQUEST_ID LIMIT 4""",
    f"""SELECT R.REQUEST_ID, P.TPA_ID, COUNT(PC.CLAUSE_ID) AS CLAUSE_REFS {JOINS}
 JOIN CASHLESSIQ.DOCS.POLICY_CLAUSE PC ON PC.PRODUCT_ID = P.PRODUCT_ID
 WHERE {SCOPE} GROUP BY R.REQUEST_ID, P.TPA_ID ORDER BY R.REQUEST_ID LIMIT 4""",
    "SHOW WAREHOUSES LIKE 'CIQ_WH'",
)
PAIRS = {("GOL001", "TPA001"), ("GOL024", "TPA003"), ("GOL027", "TPA003")}


def batch_sql():
    statements = [
        "ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS=30, "
        "STATEMENT_QUEUED_TIMEOUT_IN_SECONDS=15, "
        "QUERY_TAG='cashlessiq:p2:private-recovery-metadata'",
    ]
    for query in QUERIES:
        statements.extend((query, "SELECT LAST_QUERY_ID() AS CAPTURED_QUERY_ID"))
    return ";\n".join(statements) + ";"


def validate_capture(results):
    """Fail on unexpected shape/scope, before writing any CLI output."""
    if not isinstance(results, list) or len(results) != 11:
        raise ValueError("Unexpected batch result count")
    captures = []
    for index in range(5):
        rows, ids = results[1 + index * 2 : 3 + index * 2]
        if not isinstance(rows, list) or not 1 <= len(rows) <= (3 if index in (1, 2, 3) else 1):
            raise ValueError("Unexpected result cardinality")
        if not isinstance(ids, list) or len(ids) != 1:
            raise ValueError("Missing query ID")
        query_id = ids[0].get("CAPTURED_QUERY_ID")
        if not isinstance(query_id, str) or not query_id or len(query_id) > 128:
            raise ValueError("Invalid query ID")
        if index == 0:
            secondary = json.loads(rows[0]["SECONDARY_ROLES"])
            if rows[0]["ROLE"] != "CIQ_PRODUCT_READER" or secondary.get("value") != "":
                raise ValueError("Unexpected session authority")
        elif index in (1, 2, 3):
            pairs = {(row["REQUEST_ID"], row["TPA_ID"]) for row in rows}
            if len(rows) != 3 or pairs != PAIRS:
                raise ValueError("Unexpected source ownership")
        elif rows[0].get("name") != "CIQ_WH":
            raise ValueError("Unexpected warehouse")
        captures.append({"query_id": query_id, "rows": rows})
    return captures


def run_capture():
    start = time.monotonic()
    result = subprocess.run(
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
            batch_sql(),
        ],
        capture_output=True,
        text=True,
        timeout=180,
        check=True,
    )
    return {
        "elapsed_seconds": round(time.monotonic() - start, 3),
        "statements": 11,
        "source_selects": 3,
        "results": validate_capture(json.loads(result.stdout)),
    }


def write_private(path, data):
    with path.open("xb") as handle:
        os.chmod(path, 0o600)
        handle.write(data)


def create_checkpoint(destination, capture=False):
    if subprocess.check_output(["git", "diff", "HEAD", "--", *PATHS], cwd=ROOT):
        raise ValueError("Commit tracked rebuild changes before capture")
    destination.mkdir(mode=0o700, parents=False, exist_ok=False)
    os.chmod(destination, 0o700)
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    archive = subprocess.check_output(["git", "archive", "HEAD", "--", *PATHS], cwd=ROOT)
    write_private(destination / "rebuild.tar", archive)
    evidence = run_capture() if capture else None
    payload = json.dumps(
        {
            "version": 1,
            "revision": revision,
            "capture": evidence,
            "scope": "Metadata-only synthetic operator evidence; not a database backup",
            "limits": [
                "No raw decisions/clinical text",
                "Separate statements, not a coherent snapshot",
                "No new canonical decision validation or live isolation acceptance",
                "No measured dollars; warehouse may auto-resume; check suspension afterward",
            ],
        },
        indent=2,
    ).encode()
    write_private(destination / "evidence.json", payload)
    manifest = {
        name: hashlib.sha256((destination / name).read_bytes()).hexdigest()
        for name in ("rebuild.tar", "evidence.json")
    }
    write_private(destination / "manifest.json", json.dumps(manifest, indent=2).encode())
    verify_checkpoint(destination)


def verify_checkpoint(destination):
    manifest = json.loads((destination / "manifest.json").read_text())
    if set(manifest) != {"rebuild.tar", "evidence.json"}:
        raise ValueError("Unexpected manifest")
    for name, digest in manifest.items():
        if hashlib.sha256((destination / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Integrity mismatch")
    with tarfile.open(fileobj=io.BytesIO((destination / "rebuild.tar").read_bytes())) as archive:
        for entry in archive:
            if entry.issym() or entry.islnk() or not (entry.isfile() or entry.isdir()):
                raise ValueError("Unsupported archive entry")
            path = Path(entry.name)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("Unsafe archive path")
    evidence = json.loads((destination / "evidence.json").read_text())
    if evidence["capture"] is not None:
        # Reconstruct the expected interleaved batch shape for offline validation.
        results = [[]]
        for item in evidence["capture"]["results"]:
            results.extend((item["rows"], [{"CAPTURED_QUERY_ID": item["query_id"]}]))
        validate_capture(results)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--capture", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.capture and args.verify_only:
        parser.error("Capture and offline verification are mutually exclusive")
    try:
        if args.verify_only:
            verify_checkpoint(args.destination)
        else:
            create_checkpoint(args.destination, args.capture)
    except Exception:
        parser.exit(1, "Checkpoint failed; no raw CLI output printed. Review before retry.\n")
    print("Private checkpoint integrity verified (not a full database restore).")


if __name__ == "__main__":
    main()
