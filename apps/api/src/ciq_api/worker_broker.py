"""Offline summary routing; not mounted in HTTP startup or connected to source.

The verifier and worker calls are trusted, explicitly injected dependencies.
In-process calls do not authenticate transport peers or isolate credentials.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ciq_api.auth import IdentityVerifier, Principal
from ciq_api.models import AppUser, Tenant
from ciq_api.models import Membership as StoredMembership
from ciq_api.source_cases import ALPHA_REFERENCES
from ciq_api.source_scopes import SyntheticSourceScopes
from ciq_api.validation_worker import SummaryObservation
from ciq_api.worker_authority import (
    MAX_LIFETIME,
    Disclosure,
    Membership,
    WorkerDenied,
    issue_summary_assertion,
)


@dataclass(frozen=True)
class ResolvedWorkerIdentity:
    user_id: UUID
    membership: Membership


class WorkerMembershipStore:
    """Fresh active user/tenant/membership query per check, never an ORM cache.

    Inject a factory for new sessions. A validator pins tenant_id in its lookup
    closure; assertions identify internal application UUIDs, never OIDC subjects.
    """

    def __init__(self, sessions: Callable[[], Session]):
        self._sessions = sessions

    def _resolve(self, tenant_id: UUID, *identity_filters) -> ResolvedWorkerIdentity | None:
        try:
            with self._sessions() as session:
                row = session.execute(
                    select(AppUser.id, StoredMembership.role)
                    .join(StoredMembership, StoredMembership.user_id == AppUser.id)
                    .join(Tenant, Tenant.id == StoredMembership.tenant_id)
                    .where(
                        *identity_filters,
                        StoredMembership.tenant_id == tenant_id,
                        AppUser.active.is_(True),
                        StoredMembership.active.is_(True),
                        Tenant.active.is_(True),
                    )
                ).one_or_none()
            if row is None or row.role not in {"processor", "auditor", "medical_officer"}:
                return None
            return ResolvedWorkerIdentity(row.id, Membership(tenant_id, row.role))
        except Exception:
            raise WorkerDenied("Worker access denied") from None

    def resolve(self, principal: Principal) -> ResolvedWorkerIdentity | None:
        return self._resolve(
            principal.tenant_id,
            AppUser.issuer == principal.issuer,
            AppUser.subject == principal.subject,
        )

    def lookup(self, subject: str, tenant_id: UUID) -> Membership | None:
        try:
            user_id = UUID(subject)
            if str(user_id) != subject:
                return None
        except (ValueError, TypeError, AttributeError):
            return None
        identity = self._resolve(tenant_id, AppUser.id == user_id)
        return identity.membership if identity is not None else None


@dataclass(frozen=True)
class OfflineSummaryRoute:
    audience: str
    invoke: Callable[[str], SummaryObservation] = field(repr=False)


class OfflineSummaryBroker:
    """Authenticate -> fixed route -> summary -> fresh delivery authorization.

    This is a summary-only test composition, not the future read-worker path.
    No caller chooses tenant, disclosure, audience, destination or signing key.
    """

    def __init__(
        self,
        *,
        verifier: IdentityVerifier,
        memberships: WorkerMembershipStore,
        scopes: SyntheticSourceScopes,
        routes: Mapping[tuple[UUID, Disclosure], OfflineSummaryRoute],
        private_key: object,
        clock: Callable[[], int],
    ):
        copied = dict(routes)
        if any(
            scopes.get(tenant) is None
            or disclosure not in {"nonclinical", "medical"}
            or not route.audience
            or len(route.audience) > 120
            for (tenant, disclosure), route in copied.items()
        ) or len({route.audience for route in copied.values()}) != len(copied):
            raise ValueError("Invalid offline broker configuration")
        self._verifier = verifier
        self._memberships = memberships
        self._scopes = scopes
        self._routes = MappingProxyType(copied)
        self._key = private_key
        self._clock = clock

    def summary(self, token: str, request_id: str) -> SummaryObservation:
        try:
            principal = self._verifier.verify(token)
            identity = self._memberships.resolve(principal)
            if identity is None:
                raise WorkerDenied("Worker access denied")
            scope = self._scopes.get(identity.membership.tenant_id)
            if scope is None or request_id not in scope.request_ids:
                raise WorkerDenied("Worker access denied")
            disclosure = (
                "medical" if identity.membership.role == "medical_officer" else "nonclinical"
            )
            route = self._routes.get((identity.membership.tenant_id, disclosure))
            if route is None:
                raise WorkerDenied("Worker access denied")
            now = self._clock()
            assertion = issue_summary_assertion(
                self._key,
                subject=str(identity.user_id),
                membership=identity.membership,
                audience=route.audience,
                request_id=request_id,
                scopes=self._scopes,
                now=now,
            )
            result = SummaryObservation.model_validate(route.invoke(assertion).model_dump())
            # Re-verify session lifetime as well as current authoritative membership.
            current_principal = self._verifier.verify(token)
            current = self._memberships.resolve(current_principal)
            if (
                current_principal != principal
                or current != identity
                or not now <= self._clock() < now + MAX_LIFETIME
                or result.request_id != request_id
                or result.tpa_id != scope.tpa_id
                or result.product_id != ALPHA_REFERENCES[request_id].product_id
            ):
                raise WorkerDenied("Worker access denied")
            return result
        except Exception:
            raise WorkerDenied("Worker access denied") from None
