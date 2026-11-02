"""One canonical pure rules engine, packaged without Snowflake or model calls."""

import json
from dataclasses import asdict
from hashlib import sha256

from cashlessiq_domain.rules import evaluate_case
from cashlessiq_domain.rules.models import CostItem, MemberCondition, Policy, PreAuthFacts, Rule
from pydantic import Field

from ciq_api.contracts import Contract
from ciq_api.mvp_contracts import AssessmentInput, PolicyProposal, RuleInput


class CalculationPolicy(Contract):
    """Selected rule inputs, without other members' regression example facts."""

    product_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    version: str = Field(min_length=1, max_length=80)
    rules: list[RuleInput] = Field(min_length=1, max_length=30)


def fingerprint(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def calculate(request_id, inputs, proposal):
    inputs = AssessmentInput.model_validate(inputs)
    proposal = PolicyProposal.model_validate(proposal)
    return _calculate(request_id, inputs, proposal)


def calculate_rules(request_id, inputs, policy):
    """Offline comparison using a selected, server-owned approved policy projection.

    Approval, clause completeness and unambiguous rule types must be established
    by the caller's validated policy snapshot. Existing submissions still use the
    full PolicyProposal validation in calculate().
    """
    return _calculate(
        request_id, AssessmentInput.model_validate(inputs), CalculationPolicy.model_validate(policy)
    )


def _calculate(request_id, inputs, proposal):
    policy = Policy(
        policy_id=proposal.product_id,
        member_id=inputs.member_reference,
        product_id=proposal.product_id,
        tpa_id="synthetic",
        sum_insured_inr=inputs.sum_insured_inr,
        inception_date=inputs.inception_date,
        continuous_cover_since=inputs.continuous_cover_since,
    )
    fields = inputs.model_dump(
        exclude={
            "member_reference",
            "sum_insured_inr",
            "si_remaining_inr",
            "inception_date",
            "continuous_cover_since",
            "declared_conditions",
            "cost_breakup",
        }
    )
    facts = PreAuthFacts(
        request_id=request_id,
        **fields,
        cost_breakup=tuple(CostItem(**c.model_dump()) for c in inputs.cost_breakup),
    )
    rules = tuple(Rule(product_id=proposal.product_id, **r.model_dump()) for r in proposal.rules)
    conditions = tuple(MemberCondition(**c.model_dump()) for c in inputs.declared_conditions)
    result = evaluate_case(
        policy,
        facts,
        rules,
        si_remaining_inr=inputs.si_remaining_inr,
        declared_conditions=conditions,
    )
    output = asdict(result)
    output["outcome"] = result.outcome.value
    output["claimed_inr"] = inputs.estimated_total_inr
    output["payable_inr"] = result.payable.total_payable_inr if result.payable else None
    output["policy_version"] = proposal.version
    output["input_digest"] = fingerprint(inputs.model_dump(mode="json"))
    output["rules_digest"] = fingerprint([r.model_dump(mode="json") for r in proposal.rules])
    # Validate the arithmetic before the result can cross a persistence boundary.
    if result.payable:
        p = result.payable
        if (
            p.total_claimed_inr != inputs.estimated_total_inr
            or not 0 <= p.total_payable_inr <= p.total_claimed_inr
            or sum(line.payable_inr for line in p.lines) != p.total_payable_inr
        ):
            raise ValueError("Invalid deterministic result")
        if any(
            not line.citations or line.claimed_inr != line.payable_inr + line.deduction_inr
            for line in p.lines
        ):
            raise ValueError("Invalid evidenced calculation line")
    return output


def regression(proposal):
    policy = PolicyProposal.model_validate(proposal)
    checks = []
    for index, example in enumerate(policy.examples):
        result = calculate(f"REG-{index}", example.facts.model_dump(mode="json"), proposal)
        checks.append(
            {
                "name": example.name,
                "passed": result["outcome"] == example.expected_outcome
                and result["payable_inr"] == example.expected_payable_inr,
                "actual_outcome": result["outcome"],
                "actual_payable_inr": result["payable_inr"],
                "expected_outcome": example.expected_outcome,
                "expected_payable_inr": example.expected_payable_inr,
            }
        )
    return {
        "passed": all(c["passed"] for c in checks),
        "count": len(checks),
        "proposal_digest": fingerprint(proposal),
        "checks": checks,
    }
