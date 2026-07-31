import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from umml_manager.engine import (
    ApplyEngine,
    ApplyError,
    LegacyBaselineMigrationRequired,
)
from umml_manager.models import ModRecord, Profile
from umml_manager.resolver import resolve_profile
from umml_manager.safety import atomic_write_json, hash_file
from umml_manager.store import ManagerStore, StoreError


class RecoveryIntegrityTests(unittest.TestCase):
    def _pending_recovery(
        self,
        root: Path,
        *,
        process_check,
    ) -> tuple[ApplyEngine, Path, Path]:
        store = ManagerStore(root / "manager")
        dat = root / "dat"
        target = dat / "aa" / "aafile"
        target.parent.mkdir(parents=True)
        target.write_text("currently-modded")
        engine = ApplyEngine(store, dat, process_check=process_check)
        transaction = (
            store.paths.transactions
            / f"apply-{engine.target_id}-pending"
        )
        snapshot = transaction / "snapshots" / "aa" / "aafile"
        snapshot.parent.mkdir(parents=True)
        snapshot.write_text("snapshot-before-apply")
        atomic_write_json(
            transaction / "journal.json",
            {
                "version": 2,
                "transaction_id": transaction.name,
                "target_id": engine.target_id,
                "phase": "applying",
                "manifest": {
                    "aa/aafile": {
                        "existed": True,
                        "sha256": hash_file(snapshot),
                    }
                },
            },
        )
        return engine, target, transaction

    def test_running_game_blocks_recovery_before_snapshot_restore(self):
        with tempfile.TemporaryDirectory() as temp:
            checks = 0

            def game_starts_before_recovery(_game):
                nonlocal checks
                checks += 1
                if checks == 1:
                    return ()
                return (SimpleNamespace(name="umamusume.exe"),)

            engine, target, transaction = self._pending_recovery(
                Path(temp),
                process_check=game_starts_before_recovery,
            )

            with self.assertRaisesRegex(ApplyError, "Game is running"):
                engine.apply(resolve_profile(Profile("Off", []), []))

            self.assertEqual(target.read_text(), "currently-modded")
            self.assertTrue(transaction.is_dir())

    def test_process_check_failure_blocks_recovery_before_snapshot_restore(self):
        with tempfile.TemporaryDirectory() as temp:
            checks = 0

            def failed(_game):
                nonlocal checks
                checks += 1
                if checks == 1:
                    return ()
                raise OSError("inspection unavailable")

            engine, target, transaction = self._pending_recovery(
                Path(temp),
                process_check=failed,
            )

            with self.assertRaisesRegex(ApplyError, "writes were blocked"):
                engine.apply(resolve_profile(Profile("Off", []), []))

            self.assertEqual(target.read_text(), "currently-modded")
            self.assertTrue(transaction.is_dir())

    def test_future_registry_schema_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            store = ManagerStore(Path(temp) / "manager")
            atomic_write_json(
                store.paths.registry,
                {"version": 999, "mods": []},
            )
            with self.assertRaises(StoreError):
                store.list_mods()

    def test_future_profile_schema_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            store = ManagerStore(Path(temp) / "manager")
            atomic_write_json(
                store.paths.profiles,
                {"version": 999, "profiles": []},
            )
            with self.assertRaises(StoreError):
                store.list_profiles()

    def test_corrupt_settings_are_quarantined_before_defaults(self):
        with tempfile.TemporaryDirectory() as temp:
            store = ManagerStore(Path(temp) / "manager")
            store.paths.settings.write_text("{broken", encoding="utf-8")
            settings = store.load_settings()
            self.assertEqual(settings["version"], 1)
            self.assertIn("Original preserved", store.settings_warning)
            preserved = list(
                store.paths.root.glob("settings.json.corrupt-*")
            )
            self.assertEqual(len(preserved), 1)
            self.assertEqual(
                preserved[0].read_text(encoding="utf-8"),
                "{broken",
            )

    def test_source_change_during_copy_aborts_import(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            mod = root / "mod"
            (mod / "assets").mkdir(parents=True)
            (mod / "assets" / "file").write_text("original")
            (mod / "setting.json").write_text(
                '{"title":"Moving Target","mod_version":"1"}'
            )
            store = ManagerStore(root / "manager")
            with patch(
                "umml_manager.store.tree_digest",
                side_effect=["1" * 64, "2" * 64],
            ):
                with self.assertRaises(StoreError):
                    store.import_folder(mod)
            self.assertFalse(
                store.source_destination("moving-target", "1").exists()
            )

    def test_tampered_baseline_blocks_restore_and_keeps_active_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = ManagerStore(root / "manager")
            dat = root / "dat"
            target = dat / "aa" / "aafile"
            target.parent.mkdir(parents=True)
            target.write_text("vanilla")
            store.save_settings({"dat_path": str(dat)})

            prepared = root / "prepared"
            source = prepared / "aa" / "aafile"
            source.parent.mkdir(parents=True)
            source.write_text("modded")
            mod = ModRecord(
                "a",
                "A",
                prepared_path=str(prepared),
                files={"aa/aafile": hash_file(source)},
            )
            engine = ApplyEngine(store, dat, process_check=lambda _: ())
            engine.apply(resolve_profile(Profile("On", ["a"]), [mod]))
            baseline = store.paths.baseline / "aa" / "aafile"
            baseline.write_text("tampered")

            with self.assertRaises(ApplyError):
                engine.apply(resolve_profile(Profile("Off", []), [mod]))
            self.assertEqual(target.read_text(), "modded")

    def test_tampered_recovery_snapshot_blocks_automatic_rollback(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = ManagerStore(root / "manager")
            dat = root / "dat"
            dat.mkdir()
            engine = ApplyEngine(store, dat, process_check=lambda _: ())
            transaction = (
                store.paths.transactions
                / f"apply-{engine.target_id}-tampered"
            )
            snapshot = transaction / "snapshots" / "aa" / "aafile"
            snapshot.parent.mkdir(parents=True)
            snapshot.write_text("snapshot")
            atomic_write_json(
                transaction / "journal.json",
                {
                    "version": 2,
                    "transaction_id": transaction.name,
                    "target_id": engine.target_id,
                    "phase": "applying",
                    "manifest": {
                        "aa/aafile": {
                            "existed": True,
                            "sha256": "0" * 64,
                        }
                    },
                },
            )
            with self.assertRaises(ApplyError):
                engine._recover_incomplete_transactions()
            self.assertTrue(transaction.is_dir())

    def test_snapshot_failure_before_mutation_cleans_transaction(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = ManagerStore(root / "manager")
            dat = root / "dat"
            target = dat / "aa" / "aafile"
            target.parent.mkdir(parents=True)
            target.write_text("managed")
            engine = ApplyEngine(store, dat, process_check=lambda _: ())
            atomic_write_json(
                store.paths.state,
                {
                    "version": 2,
                    "target_id": engine.target_id,
                    "dat_path": str(dat.resolve()),
                    "files": {
                        "aa/aafile": {
                            "owner": "a",
                            "version": "1",
                            "profile": "On",
                            "sha256": hash_file(target),
                        }
                    },
                },
            )

            with patch(
                "umml_manager.engine.atomic_copy_file",
                side_effect=OSError("disk full"),
            ):
                with self.assertRaises(ApplyError) as raised:
                    engine.apply(
                        resolve_profile(Profile("Off", []), [])
                    )
            self.assertIn(
                "before game-file mutation",
                str(raised.exception),
            )
            self.assertEqual(target.read_text(), "managed")
            remaining = list(
                store.paths.transactions.glob(
                    f"apply-{engine.target_id}-*"
                )
            )
            self.assertEqual(remaining, [])

    def test_external_change_after_snapshot_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = ManagerStore(root / "manager")
            dat = root / "dat"
            target = dat / "aa" / "aafile"
            target.parent.mkdir(parents=True)
            target.write_text("vanilla")

            first_prepared = root / "prepared-first"
            first_source = first_prepared / "aa" / "aafile"
            first_source.parent.mkdir(parents=True)
            first_source.write_text("first-mod")
            first = ModRecord(
                "first",
                "First",
                prepared_path=str(first_prepared),
                files={"aa/aafile": hash_file(first_source)},
            )
            ApplyEngine(store, dat, process_check=lambda _game: ()).apply(
                resolve_profile(Profile("First", ["first"]), [first])
            )

            second_prepared = root / "prepared-second"
            second_source = second_prepared / "aa" / "aafile"
            second_source.parent.mkdir(parents=True)
            second_source.write_text("second-mod")
            second = ModRecord(
                "second",
                "Second",
                prepared_path=str(second_prepared),
                files={"aa/aafile": hash_file(second_source)},
            )
            checks = 0

            def mutate_after_snapshot(_game):
                nonlocal checks
                checks += 1
                if checks == 3:
                    target.write_text("external-during-apply")
                return ()

            engine = ApplyEngine(
                store,
                dat,
                process_check=mutate_after_snapshot,
            )
            with self.assertRaisesRegex(
                ApplyError,
                "changed after UMML Manager captured",
            ):
                engine.apply(
                    resolve_profile(
                        Profile("Second", ["second"]),
                        [first, second],
                    ),
                    force=True,
                )

            self.assertEqual(target.read_text(), "external-during-apply")
            state = json.loads(store.paths.state.read_text(encoding="utf-8"))
            self.assertEqual(state["files"]["aa/aafile"]["owner"], "first")
            self.assertEqual(
                list(
                    store.paths.transactions.glob(
                        f"apply-{engine.target_id}-*"
                    )
                ),
                [],
            )

    def test_external_change_before_snapshot_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = ManagerStore(root / "manager")
            dat = root / "dat"
            target = dat / "aa" / "aafile"
            target.parent.mkdir(parents=True)
            target.write_text("first-mod")

            base_engine = ApplyEngine(
                store,
                dat,
                process_check=lambda _game: (),
            )
            atomic_write_json(
                store.paths.state,
                {
                    "version": 2,
                    "target_id": base_engine.target_id,
                    "dat_path": str(dat.resolve()),
                    "files": {
                        "aa/aafile": {
                            "owner": "first",
                            "version": "1",
                            "profile": "First",
                            "sha256": hash_file(target),
                        }
                    },
                },
            )

            prepared = root / "prepared"
            source = prepared / "aa" / "aafile"
            source.parent.mkdir(parents=True)
            source.write_text("second-mod")
            second = ModRecord(
                "second",
                "Second",
                prepared_path=str(prepared),
                files={"aa/aafile": hash_file(source)},
            )

            class RacingEngine(ApplyEngine):
                def _apply_transaction(self, *args, **kwargs):
                    target.write_text("external-before-snapshot")
                    return super()._apply_transaction(*args, **kwargs)

            engine = RacingEngine(
                store,
                dat,
                process_check=lambda _game: (),
            )
            with self.assertRaisesRegex(
                ApplyError,
                "changed while UMML Manager was preparing",
            ):
                engine.apply(
                    resolve_profile(
                        Profile("Second", ["second"]),
                        [second],
                    )
                )

            self.assertEqual(target.read_text(), "external-before-snapshot")
            state = json.loads(store.paths.state.read_text(encoding="utf-8"))
            self.assertEqual(state["files"]["aa/aafile"]["owner"], "first")

    def test_identical_unmanaged_target_is_not_adopted_without_baseline(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = ManagerStore(root / "manager")
            dat = root / "dat"
            target = dat / "aa" / "aafile"
            target.parent.mkdir(parents=True)
            target.write_text("already-modded")
            prepared = root / "prepared"
            source = prepared / "aa" / "aafile"
            source.parent.mkdir(parents=True)
            source.write_text("already-modded")
            mod = ModRecord(
                "same",
                "Same",
                prepared_path=str(prepared),
                files={"aa/aafile": hash_file(source)},
            )
            engine = ApplyEngine(store, dat, process_check=lambda _game: ())

            with patch.object(engine, "_rollback") as rollback:
                with self.assertRaisesRegex(ApplyError, "no vanilla baseline"):
                    engine.apply(
                        resolve_profile(Profile("Same", ["same"]), [mod])
                    )
                rollback.assert_not_called()

            self.assertEqual(target.read_text(), "already-modded")
            self.assertFalse(store.paths.state.exists())
            self.assertFalse(
                (store.paths.baseline / "aa" / "aafile").exists()
            )

    def test_legacy_original_is_copied_then_matching_file_is_adopted(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = ManagerStore(root / "manager")
            dat = root / "Persistent" / "dat"
            backup = root / "Persistent" / "dat.backup"
            target = dat / "aa" / "aafile"
            legacy_original = backup / "aa" / "aafile"
            target.parent.mkdir(parents=True)
            legacy_original.parent.mkdir(parents=True)
            target.write_text("already-modded")
            legacy_original.write_text("original")

            prepared = root / "prepared"
            source = prepared / "aa" / "aafile"
            source.parent.mkdir(parents=True)
            source.write_text("already-modded")
            mod = ModRecord(
                "same",
                "Same",
                prepared_path=str(prepared),
                files={"aa/aafile": hash_file(source)},
            )
            resolution = resolve_profile(
                Profile("Same", ["same"]),
                [mod],
            )
            engine = ApplyEngine(store, dat, process_check=lambda _game: ())

            with self.assertRaises(LegacyBaselineMigrationRequired) as raised:
                engine.apply(resolution)
            self.assertTrue(raised.exception.can_import)
            self.assertEqual(raised.exception.paths, ("aa/aafile",))
            self.assertEqual(
                raised.exception.backup_root,
                backup,
            )
            self.assertFalse(store.paths.state.exists())
            self.assertFalse(
                (store.paths.baseline / "aa" / "aafile").exists()
            )

            result = engine.apply(
                resolution,
                import_legacy_baselines=True,
            )

            self.assertEqual(result.installed, 0)
            self.assertEqual(result.unchanged, 1)
            self.assertEqual(result.imported_baselines, 1)
            self.assertEqual(target.read_text(), "already-modded")
            self.assertEqual(legacy_original.read_text(), "original")
            manager_baseline = store.paths.baseline / "aa" / "aafile"
            self.assertEqual(manager_baseline.read_text(), "original")
            digest = json.loads(
                (manager_baseline.parent / "aafile.umml-sha256").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(digest["origin"], "legacy-dat.backup")
            self.assertEqual(digest["sha256"], hash_file(legacy_original))

            restored = engine.apply(
                resolve_profile(Profile("Off", []), [mod])
            )
            self.assertEqual(restored.restored, 1)
            self.assertEqual(target.read_text(), "original")
            self.assertEqual(legacy_original.read_text(), "original")

    def test_legacy_baseline_import_is_all_or_nothing_when_one_is_missing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = ManagerStore(root / "manager")
            dat = root / "Persistent" / "dat"
            backup = root / "Persistent" / "dat.backup"
            prepared = root / "prepared"
            files = {}
            for relative in ("aa/first", "bb/second"):
                target = dat / relative
                source = prepared / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                source.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(f"modded-{relative}")
                source.write_text(f"modded-{relative}")
                files[relative] = hash_file(source)
            available = backup / "aa" / "first"
            available.parent.mkdir(parents=True)
            available.write_text("original-first")
            mod = ModRecord(
                "two",
                "Two",
                prepared_path=str(prepared),
                files=files,
            )
            engine = ApplyEngine(store, dat, process_check=lambda _game: ())

            with self.assertRaises(LegacyBaselineMigrationRequired) as raised:
                engine.apply(
                    resolve_profile(Profile("Two", ["two"]), [mod]),
                    import_legacy_baselines=True,
                )

            self.assertFalse(raised.exception.can_import)
            self.assertEqual(raised.exception.importable, ("aa/first",))
            self.assertIn("bb/second", raised.exception.problems)
            self.assertFalse(
                (store.paths.baseline / "aa" / "first").exists()
            )
            self.assertFalse(store.paths.state.exists())

    def test_nonmatching_legacy_mod_uses_backup_instead_of_modded_baseline(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = ManagerStore(root / "manager")
            dat = root / "Persistent" / "dat"
            backup = root / "Persistent" / "dat.backup"
            target = dat / "aa" / "aafile"
            legacy_original = backup / "aa" / "aafile"
            source = root / "prepared" / "aa" / "aafile"
            for path in (target, legacy_original, source):
                path.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("old-legacy-mod")
            legacy_original.write_text("original")
            source.write_text("new-manager-mod")
            mod = ModRecord(
                "new",
                "New",
                prepared_path=str(root / "prepared"),
                files={"aa/aafile": hash_file(source)},
            )
            resolution = resolve_profile(
                Profile("New", ["new"]),
                [mod],
            )
            engine = ApplyEngine(
                store,
                dat,
                process_check=lambda _game: (),
            )

            with self.assertRaises(LegacyBaselineMigrationRequired) as raised:
                engine.apply(resolution)

            self.assertTrue(raised.exception.can_import)
            result = engine.apply(
                resolution,
                import_legacy_baselines=True,
            )
            self.assertEqual(result.installed, 1)
            self.assertEqual(result.imported_baselines, 1)
            self.assertEqual(target.read_text(), "new-manager-mod")
            self.assertEqual(
                (store.paths.baseline / "aa" / "aafile").read_text(),
                "original",
            )
            engine.apply(resolve_profile(Profile("Off", []), [mod]))
            self.assertEqual(target.read_text(), "original")

    def test_known_legacy_mod_without_original_is_not_captured_as_vanilla(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = ManagerStore(root / "manager")
            dat = root / "Persistent" / "dat"
            target = dat / "aa" / "aafile"
            target.parent.mkdir(parents=True)
            target.write_text("old-legacy-mod")

            old_prepared = root / "old-prepared"
            old_source = old_prepared / "aa" / "aafile"
            old_source.parent.mkdir(parents=True)
            old_source.write_text("old-legacy-mod")
            old = ModRecord(
                "old",
                "Old",
                prepared_path=str(old_prepared),
                files={"aa/aafile": hash_file(old_source)},
            )
            new_prepared = root / "new-prepared"
            new_source = new_prepared / "aa" / "aafile"
            new_source.parent.mkdir(parents=True)
            new_source.write_text("new-manager-mod")
            new = ModRecord(
                "new",
                "New",
                prepared_path=str(new_prepared),
                files={"aa/aafile": hash_file(new_source)},
            )

            with self.assertRaises(
                LegacyBaselineMigrationRequired
            ) as raised:
                ApplyEngine(
                    store,
                    dat,
                    process_check=lambda _game: (),
                ).apply(
                    resolve_profile(
                        Profile("New", ["new"]),
                        [old, new],
                    )
                )

            self.assertFalse(raised.exception.can_import)
            self.assertFalse(
                (store.paths.baseline / "aa" / "aafile").exists()
            )
            self.assertEqual(target.read_text(), "old-legacy-mod")

    def test_current_original_matching_legacy_backup_needs_no_migration(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = ManagerStore(root / "manager")
            dat = root / "Persistent" / "dat"
            backup = root / "Persistent" / "dat.backup"
            target = dat / "aa" / "aafile"
            legacy_original = backup / "aa" / "aafile"
            source = root / "prepared" / "aa" / "aafile"
            for path in (target, legacy_original, source):
                path.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("original")
            legacy_original.write_text("original")
            source.write_text("new-manager-mod")
            mod = ModRecord(
                "new",
                "New",
                prepared_path=str(root / "prepared"),
                files={"aa/aafile": hash_file(source)},
            )

            result = ApplyEngine(
                store,
                dat,
                process_check=lambda _game: (),
            ).apply(resolve_profile(Profile("New", ["new"]), [mod]))

            self.assertEqual(result.installed, 1)
            self.assertEqual(result.imported_baselines, 0)
            self.assertEqual(
                (store.paths.baseline / "aa" / "aafile").read_text(),
                "original",
            )

    def test_verified_existing_baseline_allows_matching_file_adoption(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = ManagerStore(root / "manager")
            dat = root / "dat"
            target = dat / "aa" / "aafile"
            target.parent.mkdir(parents=True)
            target.write_text("already-modded")
            store.save_settings({"dat_path": str(dat)})

            baseline = store.paths.baseline / "aa" / "aafile"
            baseline.parent.mkdir(parents=True)
            baseline.write_text("original")
            atomic_write_json(
                baseline.parent / "aafile.umml-sha256",
                {
                    "version": 1,
                    "sha256": hash_file(baseline),
                },
            )
            prepared = root / "prepared"
            source = prepared / "aa" / "aafile"
            source.parent.mkdir(parents=True)
            source.write_text("already-modded")
            mod = ModRecord(
                "same",
                "Same",
                prepared_path=str(prepared),
                files={"aa/aafile": hash_file(source)},
            )
            engine = ApplyEngine(store, dat, process_check=lambda _game: ())

            result = engine.apply(
                resolve_profile(Profile("Same", ["same"]), [mod])
            )
            self.assertEqual(result.unchanged, 1)
            self.assertEqual(result.imported_baselines, 0)
            engine.apply(resolve_profile(Profile("Off", []), [mod]))
            self.assertEqual(target.read_text(), "original")

    def test_future_active_state_schema_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = ManagerStore(root / "manager")
            dat = root / "dat"
            dat.mkdir()
            engine = ApplyEngine(store, dat, process_check=lambda _: ())
            atomic_write_json(
                store.paths.state,
                {
                    "version": 999,
                    "target_id": engine.target_id,
                    "files": {},
                },
            )
            with self.assertRaises(ApplyError):
                engine.apply(resolve_profile(Profile("Off", []), []))


if __name__ == "__main__":
    unittest.main()
