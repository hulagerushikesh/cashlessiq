"""Packaging allowlist regressions; no build, network, Docker or Snowflake."""

import tomllib
from pathlib import Path
from zipfile import ZipFile

import pytest

from scripts.check_domain_package import MODULES, verify_wheel

ROOT = Path(__file__).resolve().parents[1]


def test_domain_source_allowlist_and_cache_keys():
    config = tomllib.loads((ROOT / "packages/domain/pyproject.toml").read_text())
    assert config["project"]["dependencies"] == ["jsonschema>=4.25,<5"]
    include = config["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]
    expected = {
        f"../../src/cashlessiq/{module}.py": f"cashlessiq_domain/{module}.py"
        for module in MODULES
    }
    assert include == expected
    cache = {item["file"] for item in config["tool"]["uv"]["cache-keys"]}
    assert set(expected) <= cache


@pytest.mark.parametrize("fault", [None, "extra", "missing", "modified", "init", "dependency"])
def test_wheel_contents_fail_closed(tmp_path, fault):
    wheel = tmp_path / "boundary.whl"
    with ZipFile(wheel, "w") as archive:
        for module in MODULES:
            if fault == "missing" and module == "source_history":
                continue
            source = (ROOT / f"src/cashlessiq/{module}.py").read_bytes()
            if fault == "modified" and module == "source_history":
                source += b"\n# modified\n"
            archive.writestr(f"cashlessiq_domain/{module}.py", source)
        init = (ROOT / "packages/domain/src/cashlessiq_domain/__init__.py").read_bytes()
        archive.writestr("cashlessiq_domain/__init__.py", b"changed" if fault == "init" else init)
        metadata = "Metadata-Version: 2.4\nRequires-Dist: jsonschema<5,>=4.25\n"
        if fault == "dependency":
            metadata += "Requires-Dist: snowflake-snowpark-python\n"
        archive.writestr("cashlessiq_domain-0.1.0.dist-info/METADATA", metadata)
        if fault == "extra":
            archive.writestr("cashlessiq_domain/procs/agent.py", b"# unexpected\n")
    if fault:
        with pytest.raises(ValueError):
            verify_wheel(wheel)
    else:
        verify_wheel(wheel)


def test_domain_verification_uses_explicit_staged_source_including_initializer(tmp_path):
    # Deliberately different from this checkout: the selected source tree must
    # control verification, even if the checkout's canonical files still match.
    source = tmp_path / "source"
    init = source / "packages/domain/src/cashlessiq_domain/__init__.py"
    init.parent.mkdir(parents=True)
    init.write_bytes(b"# selected initializer\n")
    wheel = tmp_path / "selected.whl"
    with ZipFile(wheel, "w") as archive:
        for module in MODULES:
            path = source / f"src/cashlessiq/{module}.py"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"# selected source\n")
            archive.writestr(f"cashlessiq_domain/{module}.py", path.read_bytes())
        archive.writestr("cashlessiq_domain/__init__.py", init.read_bytes())
        archive.writestr("cashlessiq_domain-0.1.0.dist-info/METADATA",
                         "Metadata-Version: 2.4\nRequires-Dist: jsonschema<5,>=4.25\n")
    verify_wheel(wheel, source_root=source)
    with pytest.raises(ValueError, match="canonical source"):
        verify_wheel(wheel)
    init.write_bytes(b"changed after build")
    with pytest.raises(ValueError, match="canonical source"):
        verify_wheel(wheel, source_root=source)
