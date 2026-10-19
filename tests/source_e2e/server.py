"""Loopback-only test API with real membership DB and shared fake source gateways.

Never imported by application startup. The random disposable schema is the only
schema created/removed here; persistent sandbox identities are not seeded.
"""

import os
import runpy
import signal
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import uvicorn
from alembic import command
from alembic.config import Config
from ciq_api.auth import LOCAL_ISSUER
from ciq_api.config import Settings
from ciq_api.main import create_app
from ciq_api.models import AppUser, Membership, Tenant
from ciq_api.source_alpha import SOURCE_TENANTS
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[2]
TEST_KEY = "source-e2e-test-key-not-for-any-deployment-0000"


class DisposableTestServer(uvicorn.Server):
    @contextmanager
    def capture_signals(self):
        # Uvicorn normally replays SIGTERM after graceful shutdown, which
        # terminates the process before our outer schema-cleanup finally block.
        # This main-thread test runner restores handlers without replaying it.
        previous = {
            sig: signal.signal(sig, self.handle_exit) for sig in (signal.SIGINT, signal.SIGTERM)
        }
        try:
            yield
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)


def main() -> None:
    if os.environ.get("CIQ_SOURCE_E2E") != "1":
        raise RuntimeError("Explicit source test opt-in required")
    url = os.environ["TEST_DATABASE_URL"]
    parsed = make_url(url)
    if (
        parsed.host not in {"127.0.0.1", "localhost"}
        or parsed.port != 55432
        or parsed.database != "cashlessiq"
        or parsed.username != "ciq"
    ):
        raise RuntimeError("Source UI tests require the loopback-only product test database")
    schema = "source_e2e_" + uuid4().hex
    admin = create_engine(url)
    isolated = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    created = False
    try:
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            created = True
        config = Config(str(ROOT / "apps/api/alembic.ini"))
        with isolated.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        with Session(isolated) as session, session.begin():
            for source in SOURCE_TENANTS:
                session.add(Tenant(id=source.tenant_id, name=source.name))
                session.flush()
                for profile in source.profiles:
                    session.add(
                        AppUser(
                            id=profile.user_id,
                            issuer=LOCAL_ISSUER,
                            subject=profile.subject,
                            display_name=profile.display_name,
                        )
                    )
                    session.flush()
                    session.add(
                        Membership(
                            tenant_id=source.tenant_id, user_id=profile.user_id, role=profile.role
                        )
                    )
        # Reuse API test inputs, not frozen demo or observed live-source output.
        fixtures = runpy.run_path(str(ROOT / "apps/api/tests/test_source_cases.py"))
        repository = fixtures["build_test_sources"]()[0]
        settings = Settings(environment="test", auth_mode="local", local_auth_secret=TEST_KEY)
        app = create_app(settings, isolated, source_repository=repository)

        @app.middleware("http")
        async def test_source_outage(request, call_next):
            # Test-only transport fixture: never installed by create_app/startup.
            if (
                request.url.path == "/v2/cases"
                and request.query_params.get("search") == "TEST_SOURCE_OUTAGE"
            ):
                return JSONResponse(
                    {"detail": "Test source unavailable"},
                    status_code=503,
                    headers={"Cache-Control": "no-store"},
                )
            return await call_next(request)

        DisposableTestServer(
            uvicorn.Config(app, host="127.0.0.1", port=8003, access_log=False, log_level="warning")
        ).run()
    finally:
        isolated.dispose()
        if created:
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


if __name__ == "__main__":
    main()
