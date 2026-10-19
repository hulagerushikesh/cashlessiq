"""Tenant-scoped read repository; no Snowflake, AI, or reviewer writes."""

from importlib.resources import files
from typing import Protocol
from uuid import UUID

from pydantic import TypeAdapter

from ciq_api.contracts import CaseDetail, CaseQueue, CaseSummary, Outcome
from ciq_api.seed import TENANT_ID


class CaseRepository(Protocol):
    def list_cases(
        self, tenant_id: UUID, outcome: Outcome | None, search: str, page: int, page_size: int
    ) -> CaseQueue: ...

    def get_case(self, tenant_id: UUID, request_id: str) -> CaseDetail | None: ...


class SyntheticCaseRepository:
    """Only the fixed synthetic tenant owns these immutable, packaged snapshots."""

    def __init__(self) -> None:
        resource = files("ciq_api").joinpath("fixtures/cases.json")
        self.records = TypeAdapter(list[CaseDetail]).validate_json(resource.read_text())

    def list_cases(
        self, tenant_id: UUID, outcome: Outcome | None, search: str, page: int, page_size: int
    ) -> CaseQueue:
        matches = [
            item
            for item in self.records
            if tenant_id == TENANT_ID
            and (outcome is None or item.outcome == outcome)
            and search.casefold() in f"{item.request_id} {item.member_reference}".casefold()
        ]
        start = (page - 1) * page_size
        return CaseQueue(
            items=[
                CaseSummary.model_validate(item.model_dump(include=set(CaseSummary.model_fields)))
                for item in matches[start : start + page_size]
            ],
            total=len(matches),
            page=page,
            page_size=page_size,
        )

    def get_case(self, tenant_id: UUID, request_id: str) -> CaseDetail | None:
        if tenant_id != TENANT_ID:
            return None
        return next(
            (item.model_copy(deep=True) for item in self.records if item.request_id == request_id),
            None,
        )
