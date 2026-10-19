"""Thin HTTP layer for identity and operational health."""

from collections.abc import Iterator
from contextlib import asynccontextmanager
from secrets import compare_digest
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ciq_api.auth import JWTVerifier, issue_local_token, resolve_identity
from ciq_api.config import Settings
from ciq_api.contracts import HealthResponse, LocalSessionRequest, MeResponse, TokenResponse
from ciq_api.database import make_engine, session_for
from ciq_api.seed import TENANT_ID


def create_app(settings: Settings | None = None, engine: Engine | None = None) -> FastAPI:
    config = settings or Settings()
    database = engine or make_engine(config)
    verifier = JWTVerifier(config)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        database.dispose()

    app = FastAPI(title="CashlessIQ API", version="1.0.0", lifespan=lifespan)
    bearer = HTTPBearer(auto_error=False)

    def get_session() -> Iterator[Session]:
        with session_for(database) as session:
            yield session

    Database = Annotated[Session, Depends(get_session)]
    Credential = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]

    @app.get("/health/live", response_model=HealthResponse, operation_id="liveness")
    def live() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.get("/health/ready", response_model=HealthResponse, operation_id="readiness")
    def ready(response: Response) -> HealthResponse:
        try:
            with database.connect() as connection:
                revision = connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar()
                if revision != "0001_identity":
                    raise ValueError("Database migration required")
            return HealthResponse(status="ready")
        except (SQLAlchemyError, ValueError):
            response.status_code = 503
            return HealthResponse(status="unavailable")

    @app.get("/v1/me", response_model=MeResponse, operation_id="get_identity")
    def me(session: Database, credentials: Credential, response: Response) -> MeResponse:
        response.headers["Cache-Control"] = "no-store"
        if credentials is None:
            raise HTTPException(
                401, "Authentication required", headers={"WWW-Authenticate": "Bearer"}
            )
        return resolve_identity(session, verifier.verify(credentials.credentials), config.auth_mode)

    if config.auth_mode == "local":

        @app.post(
            "/v1/auth/local/session",
            response_model=TokenResponse,
            operation_id="create_local_session",
            include_in_schema=False,
        )
        def local_session(
            payload: LocalSessionRequest,
            session: Database,
            response: Response,
            bootstrap: Annotated[str, Header(alias="X-Local-Auth-Key")] = "",
        ) -> TokenResponse:
            if not compare_digest(
                bootstrap.encode(), config.local_auth_secret.get_secret_value().encode()
            ):
                raise HTTPException(401, "Local session bootstrap rejected")
            token = issue_local_token(config, payload.profile, TENANT_ID)
            resolve_identity(session, verifier.verify(token), "local")
            response.headers["Cache-Control"] = "no-store"
            return TokenResponse(access_token=token, expires_in=1800)

    return app
