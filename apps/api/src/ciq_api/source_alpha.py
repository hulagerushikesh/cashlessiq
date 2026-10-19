"""Fixed local-only identities for separate synthetic source tenants.

These are development fixtures, not customer onboarding or production access.
They do not enable Snowflake reads or modify the mixed offline demo tenant.
"""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

ReviewRole = Literal["processor", "medical_officer", "auditor"]


@dataclass(frozen=True)
class SourceProfile:
    user_id: UUID
    subject: str
    display_name: str
    role: ReviewRole


@dataclass(frozen=True)
class SourceTenant:
    tenant_id: UUID
    tpa_id: str
    name: str
    profiles: tuple[SourceProfile, ...]


def _profiles(tpa: str, base: int) -> tuple[SourceProfile, ...]:
    roles: tuple[ReviewRole, ...] = ("processor", "medical_officer", "auditor")
    return tuple(
        SourceProfile(
            user_id=UUID(f"00000000-0000-4000-8000-{base + index:012d}"),
            subject=f"source-alpha:{tpa}:{role}",
            display_name=f"{tpa} synthetic {role.replace('_', ' ')}",
            role=role,
        )
        for index, role in enumerate(roles, start=1)
    )


SOURCE_TENANTS = (
    SourceTenant(
        tenant_id=UUID("00000000-0000-4000-8000-000000000101"),
        tpa_id="TPA001",
        name="TPA001 · Source alpha · Synthetic only",
        profiles=_profiles("TPA001", 110),
    ),
    SourceTenant(
        tenant_id=UUID("00000000-0000-4000-8000-000000000103"),
        tpa_id="TPA003",
        name="TPA003 · Source alpha · Synthetic only",
        profiles=_profiles("TPA003", 130),
    ),
)
