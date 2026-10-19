"""Read-only source recommendation availability, never a decision generator.

An absent saved row is distinct from QUERY/REFER, invalid data, and a failed
source read. Call only after a successful, owner-scoped source inspection.
This observation is not the existing v1 HTTP case contract.
"""

from collections.abc import Mapping, Sequence, Set
from dataclasses import dataclass
from typing import Any, Literal

from .source_decision import (
    DecisionObservation,
    SourceDecisionError,
    observe_saved_decision,
)


@dataclass(frozen=True)
class MissingRecommendation:
    request_id: str
    tpa_id: str
    product_id: str
    supplied_estimate_inr: int
    state: Literal["MISSING"] = "MISSING"


@dataclass(frozen=True)
class SavedRecommendation:
    request_id: str
    tpa_id: str
    product_id: str
    supplied_estimate_inr: int
    decision: DecisionObservation
    state: Literal["SAVED"] = "SAVED"


RecommendationObservation = MissingRecommendation | SavedRecommendation


def observe_source_recommendation(
    rows: Sequence[Mapping[str, Any]],
    *,
    request_id: str,
    tpa_id: str,
    product_id: str,
    estimated_total_inr: int,
    evidence: Sequence[Mapping[str, Any]],
    verified_record_ids: Set[str],
) -> RecommendationObservation:
    """Observe a successful bounded read; never catch failed reads as absence.

    Context must come from independently validated request metadata, not an
    arbitrary client or a decision row. Missing rows contain no inferred outcome,
    payable, calculation, query or referral. Supplied estimates are not payables.
    A saved row must pass the existing canonical/citation validator. Multiple
    rows, malformed rows and unresolved citations remain errors with no fallback.
    Clause retrieval/coverage is a separate concern when no decision exists.
    """
    if (
        any(not isinstance(value, str) or not value.strip()
            for value in (request_id, tpa_id, product_id))
        or type(estimated_total_inr) is not int
        or estimated_total_inr < 0
        or isinstance(rows, (str, bytes, Mapping))
        or not isinstance(rows, Sequence)
        or len(rows) > 1
    ):
        raise SourceDecisionError("Saved source decision unavailable or invalid")

    context = {
        "request_id": request_id,
        "tpa_id": tpa_id,
        "product_id": product_id,
        "supplied_estimate_inr": estimated_total_inr,
    }
    if len(rows) == 0:
        return MissingRecommendation(**context)
    decision = observe_saved_decision(
        rows[0],
        request_id=request_id,
        tpa_id=tpa_id,
        product_id=product_id,
        estimated_total_inr=estimated_total_inr,
        evidence=evidence,
        verified_record_ids=verified_record_ids,
    )
    return SavedRecommendation(**context, decision=decision)
