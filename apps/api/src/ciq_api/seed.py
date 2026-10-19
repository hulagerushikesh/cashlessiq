"""Idempotent, synthetic-only local identity seed. Never runs in staging/production."""

from uuid import UUID

from ciq_api.auth import LOCAL_ISSUER
from ciq_api.config import Settings
from ciq_api.database import make_engine, session_for
from ciq_api.models import AppUser, Membership, Tenant
from ciq_api.source_alpha import SOURCE_TENANTS
from ciq_api.source_identity import TENANT_ID as TENANT_ID

PROFILES = {
    "processor": ("00000000-0000-4000-8000-000000000011", "Asha Deshmukh"),
    "medical_officer": ("00000000-0000-4000-8000-000000000012", "Dr. Neel Shah"),
    "auditor": ("00000000-0000-4000-8000-000000000013", "Kavya Rao"),
}


def seed(settings: Settings, *, include_source_tenants: bool = False) -> None:
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
            if include_source_tenants:
                for source in SOURCE_TENANTS:
                    tenant = session.get(Tenant, source.tenant_id)
                    if tenant is None:
                        session.add(Tenant(id=source.tenant_id, name=source.name))
                        session.flush()
                    elif tenant.name != source.name:
                        raise RuntimeError("Source alpha tenant identity conflict")
                    for profile in source.profiles:
                        user = session.get(AppUser, profile.user_id)
                        if user is None:
                            session.add(
                                AppUser(
                                    id=profile.user_id,
                                    issuer=LOCAL_ISSUER,
                                    subject=profile.subject,
                                    display_name=profile.display_name,
                                )
                            )
                            session.flush()
                        elif (user.issuer, user.subject) != (LOCAL_ISSUER, profile.subject):
                            raise RuntimeError("Source alpha user identity conflict")
                        if session.get(Membership, (source.tenant_id, profile.user_id)) is None:
                            session.add(
                                Membership(
                                    tenant_id=source.tenant_id,
                                    user_id=profile.user_id,
                                    role=profile.role,
                                )
                            )
    finally:
        engine.dispose()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include-source-tenants", action="store_true")
    args = parser.parse_args()
    seed(Settings(), include_source_tenants=args.include_source_tenants)
