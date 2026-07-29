import json
import tempfile
import unittest
from pathlib import Path

from umml_manager.library import ManagerStore
from umml_manager.models import ModRecord, Profile
from umml_manager.options import (
    OptionError,
    normalize_option_groups,
    normalize_profile_options,
    option_signature,
    option_summary,
    select_source_paths,
)
from umml_manager.resolver import resolve_profile


GROUPS = {
    "color": {
        "name": "Costume color",
        "type": "single",
        "default": "red",
        "choices": {
            "red": {
                "name": "Red",
                "include": ["variants/red/**"],
            },
            "blue": {
                "name": "Blue",
                "include": ["variants/blue/**"],
            },
        },
    },
    "extras": {
        "name": "Extras",
        "type": "multiple",
        "default": ["sparkles"],
        "choices": {
            "sparkles": {
                "name": "Sparkles",
                "include": ["extras/sparkles/**"],
            },
            "voice": {
                "name": "Voice",
                "include": ["extras/voice/**"],
            },
        },
    },
}


class ManagerOptionManifestTests(unittest.TestCase):
    def test_manifest_is_canonical_and_defaults_are_applied(self):
        groups = normalize_option_groups(GROUPS)
        selected = normalize_profile_options(groups, {})
        self.assertEqual(selected["color"], ["red"])
        self.assertEqual(selected["extras"], ["sparkles"])
        self.assertIn("Costume color: Red", option_summary(groups, selected))
        self.assertEqual(option_signature(groups, selected), option_signature(groups, {}))

    def test_profile_can_select_one_and_many(self):
        groups = normalize_option_groups(GROUPS)
        selected = normalize_profile_options(
            groups,
            {"color": "blue", "extras": ["sparkles", "voice"]},
        )
        self.assertEqual(selected["color"], ["blue"])
        self.assertEqual(selected["extras"], ["sparkles", "voice"])

    def test_unknown_choice_fails_closed(self):
        with self.assertRaisesRegex(OptionError, "unknown choice"):
            normalize_profile_options(GROUPS, {"color": "green"})

    def test_unsafe_patterns_are_rejected(self):
        invalid = {
            "color": {
                "type": "single",
                "choices": {"bad": {"include": ["../outside"]}},
            }
        }
        with self.assertRaisesRegex(OptionError, "unsafe"):
            normalize_option_groups(invalid)

    def test_ambiguous_patterns_are_rejected_against_real_sources(self):
        groups = normalize_option_groups(
            {
                "first": {
                    "type": "single",
                    "choices": {"a": {"include": ["shared/**"]}},
                },
                "second": {
                    "type": "single",
                    "choices": {"b": {"include": ["shared/file"]}},
                },
            }
        )
        with self.assertRaisesRegex(OptionError, "multiple option groups"):
            select_source_paths(groups, {}, ["shared/file"])

    def test_uncontrolled_files_remain_enabled(self):
        selected = select_source_paths(
            GROUPS,
            {"color": "blue", "extras": []},
            [
                "common/base",
                "variants/red/body",
                "variants/blue/body",
                "extras/sparkles/fx",
                "extras/voice/line",
            ],
        )
        self.assertEqual(selected, {"common/base", "variants/blue/body"})


class ManagerOptionImportTests(unittest.TestCase):
    def test_public_library_import_preserves_option_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "package"
            (package / "assets" / "variants" / "red").mkdir(parents=True)
            (package / "assets" / "variants" / "blue").mkdir(parents=True)
            (package / "assets" / "variants" / "red" / "body").write_bytes(b"red")
            (package / "assets" / "variants" / "blue" / "body").write_bytes(b"blue")
            (package / "umml-mod.json").write_text(
                json.dumps(
                    {
                        "id": "creator.configurable",
                        "title": "Configurable",
                        "mod_version": "1",
                        "option_groups": {"color": GROUPS["color"]},
                    }
                ),
                encoding="utf-8",
            )
            store = ManagerStore(root / "manager")
            record = store.import_folder(package)
            self.assertIn("color", record.option_groups)
            reloaded = store.get_mod(record.id)
            self.assertEqual(reloaded.option_groups, record.option_groups)


class ManagerOptionResolverTests(unittest.TestCase):
    def _record(self) -> ModRecord:
        return ModRecord(
            id="creator.configurable",
            name="Configurable",
            version="1",
            prepared_path="/prepared/configurable",
            files={
                "aa/aaaaaaaa": "a" * 64,
                "bb/bbbbbbbb": "b" * 64,
                "cc/cccccccc": "c" * 64,
                "dd/dddddddd": "d" * 64,
                "ee/eeeeeeee": "e" * 64,
            },
            source_files={
                "common/base": "aa/aaaaaaaa",
                "variants/red/body": "bb/bbbbbbbb",
                "variants/blue/body": "cc/cccccccc",
                "extras/sparkles/fx": "dd/dddddddd",
                "extras/voice/line": "ee/eeeeeeee",
            },
            option_groups=normalize_option_groups(GROUPS),
            prepared_against="f" * 64,
        )

    def test_profile_options_filter_prepared_claims(self):
        record = self._record()
        profile = Profile(
            "Default",
            [record.id],
            options={
                record.id: {
                    "color": "blue",
                    "extras": ["voice"],
                }
            },
        )
        result = resolve_profile(profile, [record], metadata_fingerprint="f" * 64)
        self.assertFalse(result.blocking_issues)
        self.assertEqual(
            set(result.winners),
            {"aa/aaaaaaaa", "cc/cccccccc", "ee/eeeeeeee"},
        )

    def test_invalid_profile_choice_is_a_visible_blocker(self):
        record = self._record()
        profile = Profile(
            "Default",
            [record.id],
            options={record.id: {"color": "green"}},
        )
        result = resolve_profile(profile, [record])
        self.assertTrue(result.invalid_options)
        self.assertFalse(result.winners)

    def test_old_prepared_record_requires_option_aware_reprepare(self):
        record = self._record()
        record.source_files = {}
        result = resolve_profile(Profile("Default", [record.id]), [record])
        self.assertIn("option-aware re-preparation", result.unprepared[0])
        self.assertFalse(result.winners)


if __name__ == "__main__":
    unittest.main()
