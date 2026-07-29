import json
import tempfile
import unittest
from pathlib import Path

from umml_manager.library import ManagerStore
from umml_manager.package_builder import PackageDraft, create_package_workspace
from umml_manager.store import StoreError


class ManagerPackageBuilderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = ManagerStore(Path(self.temp.name) / "manager")

    def test_creates_unimported_basic_workspace(self):
        path = create_package_workspace(
            self.store,
            PackageDraft(
                mod_id="creator.example",
                title="Example",
                version="1.0.0",
                author="Creator",
                regions=("global",),
            ),
        )
        manifest = json.loads((path / "umml-mod.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["id"], "creator.example")
        self.assertEqual(manifest["regions"], ["global"])
        self.assertTrue((path / "assets").is_dir())
        self.assertEqual(self.store.list_mods(), [])

    def test_configurable_template_is_valid_and_editable(self):
        path = create_package_workspace(
            self.store,
            PackageDraft(
                mod_id="creator.variants",
                title="Variants",
                version="1",
                configurable_template=True,
            ),
        )
        manifest = json.loads((path / "umml-mod.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["option_groups"]["variant"]["default"], ["first"])
        self.assertTrue((path / "assets" / "variants" / "first").is_dir())
        self.assertTrue((path / "assets" / "variants" / "second").is_dir())

    def test_rejects_ids_that_would_be_silently_rewritten(self):
        with self.assertRaisesRegex(StoreError, "Package ID"):
            create_package_workspace(
                self.store,
                PackageDraft(
                    mod_id="Creator Example",
                    title="Example",
                    version="1",
                ),
            )

    def test_each_workspace_is_timestamped(self):
        first = create_package_workspace(
            self.store,
            PackageDraft("creator.example", "Example", "1"),
        )
        second = create_package_workspace(
            self.store,
            PackageDraft("creator.example", "Example", "1"),
        )
        self.assertNotEqual(first, second)
        self.assertTrue(first.is_dir())
        self.assertTrue(second.is_dir())


if __name__ == "__main__":
    unittest.main()
