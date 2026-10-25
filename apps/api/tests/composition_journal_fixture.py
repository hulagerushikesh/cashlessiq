"""Exact owner-side sources in a test-only namespace; no sys.path mutation."""

import importlib

from composition_inventory_fixture import implementation as inv

implementation = importlib.import_module(inv.__package__ + ".composition_journal")
