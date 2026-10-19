"""Database factory and short-lived request sessions."""

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from ciq_api.config import Settings


def make_engine(settings: Settings) -> Engine:
    return create_engine(
        settings.database_url.get_secret_value(),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        connect_args={"connect_timeout": 3},
        hide_parameters=True,
    )


def session_for(engine: Engine) -> Session:
    return Session(engine, expire_on_commit=False)
