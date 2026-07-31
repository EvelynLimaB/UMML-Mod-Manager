import unittest

from umml_manager.models import ModRecord, Profile
from umml_manager.resolver import resolve_profile


class PlanningTests(unittest.TestCase):
    def test_stale_prepared_cache_blocks_resolution(self):
        mod = ModRecord(
            "mod",
            "Mod",
            prepared_path="/prepared",
            files={"aa/aafile": "1" * 64},
            prepared_against="a" * 64,
        )
        resolution = resolve_profile(
            Profile("Default", ["mod"]),
            [mod],
            metadata_fingerprint="b" * 64,
        )
        self.assertTrue(resolution.stale_prepared)
        self.assertFalse(resolution.winners)
        self.assertTrue(resolution.blocking_issues)

    def test_matching_prepared_metadata_is_accepted(self):
        fingerprint = "a" * 64
        mod = ModRecord(
            "mod",
            "Mod",
            prepared_path="/prepared",
            files={"aa/aafile": "1" * 64},
            prepared_against=fingerprint,
        )
        resolution = resolve_profile(
            Profile("Default", ["mod"]),
            [mod],
            metadata_fingerprint=fingerprint,
        )
        self.assertFalse(resolution.stale_prepared)
        self.assertIn("aa/aafile", resolution.winners)

    def test_profile_bound_to_another_installation_is_blocked(self):
        profile = Profile(
            "Global",
            installation_key="steam-global-primary",
        )
        resolution = resolve_profile(
            profile,
            [],
            target_installation_key="steam-global-secondary",
        )
        self.assertTrue(resolution.wrong_installation)
        self.assertTrue(resolution.blocking_issues)

    def test_unbound_profile_can_plan_for_current_installation(self):
        resolution = resolve_profile(
            Profile("Portable"),
            [],
            target_installation_key="steam-global-primary",
        )
        self.assertFalse(resolution.wrong_installation)


if __name__ == "__main__":
    unittest.main()
