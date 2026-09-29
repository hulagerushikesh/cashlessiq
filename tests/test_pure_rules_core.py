"""Architectural guardrails for the pure-Python rules package."""

import ast
from pathlib import Path


def test_rules_core_has_no_snowflake_imports() -> None:
    rules_dir = Path("src/cashlessiq/rules")
    offenders: list[str] = []
    for path in rules_dir.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            if any(name == "snowflake" or name.startswith("snowflake.") for name in names):
                offenders.append(str(path))
    assert not offenders, f"Snowflake imports found in pure rules core: {offenders}"

