import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from umml_manager.backends import (
    HACHIMI_BACKEND,
    LEGACY_ASSET_BACKEND,
    backend_for_package,
)
from umml_manager.discovery import describe_archive, describe_mod_root
from umml_manager.installations import detect_installation_candidates
from umml_manager.models import PACKAGE_HACHIMI, PACKAGE_UMML_ASSETS
from umml_manager.providers import GameBananaClient
from umml_manager.providers.base import ProviderRegistry
from umml_manager.regions import normalize_region, region_from_game_name


class ArchitectureTests(unittest.TestCase):
    def test_setting_file_without_mod_content_is_not_a_mod_root(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "setting.json").write_text(
                json.dumps({"title": "Ordinary application settings"})
            )
            self.assertIsNone(describe_mod_root(root))

    def test_unrelated_archive_is_not_automatic_candidate(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "tax-documents.zip"
            with zipfile.ZipFile(archive, "w") as package:
                package.writestr("documents/receipt.txt", "not a mod")
            self.assertIsNone(describe_archive(archive))

    def test_mod_named_archive_without_markers_requires_manual_verification(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "mystery-uma-mod.zip"
            with zipfile.ZipFile(archive, "w") as package:
                package.writestr("readme.txt", "unknown layout")
            candidate = describe_archive(archive)
            self.assertIsNotNone(candidate)
            self.assertEqual(candidate.confidence, "low")

    def test_backend_registry_keeps_detection_separate_from_support(self):
        self.assertTrue(backend_for_package(PACKAGE_UMML_ASSETS).can_deploy)
        self.assertEqual(backend_for_package(PACKAGE_UMML_ASSETS), LEGACY_ASSET_BACKEND)
        self.assertFalse(backend_for_package(PACKAGE_HACHIMI).can_deploy)
        self.assertEqual(backend_for_package(PACKAGE_HACHIMI), HACHIMI_BACKEND)

    def test_provider_registry_rejects_duplicate_ids(self):
        registry = ProviderRegistry()
        first = GameBananaClient(opener=lambda *_args, **_kwargs: None)
        second = GameBananaClient(opener=lambda *_args, **_kwargs: None)
        registry.register(first)
        with self.assertRaises(ValueError):
            registry.register(second)

    def test_installation_candidates_do_not_prepare_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            game = root / "game"
            dat = root / "persistent" / "dat"
            meta = root / "persistent" / "meta"
            game.mkdir()
            dat.mkdir(parents=True)
            meta.write_bytes(b"encrypted")
            detected = [
                SimpleNamespace(
                    key="steam-global",
                    label="Steam Global",
                    region="Global",
                    game_dir=game,
                    dat_path=dat,
                    meta_path=meta,
                    detected=True,
                )
            ]
            with patch(
                "umml_manager.platform_bridge.detect_installations",
                return_value=detected,
            ):
                candidates = detect_installation_candidates()
            self.assertEqual(len(candidates), 1)
            self.assertEqual(candidates[0].region, "global")
            self.assertEqual(candidates[0].meta_source, meta.resolve())

    def test_region_normalization_is_shared(self):
        self.assertEqual(normalize_region("Steam Global"), "global")
        self.assertEqual(normalize_region("JP"), "japan")
        self.assertEqual(region_from_game_name("Umamusume Pretty Derby Global"), "global")
        self.assertEqual(region_from_game_name("Umamusume Pretty Derby Japan"), "japan")


if __name__ == "__main__":
    unittest.main()
