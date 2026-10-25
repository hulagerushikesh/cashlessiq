"""Restore the pre-MVP synthetic backup in a temporary DB on the owned local server."""

import json
import subprocess
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
BACKUP = ROOT / "output/mvp-local/before-mvp.dump"
VERIFY = """
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url
from ciq_api.config import Settings
from ciq_api.database import make_engine
from ciq_api.seed import seed
import sys
config = Settings()
target = make_url(config.database_url.get_secret_value()).set(database=sys.argv[1])
config = Settings(**(config.model_dump() | {
    "database_url": target.render_as_string(hide_password=False)
}))
engine = make_engine(config)
try:
    with engine.begin() as connection:
        revision = connection.execute(text('SELECT version_num FROM alembic_version')).scalar()
        assert revision == '0001_identity'
        assert connection.execute(text('SELECT count(*) FROM app_user')).scalar() == 3
        migration = Config('/app/apps/api/alembic.ini')
        migration.attributes['connection'] = connection
        command.upgrade(migration, 'head')
        revision = connection.execute(text('SELECT version_num FROM alembic_version')).scalar()
        assert revision == '0003_mvp'
    seed(config)
    with engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM app_user')).scalar() == 7
    print('Backup restore, forward migration and seven-role seed verified.')
finally:
    engine.dispose()
"""


def main():
    if not BACKUP.is_file() or not 0 < BACKUP.stat().st_size <= 10 * 1024**2:
        raise ValueError("Expected bounded pre-MVP backup")
    assert BACKUP.read_bytes()[:5] == b"PGDMP"
    compose = ["docker", "compose", "--env-file", ".env.product.local", "-f", "compose.product.yml"]
    ids = {}
    for service in ("db", "api"):
        cid = subprocess.check_output([*compose, "ps", "-q", service], text=True, cwd=ROOT).strip()
        row = json.loads(subprocess.check_output(["docker", "inspect", cid], cwd=ROOT))[0]
        assert row["Id"] == cid and row["State"]["Running"]
        labels = row["Config"]["Labels"]
        assert labels["com.docker.compose.project"] == "cashlessiq-product"
        assert labels["com.docker.compose.service"] == service
        ids[service] = cid
    database = "ciq_restore_" + uuid4().hex[:12]
    subprocess.run(
        ["docker", "exec", ids["db"], "createdb", "-U", "ciq", database], check=True, cwd=ROOT
    )
    try:
        with BACKUP.open("rb") as source:
            subprocess.run(
                [
                    "docker",
                    "exec",
                    "-i",
                    ids["db"],
                    "pg_restore",
                    "-U",
                    "ciq",
                    "--no-owner",
                    "--no-privileges",
                    "--exit-on-error",
                    "-d",
                    database,
                ],
                stdin=source,
                check=True,
                cwd=ROOT,
            )
        subprocess.run(
            [
                "docker",
                "exec",
                ids["api"],
                "/app/apps/api/.venv/bin/python",
                "-c",
                VERIFY,
                database,
            ],
            check=True,
            cwd=ROOT,
        )
    finally:
        subprocess.run(
            ["docker", "exec", ids["db"], "dropdb", "-U", "ciq", database], check=True, cwd=ROOT
        )


if __name__ == "__main__":
    main()
