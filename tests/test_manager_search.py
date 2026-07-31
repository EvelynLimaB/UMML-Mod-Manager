import unittest

from umml_manager.models import ModRecord
from umml_manager.options import normalize_option_groups
from umml_manager.ui_auto_prepare_actions import AutoPrepareActions


class ManagerLibrarySearchTests(unittest.TestCase):
    def test_search_corpus_includes_targets_tags_compatibility_and_choices(self):
        record = ModRecord(
            id="creator.costume-pack",
            name="Costume pack",
            author="Creator",
            description="Selectable outfits",
            regions=["global"],
            targets={
                "characters": ["Special Week"],
                "dresses": ["100101"],
            },
            tags=["pink", "costume"],
            dependencies=["creator.base"],
            incompatibilities=["creator.old-pack"],
            load_after=["creator.base"],
            compatibility_notes="Current model layout only",
            option_groups=normalize_option_groups(
                {
                    "character": {
                        "kind": "character",
                        "type": "single",
                        "default": "special-week",
                        "choices": {
                            "special-week": {
                                "name": "Special Week",
                                "target": "1001",
                                "description": "Main character variant",
                                "include": ["characters/special-week/**"],
                            }
                        },
                    }
                }
            ),
        )
        corpus = AutoPrepareActions._package_search_text(record)
        for expected in (
            "special week",
            "100101",
            "pink",
            "creator.base",
            "creator.old-pack",
            "current model layout",
            "character",
            "1001",
            "main character variant",
        ):
            self.assertIn(expected, corpus)


if __name__ == "__main__":
    unittest.main()
