from __future__ import annotations

import unittest

from umml_manager.mod_inspection import build_component_option_groups, inspect_mod
from umml_manager.models import ModRecord
from umml_manager.options import normalize_option_groups, select_source_paths


class ManagerModInspectionTests(unittest.TestCase):
    def test_detects_character_parts_and_content_from_source_mapping(self):
        record = ModRecord(
            id="creator.rudolf-glasses",
            name="Rudolf glasses",
            files={
                "aa/aaaaaaaa": "a" * 64,
                "bb/bbbbbbbb": "b" * 64,
            },
            source_payloads={
                "chara/chr1007/accessory/glasses_model": {
                    "aa/aaaaaaaa": "a" * 64,
                },
                "chara/chr1007/accessory/glasses_texture": {
                    "bb/bbbbbbbb": "b" * 64,
                },
            },
        )
        inspection = inspect_mod(record)
        self.assertEqual(inspection.character_ids, ("1007",))
        self.assertIn("glasses", inspection.parts)
        self.assertIn("model", inspection.content_types)
        self.assertIn("textures", inspection.content_types)
        self.assertEqual(inspection.target_count, 2)
        self.assertTrue(inspection.configurable_safe)

    def test_one_source_bundle_can_own_multiple_targets(self):
        record = ModRecord(
            id="creator.bundle",
            name="Bundle",
            files={
                "aa/aaaaaaaa": "a" * 64,
                "bb/bbbbbbbb": "b" * 64,
            },
            source_payloads={
                "chara/chr1001/body/bdy100101.bundle": {
                    "aa/aaaaaaaa": "a" * 64,
                    "bb/bbbbbbbb": "b" * 64,
                }
            },
        )
        inspection = inspect_mod(record)
        self.assertEqual(inspection.source_count, 1)
        self.assertEqual(inspection.target_count, 2)
        groups = normalize_option_groups(build_component_option_groups(inspection))
        self.assertEqual(len(groups["components"]["choices"]), 1)
        selected = select_source_paths(groups, {}, record.source_payloads)
        self.assertEqual(selected, {"chara/chr1001/body/bdy100101.bundle"})

    def test_unique_sources_become_optional_component_choices(self):
        record = ModRecord(
            id="creator.parts",
            name="Parts",
            files={"aa/aaaaaaaa": "a" * 64, "bb/bbbbbbbb": "b" * 64},
            source_payloads={
                "character/chr1001/head/glasses": {
                    "aa/aaaaaaaa": "a" * 64,
                },
                "character/chr1001/body/texture": {
                    "bb/bbbbbbbb": "b" * 64,
                },
            },
        )
        inspection = inspect_mod(record)
        groups = normalize_option_groups(build_component_option_groups(inspection))
        self.assertIn("components", groups)
        self.assertEqual(groups["components"]["type"], "multiple")
        self.assertEqual(len(groups["components"]["choices"]), 2)
        selected = select_source_paths(groups, {}, record.source_payloads)
        self.assertEqual(selected, set(record.source_payloads))

    def test_sources_sharing_target_become_mutually_exclusive_variants(self):
        record = ModRecord(
            id="creator.variants",
            name="Variants",
            files={"aa/aaaaaaaa": "a" * 64},
            source_payloads={
                "characters/special-week/body": {
                    "aa/aaaaaaaa": "a" * 64,
                },
                "characters/silence-suzuka/body": {
                    "aa/aaaaaaaa": "b" * 64,
                },
            },
        )
        inspection = inspect_mod(record)
        groups = normalize_option_groups(build_component_option_groups(inspection))
        variant_ids = [key for key in groups if key.startswith("detected-variant-")]
        self.assertEqual(len(variant_ids), 1)
        group = groups[variant_ids[0]]
        self.assertEqual(group["type"], "single")
        selected = select_source_paths(groups, {}, record.source_payloads)
        self.assertEqual(len(selected), 1)

    def test_incomplete_mapping_blocks_component_generation(self):
        record = ModRecord(
            id="creator.incomplete",
            name="Incomplete",
            files={"aa/aaaaaaaa": "a" * 64, "bb/bbbbbbbb": "b" * 64},
            source_files={"body.bundle": "aa/aaaaaaaa"},
        )
        inspection = inspect_mod(record)
        self.assertFalse(inspection.configurable_safe)
        with self.assertRaises(ValueError):
            build_component_option_groups(inspection)

    def test_opaque_only_mapping_reports_limited_detection(self):
        target = "aa/" + "a" * 64
        record = ModRecord(
            id="creator.opaque",
            name="Opaque",
            source_path="/definitely/not/a/package",
            files={target: "b" * 64},
        )
        inspection = inspect_mod(record)
        self.assertTrue(inspection.warnings)
        self.assertIn("opaque", " ".join(inspection.warnings).casefold())


if __name__ == "__main__":
    unittest.main()
