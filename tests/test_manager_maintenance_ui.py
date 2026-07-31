import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from umml_manager.deployment import LegacyBaselineMigrationRequired
from umml_manager.models import ModRecord, Profile
from umml_manager.resolver import Resolution
from umml_manager.ui_library_actions import LibraryActions
from umml_manager.ui_maintenance_actions import MaintenanceActions


class FakeVar:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class FakeButton:
    def __init__(self):
        self.options = {}

    def configure(self, **options):
        self.options.update(options)


class MaintenanceUiTests(unittest.TestCase):
    def test_enabled_profile_requires_verified_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            dat = Path(temp) / "dat"
            dat.mkdir()

            class Base:
                @staticmethod
                def _configure_button(widget, *, enabled, text=None):
                    options = {"state": "normal" if enabled else "disabled"}
                    if text is not None:
                        options["text"] = text
                    widget.configure(**options)

                def refresh_action_states(self):
                    self.library.apply_button.configure(
                        state="normal",
                        text="Apply profile",
                    )

                def profile(self):
                    return Profile("Default", ["mod"])

                def current_resolution(self):
                    return Resolution(profile="Default")

            class Harness(MaintenanceActions, Base):
                pass

            harness = Harness()
            harness._closing = False
            harness._busy = False
            harness._game_running = False
            harness.metadata_fingerprint = FakeVar("")
            harness.dat_path = FakeVar(str(dat))
            harness.library = SimpleNamespace(apply_button=FakeButton())

            harness.refresh_action_states()

            self.assertEqual(
                harness.library.apply_button.options["state"],
                "disabled",
            )
            self.assertEqual(
                harness.library.apply_button.options["text"],
                "Verify metadata to apply",
            )

    def test_prepared_cache_without_target_fingerprint_is_visible(self):
        class Harness(MaintenanceActions):
            pass

        harness = Harness()
        harness.metadata_fingerprint = FakeVar("")
        status = harness._mod_status(
            ModRecord(
                "mod",
                "Mod",
                prepared_path="/prepared",
                files={"aa/hash": "1" * 64},
            )
        )
        self.assertEqual(status, "prepared; target unverified")

    def test_legacy_original_prompt_retries_with_explicit_import(self):
        class Harness(LibraryActions):
            def _run_profile_apply(
                self,
                resolution,
                *,
                import_legacy_baselines=False,
            ):
                self.retry = (resolution, import_legacy_baselines)

        harness = Harness()
        harness.root = None
        harness.status = FakeVar()
        resolution = Resolution(profile="Default")
        required = LegacyBaselineMigrationRequired(
            ["aa/aafile", "bb/bbfile"],
            backup_root=Path("/game/Persistent/dat.backup"),
            importable=["aa/aafile", "bb/bbfile"],
            problems={},
        )

        with patch(
            "umml_manager.ui_library_actions.messagebox.askyesno",
            return_value=True,
        ) as ask:
            harness._profile_apply_failed(
                resolution,
                required,
                import_legacy_baselines=False,
            )

        self.assertEqual(harness.retry, (resolution, True))
        self.assertEqual(harness.status.get(), "Legacy originals found")
        prompt = ask.call_args.args[1]
        self.assertIn("dat.backup", prompt)
        self.assertNotIn("aa/aafile", prompt)

    def test_incomplete_legacy_backup_gives_short_restore_action(self):
        class Harness(LibraryActions):
            pass

        harness = Harness()
        harness.root = None
        harness.status = FakeVar()
        required = LegacyBaselineMigrationRequired(
            ["3G/opaque-hash"],
            backup_root=Path("/game/Persistent/dat.backup"),
            importable=[],
            problems={"3G/opaque-hash": "original backup is missing"},
        )

        with patch(
            "umml_manager.ui_library_actions.messagebox.showerror"
        ) as showerror:
            harness._profile_apply_failed(
                Resolution(profile="Default"),
                required,
                import_legacy_baselines=False,
            )

        self.assertEqual(harness.status.get(), "Original files required")
        message = showerror.call_args.args[1]
        self.assertIn("Verify integrity", message)
        self.assertIn("Nothing in the game was changed", message)
        self.assertNotIn("opaque-hash", message)


if __name__ == "__main__":
    unittest.main()
