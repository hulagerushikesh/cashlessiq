"""Caller-rights Snowpark handlers for Cortex Agent custom tools."""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import UTC, date, datetime
from typing import Any

from snowflake.snowpark import Session

from cashlessiq.rules.engine import REQUIRED_FIELDS
from cashlessiq.rules.models import CostItem, MemberCondition, Policy, PreAuthFacts, Rule
from cashlessiq.rules.payable import compute_payable
from cashlessiq.rules.sla import sla_status
from cashlessiq.rules.waiting_periods import check_waiting_periods


def _value(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _money(value: Any) -> int:
    digits = re.sub(r"[^0-9]", "", str(value))
    return int(digits or 0)


def _rows(session: Session, query: str, params: list[Any]) -> list[dict[str, Any]]:
    return [row.as_dict() for row in session.sql(query, params=params).collect()]


def _load(
    session: Session, request_id: str
) -> tuple[Policy, PreAuthFacts, tuple[Rule, ...], tuple[MemberCondition, ...], int, datetime]:
    cases = _rows(
        session,
        """SELECT R.REQUEST_ID, R.RECEIVED_AT, P.POLICY_ID, P.MEMBER_ID, P.PRODUCT_ID,
                  P.TPA_ID, P.SUM_INSURED_INR, P.INCEPTION_DATE,
                  P.CONTINUOUS_COVER_SINCE, P.CUMULATIVE_BONUS_INR, P.STATUS,
                  F.DIAGNOSIS, F.ICD10_CODE, F.PROCEDURE, F.IS_EMERGENCY,
                  F.ADMISSION_DATE, F.PLANNED_LOS_DAYS, F.ROOM_CATEGORY,
                  F.ROOM_RENT_PER_DAY_INR, F.ICU_DAYS, F.COST_BREAKUP,
                  F.ESTIMATED_TOTAL_INR, F.CLINICAL_NOTE, F.MISSING_FIELDS
           FROM CASHLESSIQ.DOCS.PREAUTH_REQUEST R
           JOIN CASHLESSIQ.CORE.POLICY P ON P.POLICY_ID = R.POLICY_ID
           LEFT JOIN CASHLESSIQ.DOCS.PREAUTH_FACTS F ON F.REQUEST_ID = R.REQUEST_ID
           WHERE R.REQUEST_ID = ?""",
        [request_id],
    )
    if not cases:
        raise ValueError(f"Unknown request_id: {request_id}")
    row = cases[0]
    policy = Policy(
        policy_id=row["POLICY_ID"],
        member_id=row["MEMBER_ID"],
        product_id=row["PRODUCT_ID"],
        tpa_id=row["TPA_ID"],
        sum_insured_inr=int(row["SUM_INSURED_INR"]),
        inception_date=row["INCEPTION_DATE"],
        continuous_cover_since=row["CONTINUOUS_COVER_SINCE"],
        cumulative_bonus_inr=int(row["CUMULATIVE_BONUS_INR"]),
        status=row["STATUS"],
    )
    raw_costs = _value(row["COST_BREAKUP"]) or []
    if isinstance(raw_costs, dict):
        raw_costs = [
            {"item": item, "claimed_inr": amount}
            for item, amount in zip(
                raw_costs.get("item", []), raw_costs.get("claimed_inr", []), strict=False
            )
        ]
    costs = tuple(
        CostItem(item=str(item["item"]), claimed_inr=_money(item["claimed_inr"]))
        for item in raw_costs
        if str(item.get("item", "")).casefold() != "estimated total"
    )
    facts = PreAuthFacts(
        request_id=row["REQUEST_ID"],
        diagnosis=row["DIAGNOSIS"],
        icd10_code=row["ICD10_CODE"],
        procedure=row["PROCEDURE"],
        is_emergency=row["IS_EMERGENCY"],
        admission_date=row["ADMISSION_DATE"],
        planned_los_days=None if row["PLANNED_LOS_DAYS"] is None else int(row["PLANNED_LOS_DAYS"]),
        room_category=row["ROOM_CATEGORY"],
        room_rent_per_day_inr=None
        if row["ROOM_RENT_PER_DAY_INR"] is None
        else int(row["ROOM_RENT_PER_DAY_INR"]),
        icu_days=None if row["ICU_DAYS"] is None else int(row["ICU_DAYS"]),
        cost_breakup=costs,
        estimated_total_inr=None
        if row["ESTIMATED_TOTAL_INR"] is None
        else int(row["ESTIMATED_TOTAL_INR"]),
        clinical_note=row["CLINICAL_NOTE"],
        missing_fields=tuple(_value(row["MISSING_FIELDS"]) or ()),
    )
    rule_rows = _rows(
        session,
        "SELECT RULE_ID, PRODUCT_ID, RULE_TYPE, PARAMS, CLAUSE_ID "
        "FROM CASHLESSIQ.DOCS.POLICY_RULE WHERE PRODUCT_ID = ? ORDER BY RULE_ID",
        [policy.product_id],
    )
    rules = tuple(
        Rule(r["RULE_ID"], r["PRODUCT_ID"], r["RULE_TYPE"], _value(r["PARAMS"]), r["CLAUSE_ID"])
        for r in rule_rows
    )
    condition_rows = _rows(
        session,
        "SELECT ICD10_CODE, CONDITION_NAME, FIRST_DIAGNOSED_ON, DECLARED_AT_PROPOSAL "
        "FROM CASHLESSIQ.CORE.MEMBER_CONDITION WHERE MEMBER_ID = ?",
        [policy.member_id],
    )
    conditions = tuple(
        MemberCondition(
            r["ICD10_CODE"],
            r["CONDITION_NAME"],
            r["FIRST_DIAGNOSED_ON"],
            bool(r["DECLARED_AT_PROPOSAL"]),
        )
        for r in condition_rows
    )
    paid = _rows(
        session,
        "SELECT COALESCE(SUM(PAID_INR), 0) AS PAID FROM CASHLESSIQ.CORE.CLAIM "
        "WHERE POLICY_ID = ? AND STATUS = 'PAID' AND ADMISSION_DATE BETWEEN ? AND ?",
        [policy.policy_id, policy.inception_date, facts.admission_date or date.today()],
    )[0]["PAID"]
    remaining = max(policy.sum_insured_inr + policy.cumulative_bonus_inr - int(paid), 0)
    return policy, facts, rules, conditions, remaining, row["RECEIVED_AT"]


def tool_get_case(session: Session, request_id: str) -> dict[str, Any]:
    policy, facts, _, conditions, remaining, _ = _load(session, request_id)
    missing_fields = set(facts.missing_fields)
    for field in REQUIRED_FIELDS:
        value = getattr(facts, field)
        if value is None or (field == "cost_breakup" and not value):
            missing_fields.add(field)
    return {
        "request_id": request_id,
        "policy_id": policy.policy_id,
        "product_id": policy.product_id,
        "sum_insured_inr": policy.sum_insured_inr,
        "si_remaining_inr": remaining,
        "inception_date": policy.inception_date.isoformat(),
        "continuous_cover_since": policy.continuous_cover_since.isoformat(),
        "facts": {
            "icd10_code": facts.icd10_code,
            "is_emergency": facts.is_emergency,
            "admission_date": None
            if facts.admission_date is None
            else facts.admission_date.isoformat(),
            "planned_los_days": facts.planned_los_days,
            "room_category": facts.room_category,
            "room_rent_per_day_inr": facts.room_rent_per_day_inr,
            "icu_days": facts.icu_days,
            "cost_breakup": [asdict(item) for item in facts.cost_breakup],
            "estimated_total_inr": facts.estimated_total_inr,
        },
        "declared_icd10_codes": [c.icd10_code for c in conditions if c.declared_at_proposal],
        "missing_fields": sorted(missing_fields),
    }


def tool_check_waiting_periods(session: Session, request_id: str) -> list[dict[str, Any]]:
    policy, facts, rules, conditions, _, _ = _load(session, request_id)
    return [asdict(check) for check in check_waiting_periods(policy, facts, rules, conditions)]


def tool_compute_payable(session: Session, request_id: str) -> dict[str, Any]:
    policy, facts, rules, _, remaining, _ = _load(session, request_id)
    result = compute_payable(policy, facts, rules, remaining)
    return {
        "lines": [
            {**asdict(line), "citations": [asdict(c) for c in line.citations]}
            for line in result.lines
        ],
        "total_claimed_inr": result.total_claimed_inr,
        "total_payable_inr": result.total_payable_inr,
        "si_remaining_inr": result.si_remaining_inr,
    }


def tool_sla_status(session: Session, request_id: str) -> dict[str, Any]:
    *_, received_at = _load(session, request_id)
    status = sla_status(received_at, datetime.now(UTC))
    return {
        "received_at": received_at.isoformat(),
        "elapsed_min": status.elapsed_min,
        "remaining_min": status.remaining_min,
        "state": status.state.value,
    }
