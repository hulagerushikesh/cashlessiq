"""Shared source input types; no connector, query, database or API startup."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class SourceReadUnavailable(RuntimeError):
    """Safe boundary error; never expose connector details or credentials."""


class SourceCase(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    request_id: str
    policy_id: str
    tpa_id: str
    product_id: str
    product_name: str
    policy_version: str
    continuous_cover_since: date
    admission_date: date
    estimated_total_inr: int = Field(ge=0)
