import unittest

try:
    from PIL import Image
except ImportError:  # Legacy-only validation intentionally installs no manager deps.
    Image = None

if Image is not None:
    from umml_manager.providers.gamebanana import GameBananaFile, GameBananaMod
    from umml_manager.ui_discover_actions import DiscoverActions


class FakeWidget:
    def __init__(self):
        self.options = {}
        self.value = ""

    def configure(self, **kwargs):
        self.options.update(kwargs)

    def set(self, value):
        self.value = value

    def current(self, index):
        values = self.options.get("values", ())
        self.value = values[index]


class FakeDiscover:
    def __init__(self):
        self.gb_files = FakeWidget()
        self.install_gb_button = FakeWidget()


@unittest.skipUnless(Image is not None, "Pillow is a manager-only dependency")
class DiscoverInstallStateTests(unittest.TestCase):
    def setUp(self):
        self.actions = object.__new__(DiscoverActions)
        self.actions.discover = FakeDiscover()

    def test_incomplete_catalog_record_keeps_install_latest_enabled(self):
        mod = GameBananaMod(
            id=123,
            name="Incomplete",
            author="",
            profile_url="https://gamebanana.com/mods/123",
            files=(),
        )

        self.actions._configure_gamebanana_files(
            mod,
            details_complete=False,
            loading=True,
        )

        self.assertEqual(
            self.actions.discover.install_gb_button.options["state"],
            "normal",
        )
        self.assertEqual(
            self.actions.discover.install_gb_button.options["text"],
            "Install latest",
        )
        self.assertIn("loading details", self.actions.discover.gb_files.value)

    def test_confirmed_empty_submission_disables_install(self):
        mod = GameBananaMod(
            id=123,
            name="Empty",
            author="",
            profile_url="https://gamebanana.com/mods/123",
            files=(),
        )

        self.actions._configure_gamebanana_files(
            mod,
            details_complete=True,
        )

        self.assertEqual(
            self.actions.discover.install_gb_button.options["state"],
            "disabled",
        )
        self.assertEqual(
            self.actions.discover.install_gb_button.options["text"],
            "No files",
        )

    def test_hydrated_files_enable_real_selector(self):
        mod = GameBananaMod(
            id=123,
            name="Ready",
            author="",
            profile_url="https://gamebanana.com/mods/123",
            files=(
                GameBananaFile(
                    id=991,
                    name="ready.zip",
                    url="https://gamebanana.com/dl/991",
                    downloads=10,
                ),
            ),
        )

        self.actions._configure_gamebanana_files(
            mod,
            details_complete=True,
        )

        self.assertEqual(
            self.actions.discover.install_gb_button.options["state"],
            "normal",
        )
        self.assertEqual(
            self.actions.discover.install_gb_button.options["text"],
            "Install",
        )
        self.assertTrue(self.actions.discover.gb_files.value.startswith("991 —"))


if __name__ == "__main__":
    unittest.main()
