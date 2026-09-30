"""Run the Phase 3b ten-case agent acceptance gate."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml
from snowflake.snowpark import Session

from cashlessiq.agent_client import decide

GOLDEN_PATH = Path(__file__).parents[1] / "data_gen" / "golden_cases.yaml"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--connection", default="cashlessiq")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    cases = yaml.safe_load(GOLDEN_PATH.read_text(encoding="utf-8"))["cases"][: args.limit]

    valid = 0
    correct = 0
    session = Session.builder.config("connection_name", args.connection).create()
    try:
        for case in cases:
            request_id = case["request_id"]
            expected = case["expected_outcome"]
            try:
                decision = decide(session, request_id, persist=True)
                valid += 1
                matches = decision["outcome"] == expected
                correct += int(matches)
                print(
                    f"{request_id}: expected={expected} "
                    f"actual={decision['outcome']} match={matches}"
                )
            except Exception as exc:
                print(f"{request_id}: ERROR {type(exc).__name__}: {exc}")
    finally:
        session.close()
    print(f"schema valid: {valid}/{len(cases)}")
    print(f"outcome correct: {correct}/{len(cases)}")
    return int(valid != len(cases) or correct < min(8, len(cases)))


if __name__ == "__main__":
    raise SystemExit(main())
