import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from umml_manager.cli import main
from umml_manager.deployment import ApplyEngine
from umml_manager.gui import main as gui_main
from umml_manager.models import ModRecord, Profile
from umml_manager.preview_images import PreviewImage
from umml_manager.providers.gamebanana import (
    GameBananaFile,
    GameBananaMod,
    GameBananaPage,
)
from umml_manager.safety import hash_file
from umml_manager.resolver import resolve_profile
from umml_manager.store import ManagerStore
from umml_manager.validation import (
    collect_manager_diagnostics,
    run_disposable_self_test,
    run_live_network_smoke,
    verify_profile_on_disposable_copy,
)


class ManagerValidationTests(unittest.TestCase):
    def test_disposable_self_test_covers_release_critical_paths(self):
        report = run_disposable_self_test()

        self.assertEqual(report["status"], "passed")
        self.assertTrue(report["temporary_only"])
        self.assertFalse(report["real_game_files_changed"])
        self.assertEqual(
            set(report["checks"]),
            {
                "folder-and-zip-import",
                "profile-conflict-winner",
                "apply-switch-and-restore",
                "external-change-protection",
                "legacy-baseline-migration",
                "interrupted-transaction-recovery",
            },
        )

    def test_cli_self_test_is_json_and_does_not_open_default_store(self):
        output = StringIO()
        with tempfile.TemporaryDirectory() as temp:
            fake_default = Path(temp) / "must-not-be-created"
            with patch(
                "umml_manager.cli.default_root",
                return_value=fake_default,
            ), redirect_stdout(output):
                status = main(["--root", str(fake_default), "self-test", "--json"])

            self.assertEqual(status, 0)
            self.assertFalse(fake_default.exists())

        report = json.loads(output.getvalue())
        self.assertEqual(report["status"], "passed")

    def test_cli_doctor_does_not_create_or_repair_manager_state(self):
        output = StringIO()
        with tempfile.TemporaryDirectory() as temp:
            missing = Path(temp) / "missing-manager-root"
            with patch(
                "umml_manager.platform_bridge.format_doctor_report",
                return_value=("platform unavailable", False),
            ), patch(
                "umml_manager.network.tls_diagnostics",
                return_value=("TLS ready", True),
            ), redirect_stdout(output):
                status = main(["--root", str(missing), "doctor", "--json"])

            self.assertEqual(status, 2)
            self.assertFalse(missing.exists())

            existing = Path(temp) / "existing-manager-root"
            existing.mkdir()
            settings = existing / "settings.json"
            settings.write_bytes(b"{not-json")
            before = settings.read_bytes()
            with patch(
                "umml_manager.platform_bridge.format_doctor_report",
                return_value=("platform unavailable", False),
            ), patch(
                "umml_manager.network.tls_diagnostics",
                return_value=("TLS ready", True),
            ), redirect_stdout(StringIO()):
                status = main(
                    ["--root", str(existing), "doctor", "--json"]
                )

            self.assertEqual(status, 2)
            self.assertEqual(settings.read_bytes(), before)
            self.assertEqual(
                list(existing.glob("settings.json.corrupt-*")),
                [],
            )

    def test_gui_smoke_mode_routes_to_disposable_renderer(self):
        output = StringIO()
        with patch(
            "umml_manager.gui.run_gui_smoke_test"
        ) as smoke, redirect_stdout(output):
            status = gui_main(["--smoke-test"])

        self.assertEqual(status, 0)
        smoke.assert_called_once_with()
        self.assertIn("no real game files were changed", output.getvalue())

    def test_real_profile_payload_is_applied_only_to_disposable_copy(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dat = root / "game" / "Persistent" / "dat"
            target = dat / "aa" / "shared"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"vanilla")
            meta = root / "meta.db"
            meta.write_bytes(b"metadata")
            fingerprint = hash_file(meta)

            records = []
            for mod_id, payload in (("first", b"first"), ("second", b"second")):
                prepared = root / f"prepared-{mod_id}"
                source = prepared / "aa" / "shared"
                source.parent.mkdir(parents=True)
                source.write_bytes(payload)
                records.append(
                    ModRecord(
                        mod_id,
                        mod_id.title(),
                        version="1",
                        regions=["global"],
                        prepared_path=str(prepared),
                        files={"aa/shared": hash_file(source)},
                        prepared_against=fingerprint,
                    )
                )

            store = ManagerStore(root / "manager")
            for record in records:
                store.save_mod(record)
            profile = Profile(
                "Conflict",
                ["first", "second"],
                region="global",
                installation_key="steam-global",
            )
            store.save_profile(profile)
            store.save_settings(
                {
                    "dat_path": str(dat),
                    "meta_path": str(meta),
                    "game_dir": str(root / "game"),
                    "region": "global",
                    "installation_key": "steam-global",
                    "metadata_fingerprint": fingerprint,
                }
            )

            report = verify_profile_on_disposable_copy(
                store,
                profile,
                dat_path=dat,
                game_dir=root / "game",
                target_region="global",
                target_installation_key="steam-global",
                metadata_fingerprint=fingerprint,
                process_check=lambda _game: (),
            )

            self.assertEqual(report["status"], "passed")
            self.assertEqual(report["files"], 1)
            self.assertEqual(report["conflicts"], 1)
            self.assertEqual(target.read_bytes(), b"vanilla")
            self.assertFalse(store.paths.state.exists())
            self.assertFalse(store.paths.baseline.exists())

    def test_disposable_profile_verification_exercises_legacy_takeover(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dat = root / "Persistent" / "dat"
            target = dat / "aa" / "legacy"
            backup = root / "Persistent" / "dat.backup" / "aa" / "legacy"
            target.parent.mkdir(parents=True)
            backup.parent.mkdir(parents=True)
            target.write_bytes(b"legacy-mod")
            backup.write_bytes(b"vanilla")
            meta = root / "meta.db"
            meta.write_bytes(b"metadata")
            fingerprint = hash_file(meta)

            prepared = root / "prepared"
            source = prepared / "aa" / "legacy"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"legacy-mod")
            record = ModRecord(
                "legacy",
                "Legacy",
                version="1",
                regions=["global"],
                prepared_path=str(prepared),
                files={"aa/legacy": hash_file(source)},
                prepared_against=fingerprint,
            )
            profile = Profile(
                "Legacy",
                ["legacy"],
                region="global",
                installation_key="steam-global",
            )
            store = ManagerStore(root / "manager")
            store.save_mod(record)
            store.save_profile(profile)

            report = verify_profile_on_disposable_copy(
                store,
                profile,
                dat_path=dat,
                game_dir=None,
                target_region="global",
                target_installation_key="steam-global",
                metadata_fingerprint=fingerprint,
                process_check=lambda _game: (),
            )

            self.assertEqual(report["imported_legacy_baselines"], 1)
            self.assertEqual(target.read_bytes(), b"legacy-mod")
            self.assertEqual(backup.read_bytes(), b"vanilla")
            self.assertFalse(store.paths.state.exists())
            self.assertFalse(store.paths.baseline.exists())

    def test_active_profile_and_manager_baseline_are_copied_not_changed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dat = root / "game" / "Persistent" / "dat"
            target = dat / "aa" / "active"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"vanilla")
            meta = root / "meta.db"
            meta.write_bytes(b"metadata")
            fingerprint = hash_file(meta)

            prepared = root / "prepared"
            source = prepared / "aa" / "active"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"managed")
            record = ModRecord(
                "active",
                "Active",
                version="1",
                regions=["global"],
                prepared_path=str(prepared),
                files={"aa/active": hash_file(source)},
                prepared_against=fingerprint,
            )
            profile = Profile(
                "Active",
                ["active"],
                region="global",
                installation_key="steam-global",
            )
            store = ManagerStore(root / "manager")
            store.save_mod(record)
            store.save_profile(profile)
            store.save_settings(
                {
                    "dat_path": str(dat),
                    "meta_path": str(meta),
                    "game_dir": str(root / "game"),
                    "region": "global",
                    "installation_key": "steam-global",
                    "metadata_fingerprint": fingerprint,
                }
            )
            resolution = resolve_profile(
                profile,
                [record],
                target_region="global",
                target_installation_key="steam-global",
                metadata_fingerprint=fingerprint,
            )
            ApplyEngine(
                store,
                dat,
                game_dir=root / "game",
                process_check=lambda _game: (),
            ).apply(resolution)

            state_before = store.paths.state.read_bytes()
            baseline_before = {
                path.relative_to(store.paths.baseline): path.read_bytes()
                for path in store.paths.baseline.rglob("*")
                if path.is_file()
            }
            report = verify_profile_on_disposable_copy(
                store,
                profile,
                dat_path=dat,
                game_dir=root / "game",
                target_region="global",
                target_installation_key="steam-global",
                metadata_fingerprint=fingerprint,
                process_check=lambda _game: (),
            )

            self.assertEqual(report["status"], "passed")
            self.assertEqual(report["unchanged"], 1)
            self.assertEqual(target.read_bytes(), b"managed")
            self.assertEqual(store.paths.state.read_bytes(), state_before)
            self.assertEqual(
                {
                    path.relative_to(store.paths.baseline): path.read_bytes()
                    for path in store.paths.baseline.rglob("*")
                    if path.is_file()
                },
                baseline_before,
            )

    def test_manager_doctor_requires_verified_closed_target(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            game = root / "game"
            dat = game / "Persistent" / "dat"
            meta = root / "meta.db"
            dat.mkdir(parents=True)
            meta.write_bytes(b"metadata")
            store = ManagerStore(root / "manager")
            store.save_settings(
                {
                    "dat_path": str(dat),
                    "game_dir": str(game),
                    "meta_path": str(meta),
                    "installation_key": "steam-global",
                    "metadata_fingerprint": hash_file(meta),
                }
            )

            with patch(
                "umml_manager.platform_bridge.format_doctor_report",
                return_value=("platform ready", True),
            ), patch(
                "umml_manager.network.tls_diagnostics",
                return_value=("TLS ready", True),
            ):
                report = collect_manager_diagnostics(
                    store,
                    process_check=lambda _game: (),
                )

            self.assertTrue(report["ready"])
            self.assertEqual(report["status"], "ready")

            store.save_settings({"metadata_fingerprint": "0" * 64})
            with patch(
                "umml_manager.platform_bridge.format_doctor_report",
                return_value=("platform ready", True),
            ), patch(
                "umml_manager.network.tls_diagnostics",
                return_value=("TLS ready", True),
            ):
                report = collect_manager_diagnostics(
                    store,
                    process_check=lambda _game: (),
                )
            self.assertFalse(report["ready"])
            failed = {
                check["name"]
                for check in report["checks"]
                if not check["passed"]
            }
            self.assertEqual(failed, {"metadata-integrity"})

    def test_live_network_smoke_requires_details_files_and_preview(self):
        summary = GameBananaMod(
            123,
            "Summary",
            "Author",
            "https://gamebanana.com/mods/123",
            (),
        )
        detailed = GameBananaMod(
            123,
            "Detailed",
            "Author",
            "https://gamebanana.com/mods/123",
            (
                GameBananaFile(
                    456,
                    "mod.zip",
                    "https://gamebanana.com/dl/456",
                ),
            ),
            image_url="https://images.gamebanana.com/example.png",
        )

        class Client:
            @staticmethod
            def browse(**_kwargs):
                return GameBananaPage((summary,), 1, 1, False)

            @staticmethod
            def fetch(value):
                self.assertEqual(value, "123")
                return detailed

        class Loader:
            @staticmethod
            def load(url):
                self.assertEqual(url, detailed.image_url)
                return PreviewImage(
                    Image.new("RGBA", (320, 180)),
                    url,
                    "image/png",
                    2048,
                )

        report = run_live_network_smoke(
            client=Client(),
            preview_loader=Loader(),
        )

        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["downloadable_files"], 1)
        self.assertEqual(report["preview_size"], [320, 180])
        self.assertFalse(report["download_executed"])


if __name__ == "__main__":
    unittest.main()
