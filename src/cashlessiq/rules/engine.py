"""Deterministic orchestration for one pre-authorisation case."""

from __future__ import annotations

from .models import CaseResult, MemberCondition, Outcome, Policy, PreAuthFacts, Rule
from .payable import compute_payable
from .waiting_periods import check_waiting_periods

REQUIRED_FIELDS = (
    "diagnosis",
    "procedure",
    "admission_date",
    "room_category",
    "room_rent_per_day_inr",
    "estimated_total_inr",
    "cost_breakup",
)


def _missing(facts: PreAuthFacts) -> tuple[str, ...]:
    missing = set(facts.missing_fields)
    for field in REQUIRED_FIELDS:
        value = getattr(facts, field)
        if value is None or (field == "cost_breakup" and not value):
            missing.add(field)
    return tuple(sorted(missing))


def evaluate_case(
    policy: Policy,
    facts: PreAuthFacts,
    rules: tuple[Rule, ...],
    *,
    si_remaining_inr: int,
    declared_conditions: tuple[MemberCondition, ...] = (),
) -> CaseResult:
    """Choose QUERY, REFER, or an approval outcome without model judgment."""

    missing = _missing(facts)
    if missing:
        room_rule = next((rule for rule in rules if rule.rule_type == "ROOM_RENT_CAP"), None)
        return CaseResult(
            request_id=facts.request_id,
            outcome=Outcome.QUERY,
            payable=None,
            checks=(),
            queries=tuple(f"Please provide {field.replace('_', ' ')}." for field in missing),
            refer_reasons=(),
            clause_ids=() if room_rule is None else (room_rule.clause_id,),
        )

    checks = check_waiting_periods(policy, facts, rules, declared_conditions)
    applicable = tuple(check for check in checks if check.applies)
    if applicable:
        return CaseResult(
            request_id=facts.request_id,
            outcome=Outcome.REFER,
            payable=None,
            checks=checks,
            queries=(),
            refer_reasons=tuple(check.reason for check in applicable),
            clause_ids=tuple(dict.fromkeys(check.clause_id for check in applicable)),
        )

    payable = compute_payable(policy, facts, rules, si_remaining_inr)
    outcome = (
        Outcome.APPROVE_WITH_DEDUCTIONS
        if payable.total_payable_inr < payable.total_claimed_inr
        else Outcome.APPROVE
    )
    clause_ids = tuple(
        dict.fromkeys(
            citation.id for line in payable.lines for citation in line.citations
        )
    )
    initial_checks = tuple(
        check.clause_id
        for check in checks
        if check.rule_type == "WAITING_INITIAL" and "accident exemption" in check.reason
    )
    return CaseResult(
        request_id=facts.request_id,
        outcome=outcome,
        payable=payable,
        checks=checks,
        queries=(),
        refer_reasons=(),
        clause_ids=tuple(dict.fromkeys((*initial_checks, *clause_ids))),
    )
