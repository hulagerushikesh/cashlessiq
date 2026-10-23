"""Exact owner-side sources in a test-only namespace; no sys.path mutation."""

import importlib
import sys
from importlib.machinery import ModuleSpec
from pathlib import Path
from types import ModuleType

_name = "ciq_composition_owner_journal_test"
_package = ModuleType(_name)
_package.__path__ = [str(Path(__file__).resolve().parents[3] / "scripts")]
_package.__spec__ = ModuleSpec(_name, loader=None, is_package=True)
sys.modules[_name] = _package
implementation = importlib.import_module(_name + ".composition_journal")
