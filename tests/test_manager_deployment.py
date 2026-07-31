import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import umml_manager
from umml_manager.deployment import ApplyEngine, ApplyError
from umml_manager.legacy_host import _install_guard, _watch_game
from umml_manager.resolver import Resolution


class DeploymentBoundaryTests(unittest.TestCase):
    def test_legacy_engine_import_resolves_to_validated_facade(self):
        from umml_manager.engine import ApplyEngine as CompatibilityApplyEngine

        self.assertIs(CompatibilityApplyEngine, ApplyEngine)
        self.assertIs(umml_manager.ApplyEngine, ApplyEngine)

    def test_stale_prepared_cache_is_rejected_by_engine(self):
        resolution = Resolution(profile="Default")
        resolution.stale_prepared.append("mod-a uses old metadata")
        engine = object.__new__(ApplyEngine)

        with self.assertRaisesRegex(ApplyError, "Stale prepared caches"):
            engine._validate_resolution(resolution)

    def test_wrong_installation_is_rejected_by_engine(self):
        resolution = Resolution(profile="Default")
        resolution.wrong_installation.append("profile belongs to steam-global")
        engine = object.__new__(ApplyEngine)

        with self.assertRaisesRegex(ApplyError, "Wrong installation"):
            engine._validate_resolution(resolution)

    def test_process_inspection_failure_blocks_deployment(self):
        engine = object.__new__(ApplyEngine)
        engine.game_dir = None
        engine.process_check = Mock(side_effect=OSError("/proc unavailable"))

        with self.assertRaisesRegex(ApplyError, "writes were blocked"):
            engine._assert_game_closed()


class FakeRoot:
    def __init__(self):
        self.destroyed = False
        self.scheduled = []

    def winfo_exists(self):
        return True

    def destroy(self):
        self.destroyed = True

    def after(self, delay, callback):
        self.scheduled.append((delay, callback))


class LegacyStudioBoundaryTests(unittest.TestCase):
    def test_lifetime_watcher_closes_when_process_inspection_fails(self):
        root = FakeRoot()
        gui = SimpleNamespace(game_dir="")
        with patch(
            "umml_manager.legacy_host._running_game",
            side_effect=OSError("cannot inspect processes"),
        ), patch("umml_manager.legacy_host.messagebox.showerror") as showerror:
            _watch_game(root, gui)

        self.assertTrue(root.destroyed)
        self.assertEqual(root.scheduled, [])
        showerror.assert_called_once()

    def test_mutating_guard_does_not_call_tool_when_inspection_fails(self):
        called = []

        class LegacyGui:
            root = None
            game_dir = ""

            def delete_master_db(self):
                called.append(True)

        _install_guard(LegacyGui)
        gui = LegacyGui()
        with patch(
            "umml_manager.legacy_host._running_game",
            side_effect=OSError("cannot inspect processes"),
        ), patch("umml_manager.legacy_host.messagebox.showerror") as showerror:
            result = gui.delete_master_db()

        self.assertIsNone(result)
        self.assertEqual(called, [])
        showerror.assert_called_once()


if __name__ == "__main__":
    unittest.main()
