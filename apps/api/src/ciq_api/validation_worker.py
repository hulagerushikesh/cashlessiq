"""Offline validator handler with injected coherent inputs; no transport/live wiring."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from cashlessiq_domain.source_recommendation import (
    SavedRecommendation,
    observe_source_recommendation,
)
from pydantic import BaseModel, ConfigDict

from ciq_api.snowflake_reads import SourceCase, SourceReadUnavailable
from ciq_api.source_cases import ALPHA_REFERENCES
from ciq_api.source_contracts import MissingSourceRecommendation, SavedSourceRecommendation
from ciq_api.source_scopes import SourceScope
from ciq_api.worker_authority import SummaryAuthority, WorkerDenied


@dataclass(frozen=True, repr=False)
class ValidationInputs:
    """Trusted reader must supply one coherent snapshot, not arbitrary browser inputs.

    This container cannot establish database snapshot consistency. Live readers
    remain forbidden until that separate query/identity acceptance gate passes.
    """

    case: SourceCase
    decisions: Sequence[Mapping[str, Any]]
    evidence: Sequence[Mapping[str, Any]]


class SummaryObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request_id: str
    tpa_id: str
    product_id: str
    recommendation: MissingSourceRecommendation | SavedSourceRecommendation


class OfflineValidationWorker:
    """No endpoint/connection factory; fake input injection is explicit and local-only."""

    def __init__(
        self,
        *,
        authority: SummaryAuthority,
        scope: SourceScope,
        read_inputs: Callable[[str], ValidationInputs],
    ):
        self._authority = authority
        self._scope = scope
        self._read_inputs = read_inputs

    def validate(self, token: str) -> SummaryObservation:
        claims = self._authority.consume(token)
        # Never allow inconsistent server-side composition to reach source I/O.
        if (
            claims.tenant != str(self._scope.tenant_id)
            or claims.request_id not in self._scope.request_ids
        ):
            raise WorkerDenied("Worker access denied")
        try:
            inputs = self._read_inputs(claims.request_id)
            case = SourceCase.model_validate(inputs.case.model_dump())
            reference = ALPHA_REFERENCES[claims.request_id]
            if (
                case.request_id != claims.request_id
                or case.tpa_id != self._scope.tpa_id
                or case.policy_id != reference.policy_id
                or case.product_id != reference.product_id
                or len(inputs.evidence) > 100
            ):
                raise ValueError("Invalid input scope")
            seen = set()
            for row in inputs.evidence:
                if (
                    row["request_id"] != case.request_id
                    or row["tpa_id"] != case.tpa_id
                    or row["product_id"] != case.product_id
                    or row["clause_id"] in seen
                ):
                    raise ValueError("Invalid evidence scope")
                seen.add(row["clause_id"])
            observed = observe_source_recommendation(
                inputs.decisions,
                request_id=case.request_id,
                tpa_id=case.tpa_id,
                product_id=case.product_id,
                estimated_total_inr=case.estimated_total_inr,
                evidence=inputs.evidence,
                verified_record_ids=frozenset(),
            )
            recommendation = MissingSourceRecommendation()
            if isinstance(observed, SavedRecommendation):
                decision = observed.decision
                recommendation = SavedSourceRecommendation(
                    outcome=decision.outcome,
                    claimed_inr=decision.claimed_inr,
                    payable_inr=decision.payable_inr,
                    amount_basis=decision.amount_basis,
                )
            result = SummaryObservation(
                request_id=case.request_id,
                tpa_id=case.tpa_id,
                product_id=case.product_id,
                recommendation=recommendation,
            )
        except Exception:
            raise SourceReadUnavailable("Source validation unavailable") from None
        self._authority.before_delivery(claims)
        return result
