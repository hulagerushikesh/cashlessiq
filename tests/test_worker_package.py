"""Offline manifest/import-boundary checks, no build/container/network."""

import ast
import tomllib
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.check_worker_package import MODULES, verify_manifest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("fault", [None, "broker", "missing", "dependency", "source-fork"])
def test_worker_allowlist_is_exact(fault):
    config = deepcopy(tomllib.loads((ROOT / "apps/worker/pyproject.toml").read_text()))
    includes = config["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]
    if fault == "broker":
        includes["../api/src/ciq_api/worker_guard_broker.py"] = "ciq_api/worker_guard_broker.py"
    elif fault == "missing":
        del includes["../api/src/ciq_api/worker_guard_health.py"]
    elif fault == "dependency":
        config["project"]["dependencies"].append("sqlalchemy")
    elif fault == "source-fork":
        includes["../api/src/ciq_api/worker_guard_health.py"] = "ciq_api/other.py"
    if fault:
        with pytest.raises(ValueError, match="Worker package boundary denied"):
            verify_manifest(config)
    else:
        verify_manifest(config)


def test_v3_worker_modules_do_not_import_broker_or_database():
    forbidden = (
        "ciq_api.auth",
        "ciq_api.models",
        "ciq_api.worker_broker",
        "ciq_api.worker_guard_broker",
        "sqlalchemy",
        "fastapi",
        "snowflake",
        "psycopg",
    )
    for name in MODULES:
        tree = ast.parse((ROOT / f"apps/api/src/ciq_api/{name}.py").read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            elif isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            else:
                continue
            assert not any(
                n == bad or n.startswith(bad + ".") for n in names for bad in forbidden
            ), name


def test_docker_context_includes_every_canonical_module_but_not_broker():
    ignore = (ROOT / "apps/worker/Dockerfile.dockerignore").read_text().splitlines()
    assert all(f"!apps/api/src/ciq_api/{name}.py" in ignore for name in MODULES)
    assert "!apps/api/src/ciq_api/worker_guard_broker.py" not in ignore
    assert "!apps/worker/tests/guard_probe.py" in ignore
    dockerfile = (ROOT / "apps/worker/Dockerfile").read_text()
    assert dockerfile.rstrip().endswith("FROM runtime-base AS candidate")
    assert "worker_guard_broker.py" not in dockerfile


def test_membership_docker_context_keeps_worker_dependency_buildable():
    ignore = (ROOT / "apps/membership/Dockerfile.dockerignore").read_text().splitlines()
    assert all(f"!apps/api/src/ciq_api/{name}.py" in ignore for name in MODULES)
    assert "!apps/api/src/ciq_api/worker_guard_broker.py" not in ignore
    assert "!apps/worker/tests/guard_mtls_fixture.py" not in ignore
    dockerfile = (ROOT / "apps/membership/Dockerfile").read_text()
    assert dockerfile.rstrip().endswith("FROM runtime-base AS candidate")


def test_frozen_health_helper_is_only_in_explicit_worker_test_target():
    dockerfile = (ROOT / "apps/worker/Dockerfile").read_text()
    before, test = dockerfile.split("FROM runtime-base AS mtls-test", 1)
    test, after = test.split("FROM runtime-base AS clock-test", 1)
    assert "guard_mtls_fixture.py" not in before + after
    assert "guard_mtls_fixture.py" in test


def test_offline_supervisor_has_no_runtime_wiring_or_worker_packaging():
    name = "offline_supervisor"
    assert name not in MODULES
    for project in ("worker", "membership"):
        config = (ROOT / f"apps/{project}/pyproject.toml").read_text()
        ignore = (ROOT / f"apps/{project}/Dockerfile.dockerignore").read_text()
        assert name not in config + ignore
    main = ast.parse((ROOT / "apps/api/src/ciq_api/main.py").read_text())
    assert not any(
        (isinstance(node, ast.ImportFrom) and name in (node.module or ""))
        or (isinstance(node, ast.Import) and any(name in a.name for a in node.names))
        for node in ast.walk(main)
    )
    tree = ast.parse((ROOT / f"apps/api/src/ciq_api/{name}.py").read_text())
    modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            modules.append(node.module or "")
        elif isinstance(node, ast.Import):
            modules.extend(a.name for a in node.names)
    assert set(modules) <= {
        "__future__",
        "re",
        "collections",
        "collections.abc",
        "dataclasses",
        "enum",
        "hashlib",
        "typing",
    }


def test_composition_service_is_explicit_test_target_only():
    dockerfile = (ROOT / "apps/worker/Dockerfile").read_text()
    before, target = dockerfile.split("FROM mtls-test AS composition-test", 1)
    target, after = target.split("FROM runtime-base AS clock-test", 1)
    assert "composition_service.py" in target
    assert "composition_service.py" not in before + after
    assert 'ENTRYPOINT ["python", "-m", "ciq_worker_runtime.composition_service"]' in target
    assert dockerfile.rstrip().endswith("FROM runtime-base AS candidate")
    ignore = (ROOT / "apps/worker/Dockerfile.dockerignore").read_text()
    assert "!apps/worker/tests/composition_service.py" in ignore
    package = (ROOT / "apps/worker/pyproject.toml").read_text()
    assert "composition_service" not in package
