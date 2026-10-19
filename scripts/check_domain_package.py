"""Build and verify the pure domain wheel outside the repository import path."""

import json
import subprocess
import tempfile
import tomllib
from email.parser import Parser
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
MODULES = ("decision_schema", "source_decision", "source_history", "source_recommendation")

SMOKE = """
import importlib.util
import json
from cashlessiq_domain.decision_schema import DECISION_SCHEMA
from cashlessiq_domain.source_decision import SourceDecisionError
from cashlessiq_domain.source_history import observe_member_history
from cashlessiq_domain.source_recommendation import observe_source_recommendation

for name in ('cashlessiq', 'snowflake', 'streamlit', 'fastapi'):
    assert importlib.util.find_spec(name) is None, name
context = dict(request_id='GOL024', tpa_id='TPA003', product_id='PRODUCT1',
               estimated_total_inr=80000, evidence=[], verified_record_ids=frozenset())
missing = observe_source_recommendation([], **context)
assert missing.state == 'MISSING' and missing.supplied_estimate_inr == 80000
assert not hasattr(missing, 'decision')
try:
    observe_source_recommendation([{}], **context)
except SourceDecisionError:
    pass
else:
    raise AssertionError('Invalid saved row became missing')
assert callable(observe_member_history)
print(json.dumps(DECISION_SCHEMA, sort_keys=True))
"""


def verify_wheel(wheel: Path) -> None:
    """Fail on omitted, rewritten or extra code and undeclared heavy dependencies."""
    expected = {f"cashlessiq_domain/{name}.py" for name in MODULES}
    expected.add("cashlessiq_domain/__init__.py")
    with ZipFile(wheel) as archive:
        code = {name for name in archive.namelist() if ".dist-info/" not in name}
        if code != expected:
            raise ValueError("Unexpected domain wheel contents")
        for module in MODULES:
            canonical = ROOT / f"src/cashlessiq/{module}.py"
            if archive.read(f"cashlessiq_domain/{module}.py") != canonical.read_bytes():
                raise ValueError("Domain wheel differs from canonical source")
        metadata_path = next(name for name in archive.namelist() if name.endswith("/METADATA"))
        metadata = Parser().parsestr(archive.read(metadata_path).decode())
        if metadata.get_all("Requires-Dist") != ["jsonschema<5,>=4.25"]:
            raise ValueError("Unexpected domain runtime dependencies")


def main() -> None:
    lock = tomllib.loads((ROOT / "apps/api/uv.lock").read_text())
    dependency_names = {
        "attrs",
        "jsonschema",
        "jsonschema-specifications",
        "referencing",
        "rpds-py",
        "typing-extensions",
    }
    pins = [
        f"{item['name']}=={item['version']}"
        for item in lock["package"]
        if item["name"] in dependency_names
    ]
    if len(pins) != len(dependency_names):
        raise ValueError("Missing locked domain runtime dependencies")
    with tempfile.TemporaryDirectory(prefix="ciq-domain-check-") as directory:
        temporary = Path(directory)
        subprocess.run(
            [
                "uv",
                "build",
                "--wheel",
                str(ROOT / "packages/domain"),
                "--out-dir",
                str(temporary / "dist"),
            ],
            check=True,
            cwd=temporary,
        )
        wheels = list((temporary / "dist").glob("*.whl"))
        if len(wheels) != 1:
            raise ValueError("Expected one domain wheel")
        verify_wheel(wheels[0])
        environment = temporary / "venv"
        subprocess.run(["uv", "venv", "--python", "3.11", str(environment)], check=True)
        python = environment / "bin/python"
        subprocess.run(
            ["uv", "pip", "install", "--python", str(python), str(wheels[0]), *pins],
            check=True,
            cwd=temporary,
        )
        result = subprocess.run(
            [str(python), "-I", "-c", SMOKE],
            check=True,
            cwd=temporary,
            capture_output=True,
            text=True,
        )
        baseline = json.loads((ROOT / "tests/fixtures/migration/v1.json").read_text())
        if json.loads(result.stdout) != baseline["decision_schema"]:
            raise ValueError("Installed decision schema differs from frozen baseline")
    print(
        "Domain wheel verified: canonical bytes, frozen schema, isolated imports, "
        "no heavy runtimes."
    )


if __name__ == "__main__":
    main()
