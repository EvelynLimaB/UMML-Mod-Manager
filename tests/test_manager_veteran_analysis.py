import unittest
from types import SimpleNamespace

from umml_manager.veteran_analysis import (
    aptitude_entries,
    comparison_rows,
    factor_entries,
    factor_quality,
    legacy_sort_key,
    shared_entry_ids,
    skill_entries,
)


class VeteranAnalysisTests(unittest.TestCase):
    def test_modern_entries_keep_names_levels_and_aptitudes(self):
        record = {
            "factor_info_array": [
                {"factor_id": 101, "factor_name": "Speed", "level": 3},
                {"factor_id": 202, "level": 2},
            ],
            "skill_array": [
                {"skill_id": 44, "skill_name": "Corner Adept", "level": 1},
            ],
            "proper_distance_mile": 7,
            "proper_running_style_nige": 8,
        }

        factors = factor_entries(record)
        skills = skill_entries(record)
        quality = factor_quality(record)

        self.assertEqual(factors[0].name, "Speed")
        self.assertEqual(factors[0].level_label, "3★")
        self.assertEqual(factors[1].name, "Factor 202")
        self.assertEqual(skills[0].name, "Corner Adept")
        self.assertEqual(quality.count, 2)
        self.assertEqual(quality.total_stars, 5)
        self.assertEqual(quality.three_star_count, 1)
        self.assertIn(("Distance Mile", "7"), aptitude_entries(record))
        self.assertIn(("Running Style Nige", "8"), aptitude_entries(record))

    def test_zero_placeholder_uses_resolved_master_rarity(self):
        record = {
            "factor_info_array": [
                {
                    "factor_id": 501,
                    "factor_name": "Speed Spark",
                    "level": 0,
                    "rarity": 3,
                },
                {"factor_id": 502, "level": 0},
            ]
        }

        factors = factor_entries(record)
        quality = factor_quality(record)

        self.assertEqual(factors[0].level, 3)
        self.assertTrue(factors[0].level_known)
        self.assertEqual(factors[0].level_label, "3★")
        self.assertEqual(factors[1].level, 0)
        self.assertFalse(factors[1].level_known)
        self.assertEqual(factors[1].level_label, "—")
        self.assertEqual(quality.known_levels, 1)
        self.assertEqual(quality.total_stars, 3)
        self.assertEqual(quality.three_star_count, 1)

    def test_classic_factor_ids_do_not_invent_star_levels(self):
        record = {"factor_id_array": [10, 11, 12], "skill_id_array": [3]}
        quality = factor_quality(record)

        self.assertEqual(quality.count, 3)
        self.assertEqual(quality.known_levels, 0)
        self.assertIn("levels unavailable", quality.summary)
        self.assertEqual(factor_entries(record)[0].level_label, "—")

    def test_legacy_sort_prefers_three_star_then_known_star_total(self):
        three_star = {"factor_info_array": [{"factor_id": 1, "level": 3}]}
        two_twos = {
            "factor_info_array": [
                {"factor_id": 1, "level": 2},
                {"factor_id": 2, "level": 2},
            ]
        }

        self.assertGreater(
            legacy_sort_key(three_star, 3000),
            legacy_sort_key(two_twos, 5000),
        )

    def test_shared_ids_and_comparison_rows_are_stable(self):
        left_record = {
            "factor_info_array": [
                {"factor_id": 10, "level": 3},
                {"factor_id": 20, "level": 1},
            ]
        }
        right_record = {
            "factor_info_array": [
                {"factor_id": 20, "level": 2},
                {"factor_id": 30, "level": 3},
            ]
        }
        self.assertEqual(
            shared_entry_ids(factor_entries(left_record), factor_entries(right_record)),
            ("20",),
        )

        left = SimpleNamespace(
            speed=100,
            stamina=200,
            power=300,
            guts=400,
            wisdom=500,
            total_stats=1500,
            factor_count=2,
            skill_count=4,
        )
        right = SimpleNamespace(
            speed=120,
            stamina=180,
            power=350,
            guts=400,
            wisdom=550,
            total_stats=1600,
            factor_count=3,
            skill_count=5,
        )
        rows = {
            name: (left_value, delta, right_value)
            for name, left_value, delta, right_value in comparison_rows(left, right)
        }
        self.assertEqual(rows["Speed"], (100, 20, 120))
        self.assertEqual(rows["Stamina"], (200, -20, 180))
        self.assertEqual(rows["Total stats"], (1500, 100, 1600))


if __name__ == "__main__":
    unittest.main()
