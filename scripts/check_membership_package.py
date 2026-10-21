"""Build isolated non-editable membership wheels; never start services or read secrets."""

import os
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
PROBE = """
import importlib.util
from pathlib import Path
import sys
import ciq_api.worker_membership_store as store
from ciq_api.worker_membership import PrivateMembershipServer
assert Path(store.__file__).is_relative_to(Path(sys.prefix))
assert Path(store.__file__).read_bytes() == Path(sys.argv[1]).read_bytes()
for name in ('fastapi', 'alembic', 'uvicorn', 'snowflake', 'ciq_api.main',
             'ciq_api.models', 'ciq_api.auth', 'ciq_api.worker_broker'):
    assert importlib.util.find_spec(name) is None, name
print('PASS: canonical membership adapter, no API/auth/broker/models/Snowflake')
"""


def main():
    with TemporaryDirectory(prefix="ciq-membership-package-") as temporary:
        environment = os.environ | {"UV_PROJECT_ENVIRONMENT": str(Path(temporary) / "venv")}
        environment.pop("VIRTUAL_ENV", None)
        subprocess.run(
            ["uv", "sync", "--project", "apps/membership", "--frozen", "--no-editable"],
            cwd=ROOT,
            env=environment,
            check=True,
        )
        python = str(Path(temporary) / "venv/bin/python")
        subprocess.run(
            [
                python,
                "-I",
                "-c",
                PROBE,
                str(ROOT / "apps/api/src/ciq_api/worker_membership_store.py"),
            ],
            check=True,
        )
        refused = subprocess.run(
            [python, "-I", "-m", "ciq_membership_runtime"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert refused.returncode != 0
        assert "Membership activation unavailable" in refused.stderr
        print("PASS: default membership entry point refuses activation")


if __name__ == "__main__":
    main()
