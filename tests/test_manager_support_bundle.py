import json
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from umml_manager.store import ManagerStore
from umml_manager.support_bundle import (
    SupportBundleError,
    create_support_bundle,
    default_support_bundle_name,
)


class ManagerSupportBundleTests(unittest.TestCase):
    def test_bundle_is_small_inspectable_and_redacts_private_data(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = ManagerStore(root / "manager")
            private_game = root / "Users" / "alice" / "Games" / "Uma"
            private_dat = private_game / "Persistent" / "dat"
            private_meta = root / "Users" / "alice" / "meta.db"
            store.save_settings(
                {
                    "profile": "Testing",
                    "region": "global",
                    "theme": "dark",
                    "game_dir": str(private_game),
                    "dat_path": str(private_dat),
                    "meta_path": str(private_meta),
                    "installation_key": "steam-global-private-key",
                    "metadata_fingerprint": "f" * 64,
                    "api_token": "do-not-include-this-token",
                }
            )

            def diagnostics(_store):
                return {
                    "status": "check",
                    "ready": False,
                    "data_root": str(store.paths.root),
                    "checks": [
                        {
                            "name": "paths",
                            "passed": False,
                            "detail": (
                                f"game={private_game}; dat={private_dat}; "
                                f"meta={private_meta}"
                            ),
                        }
                    ],
                    "viewer_id": 123456789,
                    "user_name": "Trainer Alice",
                    "authorization": "Bearer secret-value",
                }

            destination = root / "report"
            result = create_support_bundle(
                store,
                destination,
                diagnostics_collector=diagnostics,
                now=datetime(2026, 7, 31, 3, 0, tzinfo=timezone.utc),
            )

            self.assertEqual(result.suffix, ".zip")
            self.assertTrue(result.is_file())
            with zipfile.ZipFile(result) as archive:
                self.assertEqual(
                    set(archive.namelist()),
                    {"README.txt", "support-report.json"},
                )
                report_text = archive.read("support-report.json").decode("utf-8")
                report = json.loads(report_text)
                readme = archive.read("README.txt").decode("utf-8")

            self.assertEqual(report["schema_version"], 1)
            self.assertEqual(report["product"], "Uma Mod Manager")
            self.assertEqual(report["configuration"]["profile"], "Testing")
            self.assertTrue(report["configuration"]["game_directory_configured"])
            self.assertTrue(
                report["configuration"]["verified_installation_identity"]
            )
            self.assertEqual(report["diagnostics"]["viewer_id"], "<redacted>")
            self.assertEqual(report["diagnostics"]["user_name"], "<redacted>")
            self.assertEqual(
                report["diagnostics"]["authorization"],
                "<redacted>",
            )
            for private_value in (
                str(private_game),
                str(private_dat),
                str(private_meta),
                str(store.paths.root),
                "do-not-include-this-token",
                "steam-global-private-key",
                "Trainer Alice",
                "secret-value",
            ):
                self.assertNotIn(private_value, report_text)
            self.assertIn("<GAME_DIR>", report_text)
            self.assertIn("Inspect support-report.json", readme)
            self.assertFalse(report["privacy"]["game_assets_included"])
            self.assertFalse(report["privacy"]["mod_payloads_included"])
            self.assertFalse(report["privacy"]["raw_settings_included"])

    def test_default_name_is_release_specific_and_stable(self):
        name = default_support_bundle_name(
            datetime(2026, 7, 31, 3, 4, 5, tzinfo=timezone.utc)
        )
        self.assertRegex(
            name,
            r"^uma-mod-manager-support-.+-20260731T030405Z\.zip$",
        )
        self.assertNotIn("~", name)

    def test_destination_cannot_be_a_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = ManagerStore(root / "manager")
            destination = root / "existing.zip"
            destination.mkdir()
            with self.assertRaises(SupportBundleError):
                create_support_bundle(
                    store,
                    destination,
                    diagnostics_collector=lambda _store: {
                        "status": "ready",
                        "ready": True,
                        "checks": [],
                    },
                )


if __name__ == "__main__":
    unittest.main()
