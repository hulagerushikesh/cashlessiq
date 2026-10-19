"""Operator-only synthetic source scopes; not application tenant provisioning.

Ownership was inspected on 19 October 2026. This manifest is deliberately
limited to three synthetic requests, not a customer entitlement registry.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from uuid import UUID

from ciq_api.seed import TENANT_ID
from ciq_api.source_alpha import SOURCE_TENANTS

VERIFIED_ALPHA_OWNERSHIP = MappingProxyType({"TPA001": ("GOL001",), "TPA003": ("GOL024", "GOL027")})


@dataclass(frozen=True)
class SourceScope:
    tenant_id: UUID
    tpa_id: str
    request_ids: tuple[str, ...]


class SyntheticSourceScopes:
    """Immutable, one-to-one operator bindings with no default/live demo tenant.

    The caller supplies server-side configuration, never browser input. These
    UUIDs do not create tenants or grant membership. Unknown tenants have no
    scope; the mixed-ownership offline demo tenant must remain offline.
    """

    def __init__(self, tenant_tpas: Mapping[UUID, str]):
        bindings = dict(tenant_tpas)
        if any(not isinstance(tenant, UUID) or tenant == TENANT_ID for tenant in bindings):
            raise ValueError("Source tenant must be a UUID distinct from the offline demo tenant")
        if any(
            not isinstance(tpa, str) or tpa not in VERIFIED_ALPHA_OWNERSHIP
            for tpa in bindings.values()
        ):
            raise ValueError("Source TPA must have verified synthetic ownership")
        if len(set(bindings.values())) != len(bindings):
            raise ValueError("Each source TPA requires a separate, unique tenant binding")
        self._scopes = MappingProxyType(
            {
                tenant: SourceScope(tenant, tpa, VERIFIED_ALPHA_OWNERSHIP[tpa])
                for tenant, tpa in bindings.items()
            }
        )

    def get(self, tenant_id: UUID) -> SourceScope | None:
        return self._scopes.get(tenant_id)


def source_alpha_scopes() -> SyntheticSourceScopes:
    """Explicit fixture mapping; not proof that these tenants have been seeded.

    HTTP still does not use this registry. Future integration must independently
    resolve active application membership before selecting a source scope.
    """
    return SyntheticSourceScopes({source.tenant_id: source.tpa_id for source in SOURCE_TENANTS})
