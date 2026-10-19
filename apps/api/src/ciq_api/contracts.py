"""Versioned API responses; generated browser types derive from these models."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthResponse(Contract):
    status: Literal["ok", "ready", "unavailable"]


class UserView(Contract):
    id: UUID
    display_name: str


class TenantView(Contract):
    id: UUID
    name: str


class MeResponse(Contract):
    schema_version: Literal[1] = 1
    user: UserView
    tenant: TenantView
    role: Literal["processor", "medical_officer", "auditor"]
    capabilities: list[str]
    identity_mode: Literal["local", "oidc"]


class LocalSessionRequest(Contract):
    profile: Literal["processor", "medical_officer", "auditor"]


class TokenResponse(Contract):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
