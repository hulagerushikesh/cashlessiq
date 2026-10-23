"""Load the exact opt-in membership image test source without sys.path changes."""

import importlib.util
import sys
from pathlib import Path

_path = Path(__file__).resolve().parents[2] / "membership/tests/composition_service.py"
_spec = importlib.util.spec_from_file_location("ciq_membership_composition_test", _path)
service = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = service
_spec.loader.exec_module(service)
