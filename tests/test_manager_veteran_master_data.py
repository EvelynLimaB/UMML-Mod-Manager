import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from umml_manager.veteran_analysis import factor_entries, skill_entries
from umml_manager.veteran_master_data import (
    VeteranMasterDataError,
    _open_read_only,
    discover_master_mdb,
    resolve_veteran_records,
)
from umml_manager.veterans import row_from_record


class _Value:
    def __init__(self, value: str):
        self.value = value

    def get(self) -> str:
        return self.value


class _Store:
    def __init__(self, settings=None):
        self.settings = dict(settings or {})

    def load_settings(self):
        return dict(self.settings)


class VeteranMasterDataTests(unittest.TestCase):
    def _create_master(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path)
        try:
            connection.executescript(
                """
                CREATE TABLE text_data (
                    category INTEGER NOT NULL,
                    "index" INTEGER NOT NULL,
                    text TEXT NOT NULL
                );
                CREATE TABLE card_data (
                    id INTEGER PRIMARY KEY,
                    chara_id INTEGER NOT NULL
                );
                CREATE TABLE succession_factor (
                    factor_id INTEGER PRIMARY KEY,
                    factor_group_id INTEGER,
                    rarity INTEGER,
                    factor_type INTEGER,
                    effect_group_id INTEGER,
                    target_type INTEGER,
                    target_value INTEGER
                );
                CREATE TABLE skill_data (
                    id INTEGER PRIMARY KEY,
                    rarity INTEGER,
                    group_id INTEGER,
                    icon_id INTEGER,
                    grade_value INTEGER,
                    skill_category INTEGER
                );
                """
            )
            connection.executemany(
                'INSERT INTO text_data(category, "index", text) VALUES (?, ?, ?)',
                (
                    (4, 100101, "Special Dreamer Special Week"),
                    (5, 100101, "Special Dreamer"),
                    (6, 1001, "Special Week"),
                    (47, 10071, "Corner Adept"),
                    (48, 10071, "Slightly increase velocity on a corner."),
                    (147, 101, "Speed Spark"),
                    (172, 101, "Increases inherited Speed."),
                ),
            )
            connection.execute(
                "INSERT INTO card_data(id, chara_id) VALUES (?, ?)",
                (100101, 1001),
            )
            connection.execute(
                """
                INSERT INTO succession_factor(
                    factor_id, factor_group_id, rarity, factor_type,
                    effect_group_id, target_type, target_value
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (101, 10, 3, 1, 20, 1, 21),
            )
            connection.execute(
                """
                INSERT INTO skill_data(
                    id, rarity, group_id, icon_id, grade_value, skill_category
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (10071, 1, 701, 10071, 120, 1),
            )
            connection.commit()
        finally:
            connection.close()

    def test_discovers_master_next_to_saved_dat_path(self):
        with tempfile.TemporaryDirectory() as temp:
            persistent = Path(temp) / "Persistent"
            dat = persistent / "dat"
            dat.mkdir(parents=True)
            master = persistent / "master" / "master.mdb"
            self._create_master(master)
            app = SimpleNamespace(
                dat_path=_Value(str(dat)),
                meta_path=_Value(""),
                game_dir=_Value(""),
                store=_Store(),
            )

            self.assertEqual(discover_master_mdb(app), master.resolve())

    def test_explicit_master_setting_takes_priority(self):
        with tempfile.TemporaryDirectory() as temp:
            master = Path(temp) / "custom" / "master.mdb"
            self._create_master(master)
            app = SimpleNamespace(
                dat_path=_Value(""),
                meta_path=_Value(""),
                game_dir=_Value(""),
                store=_Store({"master_path": str(master)}),
            )

            self.assertEqual(discover_master_mdb(app), master.resolve())

    def test_read_only_connection_observes_committed_live_wal_state(self):
        with tempfile.TemporaryDirectory() as temp:
            database = Path(temp) / "live.mdb"
            writer = sqlite3.connect(database)
            try:
                writer.execute("PRAGMA journal_mode=WAL")
                writer.execute("PRAGMA wal_autocheckpoint=0")
                writer.execute("CREATE TABLE values_now(value TEXT)")
                writer.commit()
                writer.execute("INSERT INTO values_now(value) VALUES ('current')")
                writer.commit()

                reader = _open_read_only(database)
                try:
                    row = reader.execute("SELECT value FROM values_now").fetchone()
                    self.assertEqual(row[0], "current")
                    with self.assertRaises(sqlite3.OperationalError):
                        reader.execute("INSERT INTO values_now(value) VALUES ('nope')")
                finally:
                    reader.close()
            finally:
                writer.close()

    def test_resolves_card_factor_and_skill_without_mutating_source(self):
        with tempfile.TemporaryDirectory() as temp:
            master = Path(temp) / "master.mdb"
            self._create_master(master)
            source = [
                {
                    "trained_chara_id": 55,
                    "card_id": 100101,
                    "speed": 1200,
                    "stamina": 800,
                    "power": 1100,
                    "guts": 500,
                    "wiz": 900,
                    "factor_id_array": [101],
                    "skill_id_array": [10071],
                }
            ]

            result = resolve_veteran_records(source, master)
            record = result.records[0]
            row = row_from_record(0, record)

            self.assertEqual(source[0]["factor_id_array"], [101])
            self.assertNotIn("name", source[0])
            self.assertEqual(row.name, "Special Dreamer Special Week")
            self.assertEqual(row.chara_id, "1001")
            self.assertEqual(record["costume_name"], "Special Dreamer")

            factors = factor_entries(record)
            self.assertEqual(len(factors), 1)
            self.assertEqual(factors[0].name, "Speed Spark")
            self.assertEqual(factors[0].level, 3)
            self.assertTrue(factors[0].level_known)
            self.assertEqual(
                record["factor_info_array"][0]["factor_type_name"],
                "Blue stat",
            )
            self.assertEqual(
                record["factor_info_array"][0]["factor_description"],
                "Increases inherited Speed.",
            )

            skills = skill_entries(record)
            self.assertEqual(len(skills), 1)
            self.assertEqual(skills[0].name, "Corner Adept")
            self.assertEqual(record["skill_array"][0]["icon_id"], 10071)
            self.assertEqual(
                record["skill_array"][0]["skill_description"],
                "Slightly increase velocity on a corner.",
            )
            self.assertEqual(result.card_records, 1)
            self.assertEqual(result.factor_entries, 1)
            self.assertEqual(result.skill_entries, 1)
            self.assertIn("resolved read-only", result.summary)

    def test_preserves_extractor_names_and_levels(self):
        with tempfile.TemporaryDirectory() as temp:
            master = Path(temp) / "master.mdb"
            self._create_master(master)
            source = [
                {
                    "card_id": 100101,
                    "name": "Extractor display name",
                    "factor_info_array": [
                        {"factor_id": 101, "factor_name": "Custom Spark", "level": 2}
                    ],
                    "skill_array": [
                        {"skill_id": 10071, "skill_name": "Custom Skill"}
                    ],
                }
            ]

            record = resolve_veteran_records(source, master).records[0]
            self.assertEqual(record["name"], "Extractor display name")
            self.assertEqual(
                record["factor_info_array"][0]["factor_name"],
                "Custom Spark",
            )
            self.assertEqual(record["factor_info_array"][0]["level"], 2)
            self.assertEqual(record["skill_array"][0]["skill_name"], "Custom Skill")

    def test_missing_master_is_a_safe_fallback(self):
        source = [{"card_id": 100101, "factor_id_array": [101]}]
        result = resolve_veteran_records(source, None)

        self.assertFalse(result.available)
        self.assertEqual(result.records, source)
        self.assertIsNot(result.records[0], source[0])
        self.assertIn("not found", result.summary)

    def test_incompatible_database_fails_with_actionable_error(self):
        with tempfile.TemporaryDirectory() as temp:
            master = Path(temp) / "master.mdb"
            connection = sqlite3.connect(master)
            connection.execute("CREATE TABLE unrelated(id INTEGER)")
            connection.commit()
            connection.close()

            with self.assertRaisesRegex(VeteranMasterDataError, "text_data"):
                resolve_veteran_records([{"card_id": 1}], master)


if __name__ == "__main__":
    unittest.main()
