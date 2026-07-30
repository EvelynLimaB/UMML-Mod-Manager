import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from umml_manager.library import default_root


class ManagerWindowsRootTests(unittest.TestCase):
    def test_windows_uses_local_app_data_for_new_state(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / "home"
            local = root / "LocalAppData"
            home.mkdir()
            local.mkdir()
            with (
                patch("umml_manager.library.os.name", "nt"),
                patch.dict(os.environ, {"LOCALAPPDATA": str(local)}, clear=False),
                patch("umml_manager.library.Path.home", return_value=home),
            ):
                self.assertEqual(default_root(), local / "UMML Manager")

    def test_windows_preserves_early_linux_style_state_until_migrated(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / "home"
            local = root / "LocalAppData"
            legacy = home / ".local" / "share" / "umml-manager"
            legacy.mkdir(parents=True)
            local.mkdir()
            with (
                patch("umml_manager.library.os.name", "nt"),
                patch.dict(os.environ, {"LOCALAPPDATA": str(local)}, clear=False),
                patch("umml_manager.library.Path.home", return_value=home),
            ):
                self.assertEqual(default_root(), legacy)


if __name__ == "__main__":
    unittest.main()
