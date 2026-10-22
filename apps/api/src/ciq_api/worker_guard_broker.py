"""Explicit offline v3 issuer; API-only, excluded from worker artifacts."""

from collections.abc import Callable, Mapping
from types import MappingProxyType
from uuid import UUID, uuid4

import jwt
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

from ciq_api.auth import IdentityVerifier
from ciq_api.source_identity import ALPHA_REFERENCES
from ciq_api.source_scopes import SyntheticSourceScopes
from ciq_api.validation_worker import SummaryObservation
from ciq_api.worker_authority import ISSUER, MAX_LIFETIME, Disclosure, WorkerDenied
from ciq_api.worker_broker import OfflineSummaryRoute, WorkerMembershipStore
from ciq_api.worker_guard_authority import GuardedDetail, GuardedSummary, _verified
from ciq_api.worker_guard_health import OfflineHealthGuard
from ciq_api.worker_health import SECOND


class GuardedSummaryBroker:
    """Explicit v3 issuer; no seconds-clock adapter or caller-selected destination."""

    def __init__(
        self,
        *,
        verifier: IdentityVerifier,
        memberships: WorkerMembershipStore,
        scopes: SyntheticSourceScopes,
        routes: Mapping[tuple[UUID, Disclosure], OfflineSummaryRoute],
        private_key: RSAPrivateKey,
        generation: str,
        guard: OfflineHealthGuard,
        evidence: Callable[[], str],
    ):
        copied = dict(routes)
        if (
            not isinstance(private_key, RSAPrivateKey)
            or type(guard) is not OfflineHealthGuard
            or guard._config.authority != "broker"
            or guard._config.assertion_generation != generation
            or not callable(evidence)
            or not copied
            or len({route.audience for route in copied.values()}) != len(copied)
            or any(
                scopes.get(tenant) is None
                or disclosure not in {"medical", "nonclinical"}
                or not route.audience
                or len(route.audience) > 120
                or not route.validator_audience
                or len(route.validator_audience) > 120
                or route.audience == route.validator_audience
                for (tenant, disclosure), route in copied.items()
            )
        ):
            raise ValueError("Invalid offline v3 broker")
        self._verifier, self._memberships, self._scopes = verifier, memberships, scopes
        self._routes = MappingProxyType(copied)
        self._key, self._generation, self._guard, self._evidence = (
            private_key,
            generation,
            guard,
            evidence,
        )

    def summary(self, token: str, request_id: str) -> SummaryObservation:
        try:
            principal = self._verifier.verify(token)
            identity = self._memberships.resolve(principal)
            if identity is None:
                raise WorkerDenied("Worker access denied")
            member = identity.membership
            scope = self._scopes.get(member.tenant_id)
            if scope is None or request_id not in scope.request_ids:
                raise WorkerDenied("Worker access denied")
            disclosure = "medical" if member.role == "medical_officer" else "nonclinical"
            if member.role not in {"processor", "auditor", "medical_officer"}:
                raise WorkerDenied("Worker access denied")
            route = self._routes[(member.tenant_id, disclosure)]
            interval = self._guard.observe(self._evidence)
            iat = interval.lower_ns // SECOND
            parent_id = str(uuid4())
            common = dict(
                iss=ISSUER,
                sub=str(identity.user_id),
                tenant=str(member.tenant_id),
                disclosure=disclosure,
                request_id=request_id,
                iat=iat,
                exp=iat + MAX_LIFETIME,
                assertion_generation=self._generation,
            )
            child = GuardedSummary(
                **common,
                aud=route.validator_audience,
                operation="validate_summary",
                jti=str(uuid4()),
                reader_audience=route.audience,
                parent_jti=parent_id,
            )
            parent = GuardedDetail(
                **common,
                aud=route.audience,
                operation="read_detail",
                jti=parent_id,
                summary_token=jwt.encode(child.model_dump(), self._key, algorithm="RS256"),
            )
            if not interval.permits(_verified(parent, "broker")):
                raise WorkerDenied("Worker access denied")
            assertion = jwt.encode(parent.model_dump(), self._key, algorithm="RS256")
            # Reobserve AFTER both signatures; never refresh the signed expiry.
            self._before_delivery(token, principal, identity, parent)
            result = SummaryObservation.model_validate(route.invoke(assertion).model_dump())
            self._before_delivery(token, principal, identity, parent)
            if (
                result.request_id != request_id
                or result.tpa_id != scope.tpa_id
                or result.product_id != ALPHA_REFERENCES[request_id].product_id
            ):
                raise WorkerDenied("Worker access denied")
            return result
        except Exception:
            raise WorkerDenied("Worker access denied") from None

    def _before_delivery(self, token, principal, identity, parent):
        current = self._verifier.verify(token)
        if current != principal or self._memberships.resolve(current) != identity:
            raise WorkerDenied("Worker access denied")
        interval = self._guard.observe(self._evidence)
        if not interval.permits(_verified(parent, "broker")):
            raise WorkerDenied("Worker access denied")
