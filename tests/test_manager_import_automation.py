import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from umml_manager.cli import main as cli_main
from umml_manager.legacy_archive import import_loose_legacy_archive
from umml_manager.models import ModRecord, SourceSpec
from umml_manager.providers.gamebanana import GameBananaFile, GameBananaMod
from umml_manager.providers.gamebanana_previews import PreviewGameBananaClient
from umml_manager.store import ManagerStore, StoreError
from umml_manager.ui_auto_prepare_actions import should_prepare_automatically


class LooseArchiveTests(unittest.TestCase):
    def _archive(self, root: Path, entries: dict[str, bytes]) -> Path:
        archive = root / "loose.zip"
        with zipfile.ZipFile(archive, "w") as package:
            for name, payload in entries.items():
                package.writestr(name, payload)
        return archive

    def test_provider_confirmed_unityfs_archive_is_normalized(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = self._archive(
                root,
                {
                    "cafecathole/3d/chara/body.bundle": b"UnityFS\x00synthetic",
                    "cafecathole/readme.txt": b"legacy package",
                },
            )
            store = ManagerStore(root / "manager")
            record = import_loose_legacy_archive(
                store,
                archive,
                mod_id="gamebanana-646906",
                source=SourceSpec(
                    provider="gamebanana",
                    submission_id=646906,
                    file_id=1604920,
                ),
                metadata_overrides={
                    "title": "Synthetic legacy package",
                    "mod_version": "1604920",
                    "regions": ["global"],
                },
            )

            source = Path(record.source_path)
            self.assertEqual(record.package_type, "umml-assets")
            self.assertTrue(
                (source / "assets" / "3d" / "chara" / "body.bundle").is_file()
            )
            self.assertEqual(record.source.file_id, 1604920)

    def test_deeply_nested_legacy_asset_survives_normalization(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = self._archive(
                root,
                {
                    "wrapper/a/b/c/d/e/f/g/h/i/body": b"UnityFS\x00synthetic",
                    "wrapper/a/b/c/d/e/f/g/h/i/readme.txt": b"legacy package",
                },
            )
            store = ManagerStore(root / "manager")
            record = import_loose_legacy_archive(
                store,
                archive,
                mod_id="gamebanana-deep",
                source=SourceSpec(
                    provider="gamebanana",
                    submission_id=646906,
                    file_id=1604920,
                ),
                metadata_overrides={
                    "title": "Deep legacy package",
                    "mod_version": "1604920",
                    "regions": ["global"],
                },
            )

            source = Path(record.source_path)
            self.assertEqual(record.package_type, "umml-assets")
            self.assertTrue(
                (source / "assets" / "d" / "e" / "f" / "g" / "h" / "i" / "body").is_file()
            )

    def test_plain_document_archive_is_not_misclassified(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = self._archive(root, {"readme.txt": b"not a mod"})
            store = ManagerStore(root / "manager")
            with self.assertRaises(StoreError):
                import_loose_legacy_archive(
                    store,
                    archive,
                    mod_id="gamebanana-1",
                    source=SourceSpec(provider="gamebanana"),
                    metadata_overrides={"title": "Not a mod"},
                )

    def test_executable_content_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = self._archive(
                root,
                {
                    "asset.bundle": b"UnityFS\x00synthetic",
                    "installer.exe": b"MZ",
                },
            )
            store = ManagerStore(root / "manager")
            with self.assertRaises(StoreError):
                import_loose_legacy_archive(
                    store,
                    archive,
                    mod_id="gamebanana-2",
                    source=SourceSpec(provider="gamebanana"),
                    metadata_overrides={"title": "Unsafe package"},
                )

    def test_preview_provider_uses_loose_archive_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = self._archive(
                root,
                {"wrapper/body": b"UnityFS\x00synthetic"},
            )
            store = ManagerStore(root / "manager")

            class Client(PreviewGameBananaClient):
                def fetch(self, value):
                    return GameBananaMod(
                        id=646906,
                        name="Synthetic package",
                        author="Tester",
                        profile_url="https://gamebanana.com/mods/646906",
                        files=(
                            GameBananaFile(
                                id=1604920,
                                name="loose.zip",
                                url="https://gamebanana.com/dl/1604920",
                            ),
                        ),
                        game_name="Umamusume Pretty Derby (Global)",
                    )

                def download(self, mod, destination, **kwargs):
                    return archive, SourceSpec(
                        provider="gamebanana",
                        submission_id=mod.id,
                        file_id=1604920,
                        file_name=archive.name,
                    )

            record = Client(opener=lambda *_args, **_kwargs: None).import_mod(
                store,
                "646906",
            )
            self.assertEqual(record.id, "gamebanana-646906")
            self.assertTrue((Path(record.source_path) / "assets" / "body").is_file())


class AutomaticPreparationPolicyTests(unittest.TestCase):
    def test_compatible_import_with_metadata_is_prepared_automatically(self):
        with tempfile.TemporaryDirectory() as temp:
            meta = Path(temp) / "meta.db"
            meta.write_bytes(b"db")
            record = ModRecord("mod", "Mod", package_type="umml-assets")
            self.assertTrue(should_prepare_automatically(record, str(meta)))

    def test_prepared_or_unsupported_import_is_not_reprocessed(self):
        with tempfile.TemporaryDirectory() as temp:
            meta = Path(temp) / "meta.db"
            meta.write_bytes(b"db")
            prepared = ModRecord(
                "prepared",
                "Prepared",
                package_type="umml-assets",
                prepared_path=str(Path(temp) / "prepared"),
                files={"aa/hash": "0" * 64},
            )
            unsupported = ModRecord(
                "hachimi",
                "Hachimi",
                package_type="hachimi",
            )
            self.assertFalse(should_prepare_automatically(prepared, str(meta)))
            self.assertFalse(should_prepare_automatically(unsupported, str(meta)))


class CliProviderTests(unittest.TestCase):
    def test_offline_list_does_not_initialize_network_provider(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch(
                "umml_manager.cli.PreviewGameBananaClient",
                side_effect=AssertionError("network provider should stay lazy"),
            ):
                self.assertEqual(
                    cli_main(["--root", str(Path(temp) / "manager"), "list"]),
                    0,
                )


if __name__ == "__main__":
    unittest.main()
