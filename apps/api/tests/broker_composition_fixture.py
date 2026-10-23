"""Synthetic broker identity adapter; never normal authentication/startup.

The closed fixture registry translates verified local principals to internal
UUIDs. Role/active status always comes from a fresh fixed-tenant remote lookup,
not the registry or JWT. No DB credential or fallback belongs in the broker.
"""

from types import MappingProxyType

from ciq_api.auth import LOCAL_ISSUER, Principal
from ciq_api.source_alpha import SOURCE_TENANTS
from ciq_api.worker_authority import Membership, WorkerDenied
from ciq_api.worker_broker import ResolvedWorkerIdentity


class SyntheticBrokerMemberships:
    """Exactly two trusted lookup callbacks; no caller-selected destination."""

    def __init__(self, lookups):
        expected = {tenant.tenant_id for tenant in SOURCE_TENANTS}
        if (
            type(lookups) is not dict
            or set(lookups) != expected
            or any(not callable(value) for value in lookups.values())
        ):
            raise ValueError("Invalid synthetic broker membership routes")
        self._lookups = MappingProxyType(dict(lookups))
        self._identities = MappingProxyType(
            {
                (LOCAL_ISSUER, tenant.tenant_id, profile.subject): profile.user_id
                for tenant in SOURCE_TENANTS
                for profile in tenant.profiles
            }
        )

    def resolve(self, principal):
        try:
            if type(principal) is not Principal:
                return None
            user = self._identities.get((principal.issuer, principal.tenant_id, principal.subject))
            if user is None:
                return None
            member = self._lookups[principal.tenant_id](str(user))
            if member is None:
                return None
            if (
                type(member) is not Membership
                or member.tenant_id != principal.tenant_id
                or member.role not in {"processor", "auditor", "medical_officer"}
            ):
                raise WorkerDenied("Worker access denied")
            return ResolvedWorkerIdentity(user, member)
        except Exception:
            raise WorkerDenied("Worker access denied") from None
