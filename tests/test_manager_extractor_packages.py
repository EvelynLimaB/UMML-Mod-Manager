import stat
import tempfile
import unittest
import zipfile
from pathlib import Path

from umml_manager.extractor_packages import (
    ExternalToolPackageError,
    inspect_extractor_archive,
    install_extractor_archive,
    load_managed_extractor,
)


class ManagedExtractorPackageTests(unittest.TestCase):
    def _write_package(
        self,
        destination: Path,
        *,
        root: str = "umadump-2.5.4",
        requirements: str = "minidump~=0.0.24\n",
    ) -> Path:
        archive = destination / "umadump-2.5.4.zip"
        files = {
            "main.py": "print('fixture')\n",
            "memory.py": "\n",
            "game_structs.py": "\n",
            "json_encoders.py": "\n",
            "requirements.txt": requirements,
            "update_check.py": 'CURRENT_VERSION = "2.5.4"\n',
            "README.md": "fixture\n",
        }
        with zipfile.ZipFile(archive, "w") as package:
            for name, content in files.items():
                package.writestr(f"{root}/{name}", content)
        return archive

    def test_inspects_werseter_source_release(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = self._write_package(root)

            result = inspect_extractor_archive(archive)

            self.assertEqual(result.provider, "Werseter/umadump")
            self.assertEqual(result.version, "2.5.4")
            self.assertEqual(result.source_root, "umadump-2.5.4")
            self.assertEqual(result.entrypoint, "main.py")
            self.assertEqual(result.python_requirement, "3.14+")
            self.assertEqual(len(result.archive_sha256), 64)

    def test_installs_hash_addressed_source_idempotently(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = self._write_package(root)
            tools = root / "tools"

            first = install_extractor_archive(
                archive,
                tools,
                create_runtime=False,
            )
            second = install_extractor_archive(
                archive,
                tools,
                create_runtime=False,
            )

            self.assertEqual(first, second)
            self.assertEqual(first.provider, "Werseter/umadump")
            self.assertEqual(first.version, "2.5.4")
            self.assertFalse(first.runtime_ready)
            self.assertTrue(Path(first.entrypoint).is_file())
            self.assertTrue(
                Path(first.install_root, "managed-extractor.json").is_file()
            )
            self.assertEqual(
                load_managed_extractor(first.install_root),
                first,
            )

    def test_rejects_unbundled_dependency_before_installation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = self._write_package(
                root,
                requirements=(
                    "minidump~=0.0.24\n"
                    "requests==2.0\n"
                ),
            )
            tools = root / "tools"

            with self.assertRaisesRegex(
                ExternalToolPackageError,
                "dependencies not bundled",
            ):
                install_extractor_archive(
                    archive,
                    tools,
                    create_runtime=False,
                )

            provider_root = tools / "werseter-umadump"
            self.assertFalse(
                provider_root.exists()
                and any(provider_root.iterdir())
            )

    def test_rejects_archive_traversal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = self._write_package(root)
            with zipfile.ZipFile(archive, "a") as package:
                package.writestr("../escape.py", "bad\n")

            with self.assertRaisesRegex(
                ExternalToolPackageError,
                "Unsafe extractor ZIP path",
            ):
                inspect_extractor_archive(archive)

    def test_rejects_symbolic_links(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = self._write_package(root)
            link = zipfile.ZipInfo("umadump-2.5.4/link.py")
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            with zipfile.ZipFile(archive, "a") as package:
                package.writestr(link, "main.py")

            with self.assertRaisesRegex(
                ExternalToolPackageError,
                "Links and special files",
            ):
                inspect_extractor_archive(archive)

    def test_rejects_case_insensitive_duplicate_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = self._write_package(root)
            with zipfile.ZipFile(archive, "a") as package:
                package.writestr(
                    "UMADUMP-2.5.4/MAIN.PY",
                    "duplicate\n",
                )

            with self.assertRaisesRegex(
                ExternalToolPackageError,
                "Duplicate extractor ZIP path",
            ):
                inspect_extractor_archive(archive)

    def test_rejects_multiple_project_roots(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = self._write_package(root)
            required = (
                "main.py",
                "memory.py",
                "game_structs.py",
                "json_encoders.py",
                "requirements.txt",
            )
            with zipfile.ZipFile(archive, "a") as package:
                for name in required:
                    package.writestr(f"second-project/{name}", "\n")

            with self.assertRaisesRegex(
                ExternalToolPackageError,
                "exactly one recognizable project root",
            ):
                inspect_extractor_archive(archive)


if __name__ == "__main__":
    unittest.main()
