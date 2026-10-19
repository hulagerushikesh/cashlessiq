"""Synthetic identifiers only; no database, authentication or source I/O imports."""

from dataclasses import dataclass
from types import MappingProxyType
from uuid import UUID

TENANT_ID = UUID("00000000-0000-4000-8000-000000000001")


@dataclass(frozen=True)
class AlphaReference:
    policy_id: str
    member_id: str
    product_id: str = "AS_NIA_V02_2425"


ALPHA_REFERENCES = MappingProxyType(
    {
        "GOL001": AlphaReference("POL0001", "MEM0001"),
        "GOL024": AlphaReference("POL0024", "MEM0024"),
        "GOL027": AlphaReference("POL0027", "MEM0027"),
    }
)
