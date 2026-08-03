from __future__ import annotations

import unittest

from umml_manager.ui_discover import DiscoverPage
from umml_manager.ui_library import LibraryPage
from umml_manager.ui_scrollable import ScrollablePage, responsive_columns
from umml_manager.ui_settings import SettingsPage
from umml_manager.ui_studio import StudioPage


class ResponsivePageStructureTests(unittest.TestCase):
    def test_document_pages_use_scrollable_container(self):
        self.assertTrue(issubclass(SettingsPage, ScrollablePage))
        self.assertTrue(issubclass(StudioPage, ScrollablePage))

    def test_table_pages_keep_their_own_scroll_ownership(self):
        self.assertFalse(issubclass(LibraryPage, ScrollablePage))
        self.assertFalse(issubclass(DiscoverPage, ScrollablePage))

    def test_responsive_columns_switch_at_breakpoint(self):
        self.assertEqual(responsive_columns(0), 1)
        self.assertEqual(responsive_columns(839, breakpoint=840), 1)
        self.assertEqual(responsive_columns(840, breakpoint=840), 2)
        self.assertEqual(responsive_columns(1920, breakpoint=840), 2)

    def test_invalid_breakpoint_is_safely_normalized(self):
        self.assertEqual(responsive_columns(0, breakpoint=0), 1)
        self.assertEqual(responsive_columns(1, breakpoint=0), 2)


if __name__ == "__main__":
    unittest.main()
