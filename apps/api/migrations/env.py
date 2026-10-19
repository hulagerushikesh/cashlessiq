"""Versioned database migrations; credentials are taken from the environment."""

from alembic import context

from ciq_api.config import Settings
from ciq_api.database import make_engine
from ciq_api.models import Base

config = context.config


def run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(
        url=Settings().database_url.get_secret_value(),
        target_metadata=Base.metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()
elif config.attributes.get("connection") is not None:
    run_migrations(config.attributes["connection"])
else:
    engine = make_engine(Settings())
    with engine.connect() as connection:
        run_migrations(connection)
    engine.dispose()
