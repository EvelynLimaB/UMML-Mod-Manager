from __future__ import annotations

import io
import json
import os
import tarfile
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

from umml_manager.importer_safety import is_link_like, latest_regular_json
from umml_manager.store import ManagerStore, StoreError


class ImporterSafetyTests(unittest.TestCase):
    @staticmethod
    def _write_mod(folder: Path, *, title: str = "Safe Mod") -> Path:
        (folder / "assets").mkdir(parents=True)
        (folder / "assets" / "payload.bundle").write_bytes(b"UnityFS")
        (folder / "setting.json").write_text(
            json.dumps({"title": title, "mod_version": "1"}),
            encoding="utf-8",
        )
        return folder

    @staticmethod
    def _tar_add_bytes(package: tarfile.TarFile, name: str, payload: bytes) -> None:
        info = tarfile.TarInfo(name)
        info.size = len(payload)
        package.addfile(info, io.BytesIO(payload))

    @staticmethod
    def _require_created_link(path: Path) -> None:
        if not is_link_like(path):
            raise unittest.SkipTest(
                "the runner did not create a detectable symlink or junction"
            )

    def test_regular_folder_zip_and_tar_imports_still_succeed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = ManagerStore(root / "manager")
            folder = self._write_mod(root / "folder", title="Folder Mod")
            folder_record = store.import_folder(folder)
            self.assertEqual(folder_record.name, "Folder Mod")

            zip_path = root / "zip-mod.zip"
            with zipfile.ZipFile(zip_path, "w") as package:
                package.writestr(
                    "setting.json",
                    json.dumps({"title": "ZIP Mod", "mod_version": "1"}),
                )
                package.writestr("assets/payload.bundle", b"UnityFS")
            zip_record = store.import_archive(zip_path)
            self.assertEqual(zip_record.name, "ZIP Mod")

            tar_path = root / "tar-mod.tar.gz"
            with tarfile.open(tar_path, "w:gz") as package:
                self._tar_add_bytes(
                    package,
                    "setting.json",
                    json.dumps({"title": "TAR Mod", "mod_version": "1"}).encode(),
                )
                self._tar_add_bytes(package, "assets/payload.bundle", b"UnityFS")
            tar_record = store.import_archive(tar_path)
            self.assertEqual(tar_record.name, "TAR Mod")

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_selected_folder_symlink_or_junction_is_rejected_before_resolution(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            actual = self._write_mod(root / "actual")
            selected = root / "selected"
            try:
                os.symlink(actual, selected, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"directory links unavailable: {exc}")
            self._require_created_link(selected)

            with self.assertRaisesRegex(StoreError, "non-link directory"):
                ManagerStore(root / "manager").import_folder(selected)

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_selected_archive_symlink_is_rejected_before_resolution(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            actual = root / "actual.zip"
            with zipfile.ZipFile(actual, "w") as package:
                package.writestr("setting.json", '{"title":"Archive","mod_version":"1"}')
                package.writestr("assets/payload.bundle", b"UnityFS")
            selected = root / "selected.zip"
            try:
                os.symlink(actual, selected)
            except OSError as exc:
                self.skipTest(f"file symlinks unavailable: {exc}")
            self._require_created_link(selected)

            with self.assertRaisesRegex(StoreError, "non-link file"):
                ManagerStore(root / "manager").import_archive(selected)

    def test_zip_casefold_collision_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "collision.zip"
            with zipfile.ZipFile(archive, "w") as package:
                package.writestr("setting.json", '{"title":"Collision","mod_version":"1"}')
                package.writestr("assets/File.bundle", b"one")
                package.writestr("assets/file.bundle", b"two")

            with self.assertRaisesRegex(StoreError, "cross-platform colliding path"):
                ManagerStore(root / "manager").import_archive(archive)

    def test_tar_casefold_collision_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "collision.tar"
            with tarfile.open(archive, "w") as package:
                self._tar_add_bytes(
                    package,
                    "setting.json",
                    b'{"title":"Collision","mod_version":"1"}',
                )
                self._tar_add_bytes(package, "assets/File.bundle", b"one")
                self._tar_add_bytes(package, "assets/file.bundle", b"two")

            with self.assertRaisesRegex(StoreError, "cross-platform colliding path"):
                ManagerStore(root / "manager").import_archive(archive)

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_latest_roster_output_ignores_newer_symlink(self):
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as outside_temp:
            inbox = Path(temp)
            real = inbox / "trained_chara_data.json"
            real.write_text("[]", encoding="utf-8")
            linked_target = Path(outside_temp) / "outside.json"
            linked_target.write_text("[]", encoding="utf-8")
            linked = inbox / "newest.json"
            try:
                os.symlink(linked_target, linked)
            except OSError as exc:
                self.skipTest(f"file symlinks unavailable: {exc}")
            self._require_created_link(linked)
            now = time.time_ns()
            os.utime(real, ns=(now - 2_000_000_000, now - 2_000_000_000))
            os.utime(linked_target, ns=(now, now))

            self.assertEqual(latest_regular_json(inbox), real)

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_latest_roster_output_returns_none_for_only_symlinks(self):
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as outside_temp:
            inbox = Path(temp)
            outside = Path(outside_temp) / "outside.json"
            outside.write_text("[]", encoding="utf-8")
            linked = inbox / "linked.json"
            try:
                os.symlink(outside, linked)
            except OSError as exc:
                self.skipTest(f"file symlinks unavailable: {exc}")
            self._require_created_link(linked)

            self.assertIsNone(latest_regular_json(inbox))


if __name__ == "__main__":
    unittest.main()
