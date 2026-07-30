import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from umml_manager.engine import ApplyEngine
from umml_manager.legacy_adapter import LegacyAssetAdapter
from umml_manager.library import ManagerStore
from umml_manager.models import Profile
from umml_manager.resolver import resolve_profile
from umml_manager.safety import hash_file


class ManagerConfigurableDeploymentTests(unittest.TestCase):
    def test_two_authored_variants_can_share_one_target_and_switch_profiles(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "package"
            assets = package / "assets"
            (assets / "common").mkdir(parents=True)
            (assets / "characters" / "special-week").mkdir(parents=True)
            (assets / "characters" / "silence-suzuka").mkdir(parents=True)

            common_source = assets / "common" / "shared"
            special_source = assets / "characters" / "special-week" / "body"
            suzuka_source = assets / "characters" / "silence-suzuka" / "body"
            common_bytes = b"shared package payload"
            special_bytes = b"special week payload"
            suzuka_bytes = b"silence suzuka payload"
            common_source.write_bytes(common_bytes)
            special_source.write_bytes(special_bytes)
            suzuka_source.write_bytes(suzuka_bytes)

            (package / "umml-mod.json").write_text(
                json.dumps(
                    {
                        "id": "creator.character-variants",
                        "title": "Character variants",
                        "mod_version": "1",
                        "targets": {
                            "characters": ["Special Week", "Silence Suzuka"],
                            "content": ["model"],
                        },
                        "option_groups": {
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
                        },
                    }
                ),
                encoding="utf-8",
            )

            common_hash_name = "aa" + "1" * 62
            character_hash_name = "bb" + "2" * 62
            common_target = f"aa/{common_hash_name}"
            character_target = f"bb/{character_hash_name}"
            meta = root / "meta.db"
            connection = sqlite3.connect(meta)
            try:
                connection.execute("CREATE TABLE a (n TEXT, h TEXT, e INTEGER)")
                connection.executemany(
                    "INSERT INTO a (n, h, e) VALUES (?, ?, ?)",
                    [
                        ("common/shared", common_hash_name, 0),
                        ("characters/special-week/body", character_hash_name, 0),
                        ("characters/silence-suzuka/body", character_hash_name, 0),
                    ],
                )
                connection.commit()
            finally:
                connection.close()

            store = ManagerStore(root / "manager")
            imported = store.import_folder(package)
            original_source_bytes = {
                path.relative_to(Path(imported.source_path)).as_posix(): path.read_bytes()
                for path in Path(imported.source_path).rglob("*")
                if path.is_file()
            }
            prepared = LegacyAssetAdapter(store, meta).prepare(imported)

            self.assertEqual(
                prepared.source_files["characters/special-week/body"],
                character_target,
            )
            self.assertEqual(
                prepared.source_files["characters/silence-suzuka/body"],
                character_target,
            )
            self.assertNotEqual(
                prepared.source_hashes["characters/special-week/body"],
                prepared.source_hashes["characters/silence-suzuka/body"],
            )
            self.assertNotEqual(
                prepared.source_roots["characters/special-week/body"],
                prepared.source_roots["characters/silence-suzuka/body"],
            )

            dat = root / "game" / "Persistent" / "dat"
            common_game = dat / common_target
            character_game = dat / character_target
            common_game.parent.mkdir(parents=True)
            character_game.parent.mkdir(parents=True)
            vanilla_common = b"vanilla shared"
            vanilla_character = b"vanilla character"
            common_game.write_bytes(vanilla_common)
            character_game.write_bytes(vanilla_character)
            fingerprint = hash_file(meta)
            engine = ApplyEngine(
                store,
                dat,
                game_dir=root / "game",
                process_check=lambda _game_dir: (),
            )

            special_profile = Profile(
                "Special",
                [prepared.id],
                options={prepared.id: {"character": "special-week"}},
            )
            special = resolve_profile(
                special_profile,
                [prepared],
                metadata_fingerprint=fingerprint,
            )
            self.assertFalse(special.blocking_issues)
            self.assertEqual(set(special.winners), {common_target, character_target})
            engine.apply(special)
            self.assertEqual(common_game.read_bytes(), common_bytes)
            self.assertEqual(character_game.read_bytes(), special_bytes)

            suzuka_profile = Profile(
                "Suzuka",
                [prepared.id],
                options={prepared.id: {"character": "silence-suzuka"}},
            )
            suzuka = resolve_profile(
                suzuka_profile,
                [prepared],
                metadata_fingerprint=fingerprint,
            )
            self.assertFalse(suzuka.blocking_issues)
            self.assertEqual(
                suzuka.known_mod_hashes[character_target],
                tuple(
                    sorted(
                        (
                            prepared.source_hashes["characters/special-week/body"],
                            prepared.source_hashes["characters/silence-suzuka/body"],
                        )
                    )
                ),
            )
            engine.apply(suzuka)
            self.assertEqual(common_game.read_bytes(), common_bytes)
            self.assertEqual(character_game.read_bytes(), suzuka_bytes)

            restored = resolve_profile(Profile("Vanilla", []), [prepared])
            engine.apply(restored)
            self.assertEqual(common_game.read_bytes(), vanilla_common)
            self.assertEqual(character_game.read_bytes(), vanilla_character)

            current_source_bytes = {
                path.relative_to(Path(imported.source_path)).as_posix(): path.read_bytes()
                for path in Path(imported.source_path).rglob("*")
                if path.is_file()
            }
            self.assertEqual(current_source_bytes, original_source_bytes)


if __name__ == "__main__":
    unittest.main()
