"""Loopback-only authoritative membership candidate; never normal API startup.

Only the trusted membership service receives an injected database lookup.
Workers receive a pinned mTLS client, not database credentials. Peer -> tenant
configuration is trusted and immutable; no tenant or role is accepted on wire.
This authenticates a narrow internal lookup, not a browser authorization API.
"""

from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict

from ciq_api.worker_authority import Membership, WorkerDenied
from ciq_api.worker_delegation import TransportPeer
from ciq_api.worker_transport import LoopbackSummaryClient, LoopbackSummaryServer

MEMBERSHIP_PATH = "/v1/current-membership"


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    subject: str
    nonce: str


class _Response(_Request):
    tenant: str
    role: Literal["processor", "auditor", "medical_officer"] | None


def _uuid(value: str) -> UUID:
    parsed = UUID(value)
    if str(parsed) != value:
        raise ValueError("Invalid membership message")
    return parsed


class LoopbackMembershipServer(LoopbackSummaryServer):
    """Cert-derived audience selects one tenant; one fresh lookup per request.

    The callback should be WorkerMembershipStore.lookup, which opens a fresh
    session and checks active user, tenant and membership. No list/query/export
    operation, positive cache, signing key or Snowflake dependency is supplied.
    """

    def __init__(
        self,
        *,
        context,
        peers: Mapping[str, str],
        tenants: Mapping[str, UUID],
        lookup: Callable[[str, UUID], Membership | None],
    ):
        copied = dict(tenants)
        if (
            not copied
            or set(peers.values()) != set(copied)
            or any(type(tenant) is not UUID for tenant in copied.values())
        ):
            raise ValueError("Invalid membership peer configuration")
        self._tenants = MappingProxyType(copied)
        self._lookup = lookup
        super().__init__(context=context, peers=peers, validate=None)
        self._path = MEMBERSHIP_PATH

    def _dispatch(self, message: dict, peer: TransportPeer) -> bytes:
        request = _Request.model_validate(message)
        _uuid(request.subject)
        _uuid(request.nonce)
        if type(peer) is not TransportPeer:
            raise WorkerDenied("Worker access denied")
        tenant = self._tenants[peer.audience]
        member = self._lookup(request.subject, tenant)
        if member is not None and (type(member) is not Membership or member.tenant_id != tenant):
            raise WorkerDenied("Worker access denied")
        return (
            _Response(
                subject=request.subject,
                nonce=request.nonce,
                tenant=str(tenant),
                role=member.role if member is not None else None,
            )
            .model_dump_json()
            .encode()
        )


class LoopbackMembershipClient(LoopbackSummaryClient):
    """Fixed tenant, fixed pinned service, no cache/retry or worker DB credential.

    A fresh TLS response is bound to a random request nonce and internal user UUID.
    Authorities must call again before delivery. This is point-in-time evidence,
    not a transaction spanning membership and source work; no instantaneous
    distributed revocation guarantee is claimed.
    """

    def __init__(self, *, tenant_id: UUID, **transport):
        if type(tenant_id) is not UUID or "operation" in transport:
            raise ValueError("Invalid membership client configuration")
        super().__init__(**transport)
        self._tenant = tenant_id
        self._path = MEMBERSHIP_PATH

    def lookup(self, subject: str) -> Membership | None:
        try:
            _uuid(subject)
            nonce = str(uuid4())
            result = _Response.model_validate(self._exchange({"subject": subject, "nonce": nonce}))
            if (
                result.subject != subject
                or result.nonce != nonce
                or result.tenant != str(self._tenant)
            ):
                raise WorkerDenied("Worker access denied")
            return Membership(self._tenant, result.role) if result.role is not None else None
        except Exception:
            raise WorkerDenied("Worker access denied") from None
