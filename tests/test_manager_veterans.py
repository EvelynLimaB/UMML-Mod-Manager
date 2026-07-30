import csv
import json
import tempfile
import unittest
from pathlib import Path

from umml_manager.veterans import (
    MODERN_PROJECT,
    VeteranDataError,
    VeteranStore,
    filter_rows,
    roster_summary,
    row_from_record,
)


class VeteranStoreTests(unittest.TestCase):
    def test_import_scrubs_private_fields_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "data.json"
            source.write_text(
                json.dumps(
                    [
                        {
                            "trained_chara_id": 91,
                            "chara_id": 1001,
                            "card_id": 100101,
                            "viewer_id": 123456,
                            "speed": 900,
                            "stamina": 700,
                            "power": 800,
                            "guts": 400,
                            "wiz": 600,
                            "factor_id_array": [1, 2, 3],
                            "skill_array": [10, 11],
                            "parent": {
                                "owner_viewer_id": 999,
                                "card_id": 100201,
                            },
                        }
                    ]
                ),
                encoding="utf-8",
            )
            store = VeteranStore(root / "manager" / "veterans")
            first = store.import_json(source)
            second = store.import_json(source)

            self.assertEqual(first.id, second.id)
            self.assertEqual(len(store.list_snapshots()), 1)
            records = store.load_records(first)
            self.assertEqual(len(records), 1)
            self.assertNotIn("viewer_id", records[0])
            self.assertNotIn("owner_viewer_id", records[0]["parent"])
            self.assertTrue(any("Removed 2" in warning for warning in first.warnings))
            self.assertTrue(any("Classic data.json" in warning for warning in first.warnings))

    def test_import_accepts_wrapped_record_arrays(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "wrapped.json"
            source.write_text(
                json.dumps(
                    {
                        "trained_chara_array": [
                            {"card_id": 10, "speed": 1}
                        ]
                    }
                ),
                encoding="utf-8",
            )
            store = VeteranStore(root / "veterans")
            snapshot = store.import_json(source)
            self.assertEqual(snapshot.record_count, 1)
            self.assertEqual(store.load_records(snapshot)[0]["card_id"], 10)

    def test_imports_werseter_trained_chara_output_and_scrubs_camel_case(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "trained_chara_data.json"
            source.write_text(
                json.dumps(
                    [
                        {
                            "trained_chara_id": 7001,
                            "owner_trained_chara_id": 7001,
                            "card_id": 100101,
                            "viewerId": 123,
                            "ownerViewerId": 456,
                            "speed": 1200,
                            "stamina": 800,
                            "power": 1100,
                            "guts": 500,
                            "wiz": 900,
                            "proper_distance_mile": 7,
                            "factor_info_array": [
                                {"factor_id": 1, "level": 3}
                            ],
                            "skill_array": [
                                {"skill_id": 10, "level": 1}
                            ],
                            "succession_history": {
                                "user_name": "Private trainer",
                                "circleName": "Private circle",
                            },
                        }
                    ]
                ),
                encoding="utf-8",
            )
            store = VeteranStore(root / "veterans")
            snapshot = store.import_json(source)
            records = store.load_records(snapshot)

            self.assertEqual(snapshot.provider, MODERN_PROJECT)
            self.assertEqual(snapshot.source_name, "trained_chara_data.json")
            self.assertNotIn("viewerId", records[0])
            self.assertNotIn("ownerViewerId", records[0])
            self.assertNotIn("user_name", records[0]["succession_history"])
            self.assertNotIn("circleName", records[0]["succession_history"])
            row = row_from_record(0, records[0])
            self.assertEqual(row.trained_chara_id, "7001")
            self.assertEqual(row.factor_count, 1)
            self.assertEqual(row.skill_count, 1)

    def test_non_roster_output_uses_known_werseter_sibling(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            support = root / "support_card_data.json"
            support.write_text(
                json.dumps([{"support_card_id": 30001, "level": 50}]),
                encoding="utf-8",
            )
            trained = root / "trained_chara_data.json"
            trained.write_text(
                json.dumps(
                    [
                        {
                            "trained_chara_id": 7,
                            "card_id": 100101,
                            "speed": 100,
                        }
                    ]
                ),
                encoding="utf-8",
            )
            store = VeteranStore(root / "veterans")
            snapshot = store.import_json(support)

            self.assertEqual(snapshot.source_name, "trained_chara_data.json")
            self.assertTrue(
                any("imported sibling" in warning for warning in snapshot.warnings)
            )

    def test_import_rejects_non_record_payloads(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "bad.json"
            source.write_text(
                json.dumps({"message": "not a roster"}),
                encoding="utf-8",
            )
            store = VeteranStore(root / "veterans")
            with self.assertRaises(VeteranDataError):
                store.import_json(source)

    def test_import_rejects_other_werseter_output_without_roster_sibling(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "support_card_data.json"
            source.write_text(
                json.dumps([{"support_card_id": 30001, "level": 50}]),
                encoding="utf-8",
            )
            store = VeteranStore(root / "veterans")
            with self.assertRaises(VeteranDataError):
                store.import_json(source)

    def test_row_filter_summary_and_csv_export(self):
        records = [
            {
                "chara_id": 1001,
                "card_id": 100101,
                "chara_name": "Special Week",
                "rank": "UG",
                "speed": 1200,
                "stamina": 800,
                "power": 1100,
                "guts": 500,
                "wiz": 900,
                "factor_id_array": [1, 2, 3],
                "skill_array": [10, 11],
            },
            {
                "chara_id": 1002,
                "card_id": 100201,
                "chara_name": "Silence Suzuka",
                "rank": "SS",
                "speed": 1100,
                "stamina": 600,
                "power": 900,
                "guts": 400,
                "wisdom": 800,
                "factor_id_array": [4],
                "skill_array": [12],
            },
        ]
        rows = [
            row_from_record(index, record)
            for index, record in enumerate(records)
        ]
        filtered = filter_rows(rows, "special 1200")
        self.assertEqual([row.name for row in filtered], ["Special Week"])
        summary = roster_summary(rows)
        self.assertEqual(summary["count"], 2)
        self.assertEqual(summary["unique_characters"], 2)
        self.assertEqual(summary["best_total"], 4500)
        self.assertEqual(summary["factors"], 4)
        self.assertEqual(summary["skills"], 3)

        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "roster.csv"
            VeteranStore(Path(temp) / "store").export_csv(records, target)
            with target.open("r", encoding="utf-8", newline="") as stream:
                csv_rows = list(csv.reader(stream))
            self.assertEqual(
                csv_rows[0][0:4],
                ["index", "name", "chara_id", "card_id"],
            )
            self.assertEqual(csv_rows[1][1], "Special Week")
            self.assertEqual(csv_rows[2][1], "Silence Suzuka")


if __name__ == "__main__":
    unittest.main()
