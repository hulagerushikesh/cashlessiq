"""Data-driven waiting-period and exclusion checks."""

from __future__ import annotations

import re
from datetime import date

from .models import MemberCondition, Policy, PreAuthFacts, Rule, RuleCheck


def completed_months(start: date, end: date) -> int:
    """Return whole calendar months elapsed, never a rounded approximation."""

    if end < start:
        return 0
    months = (end.year - start.year) * 12 + end.month - start.month
    return months - int(end.day < start.day)


def _tokens(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (value or "").casefold()).strip("_")


def _case_text(facts: PreAuthFacts) -> str:
    return "_".join(
        _tokens(value) for value in (facts.diagnosis, facts.procedure, facts.clinical_note)
    )


def _condition_matches(condition: str, facts: PreAuthFacts) -> bool:
    aliases = {
        "cataract": ("cataract", "phacoemulsification"),
        "hernia": ("hernia",),
        "gallstones": ("gallstone", "cholelithiasis"),
        "non_infective_arthritis": ("arthritis",),
        "joint_replacement": ("joint_replacement", "arthroplasty"),
        "osteoarthritis": ("osteoarthritis",),
        "osteoporosis": ("osteoporosis",),
        "refractive_error_below_7_5_dioptres": (
            "refractive_error",
            "refractive_eye_surgery",
        ),
    }
    text = _case_text(facts)
    return any(alias in text for alias in aliases.get(condition, (_tokens(condition),)))


def _is_accident(facts: PreAuthFacts) -> bool:
    text = _case_text(facts)
    return "accident" in text or "trauma" in text or "fracture" in text


def _result(
    rule: Rule,
    applies: bool,
    reason: str,
    *,
    elapsed: int | None = None,
    required: int | None = None,
) -> RuleCheck:
    return RuleCheck(
        rule_id=rule.rule_id,
        clause_id=rule.clause_id,
        rule_type=rule.rule_type,
        applies=applies,
        months_elapsed=elapsed,
        months_required=required,
        reason=reason,
    )


def check_waiting_periods(
    policy: Policy,
    facts: PreAuthFacts,
    rules: tuple[Rule, ...],
    declared_conditions: tuple[MemberCondition, ...] = (),
) -> tuple[RuleCheck, ...]:
    """Evaluate waiting-period and exclusion rules without Snowflake or an LLM."""

    if facts.admission_date is None:
        return ()
    admission = facts.admission_date
    cover_months = completed_months(policy.continuous_cover_since, admission)
    checks: list[RuleCheck] = []

    for rule in rules:
        if rule.product_id != policy.product_id:
            continue
        params = rule.params
        if rule.rule_type == "WAITING_INITIAL":
            days_required = int(params["days"])
            inside = (admission - policy.inception_date).days < days_required
            exempt = bool(params.get("accident_exempt")) and _is_accident(facts)
            applies = inside and not exempt
            if applies:
                reason = f"Admission is inside the first {days_required} days."
            elif inside and exempt:
                reason = "Initial waiting period is checked but the accident exemption applies."
            else:
                reason = "Initial waiting period does not apply."
            checks.append(_result(rule, applies, reason, elapsed=cover_months, required=1))
        elif rule.rule_type == "WAITING_SPECIFIC":
            required = int(params["months"])
            matched = [
                condition
                for condition in params.get("conditions", ())
                if _condition_matches(str(condition), facts)
            ]
            exempt = bool(params.get("accident_exempt")) and _is_accident(facts)
            applies = bool(matched) and cover_months < required and not exempt
            reason = (
                f"{matched[0]} is inside its {required}-month waiting period."
                if applies
                else "Specific waiting period does not apply."
            )
            checks.append(
                _result(rule, applies, reason, elapsed=cover_months, required=required)
            )
        elif rule.rule_type == "WAITING_PED":
            required = int(params["months"])
            declared_match = any(
                condition.declared_at_proposal
                and facts.icd10_code is not None
                and condition.icd10_code == facts.icd10_code
                for condition in declared_conditions
            )
            applies = declared_match and cover_months < required
            reason = (
                f"Declared pre-existing condition is inside the {required}-month window."
                if applies
                else "Pre-existing disease waiting period does not apply."
            )
            checks.append(
                _result(rule, applies, reason, elapsed=cover_months, required=required)
            )
        elif rule.rule_type == "EXCLUSION":
            condition = str(params["condition"])
            applies = _condition_matches(condition, facts)
            reason = (
                f"Case matches exclusion {condition}."
                if applies
                else "Configured exclusion does not match the case."
            )
            checks.append(_result(rule, applies, reason))

    return tuple(checks)
