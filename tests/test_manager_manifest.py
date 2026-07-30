import json
import tempfile
import unittest
from pathlib import Path

from umml_manager.library import ManagerStore
from umml_manager.manifest import ManifestError, normalize_manifest_policy
from umml_manager.models import ModRecord, Profile
from umml_manager.options import normalize_option_groups
from umml_manager.package_builder import PackageDraft, create_package_workspace
from umml_manager.resolver import resolve_profile
from umml_manager.store import StoreError


class ManagerManifestPolicyTests(unittest.TestCase):
    def test_normalizes_targets_and_compatibility(self):
        policy = normalize_manifest_policy(
            {
                "id": "creator.costume",
                "regions": ["Global", "jp"],
                "targets": {
                    "characters": ["1001", "Special Week"],
                    "dresses": "100101",
                    "content": ["model", "textures"],
                },
                "tags": ["Costume", "Pink"],
                "dependencies": ["creator.base"],
                "incompatibilities": ["creator.old"],
                "load_after": ["creator.base"],
                "compatibility_notes": "Authored for the current model layout.",
            }
        )
        self.assertEqual(policy.regions, ["global", "japan"])
        self.assertEqual(policy.targets["characters"], ["1001", "Special Week"])
        self.assertEqual(policy.targets["dresses"], ["100101"])
        self.assertEqual(policy.tags, ["costume", "pink"])
        self.assertEqual(policy.load_after, ["creator.base"])

    def test_rejects_contradictory_compatibility(self):
        with self.assertRaisesRegex(ManifestError, "both required and incompatible"):
            normalize_manifest_policy(
                {
                    "id": "creator.mod",
                    "dependencies": ["creator.base"],
                    "incompatibilities": ["creator.base"],
                }
            )

    def test_rejects_self_reference(self):
        with self.assertRaisesRegex(ManifestError, "itself"):
            normalize_manifest_policy(
                {
                    "id": "creator.mod",
                    "load_after": ["creator.mod"],
                }
            )


