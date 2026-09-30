"""Deterministic, integer-rupee payable calculations."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .models import (
    Citation,
    CitationType,
    DecisionLine,
    PayableResult,
    Policy,
    PreAuthFacts,
    Rule,
)


@dataclass(slots=True)
class _LineState:
    item: str
    claimed: int
    payable: int
    reasons: list[str] = field(default_factory=list)
    calculations: list[str] = field(default_factory=list)
    clause_ids: list[str] = field(default_factory=list)


def _normal(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.casefold()).split())


def _rule(rules: tuple[Rule, ...], rule_type: str) -> Rule | None:
    return next((rule for rule in rules if rule.rule_type == rule_type), None)


def _cite(state: _LineState, rule: Rule, reason: str, calc: str) -> None:
    if rule.clause_id not in state.clause_ids:
        state.clause_ids.append(rule.clause_id)
    state.reasons.append(reason)
    state.calculations.append(calc)


def _percentage(amount: int, percent: int) -> int:
    """Apply a percentage with deterministic half-up integer rounding."""

    return (amount * percent + 50) // 100


def _ratio(amount: int, numerator: int, denominator: int) -> int:
    return (amount * numerator + denominator // 2) // denominator


def _apply_daily_cap(
    states: list[_LineState],
    policy: Policy,
    facts: PreAuthFacts,
    rule: Rule | None,
    *,
    item_token: str,
    actual_per_day: int | None,
    days: int | None,
) -> tuple[int, int] | None:
    if rule is None or actual_per_day is None or days is None or days <= 0:
        return None
    params = rule.params
    percent_cap = _percentage(policy.sum_insured_inr, int(params["pct_of_si"]))
    eligible_per_day = min(percent_cap, int(params["max_inr_per_day"]))
    total_cap = eligible_per_day * days
    for state in states:
        if item_token not in _normal(state.item):
            continue
        previous = state.payable
        state.payable = min(state.payable, total_cap)
        _cite(
            state,
            rule,
            f"{item_token.title()} charge checked against the daily policy cap.",
            f"min({previous}, {eligible_per_day} x {days}) = {state.payable}",
        )
    return eligible_per_day, actual_per_day


def _apply_proportion(
    states: list[_LineState],
    room_ratio: tuple[int, int] | None,
    rule: Rule | None,
) -> None:
    if rule is None or room_ratio is None:
        return
    eligible, actual = room_ratio
    if actual <= eligible or actual <= 0:
        return
    applies_to = tuple(_normal(str(item)) for item in rule.params.get("applies_to", ()))
    exempt = tuple(_normal(str(item)) for item in rule.params.get("exempt_items", ()))
    for state in states:
        item = _normal(state.item)
        if not any(token in item for token in applies_to) or any(token in item for token in exempt):
            continue
        previous = state.payable
        state.payable = _ratio(state.payable, eligible, actual)
        _cite(
            state,
            rule,
            "Room eligibility ratio applies to this configured expense category.",
            f"{eligible}/{actual} x {previous} = {state.payable}",
        )


def _apply_sublimit(
    states: list[_LineState], policy: Policy, facts: PreAuthFacts, rule: Rule | None
) -> None:
    if rule is None:
        return
    procedure = _normal(str(rule.params["procedure"]))
    case_text = _normal(" ".join((facts.diagnosis or "", facts.procedure or "")))
    if procedure not in case_text:
        return
    cap = min(
        _percentage(policy.sum_insured_inr, int(rule.params["pct_of_si"])),
        int(rule.params["max_inr"]),
    )
    candidates = [state for state in states if procedure in _normal(state.item)]
    if not candidates and len(states) == 1:
        candidates = states
    remaining = cap
    for state in candidates:
        previous = state.payable
        state.payable = min(state.payable, remaining)
        remaining -= state.payable
        _cite(
            state,
            rule,
            f"{procedure.title()} is subject to a procedure sub-limit.",
            f"min({previous}, {cap}) = {state.payable}",
        )


def _apply_si_limit(states: list[_LineState], si_remaining_inr: int) -> None:
    remaining = max(si_remaining_inr, 0)
    for state in states:
        state.payable = min(state.payable, remaining)
        remaining -= state.payable


def _apply_copay(states: list[_LineState], rule: Rule | None) -> None:
    if rule is None:
        return
    percent = int(rule.params["pct"])
    for state in states:
        previous = state.payable
        state.payable = _percentage(state.payable, 100 - percent)
        _cite(
            state,
            rule,
            f"Mandatory {percent}% co-payment applied.",
            f"{previous} x {100 - percent}% = {state.payable}",
        )


def compute_payable(
    policy: Policy,
    facts: PreAuthFacts,
    rules: tuple[Rule, ...],
    si_remaining_inr: int,
) -> PayableResult:
    """Apply caps, proportions, sub-limits, SI availability, then co-payment.

    The SI limit is applied to the admissible amount before member co-payment.
    This matches the reviewed golden calculation: INR 45,000 available cover
    with 5% co-pay produces an insurer payable of INR 42,750.
    """

    product_rules = tuple(rule for rule in rules if rule.product_id == policy.product_id)
    states = [
        _LineState(item=item.item, claimed=item.claimed_inr, payable=item.claimed_inr)
        for item in facts.cost_breakup
    ]
    room_ratio = _apply_daily_cap(
        states,
        policy,
        facts,
        _rule(product_rules, "ROOM_RENT_CAP"),
        item_token="room",
        actual_per_day=facts.room_rent_per_day_inr,
        days=facts.planned_los_days,
    )
    _apply_daily_cap(
        states,
        policy,
        facts,
        _rule(product_rules, "ICU_CAP"),
        item_token="icu",
        actual_per_day=None
        if not facts.icu_days
        else sum(state.claimed for state in states if "icu" in _normal(state.item))
        // facts.icu_days,
        days=facts.icu_days,
    )
    _apply_proportion(states, room_ratio, _rule(product_rules, "PROPORTIONATE_DEDUCTION"))
    _apply_sublimit(states, policy, facts, _rule(product_rules, "PROCEDURE_SUBLIMIT"))
    _apply_si_limit(states, si_remaining_inr)
    _apply_copay(states, _rule(product_rules, "COPAY"))

    lines = tuple(
        DecisionLine(
            item=state.item,
            claimed_inr=state.claimed,
            payable_inr=state.payable,
            deduction_inr=state.claimed - state.payable,
            reason=" ".join(state.reasons) or "No configured deduction applies.",
            calc="; ".join(state.calculations) or f"{state.claimed} = {state.payable}",
            citations=tuple(Citation(CitationType.CLAUSE, cid) for cid in state.clause_ids),
        )
        for state in states
    )
    return PayableResult(
        lines=lines,
        total_claimed_inr=sum(state.claimed for state in states),
        total_payable_inr=sum(state.payable for state in states),
        si_remaining_inr=si_remaining_inr,
    )
