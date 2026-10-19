"""Opt-in synthetic repository adapter. No connector creation or snapshot fallback."""

from collections.abc import Mapping
from dataclasses import asdict
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from cashlessiq_domain.source_history import observe_member_history
from cashlessiq_domain.source_recommendation import (
    SavedRecommendation,
    observe_source_recommendation,
)

from ciq_api.snowflake_reads import SourceCase, SourceReadUnavailable
from ciq_api.source_contracts import (
    MissingSourceRecommendation,
    SavedSourceRecommendation,
    SourceCaseDetail,
    SourceCaseQueue,
    SourceCaseSummary,
    SourceClauseReference,
    SourceMemberHistory,
)
from ciq_api.source_identity import ALPHA_REFERENCES as ALPHA_REFERENCES
from ciq_api.source_identity import AlphaReference as AlphaReference
from ciq_api.source_scopes import SyntheticSourceScopes


class MetadataSource(Protocol):
    def read_cases(self, tenant_id: UUID) -> list[SourceCase]: ...


class InspectionSource(Protocol):
    def inspect(self, tenant_id: UUID, request_id: str) -> dict[str, list[dict[str, Any]]]: ...


class SourceCaseRepository:
    """Three-case synthetic alpha only; callers must resolve active membership first.

    Gateway injections do not enable themselves on HTTP startup. No record-ID
    citations are accepted until an independent record registry is implemented.
    Raw clinical JSON, decision prose/line labels and clause text are not returned.
    This preliminary view is not full case-workspace parity or production RLS.
    """

    def __init__(
        self,
        metadata: MetadataSource,
        inspection: InspectionSource,
        tenant_tpas: Mapping[UUID, str],
    ):
        self._metadata = metadata
        self._inspection = inspection
        self._scopes = SyntheticSourceScopes(tenant_tpas)

    def _read_cases(self, tenant_id: UUID) -> list[SourceCase]:
        scope = self._scopes.get(tenant_id)
        if scope is None:
            return []
        records = [
            SourceCase.model_validate(row.model_dump())
            for row in self._metadata.read_cases(tenant_id)
        ]
        if len(records) > len(scope.request_ids) or len({r.request_id for r in records}) != len(
            records
        ):
            raise ValueError("Ambiguous source metadata")
        for record in records:
            if record.request_id not in scope.request_ids or record.tpa_id != scope.tpa_id:
                raise ValueError("Source owner mismatch")
            reference = ALPHA_REFERENCES[record.request_id]
            if record.policy_id != reference.policy_id or record.product_id != reference.product_id:
                raise ValueError("Source identity mismatch")
        return sorted(records, key=lambda record: record.request_id)

    @staticmethod
    def _summary(record: SourceCase) -> SourceCaseSummary:
        return SourceCaseSummary.model_validate(record.model_dump(exclude={"tpa_id"}))

    def list_cases(
        self,
        tenant_id: UUID,
        search: str,
        page: int,
        page_size: int,
    ) -> SourceCaseQueue:
        try:
            if not 1 <= page <= 10_000 or not 1 <= page_size <= 50 or len(search) > 80:
                raise ValueError("Invalid page/filter")
            records = [
                r
                for r in self._read_cases(tenant_id)
                if search.strip().casefold() in r.request_id.casefold()
            ]
            start = (page - 1) * page_size
            return SourceCaseQueue(
                tenant_id=tenant_id,
                items=[self._summary(r) for r in records[start : start + page_size]],
                total=len(records),
                page=page,
                page_size=page_size,
            )
        except Exception as exc:
            raise SourceReadUnavailable("Source cases unavailable") from exc

    def get_case(
        self,
        tenant_id: UUID,
        request_id: str,
        *,
        include_conditions: bool = False,
    ) -> SourceCaseDetail | None:
        scope = self._scopes.get(tenant_id)
        if scope is None or request_id not in scope.request_ids:
            return None
        try:
            record = next(
                (r for r in self._read_cases(tenant_id) if r.request_id == request_id), None
            )
            if record is None:
                return None
            rows = self._inspection.inspect(tenant_id, request_id)
            if len(rows["member"]) != 1 or len(rows["evidence"]) > 100:
                raise ValueError("Invalid source coverage")
            reference = ALPHA_REFERENCES[request_id]
            history = observe_member_history(
                rows["member"][0],
                rows["conditions"],
                request_id=request_id,
                tpa_id=scope.tpa_id,
                policy_id=reference.policy_id,
                member_id=reference.member_id,
            )
            evidence = []
            seen = set()
            for row in rows["evidence"]:
                if (
                    row["request_id"] != request_id
                    or row["tpa_id"] != scope.tpa_id
                    or row["product_id"] != reference.product_id
                    or row["clause_id"] in seen
                ):
                    raise ValueError("Invalid source evidence")
                seen.add(row["clause_id"])
                page = row["page"]
                if (
                    isinstance(page, Decimal)
                    and page.is_finite()
                    and page == page.to_integral_value()
                ):
                    page = int(page)
                evidence.append(
                    SourceClauseReference(
                        clause_id=row["clause_id"],
                        title=row["heading"],
                        page=page,
                        source_url=row["source_url"],
                    )
                )
            if not evidence:
                raise ValueError("Missing evidence coverage")
            observed = observe_source_recommendation(
                rows["decision"],
                request_id=request_id,
                tpa_id=scope.tpa_id,
                product_id=reference.product_id,
                estimated_total_inr=record.estimated_total_inr,
                evidence=rows["evidence"],
                verified_record_ids=frozenset(),
            )
            recommendation = (
                SavedSourceRecommendation(
                    **{
                        key: value
                        for key, value in asdict(observed.decision).items()
                        if key != "request_id"
                    }
                )
                if isinstance(observed, SavedRecommendation)
                else MissingSourceRecommendation()
            )
            member = asdict(history)
            return SourceCaseDetail(
                tenant_id=tenant_id,
                case=self._summary(record),
                recommendation=recommendation,
                member_history=SourceMemberHistory(
                    **{
                        key: member[key]
                        for key in (
                            "member_id",
                            "sum_insured_inr",
                            "cumulative_bonus_inr",
                            "status",
                            "claim_count",
                            "total_paid_inr",
                            "last_admission_date",
                        )
                    },
                    conditions_visible=include_conditions,
                    conditions=member["conditions"] if include_conditions else None,
                ),
                evidence=evidence,
            )
        except Exception as exc:
            raise SourceReadUnavailable("Source case unavailable") from exc
