"""Import the exact opt-in worker test source without changing sys.path."""

import importlib.util
import sys
from pathlib import Path

_path = Path(__file__).resolve().parents[2] / "worker/tests/composition_service.py"
_spec = importlib.util.spec_from_file_location("ciq_composition_test_service", _path)
service = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = service
_spec.loader.exec_module(service)
