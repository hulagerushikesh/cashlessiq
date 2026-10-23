"""Offline manifest/import-boundary checks, no build/container/network."""

import ast
import shlex
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


def test_membership_composition_keeps_db_adapter_out_of_worker_image():
    dockerfile = (ROOT / "apps/membership/Dockerfile").read_text()
    before, target = dockerfile.split("FROM db-test AS composition-test", 1)
    target, after = target.split("FROM runtime-base AS candidate", 1)
    assert "composition_service.py" in target
    assert "composition_service.py" not in before + after
    assert 'ENTRYPOINT ["python", "-m", "ciq_membership_runtime.composition_service"]' in target
    worker = (ROOT / "apps/worker/Dockerfile.dockerignore").read_text()
    assert "!apps/membership/tests/composition_service.py" not in worker
    for project in ("worker", "membership"):
        assert "composition_service" not in (ROOT / f"apps/{project}/pyproject.toml").read_text()


def test_broker_test_image_has_closed_import_context_and_no_normal_activation():
    expected = set(MODULES) | {"auth", "models", "config", "worker_broker", "worker_guard_broker"}
    dockerfile = (ROOT / "apps/api/Dockerfile.broker-test").read_text()
    ignore = (ROOT / "apps/api/Dockerfile.broker-test.dockerignore").read_text().splitlines()
    copied = {
        Path(part).stem
        for line in dockerfile.splitlines()
        if line.startswith("COPY ")
        for part in shlex.split(line)[1:-1]
        if part.startswith("apps/api/src/ciq_api/")
    }
    assert copied == expected
    assert all(f"!apps/api/src/ciq_api/{name}.py" in ignore for name in expected)
    assert "!apps/api/src/**" not in ignore
    for name in expected:
        tree = ast.parse((ROOT / f"apps/api/src/ciq_api/{name}.py").read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("ciq_api."):
                assert node.module.split(".")[1] in expected
    assert "USER 10001:10001" in dockerfile
    assert "broker_composition_service.py" in dockerfile
    assert "uvicorn" not in dockerfile and "migrations" not in dockerfile
    for name in ("main", "source_cases", "snowflake_reads", "worker_membership_store"):
        assert f"!apps/api/src/ciq_api/{name}.py" not in ignore
    for name in ("broker_composition_service", "broker_composition_fixture"):
        assert name not in (ROOT / "apps/api/Dockerfile").read_text()
        assert name not in (ROOT / "apps/api/src/ciq_api/main.py").read_text()
        for project in ("worker", "membership"):
            assert (
                f"!apps/api/tests/{name}.py"
                not in (ROOT / f"apps/{project}/Dockerfile.dockerignore").read_text()
            )


def test_owner_side_launcher_is_inactive_and_absent_from_service_artifacts():
    tree = ast.parse((ROOT / "scripts/composition_inventory.py").read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.module in {"dataclasses", "hashlib", "ipaddress", "types"}
        elif isinstance(node, ast.Import):
            assert all(alias.name in {"json", "re"} for alias in node.names)
    for name in ("composition_launcher", "composition_inventory_fixture", "composition_inventory"):
        for file in (
            "apps/api/Dockerfile",
            "apps/api/Dockerfile.broker-test",
            "apps/worker/Dockerfile",
            "apps/membership/Dockerfile",
            "apps/api/src/ciq_api/main.py",
        ):
            assert name not in (ROOT / file).read_text()
    for path in ("apps/worker/Dockerfile", "apps/membership/Dockerfile"):
        target = (ROOT / path).read_text().split(" AS composition-test", 1)[1].split("FROM ", 1)[0]
        assert "CMD []" in target
    assert "CMD []" in (ROOT / "apps/api/Dockerfile.broker-test").read_text()
