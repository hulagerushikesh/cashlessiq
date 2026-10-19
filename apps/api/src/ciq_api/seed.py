"""Idempotent, synthetic-only local identity seed. Never runs in staging/production."""

from uuid import UUID

from ciq_api.auth import LOCAL_ISSUER
from ciq_api.config import Settings
from ciq_api.database import make_engine, session_for
from ciq_api.models import AppUser, Membership, Tenant

TENANT_ID = UUID("00000000-0000-4000-8000-000000000001")
PROFILES = {
    "processor": ("00000000-0000-4000-8000-000000000011", "Asha Deshmukh"),
    "medical_officer": ("00000000-0000-4000-8000-000000000012", "Dr. Neel Shah"),
    "auditor": ("00000000-0000-4000-8000-000000000013", "Kavya Rao"),
}


def seed(settings: Settings) -> None:
    if settings.environment not in {"local", "test"} or settings.auth_mode != "local":
        raise RuntimeError("Synthetic seed requires local/test identity mode")
    engine = make_engine(settings)
    try:
        with session_for(engine) as session, session.begin():
            if session.get(Tenant, TENANT_ID) is None:
                session.add(Tenant(id=TENANT_ID, name="Sahyadri Health TPA · Sandbox"))
                session.flush()
            for profile, (user_id, name) in PROFILES.items():
                user_uuid = UUID(user_id)
                if session.get(AppUser, user_uuid) is None:
                    session.add(
                        AppUser(
                            id=user_uuid,
                            issuer=LOCAL_ISSUER,
                            subject=profile,
                            display_name=name,
                        )
                    )
                    session.flush()
                if session.get(Membership, (TENANT_ID, user_uuid)) is None:
                    session.add(Membership(tenant_id=TENANT_ID, user_id=user_uuid, role=profile))
    finally:
        engine.dispose()


if __name__ == "__main__":
    seed(Settings())
