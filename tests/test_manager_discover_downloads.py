from __future__ import annotations

import unittest
from types import SimpleNamespace

from umml_manager.providers.gamebanana import GameBananaFile, GameBananaMod
from umml_manager.ui_discover_actions import DiscoverActions


class _Tree:
    def __init__(self):
        self.rows = {}

    def exists(self, key):
        return str(key) in self.rows

    def item(self, key, option=None, **values):
        key = str(key)
        if option is not None and not values:
            return self.rows[key].get(option)
        self.rows.setdefault(key, {}).update(values)
        return self.rows[key]


class DiscoverDownloadTests(unittest.TestCase):
    @staticmethod
    def _mod(*, downloads=0, files=()):
        return GameBananaMod(
            id=42,
            name="Test mod",
            author="Author",
            profile_url="https://gamebanana.com/mods/42",
            files=files,
            version="1.0",
            downloads=downloads,
        )

    def test_partial_catalog_zero_is_not_presented_as_a_real_zero(self):
        mod = self._mod(downloads=0, files=())
        self.assertEqual(DiscoverActions._gamebanana_download_label(mod), "…")
        self.assertEqual(
            DiscoverActions._gamebanana_download_label(mod, known=True),
            "0",
        )

    def test_file_metadata_makes_a_zero_count_known(self):
        file = GameBananaFile(
            id=7,
            name="mod.zip",
            url="https://gamebanana.com/dl/7",
            downloads=0,
        )
        mod = self._mod(downloads=0, files=(file,))
        self.assertEqual(DiscoverActions._gamebanana_download_label(mod), "0")

    def test_hydrated_detail_replaces_the_tree_download_value(self):
        actions = DiscoverActions()
        tree = _Tree()
        tree.rows["42"] = {
            "text": "Test mod",
            "values": ("Author", "1.0", "…"),
        }
        actions.discover = SimpleNamespace(gb_tree=tree)
        actions.gb_results = {"42": self._mod()}
        actions.gb_selected = None
        actions._closing = False
        actions._gb_catalog_detail_serial = 3

        detailed = self._mod(downloads=25)
        actions._show_hydrated_gamebanana_row(3, detailed)

        self.assertIs(actions.gb_results["42"], detailed)
        self.assertEqual(tree.rows["42"]["values"], ("Author", "1.0", "25"))

    def test_stale_page_hydration_cannot_overwrite_current_rows(self):
        actions = DiscoverActions()
        tree = _Tree()
        tree.rows["42"] = {
            "text": "Current mod",
            "values": ("Author", "1.0", "…"),
        }
        current = self._mod()
        actions.discover = SimpleNamespace(gb_tree=tree)
        actions.gb_results = {"42": current}
        actions.gb_selected = None
        actions._closing = False
        actions._gb_catalog_detail_serial = 4

        actions._show_hydrated_gamebanana_row(3, self._mod(downloads=25))

        self.assertIs(actions.gb_results["42"], current)
        self.assertEqual(tree.rows["42"]["values"][-1], "…")


if __name__ == "__main__":
    unittest.main()
