"""Import the exact inactive owner-side source without extending sys.path."""

import importlib
import sys
from importlib.machinery import ModuleSpec
from pathlib import Path
from types import ModuleType

# All owner adapters must share the same exact types across physical handoffs.
# A private test package loads the fixed sources without changing sys.path or
# making owner tooling part of the application distribution.
_name = "ciq_composition_owner_test"
if _name not in sys.modules:
    _package = ModuleType(_name)
    _package.__path__ = [str(Path(__file__).resolve().parents[3] / "scripts")]
    _package.__spec__ = ModuleSpec(_name, loader=None, is_package=True)
    sys.modules[_name] = _package
implementation = importlib.import_module(_name + ".composition_inventory")
