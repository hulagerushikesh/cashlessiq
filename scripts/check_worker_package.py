"""Check minimal canonical worker install; no service startup or real secrets."""

import json
import os
import subprocess
import tomllib
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
MODULES = (
    "__init__",
    "contracts",
    "source_contracts",
    "source_identity",
    "source_models",
    "source_alpha",
    "source_scopes",
    "validation_worker",
    "worker_authority",
    "worker_delegation",
    "worker_replay",
    "worker_clock",
    "worker_health",
    "worker_guard_state",
    "worker_guard_health",
    "worker_guard_authority",
    "worker_guard_transport",
    "worker_transport",
    "worker_membership",
)
DEPENDENCIES = ["cashlessiq-domain==0.1.0", "pydantic>=2.10,<3", "pyjwt[crypto]>=2.10,<3"]


def verify_manifest(config):
    includes = config["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]
    expected = {f"../api/src/ciq_api/{name}.py": f"ciq_api/{name}.py" for name in MODULES}
    if includes != expected or config["project"]["dependencies"] != DEPENDENCIES:
        raise ValueError("Worker package boundary denied")


PROBE = """
import importlib, importlib.util, json, sys
from pathlib import Path
root = Path(sys.argv[1])
modules = json.loads(sys.argv[2])
for name in modules:
    qualified = 'ciq_api.'+name if name != '__init__' else 'ciq_api'
    module = importlib.import_module(qualified)
    installed = Path(module.__file__)
    assert installed.is_relative_to(Path(sys.prefix)), name
    source = root / ('apps/api/src/ciq_api/'+name+'.py')
    assert installed.read_bytes() == source.read_bytes(), name
for name in ('fastapi','sqlalchemy','alembic','uvicorn','psycopg','snowflake',
             'ciq_api.main','ciq_api.auth','ciq_api.models','ciq_api.worker_broker',
             'ciq_api.worker_guard_broker','ciq_api.worker_health_collect',
             'ciq_worker_runtime.guard_probe','ciq_worker_runtime.clock_probe',
             'ciq_worker_runtime.mtls_probe','ciq_worker_runtime.guard_mtls_fixture',
             'ciq_worker_runtime.isolation_probe'):
    assert importlib.util.find_spec(name) is None, name
print('PASS: canonical v3 worker modules, no broker/API/DB/collector/test probes')
"""


def main():
    verify_manifest(tomllib.loads((ROOT / "apps/worker/pyproject.toml").read_text()))
    with TemporaryDirectory(prefix="ciq-worker-package-") as temporary:
        env = os.environ | {"UV_PROJECT_ENVIRONMENT": str(Path(temporary) / "venv")}
        env.pop("VIRTUAL_ENV", None)
        subprocess.run(
            ["uv", "sync", "--project", "apps/worker", "--frozen", "--no-editable", "--no-cache"],
            cwd=ROOT,
            env=env,
            check=True,
        )
        python = str(Path(temporary) / "venv/bin/python")
        subprocess.run([python, "-I", "-c", PROBE, str(ROOT), json.dumps(MODULES)], check=True)
        refused = subprocess.run(
            [python, "-I", "-m", "ciq_worker_runtime"], capture_output=True, text=True, check=False
        )
        assert refused.returncode == 1 and "Worker activation unavailable" in refused.stderr
        print("PASS: default worker entry point refuses activation")


if __name__ == "__main__":
    main()
