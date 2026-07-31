import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from umml_manager import engine as transaction_engine
from umml_manager import store as raw_store
from umml_manager.cli import (
    _metadata_fingerprint,
    _target_installation_key,
    build_parser,
)
from umml_manager.deployment import ApplyEngine, ApplyError
from umml_manager.library import (
    ManagerStore,
    StoreError,
    UnrecognizedModError,
    find_mod_root,
)
from umml_manager.models import ModRecord, Profile
from umml_manager.process import ProcessInspectionError, _windows_processes
from umml_manager.regions import region_from_game_name
from umml_manager.resolver import Resolution, resolve_profile
from umml_manager.safety import hash_file
from umml_manager.studio import LEGACY_TOOLS


class CleanupGuardTests(unittest.TestCase):
    def test_cli_legacy_baseline_migration_requires_explicit_flag(self):
        parser = build_parser()
        normal = parser.parse_args(
            ["apply", "Default", "--dat", "/game/Persistent/dat"]
        )
        migration = parser.parse_args(
            [
                "apply",
                "Default",
                "--dat",
                "/game/Persistent/dat",
                "--import-legacy-baselines",
            ]
        )

        self.assertFalse(normal.import_legacy_baselines)
        self.assertTrue(migration.import_legacy_baselines)

    def test_public_and_compatibility_boundaries_are_guarded(self):
        self.assertIs(transaction_engine.ApplyEngine, ApplyEngine)
        self.assertIs(raw_store.ManagerStore, ManagerStore)
        self.assertIs(raw_store.find_mod_root, find_mod_root)

    def test_deployment_rejects_every_planner_blocker_category(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dat = root / "dat"
            dat.mkdir()
            store = ManagerStore(root / "manager")
            for field, value in (
                ("stale_prepared", "stale"),
                ("wrong_installation", "wrong target"),
            ):
                resolution = Resolution(profile="Blocked")
                getattr(resolution, field).append(value)
                with self.subTest(field=field):
                    with self.assertRaises(ApplyError):
                        ApplyEngine(
                            store,
                            dat,
                            process_check=lambda _game: (),
                        ).apply(resolution)

    def test_process_inspection_failure_blocks_deployment(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dat = root / "dat"
            dat.mkdir()

            def failed_inspection(_game):
                raise RuntimeError("process backend unavailable")

            with self.assertRaisesRegex(ApplyError, "Could not verify"):
                ApplyEngine(
                    ManagerStore(root / "manager"),
                    dat,
                    process_check=failed_inspection,
                ).apply(Resolution(profile="Default"))

    def test_windows_process_backend_errors_are_not_game_closed(self):
        with patch(
            "umml_manager.process.subprocess.run",
            side_effect=OSError("tasklist unavailable"),
        ):
            with self.assertRaises(ProcessInspectionError):
                tuple(_windows_processes())

    def test_current_metadata_rejects_unfingerprinted_prepared_cache(self):
        fingerprint = "a" * 64
        mod = ModRecord(
            "legacy",
            "Legacy",
            prepared_path="/prepared",
            files={"aa/hash": "1" * 64},
        )
        resolution = resolve_profile(
            Profile("Default", [mod.id]),
            [mod],
            metadata_fingerprint=fingerprint,
        )
        self.assertTrue(resolution.stale_prepared)
        self.assertFalse(resolution.winners)

    def test_bound_profile_requires_verified_target_identity(self):
        resolution = resolve_profile(
            Profile("Bound", installation_key="steam-global"),
            [],
        )
        self.assertTrue(resolution.wrong_installation)
        self.assertIn("unverified", resolution.wrong_installation[0])

    def test_malformed_source_document_fails_as_store_error(self):
        with tempfile.TemporaryDirectory() as temp:
            store = ManagerStore(Path(temp) / "manager")
            store.paths.registry.parent.mkdir(parents=True, exist_ok=True)
            store.paths.registry.write_text(
                json.dumps(
                    {
                        "version": 2,
                        "mods": [
                            {
                                "id": "broken",
                                "name": "Broken",
                                "source": "not-an-object",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(StoreError, "Source specification"):
                store.list_mods()

    def test_unrecognized_package_uses_typed_exception(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(UnrecognizedModError):
                find_mod_root(Path(temp))

    def test_concurrent_imports_allocate_distinct_registry_records(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = ManagerStore(root / "manager")
            folders = []
            for version in ("1", "2"):
                folder = root / f"source-{version}"
                assets = folder / "assets"
                assets.mkdir(parents=True)
                (assets / f"asset-{version}").write_bytes(
                    f"payload-{version}".encode()
                )
                (folder / "umml-mod.json").write_text(
                    json.dumps(
                        {
                            "id": "same-mod",
                            "title": "Same Mod",
                            "mod_version": version,
                        }
                    ),
                    encoding="utf-8",
                )
                folders.append(folder)

            barrier = threading.Barrier(3)
            records = []
            errors = []
            result_lock = threading.Lock()

            def worker(folder):
                barrier.wait()
                try:
                    record = store.import_folder(folder)
                except Exception as exc:  # captured for the main test thread
                    with result_lock:
                        errors.append(exc)
                else:
                    with result_lock:
                        records.append(record)

            threads = [
                threading.Thread(target=worker, args=(folder,))
                for folder in folders
            ]
            for thread in threads:
                thread.start()
            barrier.wait()
            for thread in threads:
                thread.join(timeout=10)

            self.assertFalse(any(thread.is_alive() for thread in threads))
            self.assertFalse(errors)
            self.assertEqual(len(records), 2)
            self.assertEqual(len({record.id for record in records}), 2)
            self.assertEqual(len(store.list_mods()), 2)

    def test_full_legacy_workspace_is_marked_game_data_capable(self):
        full = next(tool for tool in LEGACY_TOOLS if tool.id == "full")
        self.assertTrue(full.mutating)

    def test_plain_gamebanana_game_name_maps_to_japan(self):
        self.assertEqual(
            region_from_game_name("Umamusume Pretty Derby"),
            "japan",
        )
        self.assertEqual(
            region_from_game_name("Umamusume Pretty Derby: Global"),
            "global",
        )

    def test_cli_apply_uses_and_verifies_saved_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = ManagerStore(root / "manager")
            meta = root / "meta.db"
            meta.write_bytes(b"metadata")
            store.save_settings(
                {
                    "meta_path": str(meta),
                    "metadata_fingerprint": hash_file(meta),
                }
            )
            self.assertEqual(
                _metadata_fingerprint("", store=store, required=True),
                hash_file(meta),
            )
            meta.write_bytes(b"changed")
            with self.assertRaisesRegex(StoreError, "changed"):
                _metadata_fingerprint("", store=store, required=True)

    def test_cli_apply_requires_metadata_when_settings_are_empty(self):
        with tempfile.TemporaryDirectory() as temp:
            store = ManagerStore(Path(temp) / "manager")
            with self.assertRaisesRegex(StoreError, "Apply requires"):
                _metadata_fingerprint("", store=store, required=True)

    def test_cli_does_not_implicitly_trust_unfingerprinted_saved_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = ManagerStore(root / "manager")
            meta = root / "meta.db"
            meta.write_bytes(b"metadata")
            store.save_settings({"meta_path": str(meta)})

            with self.assertRaisesRegex(StoreError, "no verified fingerprint"):
                _metadata_fingerprint("", store=store, required=True)
            self.assertEqual(
                _metadata_fingerprint("", store=store, required=False),
                "",
            )
            self.assertEqual(
                _metadata_fingerprint(
                    str(meta),
                    store=store,
                    required=True,
                ),
                hash_file(meta),
            )

    def test_saved_installation_key_is_scoped_to_saved_dat_path(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = ManagerStore(root / "manager")
            expected_dat = root / "game" / "dat"
            other_dat = root / "other" / "dat"
            expected_dat.mkdir(parents=True)
            other_dat.mkdir(parents=True)
            store.save_settings(
                {
                    "dat_path": str(expected_dat),
                    "installation_key": "steam-global",
                }
            )
            self.assertEqual(
                _target_installation_key(
                    "",
                    store=store,
                    dat_path=str(expected_dat),
                ),
                "steam-global",
            )
            self.assertEqual(
                _target_installation_key(
                    "",
                    store=store,
                    dat_path=str(other_dat),
                ),
                "",
            )

    def test_saved_installation_key_is_not_reused_without_saved_dat(self):
        with tempfile.TemporaryDirectory() as temp:
            store = ManagerStore(Path(temp) / "manager")
            store.save_settings({"installation_key": "steam-global"})
            self.assertEqual(
                _target_installation_key(
                    "",
                    store=store,
                    dat_path=str(Path(temp) / "game" / "dat"),
                ),
                "",
            )


if __name__ == "__main__":
    unittest.main()
