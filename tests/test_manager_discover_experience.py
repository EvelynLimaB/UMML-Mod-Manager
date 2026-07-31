from __future__ import annotations

import unittest
from pathlib import Path

from umml_manager.ui_discover_experience import DiscoverExperienceActions


class _Root:
    def __init__(self):
        self.callbacks = []

    def after(self, delay, callback):
        self.callbacks.append((delay, callback))


class DiscoverExperienceTests(unittest.TestCase):
    def test_initial_catalog_load_is_scheduled_once(self):
        actions = DiscoverExperienceActions()
        actions.root = _Root()
        actions._closing = False
        calls = []
        actions.ensure_gamebanana_catalog = lambda: calls.append("loaded")

        actions.schedule_initial_gamebanana_load(25)
        actions.schedule_initial_gamebanana_load(25)

        self.assertEqual(len(actions.root.callbacks), 1)
        delay, callback = actions.root.callbacks[0]
        self.assertEqual(delay, 25)
        callback()
        self.assertEqual(calls, ["loaded"])

    def test_filter_change_resets_page_saves_and_refreshes(self):
        actions = DiscoverExperienceActions()
        actions.gb_page = 7
        events = []
        actions.save_settings = lambda silent=False: events.append(("save", silent))
        actions.browse_gamebanana = lambda: events.append(("browse", True))

        actions.gamebanana_filter_changed()

        self.assertEqual(actions.gb_page, 1)
        self.assertEqual(events, [("save", True), ("browse", True)])

    def test_discover_ui_has_explicit_refresh_region_and_file_labels(self):
        source = Path("umml_manager/ui_discover.py").read_text(encoding="utf-8")
        self.assertIn('text="Region"', source)
        self.assertIn('text="Refresh"', source)
        self.assertIn('text="Download file"', source)
        self.assertIn('selectmode="browse"', source)

    def test_background_status_only_updates_inside_discover(self):
        actions = DiscoverExperienceActions()
        events = []
        actions.status = type("Status", (), {"set": lambda _self, value: events.append(value)})()
        actions._current_page = "library"
        actions._set_discover_status("hidden")
        actions._current_page = "discover"
        actions._set_discover_status("visible")
        self.assertEqual(events, ["visible"])

    def test_smoke_mode_disables_background_network(self):
        source = Path("umml_manager/gui.py").read_text(encoding="utf-8")
        self.assertIn("ManagerGUI(root, store, auto_network=False)", source)


if __name__ == "__main__":
    unittest.main()
