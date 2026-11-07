"""Compatibility backend selection. The async fallback originates in PR #1791."""

import importlib.util
import os
import sys
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class FallbackSelectionTests(unittest.TestCase):
    def load_panel(self, missing_nm=False, forced=False):
        try:
            import gi

            gi.require_version("Gtk", "3.0")
        except (ImportError, ValueError):
            self.skipTest("GTK is not installed")
        # Import GI modules before patch.dict restores sys.modules. GTypes
        # cannot be registered twice when this file is run on its own.
        importlib.import_module("panels.network")
        fallback = ModuleType("panels.network_legacy")
        fallback.Panel = type("LegacyPanel", (), {})
        modules = {"panels.network_legacy": fallback}
        if missing_nm:
            modules["ks_includes.gio_nm"] = None
        path = Path(__file__).resolve().parents[1] / "panels/network.py"
        spec = importlib.util.spec_from_file_location("network_selection_test", path)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, modules), patch.dict(os.environ):
            os.environ.pop("KLIPPERSCREEN_NETWORK_BACKEND", None)
            if forced:
                os.environ["KLIPPERSCREEN_NETWORK_BACKEND"] = "sdbus"
            spec.loader.exec_module(module)
        return module.Panel, fallback.Panel

    def test_missing_nm_automatically_selects_legacy_panel(self):
        selected, legacy = self.load_panel(missing_nm=True)
        self.assertIs(selected, legacy)

    def test_explicit_override_selects_legacy_panel(self):
        selected, legacy = self.load_panel(forced=True)
        self.assertIs(selected, legacy)

    def test_libnm_is_the_default_when_available(self):
        selected, legacy = self.load_panel()
        self.assertIsNot(selected, legacy)


if __name__ == "__main__":
    unittest.main()
