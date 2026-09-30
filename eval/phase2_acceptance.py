"""Measure the Phase 2 extraction, search, and semantic-view exit criteria."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import Any

import snowflake.connector
import yaml

GOLDEN_PATH = Path(__file__).parents[1] / "data_gen" / "golden_cases.yaml"
REQUIRED_FIELDS = (
    "diagnosis",
    "procedure",
    "admission_date",
    "room_category",
    "room_rent_per_day_inr",
    "estimated_total_inr",
    "cost_breakup",
)
SEARCH_PROBES = (
    ("room rent limit", "NIA-4.1-A"),
    ("ICU daily cap", "NIA-4.1-B"),
    ("proportionate deduction when room exceeds eligibility", "NIA-4.1-NOTE-B"),
    ("cataract treatment sublimit", "NIA-4.3"),
    ("pre-existing disease waiting period", "NIA-6.1"),
    ("hernia specific waiting period", "NIA-6.2-24"),
    ("joint replacement waiting period", "NIA-6.2-36"),
    ("first thirty days waiting period accident exception", "NIA-6.3"),
    ("refractive error exclusion below 7.5 dioptres", "NIA-7.12"),
    ("mandatory five percent co-payment", "NIA-9.5"),
)
VERIFIED_QUERIES = (
    "SELECT POLICY_ID, SI_REMAINING_INR FROM CASHLESSIQ.AI.POLICY_METRICS "
    "WHERE POLICY_ID = 'POL0001'",
    "SELECT POLICY_ID, SI_CONSUMED_INR FROM CASHLESSIQ.AI.POLICY_METRICS "
    "WHERE POLICY_ID = 'POL0001'",
    "SELECT POLICY_ID, POLICY_TENURE_MONTHS FROM CASHLESSIQ.AI.POLICY_METRICS "
    "WHERE POLICY_ID = 'POL0001'",
    "SELECT MEMBER_ID, ICD10_CODE, CONDITION_NAME FROM CASHLESSIQ.CORE.MEMBER_CONDITION "
    "WHERE MEMBER_ID = 'MEM0001' AND DECLARED_AT_PROPOSAL ORDER BY ICD10_CODE",
    "SELECT C.CLAIM_ID FROM CASHLESSIQ.CORE.CLAIM C JOIN CASHLESSIQ.CORE.POLICY P "
    "ON P.POLICY_ID = C.POLICY_ID WHERE P.MEMBER_ID = 'MEM0001' "
    "AND C.ADMISSION_DATE >= DATEADD(YEAR, -3, CURRENT_DATE())",
    "SELECT POLICY_ID, CLAIMS_LAST_3Y FROM CASHLESSIQ.AI.POLICY_METRICS "
    "WHERE POLICY_ID = 'POL0001'",
    "SELECT REQUEST_ID FROM CASHLESSIQ.DOCS.PREAUTH_REQUEST WHERE POLICY_ID = 'POL0001'",
    "SELECT REQUEST_ID, DIAGNOSIS, PROCEDURE, ESTIMATED_TOTAL_INR "
    "FROM CASHLESSIQ.DOCS.PREAUTH_FACTS WHERE REQUEST_ID = 'GOL001'",
    "SELECT P.POLICY_ID, PP.PRODUCT_NAME, T.NAME AS TPA_NAME "
    "FROM CASHLESSIQ.CORE.POLICY P JOIN CASHLESSIQ.CORE.POLICY_PRODUCT PP "
    "ON PP.PRODUCT_ID = P.PRODUCT_ID JOIN CASHLESSIQ.CORE.TPA T ON T.TPA_ID = P.TPA_ID "
    "WHERE P.POLICY_ID = 'POL0001'",
    "SELECT POLICY_ID, PRODUCT_ID, SUM_INSURED_INR, STATUS FROM CASHLESSIQ.CORE.POLICY "
    "WHERE MEMBER_ID = 'MEM0001' AND STATUS = 'ACTIVE'",
)


def _normalize(value: Any) -> Any:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        return " ".join(value.split()).casefold()
    return value


def _cost_pairs(value: Any) -> list[tuple[str, int]] | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = json.loads(value)
    def amount(raw: Any) -> int:
        return int(re.sub(r"[^0-9]", "", str(raw)))

    if isinstance(value, list):
        rows = [(_normalize(row["item"]), amount(row["claimed_inr"])) for row in value]
        return [row for row in rows if row[0] != "estimated total"]
    items = value.get("item", [])
    amounts = value.get("claimed_inr", [])
    rows = [
        (_normalize(item), amount(raw_amount))
        for item, raw_amount in zip(items, amounts, strict=True)
    ]
    return [row for row in rows if row[0] != "estimated total"]


def extraction_score(cursor: Any, cases: Iterable[dict[str, Any]]) -> tuple[int, int]:
    cursor.execute(
        "SELECT REQUEST_ID, DIAGNOSIS, PROCEDURE, ADMISSION_DATE, ROOM_CATEGORY, "
        "ROOM_RENT_PER_DAY_INR, ESTIMATED_TOTAL_INR, COST_BREAKUP "
        "FROM CASHLESSIQ.DOCS.PREAUTH_FACTS WHERE REQUEST_ID LIKE 'GOL%'"
    )
    actual = {row[0]: row[1:] for row in cursor.fetchall()}
    matches = 0
    total = 0
    failures: Counter[str] = Counter()
    for case in cases:
        row = actual[case["request_id"]]
        values = dict(zip(REQUIRED_FIELDS, row, strict=True))
        for field in REQUIRED_FIELDS:
            expected = case.get(field)
            observed = values[field]
            if field == "cost_breakup":
                equal = _cost_pairs(observed) == _cost_pairs(expected)
            else:
                equal = _normalize(observed) == _normalize(expected)
            matches += int(equal)
            total += 1
            if not equal:
                failures[field] += 1
                print(
                    f"extract: {case['request_id']} {field}: "
                    f"expected={expected!r} observed={observed!r}"
                )
    print(f"extraction mismatches by field: {dict(failures)}")
    return matches, total


def search_score(cursor: Any) -> tuple[int, int]:
    passed = 0
    for question, expected_clause in SEARCH_PROBES:
        params = json.dumps(
            {
                "query": question,
                "columns": ["CLAUSE_ID", "TEXT"],
                "filter": {"@eq": {"PRODUCT_ID": "AS_NIA_V02_2425"}},
                "limit": 3,
            }
        ).replace("'", "''")
        cursor.execute(
            "SELECT SNOWFLAKE.CORTEX.SEARCH_PREVIEW("
            f"'CASHLESSIQ.AI.CLAUSE_SEARCH', '{params}')"
        )
        payload = cursor.fetchone()[0]
        if isinstance(payload, str):
            payload = json.loads(payload)
        clause_ids = [result["CLAUSE_ID"] for result in payload["results"]]
        passed += int(expected_clause in clause_ids)
        print(f"search: {expected_clause}: {clause_ids}")
    return passed, len(SEARCH_PROBES)


def verified_query_score(cursor: Any) -> tuple[int, int]:
    passed = 0
    for query in VERIFIED_QUERIES:
        cursor.execute(query)
        cursor.fetchall()
        passed += 1
    return passed, len(VERIFIED_QUERIES)


def print_spend(cursor: Any) -> None:
    cursor.execute(
        "SELECT SERVICE_TYPE, ROUND(SUM(CREDITS_USED), 3) AS CREDITS_USED "
        "FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY "
        "WHERE USAGE_DATE >= DATEADD(DAY, -30, CURRENT_DATE()) "
        "GROUP BY SERVICE_TYPE ORDER BY CREDITS_USED DESC"
    )
    usage = cursor.fetchall()
    total = sum(float(row[1]) for row in usage)
    print(f"metered credits (30d, account-usage latency applies): {total:.3f}")
    for service_type, credits in usage:
        print(f"  {service_type}: {float(credits):.3f}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--connection", default="cashlessiq")
    args = parser.parse_args()
    cases = yaml.safe_load(GOLDEN_PATH.read_text(encoding="utf-8"))["cases"]

    with (
        snowflake.connector.connect(connection_name=args.connection) as connection,
        connection.cursor() as cursor,
    ):
        extraction = extraction_score(cursor, cases)
        search = search_score(cursor)
        verified = verified_query_score(cursor)
        print_spend(cursor)

    accuracy = extraction[0] / extraction[1]
    print(f"extraction: {extraction[0]}/{extraction[1]} = {accuracy:.1%}")
    print(f"search top-3: {search[0]}/{search[1]}")
    print(f"verified queries: {verified[0]}/{verified[1]}")
    return int(accuracy < 0.90 or search[0] != search[1] or verified[0] != verified[1])


if __name__ == "__main__":
    raise SystemExit(main())
