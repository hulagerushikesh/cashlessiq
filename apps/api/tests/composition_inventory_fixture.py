"""Import the exact inactive owner-side source without extending sys.path."""

import importlib.util
import sys
from pathlib import Path

_path = Path(__file__).resolve().parents[3] / "scripts/composition_inventory.py"
_spec = importlib.util.spec_from_file_location("ciq_composition_inventory_test", _path)
implementation = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = implementation
_spec.loader.exec_module(implementation)
