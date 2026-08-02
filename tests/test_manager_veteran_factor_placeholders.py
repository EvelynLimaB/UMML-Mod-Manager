import sqlite3
import tempfile
import unittest
from pathlib import Path

from umml_manager.veteran_analysis import factor_entries, factor_quality
from umml_manager.veteran_master_data import resolve_veteran_records


class VeteranFactorPlaceholderTests(unittest.TestCase):
    def test_extractor_zero_level_uses_installed_factor_rarity(self):
        with tempfile.TemporaryDirectory() as temp:
            master = Path(temp) / "master.mdb"
            connection = sqlite3.connect(master)
            try:
                connection.executescript(
                    """
                    CREATE TABLE text_data(
                        category INTEGER NOT NULL,
                        "index" INTEGER NOT NULL,
                        text TEXT NOT NULL
                    );
                    CREATE TABLE succession_factor(
                        factor_id INTEGER PRIMARY KEY,
                        rarity INTEGER,
                        factor_type INTEGER
                    );
                    """
                )
                connection.execute(
                    'INSERT INTO text_data(category, "index", text) VALUES (147, 501, ?)',
                    ("Speed Spark",),
                )
                connection.execute(
                    "INSERT INTO succession_factor(factor_id, rarity, factor_type) VALUES (501, 3, 1)"
                )
                connection.commit()
            finally:
                connection.close()

            source = [
                {
                    "trained_chara_id": 1,
                    "factor_info_array": [{"factor_id": 501, "level": 0}],
                }
            ]
            resolved = resolve_veteran_records(source, master).records[0]
            stored_factor = resolved["factor_info_array"][0]
            entries = factor_entries(resolved)
            quality = factor_quality(resolved)

            self.assertEqual(stored_factor["level"], 0)
            self.assertEqual(stored_factor["rarity"], 3)
            self.assertEqual(entries[0].name, "Speed Spark")
            self.assertEqual(entries[0].level, 3)
            self.assertEqual(entries[0].level_label, "3★")
            self.assertEqual(quality.total_stars, 3)
            self.assertEqual(quality.three_star_count, 1)

    def test_zero_without_master_rarity_is_unknown_not_zero_star(self):
        record = {"factor_info_array": [{"factor_id": 999, "level": 0}]}
        entry = factor_entries(record)[0]

        self.assertFalse(entry.level_known)
        self.assertEqual(entry.level_label, "—")
        self.assertIn("levels unavailable", factor_quality(record).summary)


if __name__ == "__main__":
    unittest.main()