class ManagerManifestImportTests(unittest.TestCase):
    def test_public_import_persists_targeting_and_order_policy(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "package"
            (package / "assets").mkdir(parents=True)
            (package / "assets" / "asset").write_bytes(b"UnityFS-test")
            (package / "umml-mod.json").write_text(
                json.dumps(
                    {
                        "id": "creator.character-mod",
                        "title": "Character mod",
                        "mod_version": "1",
                        "regions": ["global"],
                        "targets": {
                            "characters": ["Special Week"],
                            "content": ["model"],
                        },
                        "tags": ["Costume"],
                        "dependencies": ["creator.base"],
                        "load_after": ["creator.base"],
                        "compatibility_notes": "Needs the shared base package.",
                    }
                ),
                encoding="utf-8",
            )
            store = ManagerStore(root / "manager")
            record = store.import_folder(package)
            self.assertEqual(record.targets["characters"], ["Special Week"])
            self.assertEqual(record.targets["content"], ["model"])
            self.assertEqual(record.tags, ["costume"])
            self.assertEqual(record.dependencies, ["creator.base"])
            self.assertEqual(record.load_after, ["creator.base"])
            self.assertEqual(
                store.get_mod(record.id).compatibility_notes,
                "Needs the shared base package.",
            )

    def test_invalid_policy_leaves_no_immutable_record(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "package"
            (package / "assets").mkdir(parents=True)
            (package / "assets" / "asset").write_bytes(b"payload")
            (package / "umml-mod.json").write_text(
                json.dumps(
                    {
                        "id": "creator.invalid",
                        "title": "Invalid",
                        "mod_version": "1",
                        "dependencies": ["creator.invalid"],
                    }
                ),
                encoding="utf-8",
            )
            store = ManagerStore(root / "manager")
            with self.assertRaisesRegex(StoreError, "itself"):
                store.import_folder(package)
            self.assertEqual(store.list_mods(), [])
            self.assertFalse(store.paths.sources.exists())


class ManagerCharacterOptionTests(unittest.TestCase):
    def _record(self) -> ModRecord:
        groups = normalize_option_groups(
            {
                "character": {
                    "name": "Affected character",
                    "kind": "character",
                    "type": "single",
                    "default": "special-week",
                    "choices": {
                        "special-week": {
                            "name": "Special Week",
                            "target": "1001",
                            "include": ["characters/special-week/**"],
                        },
                        "silence-suzuka": {
                            "name": "Silence Suzuka",
                            "target": "1002",
                            "include": ["characters/silence-suzuka/**"],
                        },
                    },
                }
            }
        )
        sources = {
            "common/shared": "aa/aaaaaaaa",
            "characters/special-week/body": "bb/bbbbbbbb",
            "characters/silence-suzuka/body": "cc/cccccccc",
        }
        return ModRecord(
            id="creator.character-pack",
            name="Character pack",
            version="1",
            prepared_path="/prepared/character-pack",
            files={
                "aa/aaaaaaaa": "a" * 64,
                "bb/bbbbbbbb": "b" * 64,
            },
            source_files=sources,
            source_hashes={
                "common/shared": "a" * 64,
                "characters/special-week/body": "b" * 64,
                "characters/silence-suzuka/body": "c" * 64,
            },
            source_roots={
                "common/shared": "sources/common",
                "characters/special-week/body": "sources/special-week",
                "characters/silence-suzuka/body": "sources/silence-suzuka",
            },
            option_groups=groups,
            prepared_against="f" * 64,
        )

    def test_each_profile_resolves_a_different_character_without_source_mutation(self):
        record = self._record()
        original_mapping = dict(record.source_files)
        special = resolve_profile(
            Profile(
                "Special",
                [record.id],
                options={record.id: {"character": "special-week"}},
            ),
            [record],
            metadata_fingerprint="f" * 64,
        )
        suzuka = resolve_profile(
            Profile(
                "Suzuka",
                [record.id],
                options={record.id: {"character": "silence-suzuka"}},
            ),
            [record],
            metadata_fingerprint="f" * 64,
        )
        self.assertEqual(set(special.winners), {"aa/aaaaaaaa", "bb/bbbbbbbb"})
        self.assertEqual(set(suzuka.winners), {"aa/aaaaaaaa", "cc/cccccccc"})
        self.assertEqual(
            Path(special.winners["bb/bbbbbbbb"].source_path).parts[-2:],
            ("sources", "special-week"),
        )
        self.assertEqual(
            Path(suzuka.winners["cc/cccccccc"].source_path).parts[-2:],
            ("sources", "silence-suzuka"),
        )
        self.assertEqual(record.source_files, original_mapping)

    def test_load_order_constraints_block_wrong_order_only(self):
        base = ModRecord(
            id="creator.base",
            name="Base",
            prepared_path="/prepared/base",
            files={"aa/aaaaaaaa": "a" * 64},
        )
        addon = ModRecord(
            id="creator.addon",
            name="Addon",
            prepared_path="/prepared/addon",
            files={"bb/bbbbbbbb": "b" * 64},
            load_after=["creator.base"],
        )
        wrong = resolve_profile(Profile("Wrong", [addon.id, base.id]), [base, addon])
        right = resolve_profile(Profile("Right", [base.id, addon.id]), [base, addon])
        self.assertTrue(wrong.load_order_conflicts)
        self.assertIn("must load after creator.base", wrong.load_order_conflicts[0])
        self.assertFalse(right.load_order_conflicts)


class ManagerCharacterTemplateTests(unittest.TestCase):
    def test_builder_creates_character_selector_and_target_directories(self):
        with tempfile.TemporaryDirectory() as temp:
            store = ManagerStore(Path(temp) / "manager")
            workspace = create_package_workspace(
                store,
                PackageDraft(
                    "creator.characters",
                    "Characters",
                    "1",
                    target_characters=("Special Week", "Silence Suzuka"),
                    content_types=("model", "textures"),
                    character_template=True,
                ),
            )
            manifest = json.loads(
                (workspace / "umml-mod.json").read_text(encoding="utf-8")
            )
            group = manifest["option_groups"]["character"]
            self.assertEqual(group["kind"], "character")
            self.assertEqual(
                manifest["targets"]["characters"],
                ["Special Week", "Silence Suzuka"],
            )
            self.assertTrue(
                (workspace / "assets" / "characters" / "special-week").is_dir()
            )
            self.assertTrue(
                (workspace / "assets" / "characters" / "silence-suzuka").is_dir()
            )


if __name__ == "__main__":
    unittest.main()
